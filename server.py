import asyncio
import base64
import io
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path

# ─── platformdirs Windows ctypes workaround ─────────────────────────────────
# Some Windows + Python 3.12 + platformdirs combinations segfault inside
# `shell32.SHGetKnownFolderPath` (ctypes argtype mismatch reading address
# ~0x10). librosa pulls in platformdirs via pooch at module-load time, which
# means importing F5-TTS (which imports librosa) crashes the entire process
# before any Python exception handler can react. We replace `get_win_folder`
# with a pure-Python lookup against well-known env vars *before any other
# module imports platformdirs* — must run before `import library_store`,
# `import platformdirs`, etc.
try:
    import platformdirs.windows as _pdw

    def _safe_get_win_folder(csidl_name):
        if csidl_name == "CSIDL_LOCAL_APPDATA":
            return os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        if csidl_name == "CSIDL_APPDATA":
            return os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        if csidl_name == "CSIDL_PROFILE":
            return os.path.expanduser("~")
        if csidl_name == "CSIDL_PERSONAL":
            return os.path.expanduser("~\\Documents")
        if csidl_name == "CSIDL_COMMON_DOCUMENTS":
            return "C:\\Users\\Public\\Documents"
        if csidl_name == "CSIDL_MYPICTURES":
            return os.path.expanduser("~\\Pictures")
        if csidl_name == "CSIDL_MYMUSIC":
            return os.path.expanduser("~\\Music")
        if csidl_name == "CSIDL_MYVIDEO":
            return os.path.expanduser("~\\Videos")
        if csidl_name == "CSIDL_DESKTOPDIRECTORY":
            return os.path.expanduser("~\\Desktop")
        return os.path.expanduser("~")

    _pdw.get_win_folder = _safe_get_win_folder
except ImportError:
    pass

import numpy as np
import psutil
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import library_store
import license_manager
from text_parser import parse_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path resolution — works in dev (python server.py) AND in PyInstaller bundle.
#
# BUNDLE_DIR  = where bundled, read-only resources live (static/, etc.)
# USER_DATA_DIR = writable per-user dir for voices/, license file, logs.
#
# In dev, both default to the project root (legacy behaviour).
# In a frozen build, BUNDLE_DIR comes from sys._MEIPASS and USER_DATA_DIR
# comes from platformdirs so it works in Program Files and on user accounts
# with no write access to the install path.
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    # PyInstaller bundle. _MEIPASS is set in both onefile and onedir modes.
    BUNDLE_DIR = Path(sys._MEIPASS)
    try:
        import platformdirs
        # roaming=True targets %APPDATA% (Roaming) instead of %LOCALAPPDATA%.
        # Voices and library follow the user across machines on managed
        # networks; cache stays local via LIBROSA_DATA_DIR below.
        USER_DATA_DIR = Path(platformdirs.user_data_dir("Lector", "SIM DAD LLC", roaming=True))
    except Exception:
        USER_DATA_DIR = Path(sys.executable).parent
elif os.environ.get("LECTOR_PRODUCTION", "").lower() in ("1", "true", "yes"):
    # Tauri shell + launch.bat (post-PyInstaller pivot). Code lives in the
    # install dir (e.g. Program Files\Lector) which is read-only on standard
    # user accounts, so voices/library/cache must go to a per-user data dir.
    BUNDLE_DIR = Path(__file__).parent
    try:
        import platformdirs
        USER_DATA_DIR = Path(platformdirs.user_data_dir("Lector", "SIM DAD LLC", roaming=True))
    except Exception:
        USER_DATA_DIR = Path(__file__).parent
else:
    BUNDLE_DIR = Path(__file__).parent
    USER_DATA_DIR = Path(__file__).parent  # dev: voices/ stays in repo

