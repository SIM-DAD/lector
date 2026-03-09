# ScriVocalis

> Distraction-free manuscript editor with read-aloud and voice cloning.

**[sim-dad.github.io/scrivocalis](https://sim-dad.github.io/scrivocalis/)** · [SIM DAD LLC](https://github.com/sim-dad) · [☕ Buy me a coffee](https://ko-fi.com/simdadllc)

ScriVocalis is a local web app for researchers and writers who want to edit Markdown manuscripts and hear them read back — in any voice, including a clone of their own.

---

## Features

- **Markdown editor** — clean, distraction-free writing surface with word-by-word TTS highlighting
- **Read aloud** — sentence-level streaming TTS so playback starts immediately
- **Voice cloning** — clone any voice from a 10–20 s audio sample using [F5-TTS](https://github.com/SWivid/F5-TTS) (no training required)
- **Built-in voices** — 10 Edge TTS neural voices (US, UK, AU); no GPU needed
- **Citation stripping** — numeric `[1]` and author–year `[Smith et al., 2020]` references are removed before reading
- **Auto-save** — draft persists in the browser between sessions; export as `.md` any time
- **Dark mode** — persists across sessions

---

## Requirements

| | |
|---|---|
| OS | Windows 10 / 11 |
| Python | 3.12 |
| GPU | NVIDIA with CUDA 12.4 — required for voice cloning only; built-in voices work on CPU |

---

## Quick start

| Platform | Command |
|---|---|
| Windows | Double-click **`launch.bat`** |
| Windows (no console) | Double-click **`launch-silent.vbs`** |
| Linux / macOS | `bash launch.sh` |

The first run creates a virtual environment and installs all dependencies (~3 GB including PyTorch and F5-TTS). Subsequent launches take a few seconds. The browser opens automatically to `http://127.0.0.1:7860`.

> **macOS / Linux without NVIDIA GPU:** Built-in Edge TTS voices work normally. Voice cloning requires an NVIDIA GPU with CUDA 12.4.

### Manual install

**Windows:**
```bat
:: launch.bat stores the venv in %LOCALAPPDATA%\ScriVocalis\.venv to keep
:: the ~3 GB of packages off cloud sync. Double-click launch.bat to run.
launch.bat
```

**Linux / macOS:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install torch==2.6.0 torchaudio==2.6.0  # add --index-url …/cu124 if NVIDIA GPU present
pip install -r requirements.txt
python server.py
```

---

## Usage

1. **Write or open** — paste your text directly, or open a `.docx` / `.md` file with the **Open** button
2. **Place cursor** — click anywhere in the text to start reading from that point
3. **Play** — press **Play**; the current sentence is highlighted word-by-word as it plays
4. **Clone a voice** — click **+ Voices**, upload a 10–20 s WAV/MP3, give it a name; the first use downloads ~750 MB of model weights
5. **Export** — click **Save .md** or press `Ctrl+S` to download your draft

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+S` | Save draft as `.md` |
| `Escape` | Stop playback |

---

## Project structure

```
server.py            FastAPI backend — TTS, voice management, document parsing
text_parser.py       .docx / .md → Markdown (preserves headings/bold/italic, strips citations)
static/
  index.html         Single-page frontend (vanilla JS, no framework)
voices/              Custom voice reference audio — gitignored, created at runtime
audio_cache/         Generated audio cache — gitignored, created at runtime
pkuseg_stub/         Local stub required by F5-TTS
launch.bat           One-click Windows setup and launch
launch-silent.vbs    Windows launch without a visible console window
launch.sh            Linux / macOS setup and launch
```

---

## License

Licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE) — free for personal and noncommercial use. Voluntary tips to the author are welcome and explicitly permitted. Commercial use requires written permission from SIM DAD LLC.

If ScriVocalis is useful to you, consider [buying me a coffee](https://ko-fi.com/simdadllc). ☕
