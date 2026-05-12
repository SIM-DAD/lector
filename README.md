# Lector

> Distraction-free manuscript editor with read-aloud and voice cloning.

**[uselector.app](https://uselector.app)** · [SIM DAD LLC](https://simdadllc.com)

Lector is a standalone desktop app (Tauri-wrapped) for researchers and writers who want to edit Markdown manuscripts and hear them read back — in any voice, including a clone of their own. Customers see a native window; the FastAPI server inside is internal IPC, never exposed.

---

## Features

- **Markdown editor** — clean, distraction-free writing surface with word-by-word TTS highlighting
- **Read aloud** — sentence-level streaming TTS so playback starts immediately
- **Voice cloning** — clone any voice from a 5-15 second audio sample using [F5-TTS](https://huggingface.co/SWivid/F5-TTS) (no training required)
- **Built-in voices** — 12 Kokoro neural voices (US, UK); fully offline, no GPU needed
- **Citation stripping** — numeric `[1]` and author–year `[Smith et al., 2020]` references are removed before reading
- **Auto-save** — draft persists in the browser between sessions; export as `.md` any time
- **Dark mode** — persists across sessions

---

## Requirements

| | |
|---|---|
| OS | Windows 10 / 11, macOS (coming soon) |
| Python | 3.12 |
| GPU | Optional — NVIDIA with CUDA improves voice cloning speed; all features work on CPU |

---

## Quick start

| Platform | Command |
|---|---|
| Windows | Double-click **`launch.bat`** |
| Windows (no console) | Double-click **`launch-silent.vbs`** |
| Linux / macOS | `bash launch.sh` |

The first run creates a virtual environment and installs all dependencies (~3 GB including PyTorch). Subsequent launches take a few seconds. The browser opens automatically to `http://127.0.0.1:7860`.

> **macOS / Linux:** Built-in Kokoro voices work on any hardware. Voice cloning uses F5-TTS and works on CPU (slower) or GPU (recommended).

### Manual install

**Windows:**
```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
.venv\Scripts\python.exe server.py
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
4. **Clone a voice** — click **+ Voices**, upload a 5–15 s WAV/MP3, give it a name; the first use downloads ~1.8 GB of model weights
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
launch.bat           One-click Windows setup and launch
launch-silent.vbs    Windows launch without a visible console window
launch.sh            Linux / macOS setup and launch
```

---

## License

Lector is a commercial product. Use is governed by the [SIM DAD LLC End User License Agreement](LICENSE). All rights reserved.
