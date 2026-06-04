"""
Phase 1 acceptance test: multi-tenant PolicyContract.

Registers two different orgs/agents with different policy sets (including a custom
predicate over a non-standard field), then runs check_and_mint for several decisions
and asserts:
  - each org is enforced against ITS OWN rules only (isolation)
  - all predicates are AND-ed (any fail -> no mint)
  - a custom predicate over a non-standard field works

Run AFTER deploy + opt-in + AACR funding:
  python scripts/deploy_phase2.py
  python scripts/opt_in_asa_phase2.py
  python scripts/send_aacr_to_policy.py
  python scripts/check_phase1.py
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorand.contract_client_v2 import (  # noqa: E402
    MODE_ONCHAIN,
    OP_IN,
    OP_LE,
    OP_LT,
    add_to_set,
    register_rule,
    submit_policy_check,
)

PASS = "[PASS]"
FAIL = "[FAIL]"
_failures = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global _failures
    tag = PASS if cond else FAIL
    if not cond:
        _failures += 1
    print(f"  {tag}  {label}" + (f"  ({detail})" if detail else ""))


def _aid() -> str:
    return f"{int(time.time())}_{int(time.time() * 1000) % 10000}"


async def main() -> None:
    # Unique org ids per run so re-runs don't collide with existing boxes.
    suffix = str(int(time.time()))
    org_a = f"acme_{suffix}"
    org_b = f"neobank_{suffix}"

    print(f"\n=== Onboard ORG A ({org_a}/payment_agent): amount<5000 AND vendor in set ===")
    await register_rule(org_a, "payment_agent", MODE_ONCHAIN, OP_LT, 5000, "amount")
    await register_rule(org_a, "payment_agent", MODE_ONCHAIN, OP_IN, 0, "vendor")
    await add_to_set(org_a, "payment_agent", "vendor", "VENDOR_001")
    print("  rules + vendor set registered")

    print(f"\n=== Onboard ORG B ({org_b}/lending_agent): amount<5000000 AND rate<=24 (custom field) ===")
    await register_rule(org_b, "lending_agent", MODE_ONCHAIN, OP_LT, 5_000_000, "amount")
    await register_rule(org_b, "lending_agent", MODE_ONCHAIN, OP_LE, 24, "rate")
    print("  rules registered (note: 'rate' is a custom predicate over a non-standard field)")

    # --- ORG A cases -------------------------------------------------------
    print("\n=== ORG A: amount=4500, vendor=VENDOR_001 -> expect PASS + mint ===")
    r = await submit_policy_check(
        org_a, "payment_agent", _aid(), "deadbeef",
        values_num=[4500, 0], values_str=["", "VENDOR_001"], attested=[False, False],
        fields=["amount", "vendor"],
    )
    print(f"  result={r.policy_result} minted={r.asa_minted}")
    check("ORG A approved + AACR minted", r.asa_minted, r.policy_result)

    print("\n=== ORG A: amount=7000, vendor=VENDOR_001 -> expect amount FAIL, no mint ===")
    r = await submit_policy_check(
        org_a, "payment_agent", _aid(), "deadbeef",
        values_num=[7000, 0], values_str=["", "VENDOR_001"], attested=[False, False],
        fields=["amount", "vendor"],
    )
    print(f"  result={r.policy_result} minted={r.asa_minted}")
    check("ORG A rejected on amount (no mint)", not r.asa_minted, r.policy_result)

    print("\n=== ORG A: amount=4500, vendor=VENDOR_999 -> expect vendor FAIL, no mint ===")
    r = await submit_policy_check(
        org_a, "payment_agent", _aid(), "deadbeef",
        values_num=[4500, 0], values_str=["", "VENDOR_999"], attested=[False, False],
        fields=["amount", "vendor"],
    )
    print(f"  result={r.policy_result} minted={r.asa_minted}")
    check("ORG A rejected on vendor (no mint)", not r.asa_minted, r.policy_result)

    # --- ORG B cases (isolation + custom predicate) ------------------------
    print("\n=== ORG B: amount=4000000, rate=21 -> expect PASS (B's higher limit + rate ok) ===")
    r = await submit_policy_check(
        org_b, "lending_agent", _aid(), "deadbeef",
        values_num=[4_000_000, 21], values_str=["", ""], attested=[False, False],
        fields=["amount", "rate"],
    )
    print(f"  result={r.policy_result} minted={r.asa_minted}")
    check("ORG B approved (4M passes B's 5M limit; A's 5000 limit did NOT apply)", r.asa_minted, r.policy_result)

    print("\n=== ORG B: amount=4000000, rate=30 -> expect rate FAIL (custom predicate), no mint ===")
    r = await submit_policy_check(
        org_b, "lending_agent", _aid(), "deadbeef",
        values_num=[4_000_000, 30], values_str=["", ""], attested=[False, False],
        fields=["amount", "rate"],
    )
    print(f"  result={r.policy_result} minted={r.asa_minted}")
    check("ORG B rejected on custom 'rate' predicate (no mint)", not r.asa_minted, r.policy_result)

    print("\n=== RESULT ===")
    if _failures == 0:
        print("  ALL PHASE 1 CHECKS PASSED")
    else:
        print(f"  {_failures} CHECK(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
