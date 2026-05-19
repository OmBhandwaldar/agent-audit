"""
AgentAudit Phase 2 audit pipeline.

Two entry points share the same v2 pipeline:
  - run_audit_flow_v2(amount, vendor_id, ...) — direct payment audit (POST /api/audit)
  - run_chat_flow_v2(prompt, ...)             — autonomous chat agent (POST /api/chat)

Both call _execute_v2_pipeline(record) under the hood:
  1. Encrypt record with AES-GCM-256
  2. Upload encrypted envelope to IPFS
  3. Call PolicyContract.check_and_mint
  4. Add the record (with policy result + IPFS fields) to BatchStore

The batch is NOT flushed here. Callers trigger POST /api/batch/submit
to flush pending leaves, compute the Merkle root, and anchor it on-chain.
"""

import logging
import os
import random
import time
from hashlib import sha256

from dotenv import load_dotenv

from agent.payment_agent import run_chat_agent, run_payment_agent
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


async def _execute_v2_pipeline(record: dict, batch_store: BatchStore) -> dict:
    """
    Run the v2 on-chain pipeline for a prepared decision record.

    Steps:
      1. Encrypt the record with AES-GCM-256
      2. Upload ciphertext envelope to IPFS (action_id as metadata name)
      3. Compute sha256(CID) and call PolicyContract.check_and_mint
      4. Mutate the record with ipfs_cid, ipfs_hash, policy result, effective
         decision, and add it as a pending leaf in BatchStore

    Returns the public result dict shared by both audit and chat flows.

    Args:
        record: Prepared audit record. Must contain action_id, amount,
            vendor_id, agent_id, timestamp, and an initial agent decision.
        batch_store: Shared SQLite-backed batch store for pending leaves.

    Returns:
        Result dict with keys: decision, agent_decision, ipfs_cid,
        algorand_tx_id, policy_result, asa_minted, action_id, vendor_id,
        policy_checks, agent_id, encrypted, batch_pending_count.
    """
    action_id = record["action_id"]
    amount = record["amount"]
    vendor_id = record["vendor_id"]
    agent_id = record["agent_id"]
    timestamp = record["timestamp"]
    agent_decision = record["agent_decision"]

    # Encrypt
    envelope = encrypt_payload(record)
    logger.info("Record encrypted with AES-GCM-256 (action_id: %s)", action_id)

    # Upload to IPFS
    logger.info("Uploading encrypted envelope to IPFS (action_id: %s)...", action_id)
    try:
        ipfs_cid = await upload_to_ipfs(envelope, name=action_id)
    except Exception as e:
        raise RuntimeError(f"IPFS upload failed for action {action_id}: {e}")
    logger.info("IPFS CID: %s", ipfs_cid)

    # Hash the CID for PolicyContract
    ipfs_hash = sha256(ipfs_cid.encode()).hexdigest()

    # PolicyContract.check_and_mint
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

    # Effective decision: approved only if on-chain policy passed
    effective_decision = "approved" if policy_result.asa_minted else "rejected"

    # Mutate the record with the post-policy fields, then add to BatchStore.
    # The leaf hash is computed from this mutated record — the encrypted IPFS
    # payload preserves the agent's pre-policy view.
    record["ipfs_cid"] = ipfs_cid
    record["ipfs_hash"] = ipfs_hash
    record["policy_result"] = policy_result.policy_result
    record["policy_tx_id"] = policy_result.tx_id
    record["asa_minted"] = policy_result.asa_minted
    record["decision"] = effective_decision

    batch_store.add(record)
    logger.info(
        "Record added to BatchStore: action_id=%s pending=%d",
        action_id, batch_store.size(),
    )

    if effective_decision != agent_decision:
        logger.info(
            "Agent decision '%s' overridden to '%s' by on-chain policy: %s",
            agent_decision, effective_decision, policy_result.policy_result,
        )

    policy_checks = _parse_policy_result(policy_result.policy_result)

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
        "agent_id": agent_id,
        "encrypted": True,
        "batch_pending_count": batch_store.size(),
    }


