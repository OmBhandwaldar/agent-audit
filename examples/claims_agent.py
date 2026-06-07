"""
LIVE DEMO — an insurer's OWN claims agent, before and after AgentAudit.

Stage-tuned twin of examples/insurance_agent.py (which stays as the full reference).
Everything is hardcoded so nothing has to be typed on stage.

DEMO SHAPE (before -> onboard -> integrate -> after):
  1. Run as-is:  python examples/claims_agent.py
     The agent decides claims and prints them. Nothing is logged with us — decisions
     live only inside this process. This is the insurer's "today".
  2. Onboard the insurer at /onboard -> copy the api_key.
  3. LIVE: uncomment the two marked "AgentAudit" blocks below; paste the api_key
     (or switch to the x402 line for pay-per-call).
  4. Run again. SAME agent, SAME claims — now each decision is encrypted, IPFS-pinned,
     policy-checked on-chain, and independently verifiable. The failing claim's reason
     (hospital not in the private whitelist) is enforced off-chain (Mode 2): only a
     commitment is on-chain, re-checkable with the auditor key on the dashboard.

Onboard medi_trust with:  claim_amount < 200000  AND  hospital in {HOSP_001, HOSP_002} (private)

Prereqs for the "after" run:
  - pip install -e .                  (so `from agentaudit import AuditClient` works)
  - uvicorn api.main:app --port 8000  (backend running)
  - x402 path also needs: X402_ENABLED=true on the backend + a USDC-funded payer wallet
"""

# Same inputs both runs, so the audience watches the SAME decisions become verifiable.
# 150000 @ HOSP_001 -> pass + AACR minted ; 150000 @ HOSP_999 -> fail (private hospital check)
CLAIMS = [(150_000, "HOSP_001"), (150_000, "HOSP_999")]


def decide_claim(claim_amount: int, hospital: str) -> tuple[str, list]:
    """The insurer's own claims logic (unchanged by AgentAudit)."""
    decision = "approved" if claim_amount < 200_000 else "rejected"
    trace = [
        {"step": 1, "tool": "lookup_hospital", "args": {"hospital": hospital}, "result": "found"},
        {"step": 2, "tool": "assess_amount", "args": {"claim_amount": claim_amount}, "result": decision},
    ]
    return decision, trace


def main() -> None:
    # ── AgentAudit: connect (uncomment ONE line after onboarding) ─────────────────
    # from agentaudit import AuditClient
    # audit = AuditClient(api_key="aa_PASTE_YOUR_KEY")                                  # subscription
    # audit = AuditClient(org_id="medi_trust", x402_mnemonic="<payer 25 words>")        # OR pay-per-call (x402)
    # ──────────────────────────────────────────────────────────────────────────────

    for claim_amount, hospital in CLAIMS:
        decision, trace = decide_claim(claim_amount, hospital)
        print(f"claim={claim_amount:>7}  hospital={hospital:9}  ->  {decision}")

        # ── AgentAudit: log this decision (uncomment after onboarding) ────────────
        # r = audit.audit(
        #     agent_id="claims_agent",
        #     action="approve_claim",
        #     decision=decision,
        #     fields={"claim_amount": claim_amount, "hospital": hospital},
        #     reasoning_trace=trace,
        # )
        # print(
        #     f"          logged: action_id={r['action_id']}  "
        #     f"on-chain={r['decision']}  minted={r['asa_minted']}  policy={r['policy_result']}"
        # )
        # ──────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    main()
