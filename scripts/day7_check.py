"""
Comprehensive Phase 2 verification script.

Exercises every endpoint introduced or modified in Phase 2:
  - POST /api/audit (v2 flow: encrypt + IPFS + PolicyContract + add to batch)
  - GET /api/batch/status
  - POST /api/batch/submit (flush + Merkle root + anchor)
  - GET /api/verify (Merkle proof verify + decryption)
  - GET /api/tamper-demo (Merkle proof breaking)
  - GET /api/dashboard (with batcher state)
  - GET /api/verify (pending leaf path)
  - 404 paths

Run from project root: python scripts/day7_check.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import api.main as m
from batcher.store import BatchStore

CHECK_DB = "./data/day7_check.db"
PASS = "[PASS]"
FAIL = "[FAIL]"


def header(title):
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def check(label, cond, detail=""):
    tag = PASS if cond else FAIL
    print(f"  {tag}  {label}" + (f"  {detail}" if detail else ""))
    return cond


def main():
    # Override store to use a clean DB
    m.batch_store = BatchStore(db_path=CHECK_DB)
    client = TestClient(m.app)

    failures = 0

    # ----------------------------------------------------------------
    header("1. Initial dashboard state")
    r = client.get("/api/dashboard").json()
    if not check("dashboard returns batcher fields",
                 "pending_leaves_count" in r and "last_anchor_batch_id" in r,
                 f"pending={r.get('pending_leaves_count')}"):
        failures += 1
    if not check("pending_leaves_count is 0 on clean DB",
                 r["pending_leaves_count"] == 0):
        failures += 1
    if not check("last_anchor_batch_id is None on clean DB",
                 r["last_anchor_batch_id"] is None):
        failures += 1

    # ----------------------------------------------------------------
    header("2. POST /api/audit  (3 cases: pass / amount-fail / vendor-fail)")
    # expect_decision      = effective on-chain outcome (post-policy)
    # expect_agent_decision = what the encrypted IPFS record holds (pre-policy)
    cases = [
        {"amount": 4500, "vendor_id": "VENDOR_001", "expect_decision": "approved",
         "expect_agent_decision": "approved",
         "expect_policy": "amount:pass|vendor:pass", "expect_mint": True},
        {"amount": 7000, "vendor_id": "VENDOR_001", "expect_decision": "rejected",
         "expect_agent_decision": "rejected",
         "expect_policy": "amount:fail|vendor:pass", "expect_mint": False},
        {"amount": 4500, "vendor_id": "VENDOR_999", "expect_decision": "rejected",
         "expect_agent_decision": "approved",  # agent only sees amount; vendor fail is on-chain
         "expect_policy": "amount:pass|vendor:fail", "expect_mint": False},
    ]
    action_ids = []
    for i, c in enumerate(cases, 1):
        print(f"\n  Case {i}: amount={c['amount']} vendor={c['vendor_id']}")
        resp = client.post("/api/audit", json={"amount": c["amount"], "vendor_id": c["vendor_id"]})
        if resp.status_code != 200:
            print(f"  {FAIL}  HTTP {resp.status_code}: {resp.json()}")
            failures += 1
            continue
        r = resp.json()
        action_ids.append(r["action_id"])
        if not check(f"decision={c['expect_decision']}", r["decision"] == c["expect_decision"]):
            failures += 1
        if not check(f"policy_result={c['expect_policy']}", r["policy_result"] == c["expect_policy"]):
            failures += 1
        if not check(f"asa_minted={c['expect_mint']}", r["asa_minted"] == c["expect_mint"]):
            failures += 1
        if not check("encrypted=True", r.get("encrypted") is True):
            failures += 1
        if not check(f"batch_pending_count={i}", r["batch_pending_count"] == i):
            failures += 1
        if not check("ipfs_cid present", bool(r["ipfs_cid"])):
            failures += 1
        if not check("algorand_tx_id present", bool(r["algorand_tx_id"])):
            failures += 1

    # ----------------------------------------------------------------
    header("3. /api/verify on PENDING leaf (before flush)")
    r = client.get(f"/api/verify?action_id={action_ids[0]}").json()
    if not check("anchor_status=pending", r["anchor_status"] == "pending"):
        failures += 1
    if not check("verification.merkle_proof_valid is None",
                 r["verification"]["merkle_proof_valid"] is None):
        failures += 1
    if not check("decryption.decrypted=False (no proof yet)",
                 r["decryption"]["decrypted"] is False):
        failures += 1
    if not check("record_summary present", "record_summary" in r and bool(r["record_summary"])):
        failures += 1

    # ----------------------------------------------------------------
    header("4. /api/tamper-demo on PENDING leaf -> 400")
    resp = client.get(f"/api/tamper-demo?action_id={action_ids[0]}")
    if not check("returns 400 for not-yet-anchored leaf", resp.status_code == 400,
                 f"got {resp.status_code}"):
        failures += 1

    # ----------------------------------------------------------------
    header("5. /api/batch/status pre-flush")
    r = client.get("/api/batch/status").json()
    if not check("pending_count=3", r["pending_count"] == 3):
        failures += 1
    if not check("is_full=False (BATCH_SIZE>3)", r["is_full"] is False):
        failures += 1

    # ----------------------------------------------------------------
    header("6. POST /api/batch/submit  (flush + anchor)")
    r = client.post("/api/batch/submit").json()
    if not check("batch_id present", bool(r.get("batch_id"))):
        failures += 1
    if not check("merkle_root present", bool(r.get("merkle_root")) and len(r["merkle_root"]) == 64):
        failures += 1
    if not check("leaf_count=3", r.get("leaf_count") == 3):
        failures += 1
    if not check("anchor_tx_id present", bool(r.get("anchor_tx_id"))):
        failures += 1
    batch_id = r["batch_id"]
    print(f"      batch_id:    {batch_id}")
    print(f"      merkle_root: {r['merkle_root'][:32]}...")
    print(f"      anchor_tx:   {r['anchor_tx_id']}")

    # ----------------------------------------------------------------
    header("7. /api/batch/status post-flush")
    r = client.get("/api/batch/status").json()
    if not check("pending_count=0 after flush", r["pending_count"] == 0):
        failures += 1
    if not check("recent_batches contains the new batch",
                 any(b["batch_id"] == batch_id for b in r["recent_batches"])):
        failures += 1

    # ----------------------------------------------------------------
    header("8. GET /api/batch/{batch_id}")
    r = client.get(f"/api/batch/{batch_id}").json()
    if not check("merkle_root in response", "merkle_root" in r and len(r["merkle_root"]) == 64):
        failures += 1
    if not check("leaf_count=3", r.get("leaf_count") == 3):
        failures += 1
    if not check("anchor_tx_id in response", bool(r.get("anchor_tx_id"))):
        failures += 1

    # ----------------------------------------------------------------
    header("9. /api/verify  (anchored, with Merkle proof + decryption)")
    for aid, c in zip(action_ids, cases):
        print(f"\n  action_id={aid}  expected={c['expect_decision']}")
        r = client.get(f"/api/verify?action_id={aid}").json()
        if not check("anchor_status=anchored", r["anchor_status"] == "anchored"):
            failures += 1
        if not check("merkle_proof_valid=True",
                     r["verification"]["merkle_proof_valid"] is True):
            failures += 1
        if not check("merkle_root_onchain has 64 hex chars",
                     len(r["verification"]["merkle_root_onchain"]) == 64):
            failures += 1
        if not check("decryption.decrypted=True", r["decryption"]["decrypted"] is True):
            failures += 1
        dr = r["decryption"]["record"]
        if not check(f"decrypted.amount={c['amount']}", dr.get("amount") == c["amount"]):
            failures += 1
        if not check(f"decrypted.vendor_id={c['vendor_id']}", dr.get("vendor_id") == c["vendor_id"]):
            failures += 1
        # IPFS payload preserves the agent's pre-policy decision
        if not check(f"decrypted.decision={c['expect_agent_decision']} (agent's view)",
                     dr.get("decision") == c["expect_agent_decision"]):
            failures += 1
        # record_summary on the response carries the EFFECTIVE outcome
        if not check(f"record_summary.decision={c['expect_decision']} (effective)",
                     r["record_summary"]["decision"] == c["expect_decision"]):
            failures += 1

    # ----------------------------------------------------------------
    header("10. /api/tamper-demo  (real Merkle proof break)")
    r = client.get(f"/api/tamper-demo?action_id={action_ids[0]}").json()
    if not check("proof_original_valid=True", r["proof_original_valid"] is True):
        failures += 1
    if not check("proof_tampered_valid=False", r["proof_tampered_valid"] is False):
        failures += 1
    if not check("tamper_detected=True", r["tamper_detected"] is True):
        failures += 1
    if not check("leaf_hash_original != leaf_hash_tampered",
                 r["leaf_hash_original"] != r["leaf_hash_tampered"]):
        failures += 1
    if not check("merkle_root_onchain has 64 hex chars",
                 len(r["merkle_root_onchain"]) == 64):
        failures += 1

    # ----------------------------------------------------------------
    header("11. /api/dashboard post-flush")
    r = client.get("/api/dashboard").json()
    if not check("pending_leaves_count=0", r["pending_leaves_count"] == 0):
        failures += 1
    if not check(f"last_anchor_batch_id={batch_id}",
                 r["last_anchor_batch_id"] == batch_id):
        failures += 1
    if not check("total_audits=3", r["total_audits"] == 3):
        failures += 1
    if not check("approved_count=1", r["approved_count"] == 1):
        failures += 1
    if not check("rejected_count=2", r["rejected_count"] == 2):
        failures += 1

    # ----------------------------------------------------------------
    header("12. 404 / 502 / negative paths")
    resp = client.get("/api/verify?action_id=DOES_NOT_EXIST")
    if not check("/api/verify  404 for unknown id", resp.status_code == 404):
        failures += 1
    resp = client.get("/api/tamper-demo?action_id=DOES_NOT_EXIST")
    if not check("/api/tamper-demo  404 for unknown id", resp.status_code == 404):
        failures += 1
    resp = client.get("/api/batch/DOES_NOT_EXIST")
    if not check("/api/batch/{id}  404 for unknown batch", resp.status_code == 404):
        failures += 1
    resp = client.post("/api/batch/submit")
    if not check("/api/batch/submit  400 when no pending leaves", resp.status_code == 400):
        failures += 1

    # ----------------------------------------------------------------
    header("13. /api/export/csv")
    resp = client.get("/api/export/csv")
    if not check("status 200", resp.status_code == 200):
        failures += 1
    body = resp.text
    if not check("3 data rows in CSV", body.count("\n") == 4):  # header + 3 + trailing
        failures += 1
    if not check("contains action_id col header", "action_id" in body):
        failures += 1

    # ----------------------------------------------------------------
    header("RESULT")
    if failures == 0:
        print("  ALL CHECKS PASSED")
    else:
        print(f"  {failures} CHECK(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