STATIC_DIR = BUNDLE_DIR / "static"
VOICES_DIR = USER_DATA_DIR / "voices"
LIBRARY_DIR = USER_DATA_DIR / "library"
LIBROSA_CACHE_DIR = USER_DATA_DIR / "librosa-cache"
VOICES_DIR.mkdir(parents=True, exist_ok=True)
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
LIBROSA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
logger.info(
    "Lector paths: bundle=%s, voices=%s, library=%s",
    BUNDLE_DIR, VOICES_DIR, LIBRARY_DIR,
)
# Mop up any plaintext or ciphertext leaked by a prior crashed save/load.
library_store.cleanup_scratch_dir(LIBRARY_DIR)

# F5-TTS's import chain pulls in librosa, which calls platformdirs at module
# load time (librosa -> pooch -> platformdirs.user_cache_dir). On certain
# Windows + Python 3.12 + platformdirs combinations the ctypes call into
# shell32.SHGetKnownFolderPath segfaults (ctypes argtype mismatch reading
# from address ~0x10). librosa honours LIBROSA_DATA_DIR if set, which
# short-circuits the broken platformdirs call entirely.
os.environ.setdefault("LIBROSA_DATA_DIR", str(LIBROSA_CACHE_DIR))

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Bundled offline docs (Help link in the toolbar opens /help/). The path is
# /help, not /docs, because FastAPI auto-mounts /docs as its built-in Swagger
# UI and that would shadow ours. html=True makes /help/ auto-serve index.html.
_HELP_DIR = BUNDLE_DIR / "docs"
if _HELP_DIR.is_dir():
    app.mount("/help", StaticFiles(directory=str(_HELP_DIR), html=True), name="help")

# ---------------------------------------------------------------------------
# Built-in voices — Kokoro voicepacks (offline, Apache 2.0)
# ---------------------------------------------------------------------------

BUILTIN_VOICES = [
    # American English
    {"id": "af_heart",   "name": "Heart — US Female",     "type": "builtin"},
    {"id": "af_bella",   "name": "Bella — US Female",     "type": "builtin"},
    {"id": "af_nicole",  "name": "Nicole — US Female",    "type": "builtin"},
    {"id": "af_sarah",   "name": "Sarah — US Female",     "type": "builtin"},
    {"id": "af_nova",    "name": "Nova — US Female",      "type": "builtin"},
    {"id": "am_adam",    "name": "Adam — US Male",        "type": "builtin"},
    {"id": "am_michael", "name": "Michael — US Male",     "type": "builtin"},
    {"id": "am_eric",    "name": "Eric — US Male",        "type": "builtin"},
    # British English
    {"id": "bf_emma",    "name": "Emma — UK Female",      "type": "builtin"},
    {"id": "bf_isabella","name": "Isabella — UK Female",   "type": "builtin"},
    {"id": "bm_george",  "name": "George — UK Male",      "type": "builtin"},
    {"id": "bm_daniel",  "name": "Daniel — UK Male",      "type": "builtin"},
]

# ---------------------------------------------------------------------------
# Lazy-loaded models — only initialised on first use
# ---------------------------------------------------------------------------

_kokoro_pipeline = None
_f5_model         = None
_whisper_mod      = None

# Engine status — observed via GET /status by the frontend splash screen.
# Values: "cold" | "loading" | "ready" | "failed:<reason>"
_kokoro_status: str = "cold"
_f5_status: str     = "cold"
_status_lock        = threading.Lock()


def _set_status(engine: str, value: str) -> None:
    global _kokoro_status, _f5_status
    with _status_lock:
        if engine == "kokoro":
            _kokoro_status = value
        elif engine == "f5":
            _f5_status = value


def _available_ram_gb() -> float:
    try:
        return psutil.virtual_memory().available / (1024 ** 3)
    except Exception:
        return 8.0


def _load_kokoro():
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        from kokoro import KPipeline
        print("Loading Kokoro TTS model (first use — downloading if needed)...")
        _kokoro_pipeline = KPipeline(lang_code="a")
        print("Kokoro ready.")
    return _kokoro_pipeline


def _load_f5():
    global _f5_model
    if _f5_model is None:
        import torch
        from f5_tts.api import F5TTS

        has_cuda = torch.cuda.is_available()
        device = "cuda:0" if has_cuda else "cpu"

        print(f"Loading F5-TTS (device={device})...")
        _f5_model = F5TTS(device=device)
        print("F5-TTS ready.")
    return _f5_model


