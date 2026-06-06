"""
AgentAudit FastAPI backend.

Endpoints:
  POST /api/audit          — run the full Phase 2 audit pipeline for a payment
  POST /api/chat           — autonomous agent: pick vendor from natural language prompt
  GET  /api/verify         — verify audit record: Merkle proof + IPFS decryption
  GET  /api/dashboard      — aggregate stats + recent audit history + batcher state
  GET  /api/export/csv     — download audit history as CSV

Run with: uvicorn api.main:app --reload --port 8000
"""

import csv
import hashlib
import io
import logging
import os
import time
from collections import deque

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from algorand.contract_client_v2 import MODE_ONCHAIN, OP_IN, OP_NOT_IN, get_anchor_root
from batcher.anchor import flush_and_anchor
from batcher.merkle import verify_proof
from batcher.store import BatchStore
from crypto.payload import decrypt_payload, parse_hex_key
from sdk.audit_flow_v2 import run_audit_flow_v2, run_chat_flow_v2, run_ingest_v2
from tenancy.store import TenantStore
from tenancy.provisioning import (
    create_org,
    register_agent,
    register_policy,
    register_sensitive_policy,
    register_sensitive_set_policy,
    reverify_mode2,
)
from api.x402_gate import install_x402

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

# x402 payment gate (Flavor 1, behind X402_ENABLED). Protects POST /v1/audit/x402.
X402_ON = install_x402(app)

# In-memory audit history — holds up to 50 most recent audits, oldest auto-dropped
recent_audits: deque = deque(maxlen=50)

# Shared SQLite-backed batcher — persists across requests
batch_store = BatchStore()

# Shared tenant store (orgs, agents, per-agent rule metadata, per-org keys)
tenant_store = TenantStore()


