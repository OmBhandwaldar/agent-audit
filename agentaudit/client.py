"""
AgentAudit SDK — the client a company drops into its own agent.

The SAME working agent (procurement, insurance, lending, …) makes a decision and submits
it to AgentAudit to be logged + policy-checked. Two billing modes, chosen at construction:

  # Subscription / metered — authenticate with an API key:
  audit = AuditClient(api_key="aa_live_...", base_url="https://api.agentaudit.io")

  # Pay-per-call (x402) — the agent pays $0.01 USDC per decision; org declared, payment authorizes:
  audit = AuditClient(org_id="medico", x402_mnemonic="<payer 25 words>",
                      base_url="https://api.agentaudit.io")

Then, identically in either mode:
  result = audit.audit(
      agent_id="claims_agent",
      action="approve_claim",
      decision="approved",
      fields={"claim_amount": 150000, "hospital": "HOSP_001"},
      reasoning_trace=trace,
  )

x402 is opt-in: it only activates in x402 mode. In API-key mode no USDC moves.
The on-chain policy is authoritative — `result["decision"]` is the enforced outcome.
"""

import functools

import httpx

ALGORAND_TESTNET_CAIP2 = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="


class _AlgorandSigner:
    """ClientAvmSigner: signs the USDC payment transaction the facilitator settles (x402 mode)."""

    def __init__(self, sk_b64: str, address: str) -> None:
        self._sk = sk_b64
        self._address = address

    @property
    def address(self) -> str:
        return self._address

    def sign_transactions(self, unsigned_txns, indexes_to_sign):
        import base64

        import algosdk

        signed = []
        for i, txn_bytes in enumerate(unsigned_txns):
            if i in indexes_to_sign:
                txn = algosdk.encoding.msgpack_decode(base64.b64encode(txn_bytes).decode())
                s = txn.sign(self._sk)
                signed.append(base64.b64decode(algosdk.encoding.msgpack_encode(s)))
            else:
                signed.append(None)
        return signed


class AuditClient:
    """
    Client over the AgentAudit ingest endpoints.

    Subscription mode: pass api_key. Pay-per-call mode: pass org_id + x402_mnemonic
    (and optionally algod_url). x402 dependencies are imported lazily, so API-key-only
    users don't need the x402/algosdk packages.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "http://localhost:8000",
        *,
        org_id: str | None = None,
        x402_mnemonic: str | None = None,
        algod_url: str = "https://testnet-api.algonode.cloud",
        timeout: float = 90.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self.api_key = api_key
        self.org_id = org_id
        self._x402_mnemonic = x402_mnemonic
        self._algod_url = algod_url
        self._x402_session = None

        if x402_mnemonic:
            if not org_id:
                raise ValueError("x402 mode requires org_id (the payment authorizes; org is declared in the body)")
            self.billing = "x402"
        elif api_key:
            self.billing = "api_key"
        else:
            raise ValueError("Provide api_key (subscription) OR org_id + x402_mnemonic (pay-per-call)")

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

        In x402 mode this auto-pays $0.01 USDC before the audit runs.
        Raises on a non-2xx response (401 = bad/missing key; 402 issues = payment failure).
        """
        body = {
            "agent_id": agent_id,
            "action": action,
            "decision": decision,
            "fields": fields,
            "reasoning_trace": reasoning_trace or [],
        }
        return self._audit_x402(body) if self.billing == "x402" else self._audit_api_key(body)

    def _audit_api_key(self, body: dict) -> dict:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self.base_url}/v1/audit",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            return resp.json()

    def _audit_x402(self, body: dict) -> dict:
        session = self._ensure_x402_session()
        payload = {"org_id": self.org_id, **body}
        resp = session.post(f"{self.base_url}/v1/audit/x402", json=payload, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def _ensure_x402_session(self):
        if self._x402_session is not None:
            return self._x402_session
        import algosdk
        from x402 import x402ClientSync
        from x402.http.clients import x402_requests
        from x402.mechanisms.avm.exact import ExactAvmScheme

        sk = algosdk.mnemonic.to_private_key(self._x402_mnemonic)
        address = algosdk.account.address_from_private_key(sk)
        client = x402ClientSync()
        client.register("algorand:*", ExactAvmScheme(signer=_AlgorandSigner(sk, address), algod_url=self._algod_url))
        self._x402_session = x402_requests(client)
        return self._x402_session

    def capture(self, agent_id: str, action: str):
        """
        Decorator: audit a decision function's result automatically (either billing mode).

        The wrapped function must return {"decision": str, "fields": dict,
        optional "reasoning_trace": list}. The audit result is attached under "audit".
        """
        def decorator(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                out = fn(*args, **kwargs)
                if not isinstance(out, dict) or "decision" not in out or "fields" not in out:
                    raise ValueError("@capture-decorated function must return {'decision': ..., 'fields': {...}}")
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
