"""
Tenant provisioning for AgentAudit — the one-time human onboarding act.

create_org issues an API key (returned once) and a per-org encryption key, and records
the tenant. register_agent + register_policy register an agent's policy set both on-chain
(PolicyContract) and in the tenant store. This is what the onboarding CLI / dashboard calls.
"""

import hashlib
import logging
import secrets

from algorand.contract_client_v2 import (
    MODE_ATTESTED,
    MODE_ONCHAIN,
    OP_IN,
    OP_NOT_IN,
    add_to_set,
    register_rule,
)
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


def build_check_args(store: TenantStore, org_id: str, agent_id: str, decision_fields: dict) -> dict:
    """
    Build the per-rule arrays for submit_policy_check from a decision's field values.

    decision_fields maps field name -> value (int for numeric ops, str for set ops).
    For Mode-2 rules, decision_fields[field] should be a bool (the off-chain result).

    Returns {values_num, values_str, attested, fields} aligned to the agent's rule order.
    """
    rules = store.get_rules(org_id, agent_id)
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
            attested.append(bool(val))
        elif rule["operator"] in (OP_IN, OP_NOT_IN):
            values_num.append(0)
            values_str.append(str(val) if val is not None else "")
            attested.append(False)
        else:
            values_num.append(int(val) if val is not None else 0)
            values_str.append("")
            attested.append(False)

    return {"values_num": values_num, "values_str": values_str, "attested": attested, "fields": fields}
