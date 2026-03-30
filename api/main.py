"""
AgentAudit FastAPI backend.

Single endpoint: POST /api/audit
Receives a payment amount, runs the full audit pipeline,
and returns the result for the frontend to display.

Run with: uvicorn api.main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sdk.audit_flow import run_audit_flow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AgentAudit API",
    description="Verifiable audit infrastructure for autonomous AI agents.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    """Request body for POST /api/audit."""

    amount: int = Field(..., gt=0, description="Payment amount to evaluate")


class AuditResponse(BaseModel):
    """Response body from POST /api/audit."""

    decision: str
    ipfs_cid: str
    algorand_tx_id: str
    policy_result: str
    asa_minted: bool
    action_id: str


@app.post("/api/audit", response_model=AuditResponse)
async def audit(req: AuditRequest) -> AuditResponse:
    """
    Run the full audit pipeline for a payment amount.

    Calls the payment agent, uploads to IPFS, submits to Algorand,
    and returns the complete audit result.
    """
    logger.info("Received audit request: amount=%d", req.amount)
    try:
        result = await run_audit_flow(req.amount)
        logger.info("Audit complete: action_id=%s decision=%s", result["action_id"], result["decision"])
        return AuditResponse(**result)
    except Exception as e:
        logger.error("Audit pipeline failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
