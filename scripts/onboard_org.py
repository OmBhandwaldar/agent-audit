"""
Onboard an organisation (the one-time human provisioning step).

Issues an API key + a per-org encryption key, registers an agent, and writes the
agent's policy set both on-chain (PolicyContract) and to the tenant store.

Usage:
  python scripts/onboard_org.py [org_id] [agent_id]

Defaults: org_id=acme, agent_id=payment_agent
Policy set: amount < 5000 (Mode 1)  AND  vendor in {VENDOR_001, VENDOR_002}
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorand.contract_client_v2 import MODE_ONCHAIN, OP_IN, OP_LT  # noqa: E402
from tenancy.provisioning import create_org, register_agent, register_policy  # noqa: E402
from tenancy.store import TenantStore  # noqa: E402


async def main() -> None:
    org_id = sys.argv[1] if len(sys.argv) > 1 else "acme"
    agent_id = sys.argv[2] if len(sys.argv) > 2 else "payment_agent"

    store = TenantStore()
    if store.get_org(org_id):
        print(f"Org '{org_id}' already exists. Choose a different org_id.")
        sys.exit(1)

    print(f"Onboarding {org_id} / {agent_id} ...\n")

    creds = create_org(store, org_id)
    register_agent(store, org_id, agent_id)

    print("Registering policies on-chain...")
    await register_policy(store, org_id, agent_id, field="amount", mode=MODE_ONCHAIN, operator=OP_LT, value_num=5000)
    await register_policy(
        store, org_id, agent_id,
        field="vendor", mode=MODE_ONCHAIN, operator=OP_IN,
        set_values=["VENDOR_001", "VENDOR_002"],
    )

    print("\n=== Onboarded ===")
    print(f"  org_id:         {creds['org_id']}")
    print(f"  agent_id:       {agent_id}")
    print(f"  API key:        {creds['api_key']}        (save this — shown once)")
    print(f"  Encryption key: {creds['encryption_key']}")
    print(f"  billing_mode:   {creds['billing_mode']}")
    print(f"  policies:       amount < 5000  AND  vendor in {{VENDOR_001, VENDOR_002}}")
    print(f"  stored rules:   {store.get_rules(org_id, agent_id)}")


if __name__ == "__main__":
    asyncio.run(main())
