"""LLM layer: Responses API tool loop — all mocked, no network."""

from types import SimpleNamespace

import openai
import pytest

from core import (
    MAX_TOOL_CALLS_PER_RESPONSE,
    MODEL,
    SETUP_MESSAGE,
    Agent,
    LLMError,
    TextDelta,
    ToolEvent,
    responses_tools,
)


def delta(text):
    return SimpleNamespace(type="response.output_text.delta", delta=text)


def refusal(text):
    return SimpleNamespace(type="response.refusal.delta", delta=text)


def completed(*output):
    return SimpleNamespace(
        type="response.completed", response=SimpleNamespace(output=list(output))
    )


def failed(status="failed", code=None):
    return SimpleNamespace(
        type="response.failed",
        response=SimpleNamespace(status=status, error=SimpleNamespace(code=code)),
    )


def function_call(name, arguments, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=arguments, call_id=call_id)


def reasoning(item_id="rs_1"):
    return SimpleNamespace(type="reasoning", id=item_id, encrypted_content="encrypted")


def message_item(text):
    return SimpleNamespace(
        type="message", role="assistant", content=[SimpleNamespace(type="output_text", text=text)]
    )


class FakeStream:
    def __init__(self, events):
        self.events = events
        self.closed = False

    def __iter__(self):
        yield from self.events

    def close(self):
        self.closed = True


class FakeResponses:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []
        self.streams = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        script = self.scripts.pop(0)
        if isinstance(script, Exception):
            raise script
        stream = FakeStream(script)
        self.streams.append(stream)
        return stream


class FakeClient:
    def __init__(self, scripts):
        self.responses = FakeResponses(scripts)
        self.closed = False

    def close(self):
        self.closed = True


def make_agent(scripts, **kwargs):
    client = FakeClient(scripts)
    return Agent(api_key="test-key", client=client, **kwargs), client


def test_tool_definitions_are_converted_for_the_responses_api():
    converted = responses_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "read a file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            }
        ]
    )

    assert converted == [
        {
            "type": "function",
            "name": "read",
            "description": "read a file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            "strict": False,
        }
    ]


def test_request_uses_reasoning_medium_and_disables_storage():
    agent, client = make_agent([[delta("hi"), completed()]])

    events = list(agent.stream(agent.input_items("halo")))

    assert [event.text for event in events] == ["hi"]
    call = client.responses.calls[0]
    assert call["model"] == MODEL
    assert call["reasoning"] == {"effort": "medium"}
    assert call["store"] is False
    assert call["include"] == ["reasoning.encrypted_content"]
    assert call["stream"] is True
    assert call["instructions"]
    assert {tool["name"] for tool in call["tools"]} == {"read", "write", "edit", "bash"}
    assert all(tool["strict"] is False for tool in call["tools"])
    assert client.responses.streams[0].closed is True


def test_refusal_delta_is_surfaced():
    agent, _ = make_agent([[refusal("Maaf, aku nggak bisa bantu."), completed()]])

    events = list(agent.stream(agent.input_items("x")))

    assert "nggak bisa bantu" in "".join(event.text for event in events)


def test_completed_only_response_still_yields_text():
    # Some providers send the answer only in response.completed, with no deltas.
    agent, _ = make_agent([[completed(message_item("Halo! Ini jawaban."))]])

    events = list(agent.stream(agent.input_items("hai")))

    texts = [event.text for event in events if isinstance(event, TextDelta)]
    assert texts == ["Halo! Ini jawaban."]


def test_output_text_done_event_is_used_as_a_fallback():
    done_event = SimpleNamespace(type="response.output_text.done", text="dari done event")
    agent, _ = make_agent([[done_event, completed()]])

    events = list(agent.stream(agent.input_items("x")))

    assert [event.text for event in events if isinstance(event, TextDelta)] == ["dari done event"]


def test_dict_shaped_events_are_supported():
    script = [
        {
            "type": "response.completed",
            "response": {
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": "dari dict"}]}
                ]
            },
        }
    ]
    agent, _ = make_agent([script])

    events = list(agent.stream(agent.input_items("x")))

    assert [event.text for event in events if isinstance(event, TextDelta)] == ["dari dict"]


