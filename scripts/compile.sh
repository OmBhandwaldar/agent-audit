#!/bin/bash
# Wrapper for compiling Algorand Python contracts.
# Usage: bash scripts/compile.sh contracts/policy_contract.py
# Requires the PuyaPy compiler in the active venv:  pip install puyapy

CONTRACT=${1:-contracts/policy_contract.py}

# Resolve project root from script location so OUT_DIR is always correct
# regardless of which directory the script is run from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUT_DIR="$PROJECT_ROOT/contracts/artifacts"

VIRTUAL_ENV="$PROJECT_ROOT/.venv"
export VIRTUAL_ENV

puyapy "$CONTRACT" --out-dir "$OUT_DIR"
