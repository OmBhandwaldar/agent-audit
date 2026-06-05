"""
Example: a standalone insurance claims agent (a different company) using the AgentAudit SDK.

The SAME agent logs every decision to AgentAudit. Billing is a config choice, not a
separate agent:
  - subscription:  set AGENTAUDIT_API_KEY
  - pay-per-call:  set AGENTAUDIT_X402_MNEMONIC (+ AGENTAUDIT_ORG_ID) — the agent pays
                   $0.01 USDC per claim it logs.

Prerequisites:
  1. Onboard the insurer org:  python scripts/onboard_org.py medico claims_agent insurance_private
  2. Run the backend:          uvicorn api.main:app --port 8000
     (for x402 also: X402_ENABLED=true X402_RECIPIENT=<addr> ...)
  3. Run this example with one of:
       AGENTAUDIT_API_KEY=aa_... python examples/insurance_agent.py
       AGENTAUDIT_ORG_ID=medico AGENTAUDIT_X402_MNEMONIC="<payer 25 words>" python examples/insurance_agent.py
"""

import os

from agentaudit import AuditClient

BASE_URL = os.getenv("AGENTAUDIT_URL", "http://localhost:8000")
AGENT_ID = os.getenv("AGENTAUDIT_AGENT_ID", "claims_agent")


def _make_client() -> AuditClient:
    x402_mn = os.getenv("AGENTAUDIT_X402_MNEMONIC")
    if x402_mn:
        org_id = os.getenv("AGENTAUDIT_ORG_ID", "medico")
        print(f"[billing: x402 pay-per-call — org={org_id}, $0.01 USDC per claim]")
        return AuditClient(base_url=BASE_URL, org_id=org_id, x402_mnemonic=x402_mn)
    api_key = os.getenv("AGENTAUDIT_API_KEY")
    if api_key:
        print("[billing: subscription / API key]")
        return AuditClient(api_key=api_key, base_url=BASE_URL)
    raise SystemExit("Set AGENTAUDIT_API_KEY (subscription) or AGENTAUDIT_X402_MNEMONIC + AGENTAUDIT_ORG_ID (x402)")


def decide_claim(claim_amount: int, hospital: str) -> tuple[str, list]:
    """The insurer's own claims logic (unchanged by AgentAudit)."""
    decision = "approved" if claim_amount < 200_000 else "rejected"
    trace = [
        {"step": 1, "tool": "lookup_hospital", "args": {"hospital": hospital}, "result": "found"},
        {"step": 2, "tool": "assess_amount", "args": {"claim_amount": claim_amount}, "result": decision},
    ]
    return decision, trace


def main() -> None:
    audit = _make_client()
    for claim_amount, hospital in [(150_000, "HOSP_001"), (150_000, "HOSP_999"), (250_000, "HOSP_001")]:
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