def _load_whisper():
    global _whisper_mod
    if _whisper_mod is None:
        from faster_whisper import WhisperModel

        low_ram = _available_ram_gb() < 8
        model_size = "base" if low_ram else "base"
        print(f"Loading Whisper model ({model_size}, CPU, int8)...")
        _whisper_mod = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("Whisper ready.")
    return _whisper_mod


def _unload_whisper():
    """Free Whisper memory after transcription is done."""
    global _whisper_mod
    if _whisper_mod is not None:
        try:
            if hasattr(_whisper_mod, "model") and hasattr(_whisper_mod.model, "unload_model"):
                _whisper_mod.model.unload_model()
        except Exception:
            pass
        _whisper_mod = None


# ---------------------------------------------------------------------------
# Background preload — runs at server startup so the user's first /tts call
# does not pay the 5-30s model-load cost.
# ---------------------------------------------------------------------------

def _preload_kokoro_safe() -> None:
    _set_status("kokoro", "loading")
    try:
        _load_kokoro()
        _set_status("kokoro", "ready")
    except Exception as e:
        logger.exception("Kokoro preload failed")
        _set_status("kokoro", f"failed:{type(e).__name__}: {e}")


def _preload_f5_safe() -> None:
    _set_status("f5", "loading")
    try:
        _load_f5()
        _set_status("f5", "ready")
    except Exception as e:
        logger.exception("F5-TTS preload failed")
        _set_status("f5", f"failed:{type(e).__name__}: {e}")


def _preload_tts_engines_serially() -> None:
    """Load Kokoro, then F5 (if needed), in a single thread.

    Concurrent daemon-thread CUDA init is fragile: PyTorch's CUDA context
    is process-global, and two threads racing to allocate CUDA resources
    during model load can corrupt each other's state and segfault. We
    load sequentially in one thread so each engine sees a clean CUDA
    context. Cost: F5 preload starts ~10-15 s later than before. Benefit:
    no concurrent-CUDA-init crashes.
    """
    _preload_kokoro_safe()
    if any(VOICES_DIR.glob("*.wav")):
        _preload_f5_safe()


@app.on_event("startup")
async def _warm_models_on_boot() -> None:
    """No-op for preload. TTS engines are loaded in the main thread BEFORE
    uvicorn starts (see the `if __name__ == "__main__"` block at the bottom
    of this file).

    Why: PyTorch/CUDA initialization in a daemon thread under uvicorn
    segfaults on Windows in this dependency stack, even though the same
    code runs fine in the main thread of a regular Python process. We
    moved preload to the main thread to avoid the crash. The browser
    splash polls /status; while the server is binding the user sees a
    "Starting Lector..." state, then engines are already ready when the
    server accepts connections.

    Set LECTOR_SKIP_TTS_PRELOAD=1 to skip the main-thread preload too;
    in that mode TTS lazy-loads on first /tts call (and may crash there
    if the daemon-thread bug also affects asyncio.to_thread workers).
    """
    if os.environ.get("LECTOR_SKIP_TTS_PRELOAD", "").lower() in ("1", "true", "yes"):
        logger.warning(
            "LECTOR_SKIP_TTS_PRELOAD set; preload skipped, lazy-load on first /tts."
        )
        _set_status("kokoro", "ready")
        _set_status("f5", "ready")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

class TTSRequest(BaseModel):
    text:  str
    voice: str
    rate:  str = "+0%"


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/style.css")
async def stylesheet():
    return FileResponse(str(STATIC_DIR / "style.css"), media_type="text/css")


@app.get("/voices")
async def list_voices():
    return BUILTIN_VOICES + _custom_voices()


@app.get("/status")
async def engine_status():
    """Per-engine readiness for the splash screen.

    `has_custom_voices` tells the frontend whether F5-TTS is needed for this
    user. If False, the splash can hide as soon as Kokoro is ready.
    """
    with _status_lock:
        return {
            "kokoro": _kokoro_status,
            "f5": _f5_status,
            "has_custom_voices": bool(list(VOICES_DIR.glob("*.wav"))),
        }


