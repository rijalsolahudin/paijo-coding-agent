"""Sub-agents: allowlists, the depth guard and the `task` tool. No network."""

import json
import threading

import pytest

from core import (
    CURRENT,
    MAX_DEPTH,
    SUBAGENTS,
    Agent,
    AgentContext,
    SubAgent,
    ToolEvent,
    definitions_for,
)
from support import FakeClient, completed, delta, function_call
from tools import ToolError, label_for, schemas, summarize, task


def test_subagent_specs_restrict_the_tools_each_type_can_use():
    assert "task" not in SUBAGENTS["general"].tools
    assert set(SUBAGENTS["general"].tools) == {"read", "write", "edit", "bash"}
    for name in ("explore", "plan"):
        assert "task" not in SUBAGENTS[name].tools
        assert "write" not in SUBAGENTS[name].tools
        assert "edit" not in SUBAGENTS[name].tools


def test_definitions_for_returns_only_the_allowed_specs():
    names = {spec["function"]["name"] for spec in definitions_for(SUBAGENTS["plan"].tools)}

    assert names == {"read", "bash"}


def test_task_rejects_an_unknown_subagent_type():
    with pytest.raises(ToolError, match="unknown subagent_type"):
        task("do it", "label", "banana")


def test_task_requires_an_agent_context():
    with pytest.raises(ToolError, match="inside the agent"):
        task("do it", "label")


def test_task_refuses_to_nest_beyond_the_max_depth():
    token = CURRENT.set(AgentContext(MAX_DEPTH, threading.Event(), None))
    try:
        with pytest.raises(ToolError, match="max depth"):
            task("do it", "label")
    finally:
        CURRENT.reset(token)


def test_agent_only_runs_tools_it_advertises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    read_only = [spec for spec in schemas() if spec["function"]["name"] == "read"]
    call = function_call("write", '{"path": "x.txt", "content": "hi"}', "c1")
    client = FakeClient([[completed(call)], [delta("ok"), completed()]])
    agent = Agent(api_key="test-key", client=client, definitions=read_only)

    list(agent.stream(agent.input_items("go")))

    replay = client.responses.calls[1]["input"]
    outputs = [
        item
        for item in replay
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert "unknown tool" in outputs[0]["output"]
    assert not (tmp_path / "x.txt").exists()


def test_subagent_returns_its_final_text_and_uses_its_own_instructions():
    client = FakeClient([[delta("ke"), delta("temu"), completed()]])
    sub = SubAgent(SUBAGENTS["explore"], client=client, depth=1)

    assert sub.run("cari X") == "ketemu"
    call = client.responses.calls[0]
    assert {tool["name"] for tool in call["tools"]} == {"read", "bash"}
    assert call["instructions"] == SUBAGENTS["explore"].instructions


def test_parent_task_call_runs_a_subagent_and_returns_only_its_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    call = function_call(
        "task",
        json.dumps({"prompt": "cari X", "description": "cari X", "subagent_type": "explore"}),
        "c1",
    )
    client = FakeClient(
        [
            [completed(call)],
            [delta("sub: ketemu di a.py"), completed()],
            [delta("parent: selesai"), completed()],
        ]
    )
    agent = Agent(api_key="test-key", client=client)

    events = list(agent.stream(agent.input_items("cari X")))

    statuses = [(event.name, event.state) for event in events if isinstance(event, ToolEvent)]
    assert statuses == [("[EXPLORE]", "running"), ("[EXPLORE]", "finished")]
    replay = client.responses.calls[2]["input"]
    outputs = [
        item
        for item in replay
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert "sub: ketemu di a.py" in outputs[-1]["output"]


def test_summarize_shows_the_task_description():
    arguments = json.dumps(
        {"prompt": "cari dipakai di mana", "description": "cari diff", "subagent_type": "plan"}
    )

    assert summarize("task", arguments) == "cari diff"
    assert summarize("task", json.dumps({"prompt": "cari diff", "description": ""})) == "cari diff"


def test_label_for_brackets_the_subagent_type():
    plan = json.dumps({"prompt": "x", "description": "cari diff", "subagent_type": "plan"})

    assert label_for("task", plan) == "[PLAN]"
    assert label_for("task", "not json") == "task"
    assert label_for("read", '{"path": "a.txt"}') == "read"
