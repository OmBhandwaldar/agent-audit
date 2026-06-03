"""
Standalone check for the Phase 0 get_anchor_root rewrite (free box read).

Validates the new box-read path against live on-chain data WITHOUT any secrets:
no mnemonic, no .env, no Pinata, no Groq. Only a public AlgoNode endpoint.

Two modes:
  1. Comparison: fetch a recent batch from the live backend and confirm the
     box-read root matches the root the backend reported.
  2. Structural fallback: if no live batch is available, enumerate the
     AnchorContract's boxes directly and confirm a root decodes to 64 hex chars.

Run:  python scripts/check_anchor_read.py
   or python scripts/check_anchor_read.py <batch_id> <expected_root>
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import urllib.request

# Public config — a read-only box query needs no secrets.
os.environ.setdefault("ANCHOR_APP_ID", "762026494")
os.environ.setdefault("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorand.client import get_algod_client  # noqa: E402
from algorand.contract_client_v2 import ANCHOR_APP_ID, get_anchor_root  # noqa: E402

LIVE_BACKEND = "https://romantic-wonder-production-b252.up.railway.app"


def _fetch_recent_batch() -> dict | None:
    """Fetch the most recent anchored batch from the live backend, or None."""
    try:
        with urllib.request.urlopen(f"{LIVE_BACKEND}/api/batch/status", timeout=20) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"  (could not reach live backend: {e})")
        return None
    batches = data.get("recent_batches", [])
    return batches[0] if batches else None


def _decode_root_from_box_value(b64_value: str) -> str:
    """Decode the merkle_root (first dynamic field) from a raw AnchorRecord box value."""
    raw = base64.b64decode(b64_value)
    offset = int.from_bytes(raw[0:2], "big")
    length = int.from_bytes(raw[offset:offset + 2], "big")
    return raw[offset + 2:offset + 2 + length].decode()


async def _comparison_mode(batch_id: str, expected: str) -> bool:
    print(f"\nReading root via NEW box-read (AnchorContract {ANCHOR_APP_ID})...")
    root = await get_anchor_root(batch_id)
    print(f"  box-read merkle_root : {root}")
    print(f"  expected merkle_root : {expected}")
    return root == expected


def _structural_mode() -> bool:
    print("\nNo live batch available — enumerating AnchorContract boxes directly...")
    client = get_algod_client()
    boxes = client.application_boxes(ANCHOR_APP_ID).get("boxes", [])
    if not boxes:
        print(f"  No boxes on AnchorContract {ANCHOR_APP_ID}. Nothing to verify.")
        return False
    print(f"  {len(boxes)} box(es) found. Decoding the first...")
    name = base64.b64decode(boxes[0]["name"])
    box = client.application_box_by_name(ANCHOR_APP_ID, name)
    root = _decode_root_from_box_value(box["value"])
    print(f"  decoded merkle_root  : {root}")
    is_hex64 = len(root) == 64 and all(c in "0123456789abcdef" for c in root.lower())
    print(f"  structural check     : {'OK (64 hex chars)' if is_hex64 else 'BAD'}")
    return is_hex64


async def main() -> None:
    if len(sys.argv) >= 3:
        ok = await _comparison_mode(sys.argv[1], sys.argv[2])
    else:
        print(f"Fetching a recent batch from {LIVE_BACKEND}...")
        b = _fetch_recent_batch()
        if b and b.get("batch_id") and b.get("merkle_root"):
            print(f"  batch_id={b['batch_id']}")
            ok = await _comparison_mode(b["batch_id"], b["merkle_root"])
        else:
            ok = _structural_mode()

    print("\nRESULT:", "PASS — box-read works" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
