"""
AgentAudit SDK — the client a company drops into its own agent.

Two lines to make an agent's decisions verifiable:

    from agentaudit import AuditClient
    audit = AuditClient(api_key="aa_...", base_url="https://api.agentaudit.io")

    result = audit.audit(
        agent_id="claims_agent",
        action="approve_claim",
        decision="approved",
        fields={"claim_amount": 150000, "hospital": "HOSP_001"},
        reasoning_trace=trace,
    )
    # result -> {action_id, decision (on-chain), asa_minted, policy_result, ...}

Or wrap a decision function with the decorator (zero logic change):

    @audit.capture(agent_id="claims_agent", action="approve_claim")
    def decide(claim_amount, hospital):
        ...
        return {"decision": "approved", "fields": {...}, "reasoning_trace": [...]}

The on-chain policy is authoritative: `result["decision"]` is the enforced outcome,
which may override the agent's own decision (e.g. a non-whitelisted entity is rejected).
"""

import functools

import httpx


class AuditClient:
    """Thin HTTP client over the AgentAudit /v1/audit ingest endpoint."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:8000", timeout: float = 90.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    def audit(
        self,
        agent_id: str,
        action: str,
        decision: str,
        fields: dict,
        reasoning_trace: list | None = None,
    ) -> dict:
        """
        Submit a decision for auditing. Returns the audit result (on-chain decision,
        asa_minted, policy_result, action_id, ipfs_cid, algorand_tx_id).

        Raises httpx.HTTPStatusError on a non-2xx response (401 = bad/missing key).
        """
        payload = {
            "agent_id": agent_id,
            "action": action,
            "decision": decision,
            "fields": fields,
            "reasoning_trace": reasoning_trace or [],
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self.base_url}/v1/audit",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            return resp.json()

    def capture(self, agent_id: str, action: str):
        """
        Decorator: audit a decision function's result automatically.

        The wrapped function must return a dict with keys: decision (str),
        fields (dict), and optionally reasoning_trace (list). The decorator submits
        the audit and attaches the result under the "audit" key of the return dict.
        """
        def decorator(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                out = fn(*args, **kwargs)
                if not isinstance(out, dict) or "decision" not in out or "fields" not in out:
                    raise ValueError(
                        "@capture-decorated function must return {'decision': ..., 'fields': {...}}"
                    )
                out["audit"] = self.audit(
                    agent_id=agent_id,
                    action=action,
                    decision=out["decision"],
                    fields=out["fields"],
                    reasoning_trace=out.get("reasoning_trace"),
                )
                return out
            return wrapper
        return decorator