# ---------------------------------------------------------------------------
# License
# ---------------------------------------------------------------------------

class ActivateRequest(BaseModel):
    key: str


@app.get("/license/check")
async def license_check():
    valid, reason = await asyncio.to_thread(license_manager.check)
    return {"valid": valid, "reason": reason}


@app.post("/license/activate")
async def license_activate(req: ActivateRequest):
    ok, msg = await asyncio.to_thread(license_manager.activate, req.key)
    if ok:
        return {"ok": True}
    return JSONResponse({"ok": False, "error": msg}, status_code=400)



@app.post("/tts")
async def tts(req: TTSRequest):
    try:
        if req.voice.startswith("custom:"):
            return await _tts_custom(req.text, req.voice[len("custom:"):])
        return await _tts_builtin(req.text, req.voice, req.rate)
    except HTTPException:
        raise
    except Exception as e:
        print(f"TTS ERROR: voice={req.voice}, text={req.text[:80]!r}...\n  {type(e).__name__}: {e}")
        raise HTTPException(500, f"TTS generation failed: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Builtin TTS — Kokoro (offline)
# ---------------------------------------------------------------------------

async def _tts_builtin(text: str, voice: str, rate: str) -> dict:
    """Generate speech using Kokoro and return base64 audio + estimated word timestamps."""

    # Parse rate string ("+20%", "-10%", "+0%") to float speed multiplier
    speed = 1.0
    try:
        pct = int(rate.replace("%", "").replace("+", ""))
        speed = 1.0 + (pct / 100.0)
        speed = max(0.5, min(2.0, speed))
    except Exception:
        pass

    def _generate():
        pipeline = _load_kokoro()
        # Collect all audio chunks from the generator
        audio_parts = []
        for _gs, _ps, audio_chunk in pipeline(text, voice=voice, speed=speed):
            audio_parts.append(audio_chunk)
        if not audio_parts:
            return np.array([], dtype=np.float32)
        return np.concatenate(audio_parts)

    full_audio = await asyncio.to_thread(_generate)

    if len(full_audio) == 0:
        return {"audio": "", "words": []}

    # Encode to WAV
    buf = io.BytesIO()
    sf.write(buf, full_audio, 24000, format="WAV")
    buf.seek(0)
    audio_b64 = base64.b64encode(buf.read()).decode()

    # Return empty words — frontend falls back to sentence-level highlighting,
    # which is fast and avoids Whisper alignment or timing estimation entirely.
    return {"audio": audio_b64, "words": []}


def _estimate_word_timing(text: str, duration: float) -> list[dict]:
    """Estimate word-level timestamps by distributing duration proportionally to word length."""
    import re
    raw_words = re.findall(r'\S+', text)
    if not raw_words:
        return []

    # Weight each word by character count (longer words take longer to say)
    total_chars = sum(len(w) for w in raw_words)
    if total_chars == 0:
        return []

    words = []
    offset = 0.0
    for w in raw_words:
        words.append({"word": w, "offset": round(offset, 3)})
        # Proportional duration based on character length
        offset += (len(w) / total_chars) * duration

    return words


# ---------------------------------------------------------------------------
# Custom TTS — F5-TTS voice cloning
# ---------------------------------------------------------------------------

def _split_long_text(text: str, max_chars: int = 200) -> list[str]:
    """Split text at clause boundaries to keep each chunk under max_chars.

    F5-TTS crashes with tensor dimension mismatches when its internal
    batching splits a single long sentence into 3+ chunks.  By pre-splitting
    at commas, semicolons, or dashes we ensure each infer() call processes
    exactly one batch.
    """
    import re
    if len(text) <= max_chars:
        return [text]

    # Split at clause boundaries: comma, semicolon, em-dash, colon
    parts = re.split(r'(?<=[,;:—–\-])\s+', text)

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = (current + " " + part).strip() if current else part
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If a single part is still too long, keep it as-is (rare)
            current = part
    if current:
        chunks.append(current)
    return chunks


async def _tts_custom(text: str, voice_name: str) -> dict:
    ref_wav = VOICES_DIR / f"{voice_name}.wav"
    ref_txt = VOICES_DIR / f"{voice_name}.ref.txt"

    if not ref_wav.exists():
        raise HTTPException(404, f"Custom voice '{voice_name}' not found.")

    ref_text = ref_txt.read_text(encoding="utf-8").strip() if ref_txt.exists() else ""

    try:
        model = await asyncio.to_thread(_load_f5)
    except Exception as e:
        print(f"F5-TTS model load error: {e}")
        raise HTTPException(500, f"F5-TTS model failed to load: {e}")

    chunks = _split_long_text(text)

    try:
        def _infer():
            wavs = []
            sample_rate = None
            for chunk in chunks:
                wav, sr, _ = model.infer(
                    ref_file=str(ref_wav),
                    ref_text=ref_text,
                    gen_text=chunk,
                    show_info=print,
                    # nfe_step=16 (kept from original). Bumping to F5's 32 default
                    # roughly doubles VRAM pressure during inference and OOM-killed
                    # the server process on a fully-loaded 3090. If users report
                    # reference-text bleed, the right fix is correcting the
                    # ref.txt match (via the Voices tab editor) — that addresses
                    # the actual root cause rather than throwing diffusion steps
                    # at the symptom.
                    nfe_step=16,
                    # Higher classifier-free guidance pushes the model onto
                    # gen_text rather than drifting back to ref_text content.
                    # CFG strength is a scalar — no extra VRAM cost.
                    cfg_strength=3.0,
                )
                arr = np.array(wav) if not isinstance(wav, np.ndarray) else wav
                if arr.ndim == 2:
                    arr = arr.mean(axis=0)
                wavs.append(arr)
                sample_rate = sr
            return np.concatenate(wavs) if len(wavs) > 1 else wavs[0], sample_rate

        wav_arr, sr = await asyncio.to_thread(_infer)
    except Exception as e:
        print(f"F5-TTS inference error: {e}")
        raise HTTPException(500, f"F5-TTS inference failed: {e}")

    if not isinstance(wav_arr, np.ndarray):
        wav_arr = np.array(wav_arr)
    if wav_arr.ndim == 2:
        wav_arr = wav_arr.mean(axis=0)

    buf = io.BytesIO()
    sf.write(buf, wav_arr, int(sr), format="WAV")
    buf.seek(0)
    audio_b64 = base64.b64encode(buf.read()).decode()

    # Sentence-level highlighting for custom voices (no word timestamps needed)
    return {"audio": audio_b64, "words": []}


# ---------------------------------------------------------------------------
# Whisper word-alignment helper
# ---------------------------------------------------------------------------

async def _whisper_word_align(audio: np.ndarray, sr: int) -> list[dict]:
    """Run Whisper on generated audio to extract word-level timestamps."""
    words: list[dict] = []
    try:
        whisper = await asyncio.to_thread(_load_whisper)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio, sr, format="WAV")
            tmp_path = tmp.name
        try:
            segs, _ = await asyncio.to_thread(
                lambda: whisper.transcribe(tmp_path, word_timestamps=True)
            )
            for seg in segs:
                for w in (seg.words or []):
                    words.append({
                        "word":   w.word.strip(),
                        "offset": round(w.start, 3),
                    })
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        print(f"Whisper word-alignment failed (falling back to paragraph highlight): {e}")
    return words


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _custom_voices() -> list[dict]:
    return [
        {
            "id":   f"custom:{p.stem}",
            "name": p.stem.replace("_", " ").replace("-", " ").title(),
            "type": "custom",
        }
        for p in sorted(VOICES_DIR.glob("*.wav"))
    ]


