import asyncio
import base64
import io
import os
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import edge_tts

# Give pydub (used by F5-TTS internally) a bundled ffmpeg binary so it can
# handle MP3/M4A reference audio without requiring a system ffmpeg install.
try:
    import imageio_ffmpeg
    import pydub.utils as _pu
    _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    _pu.get_encoder_name = lambda: _ffmpeg_exe
    _pu.get_player_name  = lambda: _ffmpeg_exe
    import pydub
    pydub.AudioSegment.converter = _ffmpeg_exe
    pydub.AudioSegment.ffmpeg    = _ffmpeg_exe
    pydub.AudioSegment.ffprobe   = _ffmpeg_exe
except Exception:
    pass  # ffmpeg unavailable; WAV/FLAC reference files will still work

from text_parser import parse_file

VOICES_DIR = Path("voices")
VOICES_DIR.mkdir(exist_ok=True)

app = FastAPI()

BUILTIN_VOICES = [
    {"id": "en-US-JennyNeural",   "name": "Jenny — US Female",   "type": "builtin"},
    {"id": "en-US-AriaNeural",    "name": "Aria — US Female",    "type": "builtin"},
    {"id": "en-US-SaraNeural",    "name": "Sara — US Female",    "type": "builtin"},
    {"id": "en-US-GuyNeural",     "name": "Guy — US Male",       "type": "builtin"},
    {"id": "en-US-DavisNeural",   "name": "Davis — US Male",     "type": "builtin"},
    {"id": "en-US-TonyNeural",    "name": "Tony — US Male",      "type": "builtin"},
    {"id": "en-GB-SoniaNeural",   "name": "Sonia — UK Female",   "type": "builtin"},
    {"id": "en-GB-RyanNeural",    "name": "Ryan — UK Male",      "type": "builtin"},
    {"id": "en-AU-NatashaNeural", "name": "Natasha — AU Female", "type": "builtin"},
    {"id": "en-AU-WilliamNeural", "name": "William — AU Male",   "type": "builtin"},
]

# Lazy-loaded models — only initialised on first use
_f5_model    = None
_whisper_mod = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _custom_voices() -> list[dict]:
    return [
        {
            "id":   f"custom:{p.stem}",
            "name": p.stem.replace("_", " ").replace("-", " ").title(),
            "type": "custom",
        }
        for p in sorted(VOICES_DIR.glob("*.wav"))
    ]


def _load_f5():
    global _f5_model
    if _f5_model is None:
        from f5_tts.api import F5TTS
        print("Loading F5-TTS model (first use — downloading if needed)…")
        _f5_model = F5TTS()
        print("F5-TTS ready.")
    return _f5_model


def _load_whisper():
    global _whisper_mod
    if _whisper_mod is None:
        from faster_whisper import WhisperModel
        print("Loading Whisper model…")
        _whisper_mod = WhisperModel("base", device="cuda", compute_type="float16")
        print("Whisper ready.")
    return _whisper_mod


# ── routes ────────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text:  str
    voice: str
    rate:  str = "+0%"


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/voices")
async def list_voices():
    return BUILTIN_VOICES + _custom_voices()


@app.post("/tts")
async def tts(req: TTSRequest):
    if req.voice.startswith("custom:"):
        return await _tts_custom(req.text, req.voice[len("custom:"):])
    return await _tts_builtin(req.text, req.voice, req.rate)


async def _tts_builtin(text: str, voice: str, rate: str) -> dict:
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio_chunks: list[bytes] = []
    words: list[dict] = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            words.append({
                "word":     chunk["text"],
                "offset":   round(chunk["offset"]   / 1e7, 3),
                "duration": round(chunk["duration"]  / 1e7, 3),
            })

    return {
        "audio": base64.b64encode(b"".join(audio_chunks)).decode(),
        "words": words,
    }


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

    # Run blocking inference in a thread so the event loop stays free
    try:
        result = await asyncio.to_thread(
            lambda: model.infer(
                ref_file=str(ref_wav),
                ref_text=ref_text,
                gen_text=text,
            )
        )
    except Exception as e:
        print(f"F5-TTS inference error: {e}")
        raise HTTPException(500, f"F5-TTS inference failed: {e}")

    wav_arr, sr = result[0], result[1]
    if not isinstance(wav_arr, np.ndarray):
        wav_arr = wav_arr.numpy()
    if wav_arr.ndim == 2:
        wav_arr = wav_arr.mean(axis=0)

    buf = io.BytesIO()
    sf.write(buf, wav_arr, sr, format="WAV")
    buf.seek(0)
    audio_b64 = base64.b64encode(buf.read()).decode()

    # Use Whisper forced-alignment to get word-level timestamps from the generated audio
    words: list[dict] = []
    try:
        whisper = await asyncio.to_thread(_load_whisper)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, wav_arr, sr, format="WAV")
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

    return {
        "audio": audio_b64,
        "words": words,
    }


@app.post("/voice/add")
async def add_voice(file: UploadFile = File(...), name: str = Form(...)):
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip())
    if not safe:
        return JSONResponse({"error": "Invalid voice name."}, status_code=400)

    dest_wav = VOICES_DIR / f"{safe}.wav"
    dest_txt = VOICES_DIR / f"{safe}.ref.txt"

    # Save original, then convert to 16-bit 24 kHz mono WAV (F5-TTS expects this)
    raw_bytes = await file.read()
    suffix    = Path(file.filename).suffix.lower() or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = tmp.name
    REF_SECS = 15  # F5-TTS works best with 5–15 s of reference audio

    try:
        import torchaudio
        waveform, sr = torchaudio.load(tmp_path)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)  # stereo → mono
        if sr != 24000:
            waveform = torchaudio.functional.resample(waveform, sr, 24000)
        # Trim to REF_SECS — longer clips confuse F5-TTS and produce garbled output
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


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import threading
    import webbrowser
    import uvicorn

    import socket
    # Connect outward to find the interface actually used for LAN traffic
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "unknown"
    print(f"  Local:   http://127.0.0.1:7860")
    print(f"  Network: http://{local_ip}:7860")
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:7860")).start()
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")
