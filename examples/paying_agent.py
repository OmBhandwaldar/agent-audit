"""
Example: an autonomous agent that PAYS for each audit via x402 (USDC on Algorand).

This is the Agentic Commerce loop: the agent calls the x402-gated endpoint, receives a
402 with payment requirements, auto-pays $0.01 USDC, and the audit runs — no API key,
the payment authorizes the call (the org is still declared in the body, Flavor 1).

Prerequisites (the payer wallet needs testnet USDC):
  1. Backend running with the x402 gate on:
       X402_ENABLED=true X402_RECIPIENT=<recipient_addr> uvicorn api.main:app --port 8000
  2. Recipient opted into USDC:   X402_PAYER_MNEMONIC="<recipient 25 words>" python scripts/opt_in_usdc.py
  3. Payer opted into USDC + funded with testnet USDC (Circle faucet: https://faucet.circle.com)
  4. Run:  X402_PAYER_MNEMONIC="<payer 25 words>" python examples/paying_agent.py
"""

import base64
import os

import algosdk
from x402 import x402ClientSync
from x402.http.clients import x402_requests
from x402.mechanisms.avm.exact import ExactAvmScheme

BASE_URL = os.getenv("AGENTAUDIT_URL", "http://localhost:8000")
ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
ORG_ID = os.getenv("X402_ORG_ID", "acmedemo")
AGENT_ID = os.getenv("X402_AGENT_ID", "payment_agent")


class AlgorandSigner:
    """ClientAvmSigner: signs the USDC payment transaction the facilitator settles."""

    def __init__(self, sk_b64: str, address: str) -> None:
        self._sk = sk_b64
        self._address = address

    @property
    def address(self) -> str:
        return self._address

    def sign_transactions(self, unsigned_txns, indexes_to_sign):
        signed = []
        for i, txn_bytes in enumerate(unsigned_txns):
            if i in indexes_to_sign:
                txn = algosdk.encoding.msgpack_decode(base64.b64encode(txn_bytes).decode())
                s = txn.sign(self._sk)
                signed.append(base64.b64decode(algosdk.encoding.msgpack_encode(s)))
            else:
                signed.append(None)
        return signed


def main() -> None:
    mn = os.environ.get("X402_PAYER_MNEMONIC")
    if not mn:
        raise SystemExit("Set X402_PAYER_MNEMONIC (25 words) for the paying agent's wallet")

    sk = algosdk.mnemonic.to_private_key(mn)
    address = algosdk.account.address_from_private_key(sk)

    client = x402ClientSync()
    client.register("algorand:*", ExactAvmScheme(signer=AlgorandSigner(sk, address), algod_url=ALGOD_URL))
    session = x402_requests(client)

    print(f"Paying agent {address} -> {BASE_URL}/v1/audit/x402")
    resp = session.post(
        f"{BASE_URL}/v1/audit/x402",
        json={
            "org_id": ORG_ID,
            "agent_id": AGENT_ID,
            "action": "approve_payment",
            "decision": "approved",
            "fields": {"amount": 4500, "vendor": "VENDOR_001"},
            "reasoning_trace": [{"step": 1, "tool": "pick_vendor", "args": {}, "result": "VENDOR_001"}],
        },
    )
    print("HTTP", resp.status_code)
    data = resp.json()
    print("decision:", data.get("decision"), "minted:", data.get("asa_minted"),
          "billing:", data.get("billing"), "action_id:", data.get("action_id"))


if __name__ == "__main__":
    main()
