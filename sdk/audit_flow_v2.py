"""
AgentAudit multi-tenant audit pipeline.

Entry points (all share _execute_pipeline):
  - run_audit_flow_v2(amount, vendor_id, ...) — demo: internal payment agent (POST /api/audit)
  - run_chat_flow_v2(prompt, ...)             — demo: internal chat agent   (POST /api/chat)
  - run_ingest_v2(org_id, agent_id, ...)      — product: external agent submits a decision (POST /v1/audit)

The demo flows run AgentAudit's own agent and audit under a configured demo org.
run_ingest_v2 audits a decision an EXTERNAL agent already made, under that agent's tenant.

Pipeline per decision:
  1. Encrypt the record with the ORG's key (AES-GCM-256)
  2. Upload the encrypted envelope to IPFS
  3. build_check_args from the decision fields + the org's on-chain rules
  4. PolicyContract.check_and_mint (multi-tenant: enforces that org+agent's policy set)
  5. Add the record (with policy result) to the batch store
The batch is flushed/anchored separately via POST /api/batch/submit.
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
from crypto.payload import encrypt_payload, parse_hex_key
from ipfs.uploader import upload_to_ipfs
from tenancy.provisioning import build_check_args
from tenancy.store import TenantStore

load_dotenv()

logger = logging.getLogger(__name__)

POLICY_ID = "limit_5000"
DEMO_ORG_ID = os.getenv("DEMO_ORG_ID", "acmedemo")
DEMO_AGENT_ID = os.getenv("DEMO_AGENT_ID", "payment_agent")


async def _execute_pipeline(
    record: dict,
    decision_fields: dict,
    org_id: str,
    agent_id: str,
    batch_store: BatchStore,
    tenant_store: TenantStore,
) -> dict:
    """
    Encrypt → IPFS → PolicyContract.check_and_mint → batch, for one prepared record.

    Args:
        record: Prepared decision record (must contain action_id, timestamp).
        decision_fields: field name -> value, matching the org+agent's rule fields.
        org_id, agent_id: tenant context (must be provisioned).
        batch_store, tenant_store: shared stores.

    Returns the public result dict.
    """
    org = tenant_store.get_org(org_id)
    if not org:
        raise RuntimeError(f"Unknown org '{org_id}' — provision it with scripts/onboard_org.py")

    action_id = record["action_id"]
    record["org_id"] = org_id
    record["agent_id"] = agent_id
    record["fields"] = decision_fields  # kept for auditor re-verification (incl. Mode 2)

    # 1. Encrypt under the org's key
    enc_key = parse_hex_key(org["enc_key_hex"])
    envelope = encrypt_payload(record, key=enc_key)
    logger.info("Encrypted record for org=%s action=%s", org_id, action_id)

    # 2. Upload to IPFS
    try:
        ipfs_cid = await upload_to_ipfs(envelope, name=action_id)
    except Exception as e:
        raise RuntimeError(f"IPFS upload failed for action {action_id}: {e}")
    ipfs_hash = sha256(ipfs_cid.encode()).hexdigest()

    # 3. Build the per-rule arrays from this org+agent's policy set
    check_args = build_check_args(tenant_store, org_id, agent_id, decision_fields)

    # 4. PolicyContract.check_and_mint
    try:
        policy_result = await submit_policy_check(
            org_id=org_id,
            agent_id=agent_id,
            action_id=action_id,
            ipfs_hash=ipfs_hash,
            **check_args,
        )
    except Exception as e:
        raise RuntimeError(f"PolicyContract call failed for action {action_id}: {e}")
    logger.info(
        "Policy result: %s  minted=%s  tx=%s",
        policy_result.policy_result, policy_result.asa_minted, policy_result.tx_id,
    )

    effective_decision = "approved" if policy_result.asa_minted else "rejected"
    agent_decision = record.get("agent_decision", record.get("decision"))

    record["ipfs_cid"] = ipfs_cid
    record["ipfs_hash"] = ipfs_hash
    record["policy_result"] = policy_result.policy_result
    record["policy_tx_id"] = policy_result.tx_id
    record["asa_minted"] = policy_result.asa_minted
    record["decision"] = effective_decision

    batch_store.add(record)
    logger.info("Record added to batch: action=%s pending=%d", action_id, batch_store.size())

    return {
        "decision": effective_decision,
        "agent_decision": agent_decision,
        "ipfs_cid": ipfs_cid,
        "algorand_tx_id": policy_result.tx_id,
        "policy_result": policy_result.policy_result,
        "asa_minted": policy_result.asa_minted,
        "action_id": action_id,
        "org_id": org_id,
        "agent_id": agent_id,
        "vendor_id": record.get("vendor_id", ""),
        "fields": decision_fields,  # the agent's decision inputs, whatever their schema
        "policy_checks": _parse_policy_result(policy_result.policy_result),
        "encrypted": True,
        "batch_pending_count": batch_store.size(),
    }


def _new_action_id() -> str:
    ts = int(time.time())
    return f"{ts}_{random.randint(1000, 9999)}"


# ---------------------------------------------------------------------------
# Demo flow — internal payment agent (POST /api/audit)
# ---------------------------------------------------------------------------


async def run_audit_flow_v2(
    amount: int,
    vendor_id: str,
    batch_store: BatchStore,
    tenant_store: TenantStore,
    org_id: str = DEMO_ORG_ID,
    agent_id: str = DEMO_AGENT_ID,
) -> dict:
    """Demo: internal payment agent decides on amount, then audit under the demo org."""
    logger.info("audit flow: org=%s agent=%s amount=%d vendor=%s", org_id, agent_id, amount, vendor_id)
    agent_decision, reason, reasoning_trace = await run_payment_agent(amount, vendor_id)

    timestamp = int(time.time())
    record = {
        "action": "approve_payment",
        "action_id": _new_action_id(),
        "amount": amount,
        "vendor_id": vendor_id,
        "agent_decision": agent_decision,
        # enforced "decision" is added post-policy in _execute_pipeline — the pre-policy
        # IPFS snapshot holds only the agent's claim (agent_decision), not the verdict.
        "reason": reason,
        "reasoning_trace": reasoning_trace,
        "policy": POLICY_ID,
        "timestamp": timestamp,
    }
    decision_fields = {"amount": amount, "vendor": vendor_id}
    result = await _execute_pipeline(record, decision_fields, org_id, agent_id, batch_store, tenant_store)
    result["agent_type_id"] = "payment_approval"
    return result


# ---------------------------------------------------------------------------
# Demo flow — internal chat agent (POST /api/chat)
# ---------------------------------------------------------------------------


async def run_chat_flow_v2(
    prompt: str,
    batch_store: BatchStore,
    tenant_store: TenantStore,
    org_id: str = DEMO_ORG_ID,
    agent_id: str = DEMO_AGENT_ID,
) -> dict:
    """Demo: internal chat agent picks vendor + amount, then audit under the demo org."""
    logger.info("chat flow: org=%s prompt=%s", org_id, prompt)
    vendor_id, amount, agent_decision, reason, reasoning_trace = await run_chat_agent(prompt)

    if vendor_id is None:
        return {"agent_reply": reason, "off_topic": True}

    timestamp = int(time.time())
    record = {
        "action": "approve_payment",
        "action_id": _new_action_id(),
        "amount": amount,
        "vendor_id": vendor_id,
        "agent_decision": agent_decision,
        # enforced "decision" is added post-policy in _execute_pipeline — the pre-policy
        # IPFS snapshot holds only the agent's claim (agent_decision), not the verdict.
        "reason": reason,
        "reasoning_trace": reasoning_trace,
        "policy": POLICY_ID,
        "source": "chat_agent",
        "prompt": prompt,
        "timestamp": timestamp,
    }
    decision_fields = {"amount": amount, "vendor": vendor_id}
    result = await _execute_pipeline(record, decision_fields, org_id, agent_id, batch_store, tenant_store)

    from agent.vendors import get_vendor_by_id
    vendor = get_vendor_by_id(vendor_id)
    vendor_name = vendor["name"] if vendor else vendor_id
    if result["decision"] == "approved":
        reply = (
            f"I selected **{vendor_name} ({vendor_id})** at **Rs{amount:,}**. "
            f"Within policy and the vendor is approved — payment approved and queued for batch anchor."
        )
    else:
        reply = f"I selected **{vendor_name} ({vendor_id})** at **Rs{amount:,}**, but it did not pass policy."

    result["agent_type_id"] = "payment_approval"
    result["amount"] = amount
    result["agent_reply"] = reply
    return result


# ---------------------------------------------------------------------------
# Product flow — external agent submits a decision (POST /v1/audit)
# ---------------------------------------------------------------------------


async def run_ingest_v2(
    org_id: str,
    agent_id: str,
    action: str,
    decision: str,
    fields: dict,
    reasoning_trace: list,
    batch_store: BatchStore,
    tenant_store: TenantStore,
) -> dict:
    """
    Audit a decision an external agent already made, under its tenant.

    Args:
        org_id, agent_id: resolved from the caller's API key.
        action: e.g. "approve_loan", "approve_claim".
        decision: the agent's own decision label (e.g. "approved").
        fields: decision field values keyed by name, matching the org+agent's rule fields.
        reasoning_trace: the agent's tool-call trace (stored inside the encrypted record).
    """
    timestamp = int(time.time())
    record = {
        "action": action,
        "action_id": _new_action_id(),
        "agent_decision": decision,
        # enforced "decision" is added post-policy in _execute_pipeline — the pre-policy
        # IPFS snapshot holds only the agent's claim (agent_decision), not the verdict.
        "fields": fields,
        "reasoning_trace": reasoning_trace or [{"step": 1, "tool": "external_agent", "args": {}, "result": decision}],
        "source": "ingest",
        "timestamp": timestamp,
    }
    # Surface common fields at top level for the dashboard/summary.
    if "amount" in fields:
        record["amount"] = fields["amount"]
    if "vendor" in fields:
        record["vendor_id"] = fields["vendor"]

    return await _execute_pipeline(record, fields, org_id, agent_id, batch_store, tenant_store)
