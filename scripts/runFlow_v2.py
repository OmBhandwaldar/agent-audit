"""
Day 2 checkpoint script for AgentAudit Phase 2.

Tests the split-contract flow end-to-end (no batching or encryption yet):
  1. Upload decision JSON to IPFS
  2. Call PolicyContract.check_and_mint — policy check + AACR mint
  3. Submit a single-leaf Merkle root to AnchorContract

Usage:
  python scripts/runFlow_v2.py <amount> <vendor_id>
  python scripts/runFlow_v2.py 4500 VENDOR_001   # should approve + mint
  python scripts/runFlow_v2.py 7000 VENDOR_001   # should reject (amount fails)
  python scripts/runFlow_v2.py 4500 VENDOR_999   # should reject (vendor fails)
"""

import asyncio
import hashlib
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from algorand.contract_client_v2 import (
    get_anchor_root,
    submit_anchor_root,
    submit_policy_check,
)
from ipfs.uploader import upload_to_ipfs


def _leaf_hash(record: dict) -> str:
    """Compute SHA256 of sorted-JSON canonical form of a record."""
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def main() -> None:
    """Run the Phase 2 flow and print results."""
    amount = int(sys.argv[1]) if len(sys.argv) > 1 else 4500
    vendor_id = sys.argv[2] if len(sys.argv) > 2 else "VENDOR_001"

    action_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    agent_id = os.getenv("AGENT_ID", "agent_001")
    timestamp = int(time.time())

    print(f"\n{'='*55}")
    print(f"AgentAudit Phase 2 — runFlow_v2.py")
    print(f"{'='*55}")
    print(f"Amount:    {amount}")
    print(f"Vendor:    {vendor_id}")
    print(f"Action ID: {action_id}")
    print()

    # 1. Agent decision (simple rule — LangChain integration is Phase 1)
    policy_limit = int(os.getenv("POLICY_LIMIT", "5000"))
    decision = "approved" if amount < policy_limit else "rejected"
    reason = (
        f"Amount {amount} is within policy limit {policy_limit}"
        if amount < policy_limit
        else f"Amount {amount} exceeds policy limit {policy_limit}"
    )
    print(f"Agent decision: {decision.upper()}")
    print(f"Reason:         {reason}")
    print()

    # 2. Build decision record
    record = {
        "action": "approve_payment",
        "action_id": action_id,
        "amount": amount,
        "vendor_id": vendor_id,
        "decision": decision,
        "reason": reason,
        "policy": "limit_5000",
        "agent_id": agent_id,
        "timestamp": timestamp,
    }

    # 3. Upload to IPFS
    print("Uploading to IPFS...")
    ipfs_cid = await upload_to_ipfs(record)
    ipfs_hash = hashlib.sha256(ipfs_cid.encode()).hexdigest()
    print(f"  IPFS CID:  {ipfs_cid}")
    print(f"  IPFS hash: {ipfs_hash[:16]}...")
    print()

    # 4. Call PolicyContract.check_and_mint
    print("Calling PolicyContract.check_and_mint...")
    policy_result = await submit_policy_check(
        action_id=action_id,
        ipfs_hash=ipfs_hash,
        amount=amount,
        vendor_id=vendor_id,
        agent_id=agent_id,
        timestamp=timestamp,
    )
    print(f"  Policy TX:     {policy_result.tx_id}")
    print(f"  Policy result: {policy_result.policy_result}")
    print(f"  ASA minted:    {policy_result.asa_minted}")
    print()

    # 5. Build single-leaf Merkle root (leaf = hash of the record)
    record["policy_result"] = policy_result.policy_result
    record["policy_tx_id"] = policy_result.tx_id
    leaf = _leaf_hash(record)
    merkle_root = leaf  # single-leaf tree: root == the leaf
    leaf_count = 1

    batch_id = f"batch_{timestamp}_{random.randint(1000, 9999)}"

    print(f"Anchoring Merkle root (single leaf)...")
    print(f"  Batch ID:    {batch_id}")
    print(f"  Merkle root: {merkle_root[:16]}...")

    anchor_tx_id = await submit_anchor_root(
        batch_id=batch_id,
        merkle_root=merkle_root,
        leaf_count=leaf_count,
        timestamp=timestamp,
    )
    print(f"  Anchor TX:   {anchor_tx_id}")
    print()

    # 6. Verify round-trip — read root back from AnchorContract
    print("Verifying root round-trip from AnchorContract...")
    stored_root = await get_anchor_root(batch_id)
    root_verified = stored_root == merkle_root
    print(f"  Stored root: {stored_root[:16]}...")
    match_str = "YES" if root_verified else "NO -- MISMATCH"
    print(f"  Match:       {match_str}")
    print()

    # 7. Summary
    print(f"{'='*55}")
    print(f"Decision:      {decision.upper()}")
    print(f"IPFS CID:      {ipfs_cid}")
    print(f"Policy TX:     {policy_result.tx_id}")
    print(f"Policy Result: {policy_result.policy_result}")
    print(f"ASA Minted:    {policy_result.asa_minted}")
    print(f"Anchor TX:     {anchor_tx_id}")
    print(f"Batch ID:      {batch_id}")
    print(f"Root Verified: {root_verified}")
    print()

    if not root_verified:
        print("FAIL: Root mismatch -- AnchorContract may have a bug. Check contract code.")
        sys.exit(1)

    print("Phase 2 Day 2 checkpoint: PASSED")
    print(f"{'='*55}")


if __name__ == "__main__":
    asyncio.run(main())
