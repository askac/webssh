#!/bin/bash
# WebSSH One-liner Installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/askac/webssh/main/install.sh | bash
#   or:
#   curl -fsSL https://raw.githubusercontent.com/askac/webssh/main/install.sh | bash -s -- --dir ~/webssh

set -e

REPO_URL="https://github.com/askac/webssh.git"
INSTALL_DIR="${WEBSSH_DIR:-$HOME/webssh}"

# Allow --dir override
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir|-d) INSTALL_DIR="$2"; shift 2 ;;
        *) shift ;;
    esac
done

echo "========================================"
echo "   WebSSH Installer"
echo "========================================"

# Check dependencies
if ! command -v git &>/dev/null; then
    echo "[!] ERROR: git is required but not found."
    echo "    Install with: sudo apt install git   (Debian/Ubuntu/WSL)"
    echo "                  brew install git        (macOS)"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "[!] ERROR: python3 is required but not found."
    echo "    Install with: sudo apt install python3 python3-venv   (Debian/Ubuntu/WSL)"
    echo "                  brew install python3                      (macOS)"
    exit 1
fi

# Clone or update
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[*] Existing installation found at: $INSTALL_DIR"
    echo "[*] Pulling latest changes..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "[*] Installing to: $INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo "[+] Done. Launching WebSSH..."
echo ""
exec bash "$INSTALL_DIR/run.sh"
