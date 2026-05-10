"""
AgentAudit FastAPI backend.

Endpoints:
  POST /api/audit          — run the full audit pipeline for a payment
  POST /api/chat           — autonomous agent: pick vendor from natural language prompt
  GET  /api/verify         — independently verify any audit record by action ID
  GET  /api/dashboard      — aggregate stats + recent audit history
  GET  /api/export/csv     — download audit history as CSV
  GET  /api/tamper-demo    — simulate tampering to prove hash detection works

Run with: uvicorn api.main:app --reload --port 8000
"""

import csv
import io
import json
import logging
import os
import time
from collections import deque
from hashlib import sha256

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from algorand.contract_client import get_audit_record
from algorand.contract_client_v2 import get_anchor_root
from batcher.anchor import flush_and_anchor
from batcher.merkle import verify_proof
from batcher.store import BatchStore
from sdk.audit_flow import run_audit_flow, run_chat_flow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AgentAudit API",
    description="Verifiable audit infrastructure for autonomous AI agents.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory audit history — holds up to 50 most recent audits, oldest auto-dropped
recent_audits: deque = deque(maxlen=50)

# Shared SQLite-backed batcher — persists across requests
batch_store = BatchStore()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AuditRequest(BaseModel):
    """Request body for POST /api/audit."""

    amount: int = Field(..., gt=0, description="Payment amount to evaluate")
    vendor_id: str = Field(..., min_length=1, description="Vendor identifier to check against whitelist")
    agent_type_id: str = Field(default="payment_approval", description="Agent type identifier")


class AuditResponse(BaseModel):
    """Response body from POST /api/audit."""

    decision: str
    ipfs_cid: str
    algorand_tx_id: str
    policy_result: str
    asa_minted: bool
    action_id: str
    vendor_id: str
    policy_checks: dict
    agent_type_id: str
    agent_id: str


class VerifyResponse(BaseModel):
    """Response body from GET /api/verify."""

    action_id: str
    ipfs_hash_onchain: str   # SHA256 hex stored in the contract
    ipfs_hash_computed: str  # SHA256 hex recomputed from fetched IPFS data
    hash_match: bool         # True = verified, False = tampered or mismatch
    record: dict             # Parsed on-chain audit record fields
    ipfs_data: dict          # Full JSON fetched from IPFS


class DashboardResponse(BaseModel):
    """Response body from GET /api/dashboard."""

    total_audits: int
    approved_count: int
    rejected_count: int
    compliance_rate: float   # percentage 0–100
    recent_audits: list[dict]


class TamperDemoResponse(BaseModel):
    """Response body from GET /api/tamper-demo."""

    action_id: str
    field_tampered: str
    original_value: str
    tampered_value: str
    hash_onchain: str        # immutable — stored in Algorand
    hash_original: str       # recomputed from real IPFS data — matches on-chain
    hash_tampered: str       # what tampered content would produce — does NOT match
    match_original: bool     # always True for a valid record
    match_tampered: bool     # always False — tamper detected


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str = Field(..., min_length=1, description="Natural language task for the agent")
    agent_type_id: str = Field(default="payment_approval", description="Agent type identifier")


