# Paijo

Coding agent terminal minimalis, dibangun dengan
[prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) (true-color 24-bit)
dan [Rich](https://github.com/Textualize/rich), dengan balasan streaming lewat **OpenAI
Responses API** ke **SumoPod AI**.

Paijo punya empat tool: `read`, `write`, `edit`, dan `bash`.

## Tampilan

```
██████╗  █████╗ ██╗     ██╗ ██████╗
██╔══██╗██╔══██╗██║     ██║██╔═══██╗
██████╔╝███████║██║     ██║██║   ██║
██╔═══╝ ██╔══██║██║██   ██║██║   ██║
██║     ██║  ██║██║╚█████╔╝╚██████╔╝
╚═╝     ╚═╝  ╚═╝╚═╝ ╚════╝  ╚═════╝

# Paijo v0.1.0
# models: gpt-5.6-luna
# /home/kamu/project

 ❯ ganti sapaan di greet.py jadi 'hai'

 **Selesai.** Aku baca `greet.py` dulu, lalu ganti sapaannya.

 - `read` — 12 baris kebaca
 - `edit` — 1 baris diganti, diff bersih
 - `bash` — `python -m pytest` lolos

────────────────────────────────────────────────────────────────────────────────
❯ Ask Paijo to do something…
────────────────────────────────────────────────────────────────────────────────
```

Saat start layar dibersihkan dulu, lalu banner (wordmark PAIJO hijau plus tiga baris keterangan:
versi, model, dan direktori kerja) dicetak inline lewat scrollback dan input nyusul tepat di
bawahnya — jadi **bukan** fullscreen (nggak ada padding sampai dasar layar). Tiap pesan dicetak
**di atas prompt** sehingga masuk ke riwayat scrollback terminal.
Selama agent bekerja, indikator di atas input mengikuti fase: `Thinking…` setiap kali menunggu
model (termasuk di round berikutnya setelah tool), ` bash … running 2s` saat tool berjalan
(dengan hitungan detik), lalu preview teks saat streaming. Tiap tool yang selesai dicetak
sebagai badge hijau di scrollback (` READ  [index.html]  89 lines  0.4s`), merah kalau gagal.
Untuk `edit` dan `write`, di bawah badge ada ringkasan (`└ Updated … with 1 addition`) plus
preview diff dengan nomor baris: baris `-` berlatar merah, baris `+` berlatar hijau. Diff dari
`write` cuma untuk tampilan — model tetap menerima ringkasan singkat, jadi konteksnya nggak
bengkak. Selesai satu turn, ada footer redup ` Worked for 2m 3s` tepat di bawah balasan (jadi
persis di atas input). Input tetap bisa diketik.

## Setup

```bash
export SUMOPOD_API_KEY="sk-..."
```

Kalau belum di-set, Paijo tetap jalan tapi menampilkan pesan setup dan menolak mengirim
request. Kuncinya cuma dibaca dari environment dan nggak pernah dicetak atau disimpan.

## Instalasi

```bash
uv sync
```

## Menjalankan

Harus di **terminal asli (TTY)**, bukan lewat pipe/redirect.

```bash
uv run paijo
# atau, setelah `source .venv/bin/activate`:
paijo
# atau langsung lewat Python:
uv run python -m app
```

Biar bisa diketik `paijo` dari mana aja: `uv tool install .`

## Tools

| Tool | Signature | Perilaku |
| ---- | --------- | -------- |
| `read` | `read(path, offset=1, limit=200)` | File UTF-8 + nomor baris, offset 1-based, maksimal 2.000 baris per panggilan. |
| `write` | `write(path, content)` | Buat/timpa file UTF-8, bikin direktori induk kalau belum ada. |
| `edit` | `edit(path, old_text, new_text)` | Ganti **satu** kemunculan unik, balikin unified diff. |
| `bash` | `bash(command, timeout=30)` | Jalankan `bash -c` di launch directory, balikin stdout+stderr dan exit code. |

**Edit** mencoba pencocokan persis dulu. Kalau nggak ketemu, dia membandingkan versi
ternormalisasi (NFKC, trailing whitespace dibuang, smart quotes / Unicode dashes / spasi
khusus disamakan) sambil **mempertahankan indentasi awal**. Yang ditolak: teks pencarian
kosong, tidak ditemukan, ambigu (termasuk duplikat yang setara secara Unicode), dan
penggantian yang nggak mengubah apa-apa. Hanya baris yang tersentuh yang ditulis ulang; BOM,
gaya newline (LF/CRLF), dan permission bits file tetap dipertahankan. Penyimpanan pakai
temporary file + `os.replace` (atomik), dan file dicek dulu nggak berubah sejak dibaca.

Diff dari `edit` juga dicetak ke scrollback dengan warna gaya git: baris `-` merah, baris `+`
hijau (dipotong 40 baris pertama). Model tetap menerima diff polos sebagai output tool.

**Batasan workspace**: semua path di-resolve relatif ke direktori Paijo dijalankan, dan path
maupun symlink yang keluar dari situ ditolak. Baca/tulis dibatasi 2 MB, output tool dipotong
di 20.000 karakter dengan penanda jelas.

> **Penting:** `bash` berjalan dengan hak akses kamu dan **tidak** terisolasi oleh pengecekan
> path di atas. Anggap perintah yang dijalankan model sama seperti perintah yang kamu ketik
> sendiri.

## Cara kerja agent

- Model dipanggil lewat **Responses API** (`gpt-5.6-luna`) dengan
  `reasoning={"effort": "medium"}`, `store=False`, dan
  `include=["reasoning.encrypted_content"]`. Reasoning nggak dimatikan untuk mengaktifkan
  tools.
- Tool dieksekusi **hanya setelah respons selesai sukses**, pakai argumen function-call yang
  sudah lengkap. Setiap item output (termasuk reasoning) diputar ulang sebelum
  `function_call_output` dengan `call_id` yang cocok dikirim balik ke model.
- Hasil tool dikirim lagi ke model, dan loop berlanjut sampai model memberi jawaban akhir.
  Error tool dikembalikan ke model supaya dia bisa memulihkan diri.
- Batas per giliran user: **16 request** ke model, dan **8 tool call** per respons.

## Keybindings

| Tombol      | Aksi                                                      |
| ----------- | --------------------------------------------------------- |
| `Enter`     | Kirim pesan (diabaikan kalau turn masih berjalan)         |
| `Shift+Enter` | Baris baru di input (perlu remap, lihat catatan)          |
| `Ctrl+C`    | Hentikan turn; kalau idle, bersihkan input                |
| `Ctrl+D`    | Keluar (saat input kosong)                                |
| `/exit`, `/quit`, `:q` | Keluar lewat command                            |

> **Setup `Shift+Enter`.** Terminal mengirim byte yang sama persis dengan `Enter` (`\r`), dan
> prompt_toolkit nggak punya key untuk Shift+Enter — jadi Paijo nggak bisa membedakannya secara
> native. Remap `Shift+Enter` di terminal supaya mengirim LF (`\n`); byte itulah yang ditangkap
> Paijo sebagai baris baru.
>
> VS Code (`keybindings.json`):
>
> ```json
> {
>   "key": "shift+enter",
>   "command": "workbench.action.terminal.sendSequence",
>   "args": { "text": "\n" },
>   "when": "terminalFocus"
> }
> ```
>
> Terminal lain: pakai remap serupa yang mengirim `\n`.

## Pembatalan & error

- `Ctrl+C` menghentikan tampilan seketika, mematikan proses `bash` yang sedang jalan
  (process group), dan menghentikan tool call berikutnya. Penulisan file yang **sudah selesai
  tidak dibatalkan**.
- Kalau turn dibatalkan **setelah** ada tool yang jalan, request user + catatan interupsi
  singkat tetap disimpan di riwayat supaya retry bisa mengecek perubahan yang sudah terjadi.
  Kalau belum ada tool yang jalan, turn-nya nggak disimpan.
- Error API (key salah, saldo habis, koneksi putus, stream tidak lengkap) balik ke input dengan
  pesan readable; draf dan respons parsial tetap dipertahankan dan turn-nya nggak masuk riwayat.
- Catatan: SDK-nya sinkron dan dijalankan di worker thread, jadi UI nggak nge-block. Request
  yang in-flight bisa tetap jalan di latar belakang sampai chunk berikutnya atau timeout 60
  detik; event telat dibuang di queue milik turn itu sendiri.

## Testing

```bash
uv run pytest
```

Semua jaringan di-mock, jadi **nggak butuh API key**. Cakupannya: keempat tool, pencocokan dan
preservasi `edit` (fuzzy, BOM, CRLF, permission), pembatasan path/symlink, timeout `bash`,
chunk teks yang di-stream, replay reasoning + hasil tool, stream tidak lengkap yang **tidak**
memicu eksekusi tool, error API, kredensial hilang, pembatalan (termasuk override riwayat
setelah tool jalan), serta penyimpanan draf dan seluruh perilaku TUI sebelumnya.

### Lint & pre-commit

```bash
uv run pre-commit install            # sekali per clone
uv run pre-commit run --all-files    # ruff check+format, trailing whitespace, dll
uv run ruff check src tests          # manual
uv run ruff format src tests         # manual
```

Hook-nya jalan otomatis tiap `git commit` (ruff check `--fix` + ruff format + cek file dasar).
Config ruff ada di `pyproject.toml` (`line-length = 100`, rules `E,F,I,UP,B,SIM`).

## Struktur

```
src/
├── app.py               # front-end terminal: prompt_toolkit + render event
├── version.py
├── core/                # engine — tanpa terminal/Rich
│   ├── __init__.py      # re-export API publik
│   ├── agent.py         # Responses API: reasoning, tool loop, worker thread
│   └── session.py       # driver satu turn: event stream, commit, cancel
├── ui/
│   ├── __init__.py
│   ├── conversation.py  # render pesan statis pakai Rich (bubble, diff, markdown)
│   ├── input_area.py    # prompt input: border atas-bawah + prefix ❯
│   ├── preview.py       # pratinjau streaming (tinggi dibatasi)
│   ├── thinking.py      # indikator "Thinking…"
│   ├── toolstatus.py    # status tool di atas input
│   ├── header.py        # banner awal
│   ├── theme.py         # palet & style
│   └── console.py       # Rich console + pesan perpisahan
└── tools/
    ├── __init__.py      # ekspor + registrasi schema lewat aisuite
    ├── read.py
    ├── write.py
    ├── edit.py
    ├── bash.py
    └── utils.py         # sandbox path, limit ukuran, atomic write
```

## Catatan implementasi

- **Engine terpisah dari UI.** `core/` nggak mengimpor prompt_toolkit atau Rich.
  `Session.send(text)` mengalirkan event (`TextDelta`, `ToolEvent`, lalu `TurnDone`) dan
  mengurus commit/cancel/error, jadi front-end lain (desktop/web) tinggal mengonsumsi event
  yang sama di atas `Agent` + `tools` yang identik. Semua dependensi terminal cuma ada di
  `ui/` dan `app.py`.
- **Inline, bukan fullscreen.** `full_screen=False`, jadi prompt_toolkit cuma memiliki blok
  bawah (Thinking + status tool + preview + input) sementara output Rich masuk scrollback.
- **Definisi tool dari aisuite.** `tools/__init__.py` mengekspor empat fungsi ber-tipe dan
  mendaftarkannya lewat `aisuite.utils.tools.Tools`; schema-nya lalu dikonversi ke format
  function-tool Responses API dengan `strict=False` supaya default Python tetap berlaku.
  Eksekusi di-dispatch sendiri agar bisa melaporkan status per-call dan mencocokkan `call_id`.
- **Tool dijalankan di worker thread** bersama request, jadi file dan perintah nggak pernah
  memblokir event loop.
- **Pesan user**: blok rata kiri dengan teks putih di atas hijau muted `#2f7a3c` (hijau
  di-blend ke background gelap — terminal nggak punya alpha), penanda `❯` hijau lebih tua, plus
  1 sel padding kiri-kanan. Pesan assistant: Markdown dengan satu spasi di awal tiap baris,
  latar normal.
- **Input**: satu baris edit dengan border atas-bawah putih dan prefix `❯` hijau, tanpa
  background dan tanpa padding vertikal tambahan.
- **Streaming UI** memakai buffer dengan cursor di ujung teks dan tinggi maksimum, jadi baris
  terbaru selalu kelihatan tanpa mendorong input keluar layar.
