"""
AgentAudit FastAPI backend.

Endpoints:
  POST /api/audit          — run the full audit pipeline for a payment
  GET  /api/verify         — independently verify any audit record by action ID

Run with: uvicorn api.main:app --reload --port 8000
"""

import logging
from hashlib import sha256

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from algorand.contract_client import get_audit_record
from sdk.audit_flow import run_audit_flow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IPFS_FETCH_URL = "https://gateway.pinata.cloud/ipfs/{cid}"

app = FastAPI(
    title="AgentAudit API",
    description="Verifiable audit infrastructure for autonomous AI agents.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AuditRequest(BaseModel):
    """Request body for POST /api/audit."""

    amount: int = Field(..., gt=0, description="Payment amount to evaluate")
    vendor_id: str = Field(..., min_length=1, description="Vendor identifier to check against whitelist")


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


class VerifyResponse(BaseModel):
    """Response body from GET /api/verify."""

    action_id: str
    ipfs_hash_onchain: str   # SHA256 hex stored in the contract
    ipfs_hash_computed: str  # SHA256 hex recomputed from fetched IPFS data
    hash_match: bool         # True = verified, False = tampered or mismatch
    record: dict             # Parsed on-chain audit record fields
    ipfs_data: dict          # Full JSON fetched from IPFS


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
        result = await run_audit_flow(req.amount, req.vendor_id)
        logger.info(
            "Audit complete: action_id=%s decision=%s policy=%s",
            result["action_id"], result["decision"], result["policy_result"],
        )
        return AuditResponse(**result)
    except Exception as e:
        logger.error("Audit pipeline failed: %s", str(e))
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

    # Step 2: Derive the IPFS CID from the on-chain hash
    # The on-chain hash is sha256(cid) — we can't reverse it, so we need
    # to search by the hash. Instead, we store the CID in the IPFS data itself.
    # For the verifier, we fetch by reconstructing: the IPFS data must contain
    # action_id so we can cross-reference. We use the Pinata query API.
    # Simpler approach for MVP: frontend passes cid alongside action_id if available,
    # but for pure on-chain verification we use the Pinata list endpoint to find by name.
    # For demo: we store the action_id as the pinataMetadata name during upload.
    ipfs_data: dict = {}
    ipfs_hash_computed = ""

    try:
        ipfs_data, ipfs_hash_computed = await _fetch_and_hash_ipfs(action_id)
    except Exception as e:
        logger.warning("IPFS fetch failed for action_id %s: %s", action_id, e)
        # Return partial result — on-chain data is still useful
        return VerifyResponse(
            action_id=action_id,
            ipfs_hash_onchain=ipfs_hash_onchain,
            ipfs_hash_computed="",
            hash_match=False,
            record=record,
            ipfs_data={},
        )

    hash_match = (ipfs_hash_onchain == ipfs_hash_computed)

    logger.info(
        "Verify result for %s: hash_match=%s", action_id, hash_match
    )

    return VerifyResponse(
        action_id=action_id,
        ipfs_hash_onchain=ipfs_hash_onchain,
        ipfs_hash_computed=ipfs_hash_computed,
        hash_match=hash_match,
        record=record,
        ipfs_data=ipfs_data,
    )


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_and_hash_ipfs(action_id: str) -> tuple[dict, str]:
    """
    Fetch the IPFS JSON for a given action_id using the Pinata list API,
    then compute its SHA256 hash (of the CID) for comparison.

    Pinata stores the action_id as pinataMetadata.name during upload.
    We query /data/pinList?metadata[name]=<action_id> to find the CID,
    then fetch the content and compute sha256(cid).

    Args:
        action_id: The action ID to look up in Pinata.

    Returns:
        Tuple of (ipfs_data dict, sha256_hex_of_cid string).

    Raises:
        RuntimeError: If the CID cannot be found or content fetch fails.
    """
    import os
    pinata_jwt = os.getenv("PINATA_JWT", "")
    if not pinata_jwt:
        raise RuntimeError("PINATA_JWT not set in .env")

    headers = {"Authorization": f"Bearer {pinata_jwt}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Look up CID by action_id stored as metadata name
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

        # Fetch the actual content
        content_resp = await client.get(
            f"https://gateway.pinata.cloud/ipfs/{cid}",
            timeout=15.0,
        )
        content_resp.raise_for_status()
        ipfs_data = content_resp.json()

    # Recompute sha256(cid) — matches what audit_flow.py stores on-chain
    ipfs_hash_computed = sha256(cid.encode()).hexdigest()

    return ipfs_data, ipfs_hash_computed