class ChatResponse(BaseModel):
    """Response body from POST /api/chat."""

    reply: str                      # agent's natural language response for the chat UI
    audit_result: dict | None = None  # None when the message was off-topic


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/audit", response_model=AuditResponse)
async def audit(req: AuditRequest) -> AuditResponse:
    """
    Run the full audit pipeline for a payment amount and vendor.

    Calls the payment agent, uploads to IPFS, submits to Algorand
    (where both amount and vendor policies are checked), and returns
    the complete audit result including per-policy breakdown.
    """
    logger.info("Received audit request: amount=%d vendor_id=%s", req.amount, req.vendor_id)
    try:
        result = await run_audit_flow(req.amount, req.vendor_id, req.agent_type_id)
        logger.info(
            "Audit complete: action_id=%s decision=%s policy=%s",
            result["action_id"], result["decision"], result["policy_result"],
        )
        # Store in history for dashboard and CSV export
        recent_audits.appendleft({
            "action_id": result["action_id"],
            "decision": result["decision"],
            "agent_decision": result["agent_decision"],
            "amount": req.amount,
            "vendor_id": req.vendor_id,
            "agent_type_id": result["agent_type_id"],
            "policy_checks": result["policy_checks"],
            "policy_result": result["policy_result"],
            "asa_minted": result["asa_minted"],
            "ipfs_cid": result["ipfs_cid"],
            "algorand_tx_id": result["algorand_tx_id"],
            "timestamp": int(time.time()),
        })
        return AuditResponse(**result)
    except Exception as e:
        logger.error("Audit pipeline failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Autonomous agent chat endpoint.

    The agent receives a natural language task, autonomously selects a vendor
    and price from the vendor registry, then runs the full IPFS + Algorand
    audit pipeline. On-chain policy checks run independently of the agent's
    selection — if the vendor is not whitelisted or amount exceeds the limit,
    the transaction is recorded but no compliance receipt is minted.

    Returns the agent's natural language reply plus the full audit result.
    """
    logger.info("Chat request: %s", req.message)
    try:
        result = await run_chat_flow(req.message, req.agent_type_id)

        # Off-topic: agent replied without running the pipeline
        if result.get("off_topic"):
            logger.info("Chat off-topic — skipping audit storage.")
            return ChatResponse(reply=result["agent_reply"], audit_result=None)

        logger.info(
            "Chat complete: action_id=%s vendor=%s amount=%s decision=%s",
            result["action_id"], result["vendor_id"], result.get("amount"), result["decision"],
        )
        recent_audits.appendleft({
            "action_id": result["action_id"],
            "decision": result["decision"],
            "agent_decision": result["agent_decision"],
            "amount": result.get("amount", 0),
            "vendor_id": result["vendor_id"],
            "agent_type_id": result["agent_type_id"],
            "policy_checks": result["policy_checks"],
            "policy_result": result["policy_result"],
            "asa_minted": result["asa_minted"],
            "ipfs_cid": result["ipfs_cid"],
            "algorand_tx_id": result["algorand_tx_id"],
            "timestamp": int(time.time()),
        })
        reply = result.pop("agent_reply", "Done.")
        return ChatResponse(reply=reply, audit_result=result)
    except Exception as e:
        logger.error("Chat pipeline failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/verify", response_model=VerifyResponse)
async def verify(action_id: str = Query(..., description="Action ID to verify")) -> VerifyResponse:
    """
    Independently verify an audit record by action ID.

    Fetches the audit record from Algorand, fetches the original decision
    JSON from IPFS, recomputes the SHA256 hash, and compares it to what
    is stored on-chain. Returns hash_match=True if the record is intact.
    """
    logger.info("Verify request for action_id: %s", action_id)

    # Step 1: Fetch on-chain record
    try:
        record = await get_audit_record(action_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Audit record not found: {e}")

    if not record:
        raise HTTPException(status_code=404, detail="Audit record not found")

    ipfs_hash_onchain = record.get("ipfs_hash", "")

    # Step 2: Fetch IPFS data and recompute hash
    ipfs_data: dict = {}
    ipfs_hash_computed = ""

    try:
        cid, ipfs_data = await _fetch_ipfs_data(action_id)
        ipfs_hash_computed = sha256(cid.encode()).hexdigest()
    except Exception as e:
        logger.warning("IPFS fetch failed for action_id %s: %s", action_id, e)
        return VerifyResponse(
            action_id=action_id,
            ipfs_hash_onchain=ipfs_hash_onchain,
            ipfs_hash_computed="",
            hash_match=False,
            record=record,
            ipfs_data={},
        )

    hash_match = (ipfs_hash_onchain == ipfs_hash_computed)
    logger.info("Verify result for %s: hash_match=%s", action_id, hash_match)

    return VerifyResponse(
        action_id=action_id,
        ipfs_hash_onchain=ipfs_hash_onchain,
        ipfs_hash_computed=ipfs_hash_computed,
        hash_match=hash_match,
        record=record,
        ipfs_data=ipfs_data,
    )


@app.get("/api/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    """
    Return aggregate stats and recent audit history from the in-memory store.

    Stats are computed from audits run since the server started.
    """
    audits = list(recent_audits)
    total = len(audits)
    approved = sum(1 for a in audits if a["decision"] == "approved")
    rejected = total - approved
    compliance_rate = round((approved / total * 100), 1) if total > 0 else 0.0

    return DashboardResponse(
        total_audits=total,
        approved_count=approved,
        rejected_count=rejected,
        compliance_rate=compliance_rate,
        recent_audits=audits,
    )


@app.get("/api/export/csv")
async def export_csv():
    """
    Download audit history as a CSV file.

    Exports all audits stored in the current session's in-memory store.
    """
    output = io.StringIO()
    fieldnames = [
        "action_id", "timestamp", "amount", "vendor_id",
        "decision", "amount_check", "vendor_check",
        "policy_result", "asa_minted", "ipfs_cid", "algorand_tx_id",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for audit in recent_audits:
        writer.writerow({
            "action_id": audit["action_id"],
            "timestamp": audit["timestamp"],
            "amount": audit["amount"],
            "vendor_id": audit["vendor_id"],
            "decision": audit["decision"],
            "amount_check": audit["policy_checks"].get("amount_check", ""),
            "vendor_check": audit["policy_checks"].get("vendor_check", ""),
            "policy_result": audit["policy_result"],
            "asa_minted": audit["asa_minted"],
            "ipfs_cid": audit["ipfs_cid"],
            "algorand_tx_id": audit["algorand_tx_id"],
        })

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )


@app.get("/api/tamper-demo", response_model=TamperDemoResponse)
async def tamper_demo(action_id: str = Query(..., description="Action ID to simulate tampering on")) -> TamperDemoResponse:
    """
    Simulate tampering with an audit record to demonstrate hash detection.

    Fetches the real IPFS data, creates a tampered copy (changes amount to 1),
    and shows that the tampered content would produce a different hash that
    does NOT match what is stored on-chain — proving the audit trail is tamper-proof.
    """
    logger.info("Tamper demo request for action_id: %s", action_id)

    # Step 1: Get on-chain hash (immutable, stored in Algorand)
    try:
        record = await get_audit_record(action_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Audit record not found: {e}")

    onchain_hash = record.get("ipfs_hash", "")

    # Step 2: Fetch real IPFS data
    try:
        real_cid, real_ipfs_data = await _fetch_ipfs_data(action_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch IPFS data: {e}")

    # Step 3: Recompute hash from real data — should match on-chain
    hash_original = sha256(real_cid.encode()).hexdigest()

    # Step 4: Build tampered copy — change amount field to 1
    original_amount = str(real_ipfs_data.get("amount", "unknown"))
    tampered_data = dict(real_ipfs_data)
    tampered_data["amount"] = 1

    # Step 5: Simulate what IPFS would assign as a CID for the tampered content.
    # IPFS CIDs are content-addressed — different content = different CID.
    # We generate a deterministic fake CID to represent the tampered upload.
    tampered_json = json.dumps(tampered_data, sort_keys=True)
    simulated_tampered_cid = "Qm" + sha256(tampered_json.encode()).hexdigest()[:44]
    hash_tampered = sha256(simulated_tampered_cid.encode()).hexdigest()

    logger.info(
        "Tamper demo for %s: match_original=%s match_tampered=%s",
        action_id,
        hash_original == onchain_hash,
        hash_tampered == onchain_hash,
    )

    return TamperDemoResponse(
        action_id=action_id,
        field_tampered="amount",
        original_value=original_amount,
        tampered_value="1",
        hash_onchain=onchain_hash,
        hash_original=hash_original,
        hash_tampered=hash_tampered,
        match_original=(hash_original == onchain_hash),
        match_tampered=(hash_tampered == onchain_hash),
    )


@app.post("/api/batch/submit")
async def submit_batch() -> dict:
    """
    Flush all pending leaves, compute the Merkle root, and anchor it on AnchorContract.

    This is the demo centerpiece — one TX anchors all pending audit records.
    Returns the batch_id, merkle_root, leaf_count, and anchor TX ID.
    """
    pending = batch_store.size()
    if pending == 0:
        raise HTTPException(status_code=400, detail="No pending leaves to anchor")

    logger.info("Batch submit triggered: %d pending leaves", pending)
    try:
        batch = await flush_and_anchor(batch_store)
    except Exception as e:
        logger.error("Batch anchor failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

    logger.info("Batch anchored: batch_id=%s tx=%s", batch.batch_id, batch.anchor_tx_id)
    return {
        "batch_id": batch.batch_id,
        "merkle_root": batch.merkle_root,
        "leaf_count": len(batch.leaves),
        "anchor_tx_id": batch.anchor_tx_id,
        "explorer_url": f"https://testnet.explorer.perawallet.app/tx/{batch.anchor_tx_id}",
    }


@app.get("/api/batch/status")
async def batch_status() -> dict:
    """
    Return the current batcher state: pending leaf count and recent batches.
    """
    return {
        "pending_count": batch_store.size(),
        "is_full": batch_store.is_full(),
        "recent_batches": batch_store.recent_batches(limit=5),
    }


@app.get("/api/batch/{batch_id}")
async def get_batch(batch_id: str) -> dict:
    """
    Return metadata for a specific batch by batch_id.
    """
    batch = batch_store.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")
    return batch


@app.get("/api/verify/v2")
async def verify_v2(action_id: str = Query(..., description="Action ID to verify")) -> dict:
    """
    Verify a Phase 2 audit record using Merkle proof.

    Looks up the leaf in SQLite, fetches the on-chain Merkle root from
    AnchorContract, verifies the proof, and decrypts the IPFS payload.

    Returns verification status, proof validity, and decrypted record.
    """
    logger.info("Verify v2 request for action_id: %s", action_id)

    leaf_data = batch_store.get_leaf(action_id)
    if not leaf_data:
        raise HTTPException(status_code=404, detail=f"No leaf found for action_id: {action_id}")

    batch_id = leaf_data.get("batch_id")
    proof = leaf_data.get("proof")

    # Not yet anchored
    if not batch_id or proof is None:
        return {
            "action_id": action_id,
            "anchor_status": "pending",
            "merkle_proof_valid": None,
            "record": leaf_data["record"],
            "leaf_hash": leaf_data["leaf_hash"],
        }

    # Fetch on-chain root and verify proof
    try:
        onchain_root = await get_anchor_root(batch_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch on-chain root: {e}")

    proof_valid = verify_proof(leaf_data["leaf_hash"], proof, onchain_root)

    # Decrypt IPFS payload
    record = leaf_data["record"]
    ipfs_cid = record.get("ipfs_cid", "")
    decrypted_record: dict | None = None

    if ipfs_cid:
        try:
            from crypto.payload import decrypt_payload
            _, envelope = await _fetch_ipfs_data(action_id)
            decrypted_record = decrypt_payload(envelope)
        except Exception as e:
            logger.warning("IPFS decrypt failed for %s: %s", action_id, e)

    return {
        "action_id": action_id,
        "anchor_status": "anchored",
        "batch_id": batch_id,
        "merkle_proof_valid": proof_valid,
        "onchain_root": onchain_root,
        "leaf_hash": leaf_data["leaf_hash"],
        "proof_steps": len(proof),
        "record": record,
        "decrypted_record": decrypted_record,
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_ipfs_data(action_id: str) -> tuple[str, dict]:
    """
    Fetch the IPFS CID and JSON content for a given action_id.

    Uses the Pinata list API to look up the CID by metadata name (action_id
    is stored as pinataMetadata.name during upload), then fetches the content.

    Args:
        action_id: The action ID to look up in Pinata.

    Returns:
        Tuple of (cid string, ipfs_data dict).

    Raises:
        RuntimeError: If CID cannot be found or content fetch fails.
    """
    pinata_jwt = os.getenv("PINATA_JWT", "")
    if not pinata_jwt:
        raise RuntimeError("PINATA_JWT not set in .env")

    headers = {"Authorization": f"Bearer {pinata_jwt}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        list_resp = await client.get(
            "https://api.pinata.cloud/data/pinList",
            params={"metadata[name]": action_id, "status": "pinned"},
            headers=headers,
        )
        list_resp.raise_for_status()
        rows = list_resp.json().get("rows", [])

        if not rows:
            raise RuntimeError(f"No IPFS pin found for action_id: {action_id}")

        cid = rows[0]["ipfs_pin_hash"]

        content_resp = await client.get(
            f"https://gateway.pinata.cloud/ipfs/{cid}",
            timeout=15.0,
        )
        content_resp.raise_for_status()
        ipfs_data = content_resp.json()

    return cid, ipfs_data