def test_tool_loop_replays_reasoning_and_sends_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")

    reason = reasoning()
    call = function_call("read", '{"path": "a.txt"}', "call_1")
    agent, client = make_agent([[completed(reason, call)], [delta("done"), completed()]])

    events = list(agent.stream(agent.input_items("read a.txt")))

    statuses = [(event.name, event.state) for event in events if isinstance(event, ToolEvent)]
    assert statuses == [("read", "running"), ("read", "finished")]
    assert any(isinstance(event, TextDelta) and event.text == "done" for event in events)

    replay = client.responses.calls[1]["input"]
    assert reason in replay  # reasoning is replayed, not dropped
    assert call in replay
    outputs = [
        item
        for item in replay
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert outputs[0]["call_id"] == "call_1"
    assert "hello" in outputs[0]["output"]


def test_tool_errors_are_returned_to_the_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    call = function_call("edit", '{"path": "missing.txt", "old_text": "a", "new_text": "b"}', "c1")
    agent, client = make_agent([[completed(call)], [delta("ok"), completed()]])

    events = list(agent.stream(agent.input_items("edit")))

    assert ("edit", "failed") in [(e.name, e.state) for e in events if isinstance(e, ToolEvent)]
    replay = client.responses.calls[1]["input"]
    outputs = [
        item
        for item in replay
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert outputs[0]["output"].startswith("error:")


def test_incomplete_stream_does_not_execute_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    call = function_call("bash", '{"command": "touch marker"}', "c1")
    item_done = SimpleNamespace(type="response.output_item.done", item=call)
    # The stream ends without response.completed, so the call must not run.
    agent, _ = make_agent([[item_done, delta("partial")]])

    with pytest.raises(LLMError, match="incomplete"):
        list(agent.stream(agent.input_items("go")))

    assert not (tmp_path / "marker").exists()


def test_failed_event_is_reported():
    agent, _ = make_agent([[failed(status="failed", code="server_error")]])

    with pytest.raises(LLMError, match="server_error"):
        list(agent.stream(agent.input_items("x")))


def test_timeout_is_reported_distinctly():
    agent, _ = make_agent([openai.APITimeoutError(request=None)])

    with pytest.raises(LLMError, match="timeout"):
        list(agent.stream(agent.input_items("x")))


def test_connection_error_includes_the_underlying_cause():
    error = openai.APIConnectionError(request=None)
    error.__cause__ = ConnectionResetError("boom")
    agent, _ = make_agent([error])

    with pytest.raises(LLMError, match="ConnectionResetError"):
        list(agent.stream(agent.input_items("x")))


def test_api_error_is_mapped_readably():
    error = openai.AuthenticationError(
        "bad key",
        response=SimpleNamespace(status_code=401, headers={}, request=None),
        body={"error": {"type": "invalid_request_error", "code": "invalid_api_key"}},
    )
    agent, _ = make_agent([error])

    with pytest.raises(LLMError, match="401"):
        list(agent.stream(agent.input_items("x")))


def test_commit_stores_canonical_message_items():
    agent, _ = make_agent([[]])

    agent.commit("halo", "jawaban")

    assert agent.history == [
        {"role": "user", "content": "halo"},
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "jawaban"}],
        },
    ]


def test_missing_api_key_returns_the_setup_message():
    agent = Agent(api_key="")

    assert agent.configured is False
    with pytest.raises(LLMError) as excinfo:
        list(agent.stream(agent.input_items("x")))
    assert SETUP_MESSAGE.splitlines()[0] in str(excinfo.value)


def test_cancel_stops_further_tool_calls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = [
        function_call("bash", '{"command": "echo one"}', "c1"),
        function_call("bash", '{"command": "echo two"}', "c2"),
    ]
    agent, _ = make_agent([[completed(*calls)]])

    seen: list[ToolEvent] = []
    for event in agent.stream(agent.input_items("go")):
        if isinstance(event, ToolEvent):
            seen.append(event)
            if event.state == "finished":
                agent.cancel()

    assert len([event for event in seen if event.state == "running"]) == 1


def test_tool_calls_are_capped_per_response(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = [
        function_call("bash", '{"command": "true"}', f"c{i}")
        for i in range(MAX_TOOL_CALLS_PER_RESPONSE + 1)
    ]
    agent, client = make_agent([[completed(*calls)], [delta("done"), completed()]])

    events = list(agent.stream(agent.input_items("go")))

    running = [
        event for event in events if isinstance(event, ToolEvent) and event.state == "running"
    ]
    assert len(running) == MAX_TOOL_CALLS_PER_RESPONSE

    replay = client.responses.calls[1]["input"]
    outputs = [
        item
        for item in replay
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert outputs[-1]["output"].startswith("skipped:")
