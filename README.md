# Paijo

Coding agent terminal minimalis, dibangun dengan
[prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) (true-color 24-bit)
dan [Rich](https://github.com/Textualize/rich), dengan balasan streaming lewat **OpenAI
Responses API** ke **SumoPod AI**.

Paijo punya empat tool: `read`, `write`, `edit`, dan `bash`.

## Tampilan

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Paijo v0.1.0 · Enter send · Alt+Enter newline · Ctrl+C cancel · Ctrl+D quit  │
└──────────────────────────────────────────────────────────────────────────────┘

                                          ganti sapaan di greet.py jadi 'hai' 

 **Selesai.** Aku baca `greet.py` dulu, lalu ganti sapaannya.

 - `read` — 12 baris kebaca
 - `edit` — 1 baris diganti, diff bersih
 - `bash` — `python -m pytest` lolos

┌──────────────────────────────────────────────────────────────────────────────┐
│› Ask Paijo to do something…                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Tampilan awal terasa fullscreen: layar dibersihkan, banner dicetak di atas, input nempel di
bawah. Tiap pesan dicetak **di atas prompt** sehingga masuk ke riwayat scrollback terminal.
Selama agent bekerja, status tool (`read running`, `edit finished`, dst.) tampil di atas area
input, dan input tetap bisa diketik.

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
| `Alt+Enter` | Baris baru di input                                       |
| `Ctrl+C`    | Hentikan turn; kalau idle, bersihkan input                |
| `Ctrl+D`    | Keluar (saat input kosong)                                |
| `/exit`, `/quit`, `:q` | Keluar lewat command                            |

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

## Struktur

```
src/
├── app.py           # aplikasi inline: layout, keybindings, alur turn
├── llm.py           # Responses API: reasoning, tool loop, worker thread
├── tools/
│   ├── __init__.py  # ekspor + registrasi schema lewat aisuite
│   ├── read.py
│   ├── write.py
│   ├── edit.py
│   ├── bash.py
│   └── utils.py     # sandbox path, limit ukuran, atomic write
├── preview.py       # pratinjau streaming (tinggi dibatasi)
├── toolstatus.py    # status tool di atas input
├── thinking.py      # indikator "Thinking…"
├── conversation.py  # render pesan statis pakai Rich
├── input_area.py    # prompt input 3 baris (#393939)
├── header.py        # banner awal
├── theme.py         # palet & style
├── console.py       # Rich console + pesan perpisahan
└── version.py
```

## Catatan implementasi

- **Inline, bukan fullscreen.** `full_screen=False`, jadi prompt_toolkit cuma memiliki blok
  bawah (Thinking + status tool + preview + input) sementara output Rich masuk scrollback.
- **Definisi tool dari aisuite.** `tools/__init__.py` mengekspor empat fungsi ber-tipe dan
  mendaftarkannya lewat `aisuite.utils.tools.Tools`; schema-nya lalu dikonversi ke format
  function-tool Responses API dengan `strict=False` supaya default Python tetap berlaku.
  Eksekusi di-dispatch sendiri agar bisa melaporkan status per-call dan mencocokkan `call_id`.
- **Tool dijalankan di worker thread** bersama request, jadi file dan perintah nggak pernah
  memblokir event loop.
- **Streaming UI** memakai buffer dengan cursor di ujung teks dan tinggi maksimum, jadi baris
  terbaru selalu kelihatan tanpa mendorong input keluar layar.
