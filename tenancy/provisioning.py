"""
Tenant provisioning for AgentAudit — the one-time human onboarding act.

create_org issues an API key (returned once) and a per-org encryption key, and records
the tenant. register_agent + register_policy register an agent's policy set both on-chain
(PolicyContract) and in the tenant store. This is what the onboarding CLI / dashboard calls.
"""

import hashlib
import json
import logging
import secrets

from algorand.contract_client_v2 import (
    MODE_ATTESTED,
    MODE_ONCHAIN,
    OP_EQ,
    OP_GE,
    OP_GT,
    OP_IN,
    OP_LE,
    OP_LT,
    OP_NE,
    OP_NOT_IN,
    add_to_set,
    register_rule,
)
from crypto.payload import decrypt_payload, encrypt_payload, parse_hex_key
from tenancy.store import TenantStore

logger = logging.getLogger(__name__)


def _generate_api_key() -> str:
    """Generate a public-facing API key (returned to the org once, never stored raw)."""
    return "aa_" + secrets.token_urlsafe(24)


def _hash_api_key(api_key: str) -> str:
    """SHA256 hash of an API key, for storage and lookup."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def _generate_enc_key_hex() -> str:
    """Generate a fresh 256-bit AES key (hex) for the org's records + Mode-2 policies."""
    return secrets.token_bytes(32).hex()


def create_org(store: TenantStore, org_id: str, billing_mode: str = "api_key") -> dict:
    """
    Provision a new organisation.

    Returns a dict with the org_id, the plaintext api_key, and the encryption_key.
    Both secrets are shown ONCE here — only the api_key hash is persisted; the
    encryption key is stored (this round) so the backend can encrypt under it.

    Raises:
        ValueError: if the org already exists.
    """
    if store.get_org(org_id):
        raise ValueError(f"Org '{org_id}' already exists")

    api_key = _generate_api_key()
    enc_key_hex = _generate_enc_key_hex()
    store.create_org(org_id, _hash_api_key(api_key), enc_key_hex, key_version=1, billing_mode=billing_mode)
    logger.info("Provisioned org %s (billing=%s)", org_id, billing_mode)
    return {"org_id": org_id, "api_key": api_key, "encryption_key": enc_key_hex, "billing_mode": billing_mode}


def register_agent(store: TenantStore, org_id: str, agent_id: str) -> None:
    """Register an agent under an org."""
    if not store.get_org(org_id):
        raise ValueError(f"Org '{org_id}' does not exist")
    store.add_agent(org_id, agent_id)
    logger.info("Registered agent %s/%s", org_id, agent_id)


async def register_policy(
    store: TenantStore,
    org_id: str,
    agent_id: str,
    *,
    field: str,
    mode: int = MODE_ONCHAIN,
    operator: int = 0,
    value_num: int = 0,
    commitment: str = "",
    set_values: list[str] | None = None,
) -> int:
    """
    Register one predicate for an agent: write it on-chain and mirror it in the store.

    For in/not_in operators, pass set_values to seed the on-chain membership set.
    For Mode-2 (private) policies, pass the commitment (sha256 of the policy doc).

    Returns the assigned rule index (matches the on-chain index).
    """
    if not store.get_org(org_id):
        raise ValueError(f"Org '{org_id}' does not exist")

    _tx_id, idx = await register_rule(org_id, agent_id, mode, operator, value_num, field, commitment)
    store.add_rule(org_id, agent_id, idx, mode, operator, value_num, field, commitment)

    if set_values and operator in (OP_IN, OP_NOT_IN):
        for value in set_values:
            await add_to_set(org_id, agent_id, field, value)
            logger.info("Seeded set %s/%s %s=%s", org_id, agent_id, field, value)

    logger.info("Registered policy %s/%s idx=%d field=%s mode=%d op=%d", org_id, agent_id, idx, field, mode, operator)
    return idx


# ---------------------------------------------------------------------------
# Mode 2 (private policy): doc + commitment + off-chain evaluation
# ---------------------------------------------------------------------------


