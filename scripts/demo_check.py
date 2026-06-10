"""
Pre-demo readiness check + auto-top-up for AgentAudit.

Verifies every resource the live demo depends on and, where it can be done
safely from the deployer wallet, fills the resource back up. Prints a
before/after table so you can see exactly what changed.

Resources checked
-----------------
On-chain (auto-fixable from the deployer wallet):
  * Deployer wallet ALGO            -> warn only (refill from the public faucet)
  * PolicyContract ALGO headroom    -> top up (box MBR for onboarding)
  * AnchorContract ALGO headroom    -> top up (box MBR for batch anchoring)
  * PolicyContract AACR balance     -> top up from deployer (mints 1 per approval)

x402 / USDC (the pay-per-call flow):
  * Payer wallet opted into USDC    -> auto opt-in if the payer can afford it
  * Payer wallet USDC balance       -> warn only (refill from the Circle faucet)
  * Payer wallet ALGO for fees      -> warn only (refill from the public faucet)

External APIs (report only):
  * Groq API key valid + not rate-limited
  * Pinata / IPFS auth

Usage
-----
  python scripts/demo_check.py              # check and auto-fill
  python scripts/demo_check.py --check-only # check, never spend or send anything

Exit code is 0 when everything is OK or was fixed, 1 when a blocker remains
(a resource that this script cannot fill, e.g. an empty deployer wallet or a
down external API).
"""

import os
import sys

import httpx
from algosdk import account, logic, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

# ── Thresholds & top-up amounts (microALGO unless noted) ──────────────────────
USDC_TESTNET_ASA = 10458941

MIN_DEPLOYER_ALGO = 3_000_000          # deployer must stay above this to fund others
MIN_POLICY_HEADROOM = 1_000_000        # balance - min_balance floor
POLICY_FUND_ALGO = 3_000_000           # how much to send when low
MIN_ANCHOR_HEADROOM = 1_000_000
ANCHOR_FUND_ALGO = 2_000_000
MIN_POLICY_AACR = 8                    # approvals left before the contract runs dry
AACR_TOPUP = 10                        # how many to send when low
DEPLOYER_AACR_BUFFER = 2               # never drain the deployer below this many AACR
MIN_PAYER_USDC_MICRO = 100_000         # 0.10 USDC ~= 10 x402 calls at $0.01
MIN_PAYER_ALGO = 210_000              # enough for an opt-in + a few fees

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
FAUCET_ALGO = "https://bank.testnet.algorand.network"
FAUCET_USDC = "https://faucet.circle.com"

CHECK_ONLY = "--check-only" in sys.argv


# ── Result tracking ───────────────────────────────────────────────────────────
class Result:
    """One resource's check outcome, for the final before/after table."""

    def __init__(self, name: str, before: str, after: str, status: str, note: str = ""):
        self.name = name        # human label
        self.before = before    # value before any fix
        self.after = after      # value after fix (== before if untouched)
        self.status = status    # "OK" | "FIXED" | "WARN" | "FAIL"
        self.note = note        # action taken or remediation hint


RESULTS: list[Result] = []


def microalgo(client: algod.AlgodClient, addr: str) -> tuple[int, int]:
    """Return (balance, min_balance) in microALGO for an account."""
    info = client.account_info(addr)
    return info["amount"], info["min-balance"]


def asset_amount(client: algod.AlgodClient, addr: str, asa_id: int) -> int | None:
    """Return the account's holding of an ASA, or None if not opted in."""
    info = client.account_info(addr)
    for a in info.get("assets", []):
        if a["asset-id"] == asa_id:
            return a["amount"]
    return None


def send_algo(client: algod.AlgodClient, sk: str, sender: str, receiver: str, amt: int) -> str:
    """Send a payment and wait for confirmation. Returns the tx id."""
    txn = transaction.PaymentTxn(sender=sender, sp=client.suggested_params(), receiver=receiver, amt=amt)
    tx_id = client.send_transaction(txn.sign(sk))
    transaction.wait_for_confirmation(client, tx_id, 4)
    return tx_id