def require_org(authorization: str | None = Header(None)) -> dict:
    """
    Resolve the calling org from a Bearer API key (auth dependency for /v1/*).

    Raises 401 if the header is missing or the key is unknown.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing 'Authorization: Bearer <api_key>' header")
    api_key = authorization.split(" ", 1)[1].strip()
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    org = tenant_store.get_org_by_api_key_hash(api_key_hash)
    if not org:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return org


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
    encrypted: bool = True
    batch_pending_count: int = 0


class DashboardResponse(BaseModel):
    """Response body from GET /api/dashboard."""

    total_audits: int
    approved_count: int
    rejected_count: int
    compliance_rate: float        # percentage 0–100
    recent_audits: list[dict]
    pending_leaves_count: int = 0
    last_anchor_batch_id: str | None = None


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
    Run the Phase 2 audit pipeline for a payment amount and vendor.

    Encrypts the decision record with AES-GCM, uploads to IPFS, calls
    PolicyContract (on-chain policy checks + AACR mint if both pass),
    adds the record as a pending leaf in the SQLite batcher, and returns
    the complete audit result. Records accumulate until POST /api/batch/submit
    is called to flush and anchor the Merkle root on AnchorContract.
    """
    logger.info("Received audit request: amount=%d vendor_id=%s", req.amount, req.vendor_id)
    try:
        result = await run_audit_flow_v2(req.amount, req.vendor_id, batch_store, tenant_store)
        logger.info(
            "Audit complete: action_id=%s decision=%s policy=%s pending=%d",
            result["action_id"], result["decision"],
            result["policy_result"], result["batch_pending_count"],
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
        result = await run_chat_flow_v2(req.message, batch_store, tenant_store)

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


class IngestRequest(BaseModel):
    """Request body for POST /v1/audit (external agent submits a finished decision)."""

    agent_id: str = Field(..., min_length=1, description="Agent id within the org (matches provisioned rules)")
    action: str = Field(..., min_length=1, description="Decision type, e.g. approve_loan")
    decision: str = Field(..., min_length=1, description="The agent's own decision label")
    fields: dict = Field(default_factory=dict, description="Decision field values keyed by name")
    reasoning_trace: list = Field(default_factory=list, description="Agent tool-call trace")


@app.post("/v1/audit")
async def ingest_audit(req: IngestRequest, org: dict = Depends(require_org)) -> dict:
    """
    Product ingest endpoint: audit a decision an external agent already made.

    Auth: `Authorization: Bearer <api_key>` resolves the org. The decision is audited
    under org_id/req.agent_id against that agent's on-chain policy set (encrypted under
    the org's key, policy-checked, queued for batch anchoring).
    """
    org_id = org["org_id"]
    logger.info("Ingest: org=%s agent=%s action=%s", org_id, req.agent_id, req.action)
    try:
        result = await run_ingest_v2(
            org_id, req.agent_id, req.action, req.decision,
            req.fields, req.reasoning_trace, batch_store, tenant_store,
        )
        recent_audits.appendleft({
            "action_id": result["action_id"],
            "decision": result["decision"],
            "agent_decision": result["agent_decision"],
            "amount": req.fields.get("amount", 0),
            "vendor_id": req.fields.get("vendor", ""),
            "agent_type_id": req.agent_id,
            "policy_checks": result["policy_checks"],
            "policy_result": result["policy_result"],
            "asa_minted": result["asa_minted"],
            "ipfs_cid": result["ipfs_cid"],
            "algorand_tx_id": result["algorand_tx_id"],
            "timestamp": int(time.time()),
        })
        return result
    except Exception as e:
        logger.error("Ingest failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


class X402IngestRequest(BaseModel):
    """Request body for POST /v1/audit/x402 (x402 payment authorizes; org declared in body)."""

    org_id: str = Field(..., min_length=1, description="Org the paying agent belongs to")
    agent_id: str = Field(..., min_length=1, description="Agent id within the org")
    action: str = Field(..., min_length=1)
    decision: str = Field(..., min_length=1)
    fields: dict = Field(default_factory=dict)
    reasoning_trace: list = Field(default_factory=list)


@app.post("/v1/audit/x402")
async def ingest_audit_x402(req: X402IngestRequest) -> dict:
    """
    Pay-per-call ingest. The x402 middleware verifies a $0.01 USDC payment before this
    handler runs and settles after it returns; the org is declared in the body (Flavor 1:
    provisioned tenant, payment authorizes the call instead of an API key).
    """
    org = tenant_store.get_org(req.org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Unknown org '{req.org_id}'")
    logger.info("x402 ingest: org=%s agent=%s action=%s", req.org_id, req.agent_id, req.action)
    try:
        result = await run_ingest_v2(
            req.org_id, req.agent_id, req.action, req.decision,
            req.fields, req.reasoning_trace, batch_store, tenant_store,
        )
        recent_audits.appendleft({
            "action_id": result["action_id"], "decision": result["decision"],
            "agent_decision": result["agent_decision"], "amount": req.fields.get("amount", 0),
            "vendor_id": req.fields.get("vendor", ""), "agent_type_id": req.agent_id,
            "policy_checks": result["policy_checks"], "policy_result": result["policy_result"],
            "asa_minted": result["asa_minted"], "ipfs_cid": result["ipfs_cid"],
            "algorand_tx_id": result["algorand_tx_id"], "timestamp": int(time.time()),
        })
        result["billing"] = "x402"
        return result
    except Exception as e:
        logger.error("x402 ingest failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


class PolicySpec(BaseModel):
    """One policy in an onboarding request."""

    field: str = Field(..., min_length=1)
    operator: int = Field(..., ge=1, le=8, description="1<,2<=,3>,4>=,5==,6!=,7 in,8 not_in")
    value_num: int = 0
    set_values: list[str] = Field(default_factory=list)
    private: bool = False  # True = Mode 2 (encrypted off-chain, commitment-only)


class OnboardRequest(BaseModel):
    """Request body for POST /v1/onboard (self-serve provisioning)."""

    org_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    billing_mode: str = Field(default="api_key", description="api_key (subscription) or x402 (pay-per-call)")
    policies: list[PolicySpec] = Field(default_factory=list)


@app.post("/v1/onboard")
async def onboard(req: OnboardRequest) -> dict:
    """
    Self-serve onboarding: create the org (plan), register an agent, register its policy set
    on-chain (public Mode-1 + private Mode-2), and return the API key + encryption key (once)
    plus the registered rules. Demo endpoint — in production this is gated to the platform.
    """
    if tenant_store.get_org(req.org_id):
        raise HTTPException(status_code=409, detail=f"Org '{req.org_id}' already exists")
    logger.info("Onboard: org=%s agent=%s plan=%s policies=%d", req.org_id, req.agent_id, req.billing_mode, len(req.policies))
    try:
        creds = create_org(tenant_store, req.org_id, billing_mode=req.billing_mode)
        register_agent(tenant_store, req.org_id, req.agent_id)
        for p in req.policies:
            is_set = p.operator in (OP_IN, OP_NOT_IN)
            if p.private and is_set:
                await register_sensitive_set_policy(
                    tenant_store, req.org_id, req.agent_id, field=p.field, operator=p.operator, members=p.set_values
                )
            elif p.private:
                await register_sensitive_policy(
                    tenant_store, req.org_id, req.agent_id, field=p.field, operator=p.operator, value_num=p.value_num
                )
            else:
                await register_policy(
                    tenant_store, req.org_id, req.agent_id, field=p.field, mode=MODE_ONCHAIN,
                    operator=p.operator, value_num=p.value_num, set_values=(p.set_values or None),
                )
    except Exception as e:
        logger.error("Onboard failed: %s", e)
        # Roll back the half-provisioned org so the name is free to retry.
        tenant_store.delete_org(req.org_id)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "org_id": req.org_id,
        "agent_id": req.agent_id,
        "billing_mode": req.billing_mode,
        "api_key": creds["api_key"],
        "encryption_key": creds["encryption_key"],
        "fields": [p.field for p in req.policies],
        "rules": tenant_store.get_rules(req.org_id, req.agent_id),
    }


@app.get("/api/verify")
async def verify(
    action_id: str = Query(..., description="Action ID to verify"),
    x_auditor_key: str | None = Header(
        None,
        alias="X-Auditor-Key",
        description="Hex-encoded AES-256 auditor key. Omit to skip decryption.",
    ),
) -> dict:
    """
    Verify a Phase 2 audit record by action ID.

    Looks up the leaf in SQLite, verifies the Merkle inclusion proof against
    the on-chain root stored in AnchorContract, fetches the encrypted IPFS
    envelope, and — when an auditor key is supplied via the X-Auditor-Key
    header — attempts to decrypt it.

    Decryption states returned to the client:
      key_provided=False              → ciphertext envelope only (public view)
      key_provided=True, key_valid=False → bad key, envelope still returned
      key_provided=True, key_valid=True  → plaintext record returned

    Merkle proof verification is always public — the auditor key is only
    needed to read the contents.
    """
    logger.info(
        "Verify request for action_id: %s (key_provided=%s)",
        action_id, bool(x_auditor_key),
    )

    leaf_data = batch_store.get_leaf(action_id)
    if not leaf_data:
        raise HTTPException(status_code=404, detail=f"No audit record found for action_id: {action_id}")

    batch_id = leaf_data.get("batch_id")
    proof = leaf_data.get("proof")
    record = leaf_data["record"]

    # Not yet anchored — batch still pending
    if not batch_id or proof is None:
        return {
            "action_id": action_id,
            "anchor_status": "pending",
            "verification": {
                "merkle_proof_valid": None,
                "batch_id": None,
                "merkle_root_onchain": None,
            },
            "decryption": _empty_decryption_section(),
            "record_summary": _build_record_summary(record),
        }

    # Fetch on-chain root from AnchorContract
    try:
        onchain_root = await get_anchor_root(batch_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch on-chain root: {e}")

    proof_valid = verify_proof(leaf_data["leaf_hash"], proof, onchain_root)
    logger.info("Verify result for %s: proof_valid=%s", action_id, proof_valid)

    # Fetch encrypted envelope from IPFS regardless of key — the ciphertext
    # is public and the frontend needs it to show "encrypted blob" state.
    ipfs_cid = record.get("ipfs_cid", "")
    decryption_section = await _attempt_decryption(ipfs_cid, x_auditor_key, action_id)

    # Mode-2 auditor re-check: with the org key, decrypt each private policy doc, confirm it
    # hashes to the on-chain commitment, and re-run the check against the decision's fields.
    mode2_reverify = _reverify_mode2(record, x_auditor_key)

    return {
        "action_id": action_id,
        "anchor_status": "anchored",
        "verification": {
            "merkle_proof_valid": proof_valid,
            "batch_id": batch_id,
            "leaf_hash": leaf_data["leaf_hash"],
            "proof_steps": len(proof),
            "merkle_root_onchain": onchain_root,
        },
        "decryption": decryption_section,
        "mode2_reverify": mode2_reverify,
        "record_summary": _build_record_summary(record),
    }


def _empty_decryption_section() -> dict:
    """Decryption section for pending leaves — no envelope fetched yet."""
    return {
        "encrypted": True,
        "key_provided": False,
        "key_valid": None,
        "decrypted": False,
        "record": None,
        "envelope": None,
        "error": None,
    }


async def _attempt_decryption(ipfs_cid: str, x_auditor_key: str | None, action_id: str) -> dict:
    """
    Fetch the encrypted envelope from IPFS and, if a key was supplied, try to
    decrypt it. Returns a fully-populated decryption section dict.

    Never raises — all failures are surfaced via the `error` field so the
    frontend can render the corresponding state.
    """
    section = _empty_decryption_section()

    if not ipfs_cid:
        section["error"] = "No IPFS CID on record"
        return section

    try:
        envelope = await _fetch_ipfs_by_cid(ipfs_cid)
    except Exception as e:
        logger.warning("IPFS fetch failed for %s: %s", action_id, e)
        section["error"] = f"IPFS fetch failed: {e}"
        return section

    section["envelope"] = envelope

    if not x_auditor_key:
        return section  # ciphertext-only response

    section["key_provided"] = True
    try:
        key_bytes = parse_hex_key(x_auditor_key)
    except ValueError as e:
        section["key_valid"] = False
        section["error"] = str(e)
        return section

    try:
        section["record"] = decrypt_payload(envelope, key=key_bytes)
        section["decrypted"] = True
        section["key_valid"] = True
    except Exception as e:
        logger.info("Decryption with supplied key failed for %s: %s", action_id, e)
        section["key_valid"] = False
        section["error"] = "Decryption failed — wrong key or tampered payload"

    return section


@app.get("/api/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    """
    Return aggregate stats, recent audit history, and current batcher state.

    Stats are computed from audits run since the server started.
    Batcher state (pending_leaves_count, last_anchor_batch_id) reflects
    the live SQLite store and survives server restarts.
    """
    audits = list(recent_audits)
    total = len(audits)
    approved = sum(1 for a in audits if a["decision"] == "approved")
    rejected = total - approved
    compliance_rate = round((approved / total * 100), 1) if total > 0 else 0.0

    recent = batch_store.recent_batches(limit=1)
    last_anchor_batch_id = recent[0]["batch_id"] if recent else None

    return DashboardResponse(
        total_audits=total,
        approved_count=approved,
        rejected_count=rejected,
        compliance_rate=compliance_rate,
        recent_audits=audits,
        pending_leaves_count=batch_store.size(),
        last_anchor_batch_id=last_anchor_batch_id,
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


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reverify_mode2(record: dict, x_auditor_key: str | None) -> list | None:
    """
    Auditor re-check of Mode-2 (private) policies for a record, if a valid key is supplied.

    Returns a per-rule list of {idx, field, commitment_matches, recheck_pass}, or None when
    no/invalid key was given or the org+agent has no Mode-2 rules.
    """
    if not x_auditor_key:
        return None
    org_id, agent_id = record.get("org_id"), record.get("agent_id")
    if not org_id or not agent_id:
        return None
    try:
        key_bytes = parse_hex_key(x_auditor_key)
    except ValueError:
        return None
    try:
        results = reverify_mode2(tenant_store, org_id, agent_id, record.get("fields", {}), key_bytes)
    except Exception as e:
        logger.warning("Mode-2 reverify failed: %s", e)
        return None
    return results or None


def _build_record_summary(record: dict) -> dict:
    """Extract the fields shown in verify responses without the full record blob."""
    return {
        "decision": record.get("decision"),
        "amount": record.get("amount"),
        "vendor_id": record.get("vendor_id"),
        "policy_result": record.get("policy_result"),
        "asa_minted": record.get("asa_minted"),
        "policy_tx_id": record.get("policy_tx_id"),
        "ipfs_cid": record.get("ipfs_cid"),
        "timestamp": record.get("timestamp"),
    }


async def _fetch_ipfs_by_cid(cid: str) -> dict:
    """
    Fetch and return JSON content from the IPFS gateway by CID.

    Args:
        cid: IPFS content identifier.

    Returns:
        Parsed JSON dict from the gateway.

    Raises:
        RuntimeError: If the gateway request fails.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"https://gateway.pinata.cloud/ipfs/{cid}")
        resp.raise_for_status()
        return resp.json()
