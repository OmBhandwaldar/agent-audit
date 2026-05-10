"""
AgentAudit Phase 2 audit pipeline.

run_audit_flow_v2() is the v2 entry point for the full audit flow:
  1. Agent decides approve/reject (based on amount)
  2. Decision JSON encrypted with AES-GCM
  3. Encrypted envelope uploaded to IPFS
  4. PolicyContract.check_and_mint called (policy checks + optional AACR mint)
  5. Record added to SQLite-backed BatchStore as a pending leaf
  6. Returns full result dict for API and frontend

The batch is NOT flushed here. Callers trigger POST /api/batch/submit
to flush pending leaves, compute the Merkle root, and anchor it on-chain.
"""

import logging
import os
import random
import time
from hashlib import sha256

from dotenv import load_dotenv

from agent.payment_agent import run_payment_agent
from algorand.contract_client_v2 import _parse_policy_result, submit_policy_check
from batcher.store import BatchStore
from crypto.payload import encrypt_payload
from ipfs.uploader import upload_to_ipfs

load_dotenv()

logger = logging.getLogger(__name__)

AGENT_ID = os.getenv("AGENT_ID", "agent_001")
POLICY_ID = "limit_5000"

AGENT_TYPE_CONFIG = {
    "payment_approval":  {"action": "approve_payment",   "agent_id_suffix": "payment_agent"},
    "vendor_onboarding": {"action": "vendor_onboarding", "agent_id_suffix": "vendor_agent"},
    "expense_claim":     {"action": "expense_claim",      "agent_id_suffix": "expense_agent"},
}


async def run_audit_flow_v2(
    amount: int,
    vendor_id: str,
    batch_store: BatchStore,
    agent_type_id: str = "payment_approval",
) -> dict:
    """
    Run the Phase 2 audit pipeline for a payment approval request.

    Steps:
      1. Agent decides approve/reject based on amount
      2. Build decision record
      3. Encrypt record with AES-GCM-256
      4. Upload encrypted envelope to IPFS (action_id stored as metadata name)
      5. sha256(CID) = ipfs_hash passed to PolicyContract
      6. PolicyContract.check_and_mint: checks amount limit + vendor whitelist,
         mints 1 AACR if both pass
      7. Add plaintext record (with policy result + IPFS fields) to BatchStore
         as a pending leaf — batch is NOT flushed here
      8. Return full result dict

    Args:
        amount: Payment amount to evaluate.
        vendor_id: Vendor identifier to check against the on-chain whitelist.
        batch_store: The shared SQLite-backed batch store for pending leaves.
        agent_type_id: Agent type identifier (default: "payment_approval").

    Returns:
        Dict with keys: decision, agent_decision, ipfs_cid, algorand_tx_id,
        policy_result, asa_minted, action_id, vendor_id, policy_checks,
        agent_type_id, agent_id, encrypted, batch_pending_count.

    Raises:
        RuntimeError: If any step in the pipeline fails.
    """
    type_config = AGENT_TYPE_CONFIG.get(agent_type_id, AGENT_TYPE_CONFIG["payment_approval"])
    action_name = type_config["action"]
    agent_id = f"{type_config['agent_id_suffix']}_001"

    logger.info(
        "v2 audit started: agent_type=%s amount=%d vendor=%s",
        agent_type_id, amount, vendor_id,
    )

    # Step 1: Agent decision
    agent_decision, reason = await run_payment_agent(amount, vendor_id)
    logger.info("Agent decision: %s", agent_decision)

    # Step 2: Build decision record
    timestamp = int(time.time())
    action_id = f"{timestamp}_{random.randint(1000, 9999)}"

    record = {
        "action": action_name,
        "action_id": action_id,
        "agent_type": agent_type_id,
        "amount": amount,
        "vendor_id": vendor_id,
        "agent_decision": agent_decision,
        "decision": agent_decision,
        "reason": reason,
        "policy": POLICY_ID,
        "agent_id": agent_id,
        "timestamp": timestamp,
    }

    # Step 3: Encrypt record
    envelope = encrypt_payload(record)
    logger.info("Record encrypted with AES-GCM-256")

    # Step 4: Upload encrypted envelope to IPFS
    logger.info("Uploading encrypted envelope to IPFS (action_id: %s)...", action_id)
    try:
        ipfs_cid = await upload_to_ipfs(envelope, name=action_id)
    except Exception as e:
        raise RuntimeError(f"IPFS upload failed for action {action_id}: {e}")
    logger.info("IPFS CID: %s", ipfs_cid)

    # Step 5: Hash the CID for PolicyContract
    ipfs_hash = sha256(ipfs_cid.encode()).hexdigest()

    # Step 6: PolicyContract.check_and_mint
    logger.info("Calling PolicyContract.check_and_mint (action_id: %s)...", action_id)
    try:
        policy_result = await submit_policy_check(
            action_id=action_id,
            ipfs_hash=ipfs_hash,
            amount=amount,
            vendor_id=vendor_id,
            agent_id=agent_id,
            timestamp=timestamp,
        )
    except Exception as e:
        raise RuntimeError(f"PolicyContract call failed for action {action_id}: {e}")
    logger.info(
        "PolicyContract result: %s  ASA minted: %s  TX: %s",
        policy_result.policy_result, policy_result.asa_minted, policy_result.tx_id,
    )

    # Step 7: Add to BatchStore (plaintext record with all fields populated)
    record["ipfs_cid"] = ipfs_cid
    record["ipfs_hash"] = ipfs_hash
    record["policy_result"] = policy_result.policy_result
    record["policy_tx_id"] = policy_result.tx_id
    record["asa_minted"] = policy_result.asa_minted
    # Effective decision: approved only if on-chain policy passes
    effective_decision = "approved" if policy_result.asa_minted else "rejected"
    record["decision"] = effective_decision

    batch_store.add(record)
    logger.info(
        "Record added to BatchStore: action_id=%s pending=%d",
        action_id, batch_store.size(),
    )

    policy_checks = _parse_policy_result(policy_result.policy_result)

    if effective_decision != agent_decision:
        logger.info(
            "Agent decision '%s' overridden to '%s' by on-chain policy: %s",
            agent_decision, effective_decision, policy_result.policy_result,
        )

    return {
        "decision": effective_decision,
        "agent_decision": agent_decision,
        "ipfs_cid": ipfs_cid,
        "algorand_tx_id": policy_result.tx_id,
        "policy_result": policy_result.policy_result,
        "asa_minted": policy_result.asa_minted,
        "action_id": action_id,
        "vendor_id": vendor_id,
        "policy_checks": policy_checks,
        "agent_type_id": agent_type_id,
        "agent_id": agent_id,
        "encrypted": True,
        "batch_pending_count": batch_store.size(),
    }