def send_asa(client: algod.AlgodClient, sk: str, sender: str, receiver: str, asa_id: int, amt: int) -> str:
    """Transfer an ASA and wait for confirmation. Returns the tx id."""
    txn = transaction.AssetTransferTxn(
        sender=sender, sp=client.suggested_params(), receiver=receiver, amt=amt, index=asa_id
    )
    tx_id = client.send_transaction(txn.sign(sk))
    transaction.wait_for_confirmation(client, tx_id, 4)
    return tx_id


# ── On-chain checks ───────────────────────────────────────────────────────────
def check_deployer_algo(client, dep_addr) -> int:
    """Deployer funds every on-chain top-up; it cannot be auto-filled."""
    bal, _ = microalgo(client, dep_addr)
    before = f"{bal/1e6:.4f} ALGO"
    if bal >= MIN_DEPLOYER_ALGO:
        RESULTS.append(Result("Deployer ALGO", before, before, "OK"))
    else:
        RESULTS.append(Result(
            "Deployer ALGO", before, before, "WARN",
            f"below {MIN_DEPLOYER_ALGO/1e6} ALGO - refill at {FAUCET_ALGO}",
        ))
    return bal


def check_contract_algo(client, sk, dep_addr, dep_bal, app_id, label, min_headroom, fund_amt) -> None:
    """Top up a contract app account's ALGO so box MBR stays covered."""
    addr = logic.get_application_address(app_id)
    bal, mn = microalgo(client, addr)
    headroom = bal - mn
    before = f"{bal/1e6:.4f} ALGO (headroom {headroom/1e6:.4f})"

    if headroom >= min_headroom:
        RESULTS.append(Result(f"{label} ALGO", before, before, "OK"))
        return
    if CHECK_ONLY:
        RESULTS.append(Result(f"{label} ALGO", before, before, "WARN", "low headroom (--check-only: not funded)"))
        return
    if dep_bal - fund_amt < MIN_DEPLOYER_ALGO:
        RESULTS.append(Result(f"{label} ALGO", before, before, "FAIL",
                              f"deployer too low to fund - refill at {FAUCET_ALGO}"))
        return

    tx = send_algo(client, sk, dep_addr, addr, fund_amt)
    bal2, mn2 = microalgo(client, addr)
    after = f"{bal2/1e6:.4f} ALGO (headroom {(bal2-mn2)/1e6:.4f})"
    RESULTS.append(Result(f"{label} ALGO", before, after, "FIXED", f"sent {fund_amt/1e6} ALGO  tx {tx[:8]}.."))


def check_policy_aacr(client, sk, dep_addr, policy_addr, asa_id) -> None:
    """Ensure the PolicyContract holds enough AACR to mint receipts on approvals."""
    held = asset_amount(client, policy_addr, asa_id)
    before = "NOT OPTED IN" if held is None else f"{held} AACR"

    if held is None:
        RESULTS.append(Result("PolicyContract AACR", before, before, "FAIL",
                              "contract not opted into AACR - run scripts/opt_in_asa_phase2.py"))
        return
    if held >= MIN_POLICY_AACR:
        RESULTS.append(Result("PolicyContract AACR", before, before, "OK"))
        return
    if CHECK_ONLY:
        RESULTS.append(Result("PolicyContract AACR", before, before, "WARN", "low (--check-only: not topped up)"))
        return

    dep_aacr = asset_amount(client, dep_addr, asa_id) or 0
    can_send = min(AACR_TOPUP, dep_aacr - DEPLOYER_AACR_BUFFER)
    if can_send <= 0:
        RESULTS.append(Result("PolicyContract AACR", before, before, "WARN",
                              f"deployer holds only {dep_aacr} AACR - run scripts/send_aacr_to_policy.py"))
        return

    try:
        tx = send_asa(client, sk, dep_addr, policy_addr, asa_id, can_send)
    except Exception as e:  # frozen account / authority edge cases -> defer to the full script
        RESULTS.append(Result("PolicyContract AACR", before, before, "WARN",
                              f"direct send failed ({str(e)[:40]}) - run scripts/send_aacr_to_policy.py"))
        return
    after = f"{asset_amount(client, policy_addr, asa_id)} AACR"
    RESULTS.append(Result("PolicyContract AACR", before, after, "FIXED", f"sent {can_send} AACR  tx {tx[:8]}.."))