def _canonical(doc: dict) -> str:
    """Canonical JSON for committing/hashing a policy doc."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def policy_commitment(doc: dict) -> str:
    """sha256 of the canonical policy doc — the value stored on-chain for a Mode-2 rule."""
    return hashlib.sha256(_canonical(doc).encode()).hexdigest()


def _eval_numeric(operator: int, lhs: int, rhs: int) -> bool:
    """Evaluate a numeric predicate operator."""
    return {
        OP_LT: lhs < rhs, OP_LE: lhs <= rhs, OP_GT: lhs > rhs,
        OP_GE: lhs >= rhs, OP_EQ: lhs == rhs, OP_NE: lhs != rhs,
    }.get(operator, False)


def _eval_doc(doc: dict, field_value) -> bool:
    """
    Evaluate a private policy doc against a decision field value.

    Numeric ops use doc['value_num']; set ops (in/not_in) use doc['members'].
    """
    op = int(doc["operator"])
    if op in (OP_IN, OP_NOT_IN):
        in_set = str(field_value) in doc.get("members", [])
        return in_set if op == OP_IN else not in_set
    return _eval_numeric(op, int(field_value), int(doc["value_num"]))


async def register_sensitive_policy(
    store: TenantStore,
    org_id: str,
    agent_id: str,
    *,
    field: str,
    operator: int,
    value_num: int,
) -> int:
    """
    Register a Mode-2 (private) numeric predicate. The threshold stays secret: the policy
    doc is encrypted under the org key and stored off-chain; only its sha256 commitment is
    written on-chain (operator/value are NOT on-chain). Returns the rule index.
    """
    org = store.get_org(org_id)
    if not org:
        raise ValueError(f"Org '{org_id}' does not exist")

    doc = {"field": field, "operator": operator, "value_num": value_num}
    commitment = policy_commitment(doc)
    enc_key = parse_hex_key(org["enc_key_hex"])
    envelope = encrypt_payload(doc, key=enc_key)

    # On-chain: mode=ATTESTED + commitment + field label. operator/value omitted (private).
    _tx_id, idx = await register_rule(org_id, agent_id, MODE_ATTESTED, 0, 0, field, commitment)
    store.add_rule(org_id, agent_id, idx, MODE_ATTESTED, 0, 0, field, commitment, json.dumps(envelope))
    logger.info("Registered Mode-2 (private) policy %s/%s idx=%d field=%s", org_id, agent_id, idx, field)
    return idx


async def register_sensitive_set_policy(
    store: TenantStore,
    org_id: str,
    agent_id: str,
    *,
    field: str,
    operator: int,
    members: list[str],
) -> int:
    """
    Register a Mode-2 (private) set-membership predicate — a confidential whitelist.

    The member list stays secret: the policy doc (with the members) is encrypted under the
    org key and stored off-chain; only its sha256 commitment is written on-chain. Membership
    is checked off-chain. operator must be OP_IN or OP_NOT_IN. Returns the rule index.
    """
    if operator not in (OP_IN, OP_NOT_IN):
        raise ValueError("register_sensitive_set_policy requires OP_IN or OP_NOT_IN")
    org = store.get_org(org_id)
    if not org:
        raise ValueError(f"Org '{org_id}' does not exist")

    doc = {"field": field, "operator": operator, "members": sorted(members)}
    commitment = policy_commitment(doc)
    enc_key = parse_hex_key(org["enc_key_hex"])
    envelope = encrypt_payload(doc, key=enc_key)

    _tx_id, idx = await register_rule(org_id, agent_id, MODE_ATTESTED, 0, 0, field, commitment)
    store.add_rule(org_id, agent_id, idx, MODE_ATTESTED, 0, 0, field, commitment, json.dumps(envelope))
    logger.info("Registered Mode-2 (private SET) policy %s/%s idx=%d field=%s", org_id, agent_id, idx, field)
    return idx


def _evaluate_sensitive(rule: dict, field_value, enc_key: bytes) -> bool:
    """Decrypt a Mode-2 rule's policy doc with the org key and evaluate it off-chain."""
    if field_value is None or not rule.get("doc_cipher"):
        return False
    doc = decrypt_payload(json.loads(rule["doc_cipher"]), key=enc_key)
    return _eval_doc(doc, field_value)


def build_check_args(store: TenantStore, org_id: str, agent_id: str, decision_fields: dict) -> dict:
    """
    Build the per-rule arrays for submit_policy_check from a decision's field values.

    Mode-1 rules: numeric value -> values_num; set value -> values_str.
    Mode-2 rules: the backend enforces the private policy off-chain (decrypt the doc with
    the org key, evaluate) and passes the result as attested[i].

    Returns {values_num, values_str, attested, fields} aligned to the agent's rule order.
    """
    rules = store.get_rules(org_id, agent_id)
    org = store.get_org(org_id)
    enc_key = parse_hex_key(org["enc_key_hex"]) if org else b""

    values_num: list[int] = []
    values_str: list[str] = []
    attested: list[bool] = []
    fields: list[str] = []

    for rule in rules:
        field = rule["field"]
        fields.append(field)
        val = decision_fields.get(field)
        if rule["mode"] == MODE_ATTESTED:
            values_num.append(0)
            values_str.append("")
            attested.append(_evaluate_sensitive(rule, val, enc_key))
        elif rule["operator"] in (OP_IN, OP_NOT_IN):
            values_num.append(0)
            values_str.append(str(val) if val is not None else "")
            attested.append(False)
        else:
            values_num.append(int(val) if val is not None else 0)
            values_str.append("")
            attested.append(False)

    return {"values_num": values_num, "values_str": values_str, "attested": attested, "fields": fields}


def reverify_mode2(store: TenantStore, org_id: str, agent_id: str, decision_fields: dict, key_bytes: bytes) -> list[dict]:
    """
    Auditor re-check of Mode-2 rules: with the org key, decrypt each private policy doc,
    confirm it hashes to the on-chain commitment, and re-run the check against the decision.

    Returns one dict per Mode-2 rule: {idx, field, commitment_matches, recheck_pass}.
    """
    results: list[dict] = []
    for rule in store.get_rules(org_id, agent_id):
        if rule["mode"] != MODE_ATTESTED or not rule.get("doc_cipher"):
            continue
        try:
            doc = decrypt_payload(json.loads(rule["doc_cipher"]), key=key_bytes)
        except Exception:
            results.append({"idx": rule["idx"], "field": rule["field"], "commitment_matches": False, "recheck_pass": None})
            continue
        matches = policy_commitment(doc) == rule["commitment"]
        val = decision_fields.get(rule["field"])
        recheck = _eval_doc(doc, val) if val is not None else None
        results.append({
            "idx": rule["idx"], "field": rule["field"],
            "commitment_matches": matches, "recheck_pass": recheck,
        })
    return results
