#!/bin/bash

# WebSSH Startup Script
# Ensure this runs in a WSL environment

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/tools/.venv_wsl"
APP_FILE="$PROJECT_DIR/app.py"
REQ_FILE="$PROJECT_DIR/requirements.txt"
INSTALLED_FLAG="$VENV_DIR/.installed"

echo "========================================"
echo "   WebSSH Automated Starter (WSL)"
echo "========================================"

# Check for force flag
FORCE_RECHECK=false
if [[ "$1" == "--force" || "$1" == "-f" ]]; then
    FORCE_RECHECK=true
fi

# 1. Check and create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "[*] Creating virtual environment: $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[!] ERROR: Failed to create virtual environment. Ensure python3-venv is installed."
        exit 1
    fi
    FORCE_RECHECK=true
fi

# 2. Activate virtual environment
source "$VENV_DIR/bin/activate"

# 3. Check and install dependencies
if [ "$FORCE_RECHECK" = true ] || [ ! -f "$INSTALLED_FLAG" ]; then
    if [ -f "$REQ_FILE" ]; then
        echo "[*] Installing/Updating dependencies from requirements.txt..."
        pip install -q -r "$REQ_FILE"
    else
        echo "[!] WARNING: requirements.txt not found, installing basic packages..."
        pip install -q Flask Flask-SocketIO paramiko eventlet
    fi

    if [ $? -eq 0 ]; then
        touch "$INSTALLED_FLAG"
        echo "[+] Dependencies verified and flag created."
    else
        echo "[!] ERROR: Failed to install dependencies."
        exit 1
    fi
else
    echo "[*] Skipping dependency check (flag exists)."
    echo "[*] Hint: Use './run.sh --force' or delete '$INSTALLED_FLAG' to re-check."
fi

# 4. Start the server

echo "[*] Starting WebSSH server..."
python "$APP_FILE"