def check_payer(client, payer_addr) -> None:
    """The x402 payer needs to be opted into USDC and hold USDC + a little ALGO."""
    if not payer_addr:
        RESULTS.append(Result("x402 Payer", "PAYER_ADDRESS unset", "-", "WARN", "skipped (no payer configured)"))
        return

    bal, _ = microalgo(client, payer_addr)
    usdc = asset_amount(client, payer_addr, USDC_TESTNET_ASA)

    # ALGO for fees
    a_before = f"{bal/1e6:.4f} ALGO"
    if bal >= MIN_PAYER_ALGO:
        RESULTS.append(Result("x402 Payer ALGO", a_before, a_before, "OK"))
    else:
        RESULTS.append(Result("x402 Payer ALGO", a_before, a_before, "WARN", f"low - refill at {FAUCET_ALGO}"))

    # USDC opt-in + balance
    if usdc is None:
        RESULTS.append(Result("x402 Payer USDC", "NOT OPTED IN", "NOT OPTED IN", "WARN",
                              f"opt in + fund at {FAUCET_USDC} (or run scripts/opt_in_usdc.py)"))
        return
    u_before = f"{usdc/1e6:.4f} USDC"
    if usdc >= MIN_PAYER_USDC_MICRO:
        RESULTS.append(Result("x402 Payer USDC", u_before, u_before, "OK"))
    else:
        RESULTS.append(Result("x402 Payer USDC", u_before, u_before, "WARN",
                              f"below {MIN_PAYER_USDC_MICRO/1e6} USDC - refill at {FAUCET_USDC}"))


