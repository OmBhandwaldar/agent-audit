#!/bin/bash
# Wrapper for compiling Algorand Python contracts on Windows.
# Usage: bash scripts/compile.sh contracts/audit_contract.py
# Required because puyapy needs VIRTUAL_ENV set to find the correct Python (not Windows Store redirect).

CONTRACT=${1:-contracts/audit_contract.py}

# Resolve project root from script location so OUT_DIR is always correct
# regardless of which directory the script is run from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUT_DIR="$PROJECT_ROOT/contracts/artifacts"

VIRTUAL_ENV="$PROJECT_ROOT/.venv"
export VIRTUAL_ENV

"C:/Users/ombha/pipx/venvs/puyapy/Scripts/puyapy.exe" "$CONTRACT" --out-dir "$OUT_DIR"
