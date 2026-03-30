#!/bin/bash
# Wrapper for compiling Algorand Python contracts on Windows.
# Usage: bash scripts/compile.sh contracts/audit_contract.py
# Required because puyapy needs VIRTUAL_ENV set to find the correct Python (not Windows Store redirect).

CONTRACT=${1:-contracts/audit_contract.py}
OUT_DIR="contracts/artifacts"

VIRTUAL_ENV="$(pwd)/.venv"
export VIRTUAL_ENV

"C:/Users/ombha/pipx/venvs/puyapy/Scripts/puyapy.exe" "$CONTRACT" --out-dir "$OUT_DIR"