# ---------------------------------------------------------------------------
# Voice management
# ---------------------------------------------------------------------------

@app.post("/voice/add")
async def add_voice(file: UploadFile = File(...), name: str = Form(...)):
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip())
    if not safe:
        return JSONResponse({"error": "Invalid voice name."}, status_code=400)

    dest_wav = VOICES_DIR / f"{safe}.wav"
    dest_txt = VOICES_DIR / f"{safe}.ref.txt"

    # Save original, then convert to 16-bit 24 kHz mono WAV
    raw_bytes = await file.read()
    suffix    = Path(file.filename).suffix.lower() or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = tmp.name

    REF_SECS = 15  # F5-TTS optimal: 5-15s of clean, single-speaker audio

    try:
        import torchaudio
        waveform, sr = torchaudio.load(tmp_path)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)  # stereo -> mono
        if sr != 24000:
            waveform = torchaudio.functional.resample(waveform, sr, 24000)
        # Trim to REF_SECS — very long clips degrade cloning quality
        max_samples = REF_SECS * 24000
        if waveform.shape[-1] > max_samples:
            waveform = waveform[..., :max_samples]
        torchaudio.save(str(dest_wav), waveform, 24000, bits_per_sample=16)
    except Exception as e:
        print(f"Audio conversion failed ({e}), saving raw bytes instead.")
        dest_wav.write_bytes(raw_bytes)
    finally:
        os.unlink(tmp_path)

    # Auto-transcribe so F5-TTS has the reference text it needs
    ref_text = ""
    try:
        whisper  = await asyncio.to_thread(_load_whisper)
        segs, _  = await asyncio.to_thread(lambda: whisper.transcribe(str(dest_wav)))
        ref_text = " ".join(s.text for s in segs).strip()
    except Exception as e:
        print(f"Whisper transcription failed (continuing without ref text): {e}")

    dest_txt.write_text(ref_text, encoding="utf-8")

    # If F5-TTS hasn't been loaded yet (this is the user's first custom voice),
    # kick off preload now so playback is instant when they close the dialog.
    if _f5_status in ("cold", "failed") or _f5_status.startswith("failed:"):
        threading.Thread(target=_preload_f5_safe, daemon=True,
                         name="lector-f5-preload-on-add").start()

    return {
        "id":       f"custom:{safe}",
        "name":     name.strip(),
        "type":     "custom",
        "ref_text": ref_text,
    }