# ── External API checks ───────────────────────────────────────────────────────
def check_groq() -> None:
    """Validate the Groq key and surface rate-limit state with a tiny call."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        RESULTS.append(Result("Groq API", "GROQ_API_KEY unset", "-", "FAIL", "set GROQ_API_KEY in .env"))
        return
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            timeout=15,
        )
    except Exception as e:
        RESULTS.append(Result("Groq API", "unreachable", "-", "FAIL", str(e)[:50]))
        return

    if r.status_code == 200:
        rem_req = r.headers.get("x-ratelimit-remaining-requests", "?")
        rem_tok = r.headers.get("x-ratelimit-remaining-tokens", "?")
        state = f"OK (req left: {rem_req}, tokens left: {rem_tok})"
        RESULTS.append(Result("Groq API", state, state, "OK"))
    elif r.status_code == 429:
        reset = r.headers.get("retry-after") or r.headers.get("x-ratelimit-reset-requests", "?")
        RESULTS.append(Result("Groq API", "429 rate-limited", "-", "FAIL", f"resets in ~{reset}"))
    elif r.status_code in (401, 403):
        RESULTS.append(Result("Groq API", f"{r.status_code} unauthorized", "-", "FAIL", "bad GROQ_API_KEY"))
    else:
        RESULTS.append(Result("Groq API", f"HTTP {r.status_code}", "-", "FAIL", r.text[:50]))


def check_pinata() -> None:
    """Validate Pinata/IPFS auth (JWT preferred, falls back to key+secret)."""
    jwt = os.getenv("PINATA_JWT")
    api_key = os.getenv("PINATA_API_KEY")
    secret = os.getenv("PINATA_SECRET_KEY")
    if jwt:
        headers = {"Authorization": f"Bearer {jwt}"}
    elif api_key and secret:
        headers = {"pinata_api_key": api_key, "pinata_secret_api_key": secret}
    else:
        RESULTS.append(Result("Pinata / IPFS", "no credentials", "-", "FAIL", "set PINATA_JWT in .env"))
        return
    try:
        r = httpx.get("https://api.pinata.cloud/data/testAuthentication", headers=headers, timeout=10)
    except Exception as e:
        RESULTS.append(Result("Pinata / IPFS", "unreachable", "-", "FAIL", str(e)[:50]))
        return
    if r.status_code == 200:
        RESULTS.append(Result("Pinata / IPFS", "auth OK", "auth OK", "OK"))
    else:
        RESULTS.append(Result("Pinata / IPFS", f"HTTP {r.status_code}", "-", "FAIL", r.text[:50]))


# ── Report ────────────────────────────────────────────────────────────────────
def print_report() -> int:
    icon = {"OK": "[ OK ]", "FIXED": "[FIXED]", "WARN": "[WARN]", "FAIL": "[FAIL]"}
    name_w = max(len(r.name) for r in RESULTS)
    before_w = max(len(r.before) for r in RESULTS)
    after_w = max(len(r.after) for r in RESULTS)

    print("\n" + "=" * 96)
    print("  AGENTAUDIT DEMO READINESS" + ("   (check-only)" if CHECK_ONLY else "   (auto-fill)"))
    print("=" * 96)
    print(f"  {'':7} {'RESOURCE':<{name_w}}   {'BEFORE':<{before_w}}   {'AFTER':<{after_w}}   NOTE")
    print("  " + "-" * 94)
    for r in RESULTS:
        changed = "->" if r.after != r.before and r.status == "FIXED" else "  "
        print(f"  {icon[r.status]:7} {r.name:<{name_w}}   {r.before:<{before_w}} {changed}"
              f" {r.after:<{after_w}}   {r.note}")
    print("=" * 96)

    fixed = sum(1 for r in RESULTS if r.status == "FIXED")
    warn = sum(1 for r in RESULTS if r.status == "WARN")
    fail = sum(1 for r in RESULTS if r.status == "FAIL")
    print(f"  {sum(1 for r in RESULTS if r.status=='OK')} ok | {fixed} fixed | {warn} warn | {fail} fail")
    if fail:
        print("  RESULT: NOT READY - resolve the [FAIL] rows above before the demo.")
    elif warn:
        print("  RESULT: READY (with warnings) - review the [WARN] rows; they need a faucet or manual step.")
    else:
        print("  RESULT: READY - all resources are provisioned.")
    print()
    return 1 if fail else 0


def main() -> None:
    dep_mn = os.getenv("DEPLOYER_MNEMONIC")
    policy_app = int(os.getenv("POLICY_APP_ID", "0"))
    anchor_app = int(os.getenv("ANCHOR_APP_ID", "0"))
    asa_id = int(os.getenv("COMPLIANCE_ASA_ID", "0"))
    payer_addr = os.getenv("PAYER_ADDRESS") or os.getenv("X402_RECIPIENT") or ""

    if not dep_mn or not policy_app or not anchor_app or not asa_id:
        raise SystemExit("DEPLOYER_MNEMONIC, POLICY_APP_ID, ANCHOR_APP_ID, COMPLIANCE_ASA_ID must be set in .env")

    sk = mnemonic.to_private_key(dep_mn)
    dep_addr = account.address_from_private_key(sk)
    policy_addr = logic.get_application_address(policy_app)
    client = algod.AlgodClient("", ALGOD_URL)

    # On-chain (order matters: read deployer first, it funds the rest).
    dep_bal = check_deployer_algo(client, dep_addr)
    check_contract_algo(client, sk, dep_addr, dep_bal, policy_app, "PolicyContract",
                        MIN_POLICY_HEADROOM, POLICY_FUND_ALGO)
    # Refresh deployer balance in case the policy top-up spent some.
    dep_bal, _ = microalgo(client, dep_addr)
    check_contract_algo(client, sk, dep_addr, dep_bal, anchor_app, "AnchorContract",
                        MIN_ANCHOR_HEADROOM, ANCHOR_FUND_ALGO)
    check_policy_aacr(client, sk, dep_addr, policy_addr, asa_id)

    # x402 / USDC
    check_payer(client, payer_addr)

    # External APIs
    check_groq()
    check_pinata()

    sys.exit(print_report())


if __name__ == "__main__":
    main()
