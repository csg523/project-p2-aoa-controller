#!/usr/bin/env bash
# Launch the AoA Controller GUI
# Usage: ./run_gui.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Ensure dependencies are installed
pip install -q PyQt5 pyqtgraph numpy 2>/dev/null || true

echo "Starting AoA Controller GUI..."
cd "$SCRIPT_DIR"
python tools/gui.py
