#!/bin/bash
# ScriVocalis — Linux / macOS launcher
# Usage: bash launch.sh
set -e
cd "$(dirname "$0")"

LOG="./launch_log.txt"
echo "[$(date)] Launch started" > "$LOG"

# ── Find Python 3.12 ──────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; v=sys.version_info; print(v.major,v.minor)" 2>/dev/null)
        if [ "$VER" = "3 12" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.12 not found."
    echo "Install it from https://www.python.org/downloads/"
    exit 1
fi

# ── First-time setup ──────────────────────────────────────────────────────────
if [ ! -f ".venv/bin/python" ]; then
    echo "[1/4] Creating virtual environment (Python 3.12)..."
    "$PYTHON" -m venv .venv >> "$LOG" 2>&1
    source .venv/bin/activate

    # Detect CUDA (Linux) vs CPU (macOS or no GPU)
    if [[ "$(uname)" == "Linux" ]] && command -v nvidia-smi &>/dev/null; then
        echo "[2/4] Installing PyTorch 2.6.0 with CUDA 12.4..."
        pip install torch==2.6.0 torchaudio==2.6.0 \
            --index-url https://download.pytorch.org/whl/cu124 >> "$LOG" 2>&1
    else
        echo "[2/4] Installing PyTorch 2.6.0 (CPU)..."
        echo "      Note: voice cloning requires an NVIDIA GPU — built-in voices will still work."
        pip install torch==2.6.0 torchaudio==2.6.0 >> "$LOG" 2>&1
    fi
    echo "[2/4] PyTorch installed." >> "$LOG"

    echo "[3/4] Installing numpy..."
    pip install numpy >> "$LOG" 2>&1

    echo "[4/4] Installing remaining dependencies..."
    pip install -r requirements.txt >> "$LOG" 2>&1

    echo ""
    echo "Setup complete."
    echo ""
else
    source .venv/bin/activate
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo "Starting ScriVocalis at http://127.0.0.1:7860"
echo "Log: $LOG"
echo ""
python server.py 2>&1 | tee -a "$LOG"
