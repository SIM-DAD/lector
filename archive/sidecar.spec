# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Lector Python sidecar.

Builds server.py into an ONEDIR bundle for Tauri's externalBin.
Onedir produces a folder of files (faster build, faster cold start,
smaller-feeling install) instead of a single multi-GB .exe.

The binary must be named with a target-triple suffix for Tauri to find it:
  lector-api-x86_64-pc-windows-msvc.exe   (Windows)
  lector-api-aarch64-apple-darwin          (macOS ARM)
  lector-api-x86_64-unknown-linux-gnu      (Linux)

Run:  .venv\\Scripts\\python -m PyInstaller sidecar.spec --clean --noconfirm
Output (Windows): dist/lector-api-x86_64-pc-windows-msvc/lector-api-x86_64-pc-windows-msvc.exe
                  + a folder of bundled DLLs and Python libs alongside it.

Tauri's externalBin reference points at the .exe; Tauri ships the surrounding
folder verbatim so Python deps load correctly at runtime.
"""

import platform
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH)


# ── Collect non-Python data files from packages that ship them.
# PyInstaller's hooks copy .py bytecode automatically but miss JSON/YAML/.bin
# data files. Each call returns (datas, binaries, hiddenimports) tuples we
# splat into the Analysis below. Wrapped in try/except so a missing optional
# dependency doesn't block the build.

def _safe_collect_all(pkg):
    try:
        return collect_all(pkg)
    except Exception as e:
        print(f"[spec] collect_all({pkg!r}) skipped: {e}")
        return ([], [], [])

def _safe_collect_data(pkg, **kw):
    try:
        return collect_data_files(pkg, **kw)
    except Exception as e:
        print(f"[spec] collect_data_files({pkg!r}) skipped: {e}")
        return []

_lt_datas     = _safe_collect_data("language_tags")
_kokoro_all   = _safe_collect_all("kokoro")
_f5_all       = _safe_collect_all("f5_tts")
_misaki_all   = _safe_collect_all("misaki")                 # phoneme dict + spacy hooks
_phonemizer_d = _safe_collect_data("phonemizer")            # Kokoro fallback
_espeakng_d   = _safe_collect_data("espeakng_loader")       # phonemizer backend on Win

# ── transformers uses _LazyModule with __getattr__ to expose `pipeline` and
# the auto-classes. PyInstaller's static analysis can't see lazy attributes,
# so the bundled transformers __init__ won't have `pipeline` available unless
# we force eager collection of all submodules.
_transformers_all = _safe_collect_all("transformers")
_hf_hub_all       = _safe_collect_all("huggingface_hub")     # transformers' download backbone
_safetensors_all  = _safe_collect_all("safetensors")         # F5 model format

# ── spaCy language models — misaki uses en_core_web_sm for English G2P.
#    Without these bundled, Kokoro tries to pip-download the model at runtime,
#    fails with "No package installer found" (no pip in the .exe), Kokoro fails.
#    Collect any installed en_core_web_* model defensively.
_en_sm  = _safe_collect_all("en_core_web_sm")
_en_md  = _safe_collect_all("en_core_web_md")
_en_lg  = _safe_collect_all("en_core_web_lg")
_en_trf = _safe_collect_all("en_core_web_trf")

# ── NLTK data — librosa / textual processing libs sometimes pull NLTK corpora
_nltk_d = _safe_collect_data("nltk_data") if False else []  # disabled, NLTK not currently in dep tree

# Determine target triple for Tauri sidecar naming
if sys.platform == "win32":
    triple = "x86_64-pc-windows-msvc"
elif sys.platform == "darwin":
    arch = "aarch64" if platform.machine() == "arm64" else "x86_64"
    triple = f"{arch}-apple-darwin"
else:
    triple = "x86_64-unknown-linux-gnu"

exe_name = f"lector-api-{triple}"


# ── Heavy / cloud / training-only deps that get pulled transitively but
#    Lector does not need at runtime.
#
#    LESSON FROM ITERATION 1: torch.ao.quantization imports unittest.mock at
#    module load, so excluding 'unittest' kills Kokoro. Same risk applies to
#    other stdlib modules that look unused but are pulled deep in torch/
#    transformers internals. RULE: never exclude stdlib modules.
#
#    Similarly conservative on third-party deps: only exclude packages we
#    know are pure UI / cloud / training-time and have no chance of being
#    touched during inference. If a future error reveals an over-exclusion,
#    add it back here and rebuild.
# EXCLUDES philosophy (revised after F5 broke from google.api_core exclusion):
# Be EXTREMELY conservative. Only exclude packages that CANNOT plausibly
# be touched by the runtime path. Every "obviously unused" cloud SDK or
# training package turns out to be imported deep in transformers, datasets,
# huggingface_hub, or one of their transitive deps. Fail-soft is impossible
# from PyInstaller's static analysis perspective; the import happens at
# module load and brings down the whole package.
EXCLUDES = [
    # GUI toolkits we definitely don't bundle. Lector's GUI is the Tauri-
    # embedded webview running our FastAPI-served HTML/JS frontend; the
    # Python sidecar never instantiates a Qt or wx widget.
    "PySide6", "PyQt5", "PyQt6", "wx",
    # Demo UI frameworks pulled by F5-TTS upstream — F5 only uses these in
    # its CLI/web demo, not in the inference path we call.
    "gradio", "gradio_client",
    # Heavy alt ML backends — transformers degrades gracefully when missing.
    "tensorflow", "keras", "tensorboard",
    # CUDA quantization — we don't quantize, missing CUDA libs anyway.
    "bitsandbytes",
]

a = Analysis(
    [str(ROOT / "server.py")],
    pathex=[str(ROOT)],
    binaries=[
        *_kokoro_all[1],
        *_f5_all[1],
        *_misaki_all[1],
        *_en_sm[1], *_en_md[1], *_en_lg[1], *_en_trf[1],
        *_transformers_all[1],
        *_hf_hub_all[1],
        *_safetensors_all[1],
    ],
    datas=[
        (str(ROOT / "static"), "static"),
        *_lt_datas,
        *_kokoro_all[0],
        *_f5_all[0],
        *_misaki_all[0],
        *_phonemizer_d,
        *_espeakng_d,
        *_en_sm[0], *_en_md[0], *_en_lg[0], *_en_trf[0],
        *_transformers_all[0],
        *_hf_hub_all[0],
        *_safetensors_all[0],
    ],
    hiddenimports=[
        # FastAPI / uvicorn submodules PyInstaller can't auto-detect
        "uvicorn", "uvicorn.logging",
        "uvicorn.loops", "uvicorn.loops.auto",
        "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan", "uvicorn.lifespan.on",
        "fastapi", "pydantic",
        # Audio I/O
        "soundfile",
        # TTS engines (lazy-loaded at runtime)
        "kokoro",
        "f5_tts", "f5_tts.api",
        # Whisper for ref-text auto-transcription on voice add
        "faster_whisper", "ctranslate2",
        # Torch (lazy-loaded by f5_tts)
        "torch", "torchaudio",
        # Language tag DB (pulled in by kokoro for BCP-47 handling)
        "language_tags",
        # Phoneme dictionary used by Kokoro
        "misaki",
        # First-party modules
        "text_parser", "license_manager",
        # Cross-platform helpers
        "platformdirs", "psutil",
        # spaCy language models (only en_core_web_sm currently installed,
        # but spec collects any present). en_core_web_sm is the one misaki
        # actually loads.
        "en_core_web_sm",
        # transformers — the submodules `pipeline` resolves to via _LazyModule.
        # Without these explicit hidden imports the bundled transformers
        # __init__ raises "Could not import module 'pipeline'" on F5's
        # `from transformers import pipeline`.
        "transformers",
        "transformers.pipelines",
        "transformers.pipelines.base",
        "transformers.pipelines.text_generation",
        "transformers.pipelines.text_classification",
        "transformers.pipelines.feature_extraction",
        "transformers.pipelines.text_to_audio",
        "transformers.pipelines.audio_classification",
        "transformers.pipelines.automatic_speech_recognition",
        "transformers.models.auto",
        "transformers.models.auto.modeling_auto",
        "transformers.models.auto.tokenization_auto",
        "transformers.models.auto.processing_auto",
        "transformers.models.auto.configuration_auto",
        "transformers.models.auto.feature_extraction_auto",
        # huggingface_hub backbone
        "huggingface_hub",
        "safetensors",
        "safetensors.torch",
        # Anything else the collect_all calls discovered
        *_kokoro_all[2],
        *_f5_all[2],
        *_misaki_all[2],
        *_en_sm[2], *_en_md[2], *_en_lg[2], *_en_trf[2],
        *_transformers_all[2],
        *_hf_hub_all[2],
        *_safetensors_all[2],
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

# ── ONEDIR build: EXE + COLLECT (folder of files), NOT a single mega-.exe.
# The folder ships verbatim inside the Tauri bundle.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,        # binaries collected into the folder by COLLECT
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,                 # keep stdout/stderr visible for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=exe_name,                # the OUTPUT FOLDER name (also contains the .exe)
)
