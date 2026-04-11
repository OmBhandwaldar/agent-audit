"""
AgentAudit core pipeline.

run_audit_flow() is the single entry point for the full audit flow:
  1. Agent decides approve/reject (based on amount)
  2. Decision JSON uploaded to IPFS
  3. Audit record submitted to Algorand smart contract
     — contract checks amount limit AND vendor whitelist
  4. Returns full result dict for API and frontend
"""

import logging
import os
import random
import time
from hashlib import sha256

from dotenv import load_dotenv

from agent.payment_agent import decide_payment, run_payment_agent
from algorand.contract_client import submit_audit
from ipfs.uploader import upload_to_ipfs

load_dotenv()

logger = logging.getLogger(__name__)

AGENT_ID = os.getenv("AGENT_ID", "agent_001")
POLICY_ID = "limit_5000"


def _parse_policy_result(policy_result: str) -> dict:
    """
    Parse "amount:pass|vendor:pass" into per-check dict.

    Returns:
        Dict with keys: amount_check, vendor_check. Values: "pass" or "fail".
    """
    checks: dict = {}
    for part in policy_result.split("|"):
        if ":" in part:
            key, value = part.split(":", 1)
            checks[f"{key}_check"] = value
    return checks


AGENT_TYPE_CONFIG = {
    "payment_approval":  {"action": "approve_payment",    "agent_id_suffix": "payment_agent"},
    "vendor_onboarding": {"action": "vendor_onboarding",  "agent_id_suffix": "vendor_agent"},
    "expense_claim":     {"action": "expense_claim",       "agent_id_suffix": "expense_agent"},
}

async def run_audit_flow(amount: int, vendor_id: str, agent_type_id: str = "payment_approval") -> dict:
    """
    Run the full audit pipeline for a payment approval request.

    Steps:
      1. Agent decides approve/reject based on amount
      2. Decision record (with vendor_id) uploaded to IPFS via Pinata
      3. SHA256 of CID computed as ipfs_hash
      4. Audit record submitted to Algorand smart contract
         — contract runs two policy checks: amount limit + vendor whitelist
      5. Returns complete result dict

    Args:
        amount: Payment amount to evaluate.
        vendor_id: Vendor identifier to check against the on-chain whitelist.

    Returns:
        Dict with keys: decision, ipfs_cid, algorand_tx_id, policy_result,
        asa_minted, action_id, vendor_id, policy_checks.

    Raises:
        RuntimeError: If any step in the pipeline fails.
    """
    # Step 1: Agent decision (amount only — vendor check is on-chain)
    type_config = AGENT_TYPE_CONFIG.get(agent_type_id, AGENT_TYPE_CONFIG["payment_approval"])
    action_name = type_config["action"]
    agent_id = f"{type_config['agent_id_suffix']}_001"
    logger.info("Running %s agent for amount: %d, vendor: %s", agent_type_id, amount, vendor_id)
    agent_decision, reason = await run_payment_agent(amount, vendor_id)
    logger.info("Agent decision: %s", agent_decision)

    # Step 2: Build decision record
    timestamp = int(time.time())
    action_id = f"{timestamp}_{random.randint(1000, 9999)}"

    record = {
        "action": action_name,
        "agent_type": agent_type_id,
        "amount": amount,
        "vendor_id": vendor_id,
        "agent_decision": agent_decision,  # what the agent decided (amount only)
        "reason": reason,
        "policy": POLICY_ID,
        "agent_id": agent_id,
        "timestamp": timestamp,
    }

    # Step 3: Upload to IPFS — action_id stored as Pinata metadata name for later lookup
    logger.info("Uploading decision record to IPFS...")
    try:
        ipfs_cid = await upload_to_ipfs(record, name=action_id)
    except Exception as e:
        raise RuntimeError(f"IPFS upload failed for action {action_id}: {e}")
    logger.info("IPFS CID: %s", ipfs_cid)

    # Step 4: Hash the CID for on-chain storage
    ipfs_hash = sha256(ipfs_cid.encode()).hexdigest()

    # Step 5: Submit to Algorand smart contract
    # Pass agent_decision as the decision field the contract stores
    record["decision"] = agent_decision
    logger.info("Submitting audit record to Algorand (action_id: %s)...", action_id)
    try:
        tx_result = await submit_audit(action_id, ipfs_hash, record)
    except Exception as e:
        raise RuntimeError(f"Algorand submission failed for action {action_id}: {e}")
    logger.info("Algorand TX confirmed: %s", tx_result.tx_id)

    # Step 6: Parse per-policy breakdown
    policy_checks = _parse_policy_result(tx_result.policy_result)

    # Step 7: Compute effective decision — "approved" only if ALL policies pass
    # The agent checks amount; the contract also checks vendor. Both must pass.
    effective_decision = "approved" if tx_result.asa_minted else "rejected"
    if effective_decision != agent_decision:
        logger.info(
            "Agent decision '%s' overridden to '%s' based on on-chain policy result: %s",
            agent_decision, effective_decision, tx_result.policy_result,
        )

    return {
        "decision": effective_decision,
        "ipfs_cid": ipfs_cid,
        "algorand_tx_id": tx_result.tx_id,
        "policy_result": tx_result.policy_result,
        "asa_minted": tx_result.asa_minted,
        "action_id": action_id,
        "vendor_id": vendor_id,
        "policy_checks": policy_checks,
        "agent_type_id": agent_type_id,
        "agent_id": agent_id,
    }
