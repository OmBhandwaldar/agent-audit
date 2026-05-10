"""
Phase 2 checkpoint script for AgentAudit.

Runs 3 audit records through the full Phase 2 pipeline:
  1. Encrypt decision JSON with AES-GCM-256
  2. Upload encrypted envelope to IPFS
  3. Call PolicyContract.check_and_mint (policy check + AACR mint)
  4. Add record to BatchStore
  5. Flush batch -> compute Merkle root -> anchor on AnchorContract
  6. Verify root round-trip and Merkle proof for each record

Usage:
  python scripts/runFlow_v2.py
"""

import asyncio
import hashlib
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from algorand.contract_client_v2 import get_anchor_root, submit_policy_check
from batcher.anchor import flush_and_anchor
from batcher.merkle import verify_proof
from batcher.store import BatchStore
from crypto.payload import encrypt_payload
from ipfs.uploader import upload_to_ipfs

# Three test cases covering all policy outcomes
TEST_CASES = [
    {"amount": 4500, "vendor_id": "VENDOR_001"},  # pass + pass -> mint
    {"amount": 7000, "vendor_id": "VENDOR_001"},  # fail + pass -> no mint
    {"amount": 4500, "vendor_id": "VENDOR_999"},  # pass + fail -> no mint
]


async def process_record(
    amount: int,
    vendor_id: str,
    agent_id: str,
    store: BatchStore,
    index: int,
) -> dict:
    """
    Run one audit record through encrypt -> IPFS -> PolicyContract -> BatchStore.

    Returns the completed record dict (with policy fields added).
    """
    action_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    timestamp = int(time.time())
    policy_limit = int(os.getenv("POLICY_LIMIT", "5000"))

    decision = "approved" if amount < policy_limit else "rejected"
    reason = (
        f"Amount {amount} is within policy limit {policy_limit}"
        if decision == "approved"
        else f"Amount {amount} exceeds policy limit {policy_limit}"
    )

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

    print(f"  [{index+1}] amount={amount} vendor={vendor_id} decision={decision.upper()}")

    # Encrypt + upload
    envelope = encrypt_payload(record)
    ipfs_cid = await upload_to_ipfs(envelope, name=action_id)
    ipfs_hash = hashlib.sha256(ipfs_cid.encode()).hexdigest()
    print(f"       IPFS: {ipfs_cid[:20]}... (encrypted)")

    # Policy check
    policy_result = await submit_policy_check(
        action_id=action_id,
        ipfs_hash=ipfs_hash,
        amount=amount,
        vendor_id=vendor_id,
        agent_id=agent_id,
        timestamp=timestamp,
    )
    print(f"       Policy: {policy_result.policy_result}  ASA minted: {policy_result.asa_minted}")
    print(f"       TX: {policy_result.tx_id}")

    # Attach policy fields then add to batcher
    record["ipfs_cid"] = ipfs_cid
    record["ipfs_hash"] = ipfs_hash
    record["policy_result"] = policy_result.policy_result
    record["policy_tx_id"] = policy_result.tx_id
    record["asa_minted"] = policy_result.asa_minted

    store.add(record)
    return record


async def main() -> None:
    """Run 3 audit records through Phase 2 pipeline and anchor as a batch."""
    agent_id = os.getenv("AGENT_ID", "agent_001")
    store = BatchStore()

    print(f"\n{'='*60}")
    print("AgentAudit Phase 2 -- Merkle Batch Checkpoint")
    print(f"{'='*60}")
    print(f"Processing {len(TEST_CASES)} records...")
    print()

    records = []
    for i, case in enumerate(TEST_CASES):
        rec = await process_record(
            amount=case["amount"],
            vendor_id=case["vendor_id"],
            agent_id=agent_id,
            store=store,
            index=i,
        )
        records.append(rec)
        print()

    # Flush and anchor the batch
    print(f"Flushing batch ({store.size()} records) and anchoring Merkle root...")
    batch = await flush_and_anchor(store)
    anchor_tx_id = batch.anchor_tx_id  # type: ignore[attr-defined]
    print(f"  Batch ID:    {batch.batch_id}")
    print(f"  Merkle root: {batch.merkle_root[:32]}...")
    print(f"  Anchor TX:   {anchor_tx_id}")
    print()

    # Verify root round-trip from AnchorContract
    print("Verifying root round-trip from AnchorContract...")
    stored_root = await get_anchor_root(batch.batch_id)
    root_match = stored_root == batch.merkle_root
    print(f"  Stored root: {stored_root[:32]}...")
    print(f"  Match:       {'YES' if root_match else 'NO -- MISMATCH'}")
    print()

    # Verify Merkle proof for each leaf
    print("Verifying Merkle proofs for all leaves...")
    all_proofs_ok = True
    for i, entry in enumerate(batch.entries):
        proof = batch.proof_for(i)
        ok = verify_proof(entry.leaf, proof, batch.merkle_root)
        status = "PASS" if ok else "FAIL"
        print(f"  Leaf {i} (action={entry.record['action_id']}): proof_len={len(proof)}  {status}")
        if not ok:
            all_proofs_ok = False
    print()

    # Summary
    print(f"{'='*60}")
    print(f"Records processed: {len(records)}")
    print(f"Batch ID:          {batch.batch_id}")
    print(f"Merkle root:       {batch.merkle_root}")
    print(f"Anchor TX:         {anchor_tx_id}")
    print(f"Root verified:     {root_match}")
    print(f"All proofs valid:  {all_proofs_ok}")
    print()

    if not root_match or not all_proofs_ok:
        print("FAIL: One or more checks failed.")
        sys.exit(1)

    print("Phase 2 Merkle batch checkpoint: PASSED")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