@app.delete("/voice/{name}")
async def delete_voice(name: str):
    wav = VOICES_DIR / f"{name}.wav"
    if not wav.exists():
        return JSONResponse({"error": "Voice not found."}, status_code=404)
    wav.unlink(missing_ok=True)
    (VOICES_DIR / f"{name}.ref.txt").unlink(missing_ok=True)
    return {"ok": True}


class RefTextRequest(BaseModel):
    ref_text: str


@app.get("/voice/{name}/ref-text")
async def get_voice_ref_text(name: str):
    """Return the reference transcription paired with a custom voice WAV.

    The frontend Voices tab lets users edit this to correct Whisper's
    auto-transcription — a precise ref_text is what keeps F5 from
    hallucinating reference-audio content into the output.
    """
    wav = VOICES_DIR / f"{name}.wav"
    if not wav.exists():
        return JSONResponse({"error": "Voice not found."}, status_code=404)
    ref = VOICES_DIR / f"{name}.ref.txt"
    text = ref.read_text(encoding="utf-8") if ref.exists() else ""
    return {"name": name, "ref_text": text}


@app.post("/voice/{name}/ref-text")
async def set_voice_ref_text(name: str, req: RefTextRequest):
    wav = VOICES_DIR / f"{name}.wav"
    if not wav.exists():
        return JSONResponse({"error": "Voice not found."}, status_code=404)
    text = (req.ref_text or "").strip()
    if not text:
        return JSONResponse({"error": "ref_text cannot be empty."}, status_code=400)
    (VOICES_DIR / f"{name}.ref.txt").write_text(text, encoding="utf-8")
    return {"ok": True, "ref_text": text}


@app.post("/parse")
async def parse_document(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".docx", ".md"}:
        return JSONResponse({"error": "Only .docx and .md files are supported."}, status_code=400)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text = parse_file(tmp_path)
        return {"text": text}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Encrypted document library
