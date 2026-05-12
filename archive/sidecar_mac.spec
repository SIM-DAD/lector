# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Lector Python sidecar — macOS (Apple Silicon + Intel).

Mirrors sidecar.spec (Windows) with the same hard-won lessons from
2026-04-25 iteration: ONEDIR mode, conservative excludes, defensive
collect_all for kokoro / f5_tts / misaki / language_tags / spaCy models.

Run:  .venv/bin/python -m PyInstaller sidecar_mac.spec --clean --noconfirm
Output (Apple Silicon):
  dist/lector-api-aarch64-apple-darwin/lector-api-aarch64-apple-darwin
  + a folder of bundled dylibs and Python libs.
Output (Intel):
  dist/lector-api-x86_64-apple-darwin/...

The folder ships verbatim inside the Tauri NSIS-equivalent bundle
(.dmg + codesigned .app on macOS). Tauri's externalBin reference
points at the binary; the surrounding folder is bundled as-is.
"""

import platform
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

if sys.platform != "darwin":
    sys.exit("sidecar_mac.spec is for macOS only. Use sidecar.spec on Windows.")

ROOT = Path(SPECPATH)

arch = "aarch64" if platform.machine() == "arm64" else "x86_64"
triple = f"{arch}-apple-darwin"
exe_name = f"lector-api-{triple}"


# ── Defensive data collection. Same set as Windows spec — every package
# that ships JSON/YAML/binary data files needs explicit collection because
# PyInstaller only auto-copies .py bytecode.

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
_misaki_all   = _safe_collect_all("misaki")
_phonemizer_d = _safe_collect_data("phonemizer")
_espeakng_d   = _safe_collect_data("espeakng_loader")

# spaCy models. en_core_web_sm is what misaki actually uses for English G2P.
# Without bundling, Kokoro tries to pip-download at runtime (no pip in bundle = fail).
_en_sm  = _safe_collect_all("en_core_web_sm")
_en_md  = _safe_collect_all("en_core_web_md")
_en_lg  = _safe_collect_all("en_core_web_lg")
_en_trf = _safe_collect_all("en_core_web_trf")

# transformers uses _LazyModule with __getattr__. PyInstaller can't see lazy
# attributes, so the bundled transformers __init__ doesn't expose `pipeline`
# unless we collect_all + add explicit hidden imports for transformers.pipelines.
_transformers_all = _safe_collect_all("transformers")
_hf_hub_all       = _safe_collect_all("huggingface_hub")
_safetensors_all  = _safe_collect_all("safetensors")


# ── EXCLUDES philosophy: be EXTREMELY conservative. Every "obviously unused"
# transitive dep we exclude turns out to be touched deep in transformers/
# datasets/huggingface_hub init. (Empirically validated 2026-04-25 — google.*
# exclusion broke F5 because some HF lineage probes for it.)
EXCLUDES = [
    # GUI toolkits we definitely don't bundle. Lector's GUI is the Tauri-
    # embedded WKWebView running our FastAPI-served HTML/JS frontend; the
    # Python sidecar never instantiates a Qt or wx widget.
    "PySide6", "PyQt5", "PyQt6", "wx",
    # Demo UI frameworks pulled by F5-TTS upstream.
    "gradio", "gradio_client",
    # Heavy alt ML backends — transformers degrades gracefully when missing.
    "tensorflow", "keras", "tensorboard",
    # CUDA quantization — irrelevant on Apple Silicon, no CUDA at all.
    "bitsandbytes",
    # Windows-only libs that may be falsely picked up by PyInstaller analysis.
    "win32api", "win32con", "win32gui",
    "winreg", "pywintypes", "pythoncom",
    "watchdog.observers.winapi",
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
        # FastAPI / uvicorn submodules
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
        # Whisper
        "faster_whisper", "ctranslate2",
        # Torch
        "torch", "torchaudio",
        # Language data
        "language_tags",
        "misaki",
        "en_core_web_sm",
        # First-party
        "text_parser", "license_manager",
        # Cross-platform helpers (platformdirs returns macOS Application Support paths)
        "platformdirs", "psutil",
        # transformers — explicit submodules `pipeline` resolves to via _LazyModule
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
        "huggingface_hub",
        "safetensors",
        "safetensors.torch",
        # Anything the collect_all calls discovered
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

# ── ONEDIR build (NOT onefile). Same reasoning as Windows spec:
# faster cold-start, no extraction-to-temp on every launch, AV-friendlier.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                    # UPX breaks code signing on macOS
    console=True,                 # keep stdout visible for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=arch,
    codesign_identity=None,       # codesign in a post-build step (Apple Developer ID)
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=exe_name,
)
