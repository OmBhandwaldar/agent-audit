"""
Example: a standalone insurance claims agent in a *different* company, using the
AgentAudit SDK to make its decisions independently verifiable.

This proves the platform is decision-agnostic: the same audit layer that handles a
procurement agent handles an insurance claims agent, with no change to AgentAudit.

Prerequisites:
  1. Onboard an insurer org:
       python scripts/onboard_org.py insurer claims_agent insurance
     (prints an API key — copy it)
  2. Run the backend:
       uvicorn api.main:app --port 8000
  3. Run this example:
       AGENTAUDIT_API_KEY=aa_... python examples/insurance_agent.py
"""

import os

from agentaudit import AuditClient

API_KEY = os.environ.get("AGENTAUDIT_API_KEY", "")
BASE_URL = os.getenv("AGENTAUDIT_URL", "http://localhost:8000")
AGENT_ID = os.getenv("AGENTAUDIT_AGENT_ID", "claims_agent")

audit = AuditClient(api_key=API_KEY, base_url=BASE_URL)


def decide_claim(claim_amount: int, hospital: str) -> tuple[str, list]:
    """The insurer's own claims logic (unchanged by AgentAudit)."""
    decision = "approved" if claim_amount < 200_000 else "rejected"
    trace = [
        {"step": 1, "tool": "lookup_hospital", "args": {"hospital": hospital}, "result": "found"},
        {"step": 2, "tool": "assess_amount", "args": {"claim_amount": claim_amount}, "result": decision},
    ]
    return decision, trace


def main() -> None:
    if not API_KEY:
        raise SystemExit("Set AGENTAUDIT_API_KEY (from onboard_org.py insurer claims_agent insurance)")

    cases = [
        (150_000, "HOSP_001"),  # within limit + whitelisted hospital -> approved
        (150_000, "HOSP_999"),  # hospital not whitelisted -> rejected on-chain
        (250_000, "HOSP_001"),  # over the claim limit -> rejected on-chain
    ]
    for claim_amount, hospital in cases:
        agent_decision, trace = decide_claim(claim_amount, hospital)
        result = audit.audit(
            agent_id=AGENT_ID,
            action="approve_claim",
            decision=agent_decision,
            fields={"claim_amount": claim_amount, "hospital": hospital},
            reasoning_trace=trace,
        )
        print(
            f"claim={claim_amount:>7} hospital={hospital:8} | "
            f"agent={agent_decision:8} on-chain={result['decision']:8} "
            f"minted={str(result['asa_minted']):5} policy={result['policy_result']} "
            f"action_id={result['action_id']}"
        )


if __name__ == "__main__":
    main()
