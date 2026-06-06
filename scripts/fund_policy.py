"""
Top up the PolicyContract app account with ALGO for box-storage MBR.

The contract's minimum balance grows with every onboarded org/agent/rule (each box
raises MBR). If onboarding fails with "balance ... below min ...", run this.

Usage: python scripts/fund_policy.py [algos]   (default 2)
Note: the deployer wallet must itself be above its own min balance — if it's drained,
fund the deployer from https://bank.testnet.algorand.network first.
"""

import os
import sys

from algosdk import account, logic, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

ALGOS = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")


def main() -> None:
    app_id = int(os.getenv("POLICY_APP_ID", "0"))
    if not app_id:
        raise SystemExit("POLICY_APP_ID not set in .env")
    sk = mnemonic.to_private_key(os.getenv("DEPLOYER_MNEMONIC"))
    addr = account.address_from_private_key(sk)
    client = algod.AlgodClient("", ALGOD_URL)
    app_addr = logic.get_application_address(app_id)

    txn = transaction.PaymentTxn(addr, client.suggested_params(), app_addr, int(ALGOS * 1_000_000))
    tx_id = client.send_transaction(txn.sign(sk))
    transaction.wait_for_confirmation(client, tx_id, 4)

    info = client.account_info(app_addr)
    headroom = (info["amount"] - info["min-balance"]) / 1e6
    print(f"Funded PolicyContract {app_addr} with {ALGOS} ALGO  (tx {tx_id})")
    print(f"  balance={info['amount']/1e6}  min={info['min-balance']/1e6}  headroom={headroom} ALGO")


if __name__ == "__main__":
    main()