# ---------------------------------------------------------------------------
# Each saved document is `library/{slug}.txt.age` encrypted to the user's
# X25519 key in the OS keystore (DPAPI on Windows, Keychain on macOS,
# libsecret on Linux). See lector/crypto.py and library_store.py.
# Threat model: simdad-crypto README §1.

class LibrarySaveRequest(BaseModel):
    name: str
    content: str


@app.get("/library")
async def library_list():
    """Return the encrypted document library listing (no decryption)."""
    docs = await asyncio.to_thread(library_store.list_documents, LIBRARY_DIR)
    return {"documents": docs}


@app.post("/library/save")
async def library_save(req: LibrarySaveRequest):
    name = req.name.strip()
    if not name:
        return JSONResponse({"error": "Document name is required."}, status_code=400)
    try:
        doc = await asyncio.to_thread(
            library_store.save_document, LIBRARY_DIR, name, req.content
        )
        return doc
    except library_store.crypto.KeystoreUnavailableError as e:
        return JSONResponse({"error": f"OS keystore unavailable: {e}"}, status_code=503)
    except Exception as e:
        logger.exception("Library save failed")
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"}, status_code=500
        )


@app.get("/library/{doc_id}")
async def library_load(doc_id: str):
    try:
        doc = await asyncio.to_thread(library_store.load_document, LIBRARY_DIR, doc_id)
        return doc
    except FileNotFoundError:
        return JSONResponse({"error": "Document not found."}, status_code=404)
    except library_store.crypto.DecryptionError as e:
        return JSONResponse({"error": f"Decryption failed: {e}"}, status_code=500)
    except library_store.crypto.KeystoreUnavailableError as e:
        return JSONResponse({"error": f"OS keystore unavailable: {e}"}, status_code=503)
    except Exception as e:
        logger.exception("Library load failed")
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"}, status_code=500
        )


@app.delete("/library/{doc_id}")
async def library_delete(doc_id: str):
    await asyncio.to_thread(library_store.delete_document, LIBRARY_DIR, doc_id)
    return {"ok": True}


@app.get("/identity/recovery-key")
async def identity_recovery_key():
    """Reveal the AGE-SECRET-KEY-1... private key that protects the encrypted
    library. Customers need this string to recover their library if they
    reinstall, switch machines, or lose access to the OS keystore. The string
    must be stored somewhere secure (password manager, printed paper)."""
    try:
        import crypto
        key = await asyncio.to_thread(crypto.get_identity)
        return {"key": key}
    except Exception as e:
        logger.exception("Recovery key reveal failed")
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"}, status_code=500
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import threading
    import webbrowser
    import uvicorn

    # Preload TTS engines in the MAIN thread BEFORE uvicorn starts. PyTorch
    # CUDA initialization in a daemon thread under uvicorn segfaults on
    # Windows in this dependency stack (empirically confirmed: same code
    # runs fine in main thread of a plain Python process, crashes when
    # spawned as a daemon thread from inside uvicorn's startup hook).
    # Cost: ~10-30 s startup delay on first launch; the browser splash
    # polls /status and shows "Starting Lector..." until the server binds.
    if os.environ.get("LECTOR_SKIP_TTS_PRELOAD", "").lower() not in ("1", "true", "yes"):
        sys.stdout.write("Preloading TTS engines in main thread (one-time, ~10-30s)...\n")
        sys.stdout.flush()
        _preload_kokoro_safe()
        if any(VOICES_DIR.glob("*.wav")):
            _preload_f5_safe()
        sys.stdout.write("TTS engines ready.\n")
        sys.stdout.flush()

    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "unknown"
    print(f"  Local:   http://127.0.0.1:7860")
    print(f"  Network: http://{local_ip}:7860")
    # Under the Tauri shell the webview is the UI; spawning a browser tab opens
    # a parallel window the customer didn't ask for. Skip when LECTOR_PRODUCTION
    # is set (launch.bat exports it); keep the auto-open for plain-Python dev.
    if os.environ.get("LECTOR_PRODUCTION", "").lower() not in ("1", "true", "yes"):
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:7860")).start()
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")
