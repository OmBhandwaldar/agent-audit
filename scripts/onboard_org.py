"""
Onboard an organisation (the one-time human provisioning step).

Issues an API key + a per-org encryption key, registers an agent, and writes the
agent's policy set both on-chain (PolicyContract) and to the tenant store.

Usage:
  python scripts/onboard_org.py [org_id] [agent_id] [preset]

preset in {payment (default), insurance, lending} — the policy set to register:
  payment   : amount < 5000        AND vendor in {VENDOR_001, VENDOR_002}
  insurance : claim_amount < 200000 AND hospital in {HOSP_001, HOSP_002}
  lending   : loan_amount < 5000000 AND rate <= 24   (rate is a custom predicate)
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorand.contract_client_v2 import MODE_ONCHAIN, OP_IN, OP_LE, OP_LT  # noqa: E402
from tenancy.provisioning import (  # noqa: E402
    create_org,
    register_agent,
    register_policy,
    register_sensitive_policy,
    register_sensitive_set_policy,
)
from tenancy.store import TenantStore  # noqa: E402

# Each spec is a Mode-1 (public) predicate unless "private": True (Mode-2, encrypted threshold).
PRESETS = {
    "payment": [
        {"field": "amount", "operator": OP_LT, "value_num": 5000},
        {"field": "vendor", "operator": OP_IN, "set_values": ["VENDOR_001", "VENDOR_002"]},
    ],
    "insurance": [
        {"field": "claim_amount", "operator": OP_LT, "value_num": 200_000},
        {"field": "hospital", "operator": OP_IN, "set_values": ["HOSP_001", "HOSP_002"]},
    ],
    "lending": [
        {"field": "loan_amount", "operator": OP_LT, "value_num": 5_000_000},
        {"field": "rate", "operator": OP_LE, "value_num": 24},
    ],
    # Mixed: a public loan limit + a PRIVATE internal risk-tier threshold (Mode 2).
    "lending_private": [
        {"field": "loan_amount", "operator": OP_LT, "value_num": 5_000_000},
        {"field": "risk_tier", "operator": OP_LE, "value_num": 3, "private": True},
    ],
    # Mixed: a public claim limit + a PRIVATE (confidential) approved-hospital whitelist.
    "insurance_private": [
        {"field": "claim_amount", "operator": OP_LT, "value_num": 200_000},
        {"field": "hospital", "operator": OP_IN, "set_values": ["HOSP_001", "HOSP_002"], "private": True},
    ],
}


async def main() -> None:
    org_id = sys.argv[1] if len(sys.argv) > 1 else "acme"
    agent_id = sys.argv[2] if len(sys.argv) > 2 else "payment_agent"
    preset = sys.argv[3] if len(sys.argv) > 3 else "payment"

    if preset not in PRESETS:
        print(f"Unknown preset '{preset}'. Choose from: {', '.join(PRESETS)}")
        sys.exit(1)

    store = TenantStore()
    if store.get_org(org_id):
        print(f"Org '{org_id}' already exists. Choose a different org_id.")
        sys.exit(1)

    print(f"Onboarding {org_id} / {agent_id}  (preset: {preset}) ...\n")

    creds = create_org(store, org_id)
    register_agent(store, org_id, agent_id)

    print("Registering policies on-chain...")
    for spec in PRESETS[preset]:
        if spec.get("private") and spec.get("set_values") is not None:
            await register_sensitive_set_policy(
                store, org_id, agent_id,
                field=spec["field"], operator=spec["operator"], members=spec["set_values"],
            )
        elif spec.get("private"):
            await register_sensitive_policy(
                store, org_id, agent_id,
                field=spec["field"], operator=spec["operator"], value_num=spec["value_num"],
            )
        else:
            await register_policy(
                store, org_id, agent_id,
                field=spec["field"],
                mode=MODE_ONCHAIN,
                operator=spec["operator"],
                value_num=spec.get("value_num", 0),
                set_values=spec.get("set_values"),
            )

    print("\n=== Onboarded ===")
    print(f"  org_id:         {creds['org_id']}")
    print(f"  agent_id:       {agent_id}")
    print(f"  preset:         {preset}")
    print(f"  API key:        {creds['api_key']}        (save this — shown once)")
    print(f"  Encryption key: {creds['encryption_key']}")
    print(f"  stored rules:   {store.get_rules(org_id, agent_id)}")


if __name__ == "__main__":
    asyncio.run(main())