async def run_audit_flow_v2(
    amount: int,
    vendor_id: str,
    batch_store: BatchStore,
    agent_type_id: str = "payment_approval",
) -> dict:
    """
    Run the Phase 2 audit pipeline for a direct payment approval request.

    Args:
        amount: Payment amount to evaluate.
        vendor_id: Vendor identifier to check against the on-chain whitelist.
        batch_store: Shared SQLite-backed batch store for pending leaves.
        agent_type_id: Agent type identifier (default: "payment_approval").

    Returns:
        Result dict from _execute_v2_pipeline plus agent_type_id.
    """
    type_config = AGENT_TYPE_CONFIG.get(agent_type_id, AGENT_TYPE_CONFIG["payment_approval"])
    action_name = type_config["action"]
    agent_id = f"{type_config['agent_id_suffix']}_001"

    logger.info(
        "v2 audit started: agent_type=%s amount=%d vendor=%s",
        agent_type_id, amount, vendor_id,
    )

    # Step 1: Agent decision (amount only — vendor check is on-chain)
    agent_decision, reason, reasoning_trace = await run_payment_agent(amount, vendor_id)
    logger.info("Agent decision: %s  (trace steps: %d)", agent_decision, len(reasoning_trace))

    # Step 2: Build record
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
        "reasoning_trace": reasoning_trace,
        "policy": POLICY_ID,
        "agent_id": agent_id,
        "timestamp": timestamp,
    }

    result = await _execute_v2_pipeline(record, batch_store)
    result["agent_type_id"] = agent_type_id
    return result


async def run_chat_flow_v2(
    prompt: str,
    batch_store: BatchStore,
    agent_type_id: str = "payment_approval",
) -> dict:
    """
    Run the Phase 2 chat pipeline: agent autonomously selects vendor + amount,
    then runs the same v2 pipeline as run_audit_flow_v2.

    Args:
        prompt: Natural language task, e.g. "Find a vendor for office electronics."
        batch_store: Shared SQLite-backed batch store for pending leaves.
        agent_type_id: Agent type identifier (default: "payment_approval").

    Returns:
        Result dict from _execute_v2_pipeline plus:
          agent_type_id, amount, agent_reply, off_topic (when applicable).
        For off-topic prompts: {"agent_reply": str, "off_topic": True}.
    """
    type_config = AGENT_TYPE_CONFIG.get(agent_type_id, AGENT_TYPE_CONFIG["payment_approval"])
    action_name = type_config["action"]
    agent_id = f"{type_config['agent_id_suffix']}_001"

    logger.info("v2 chat started. Prompt: %s", prompt)

    # Step 1: Chat agent picks vendor + amount + decision
    vendor_id, amount, agent_decision, reason, reasoning_trace = await run_chat_agent(prompt)

    # Off-topic: agent responded with plain text, no vendor selected
    if vendor_id is None:
        logger.info("Chat agent flagged off-topic. Returning plain reply.")
        return {"agent_reply": reason, "off_topic": True}

    logger.info(
        "Chat agent selected: vendor=%s amount=%d decision=%s  (trace steps: %d)",
        vendor_id, amount, agent_decision, len(reasoning_trace),
    )

    # Step 2: Build record
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
        "reasoning_trace": reasoning_trace,
        "policy": POLICY_ID,
        "agent_id": agent_id,
        "source": "chat_agent",
        "prompt": prompt,
        "timestamp": timestamp,
    }

    # Step 3: Run shared v2 pipeline
    result = await _execute_v2_pipeline(record, batch_store)

    # Step 4: Build natural language reply for the chat UI
    from agent.vendors import get_vendor_by_id
    vendor = get_vendor_by_id(vendor_id)
    vendor_name = vendor["name"] if vendor else vendor_id
    policy_limit = int(os.getenv("POLICY_LIMIT", "5000"))

    if result["decision"] == "approved":
        agent_reply = (
            f"I've reviewed the available vendors and selected **{vendor_name} ({vendor_id})** "
            f"at **Rs{amount:,}**. This is within the Rs{policy_limit:,} budget "
            f"and the vendor is on the approved list. Payment approved and queued for batch anchor."
        )
    else:
        agent_reply = (
            f"I selected **{vendor_name} ({vendor_id})** at **Rs{amount:,}** for this task."
        )

    result["agent_type_id"] = agent_type_id
    result["amount"] = amount
    result["agent_reply"] = agent_reply
    return result
