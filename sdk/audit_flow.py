"""
AgentAudit core pipeline.

run_audit_flow() is the single entry point for the full audit flow:
  1. Agent decides approve/reject
  2. Decision JSON uploaded to IPFS
  3. Audit record submitted to Algorand smart contract
  4. Returns full result dict for API and frontend
"""

import logging
import os
import random
import time
from hashlib import sha256

from dotenv import load_dotenv

from agent.payment_agent import decide_payment
from algorand.contract_client import submit_audit
from ipfs.uploader import upload_to_ipfs

load_dotenv()

logger = logging.getLogger(__name__)

AGENT_ID = os.getenv("AGENT_ID", "agent_001")
POLICY_ID = "limit_5000"


async def run_audit_flow(amount: int) -> dict:
    """
    Run the full audit pipeline for a payment approval request.

    Steps:
      1. Agent decides approve/reject based on policy
      2. Decision record uploaded to IPFS via Pinata
      3. SHA256 of CID computed as ipfs_hash
      4. Audit record submitted to Algorand smart contract
      5. Returns complete result dict

    Args:
        amount: Payment amount to evaluate.

    Returns:
        Dict with keys: decision, ipfs_cid, algorand_tx_id,
        policy_result, asa_minted, action_id.

    Raises:
        RuntimeError: If any step in the pipeline fails.
    """
    # Step 1: Agent decision
    logger.info("Running payment agent for amount: %d", amount)
    decision, reason = decide_payment(amount)
    logger.info("Agent decision: %s", decision)

    # Step 2: Build decision record
    timestamp = int(time.time())
    action_id = f"{timestamp}_{random.randint(1000, 9999)}"

    record = {
        "action": "approve_payment",
        "amount": amount,
        "decision": decision,
        "reason": reason,
        "policy": POLICY_ID,
        "agent_id": AGENT_ID,
        "timestamp": timestamp,
    }

    # Step 3: Upload to IPFS
    logger.info("Uploading decision record to IPFS...")
    try:
        ipfs_cid = await upload_to_ipfs(record)
    except Exception as e:
        raise RuntimeError(f"IPFS upload failed for action {action_id}: {e}")
    logger.info("IPFS CID: %s", ipfs_cid)

    # Step 4: Hash the CID for on-chain storage
    ipfs_hash = sha256(ipfs_cid.encode()).hexdigest()

    # Step 5: Submit to Algorand smart contract
    logger.info("Submitting audit record to Algorand (action_id: %s)...", action_id)
    try:
        tx_result = await submit_audit(action_id, ipfs_hash, record)
    except Exception as e:
        raise RuntimeError(f"Algorand submission failed for action {action_id}: {e}")
    logger.info("Algorand TX confirmed: %s", tx_result.tx_id)

    return {
        "decision": decision,
        "ipfs_cid": ipfs_cid,
        "algorand_tx_id": tx_result.tx_id,
        "policy_result": tx_result.policy_result,
        "asa_minted": tx_result.asa_minted,
        "action_id": action_id,
    }
