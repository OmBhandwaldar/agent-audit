"""
Top up the AnchorContract with ALGO so it can pay box min-balance for new batches.

Each Merkle root anchored creates a new box in the AnchorContract's storage,
which raises the contract account's required minimum balance. After many
batches the contract runs low and submit_root inner txs start failing with
"balance X below min Y".

Run this when /api/batch/submit returns:
    "account POWW... balance X below min Y"

Sends ALGO from the deployer wallet to the AnchorContract address.
"""

import os
import sys

from algosdk import account, logic, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
ANCHOR_APP_ID = int(os.getenv("ANCHOR_APP_ID", "0"))
POLICY_APP_ID = int(os.getenv("POLICY_APP_ID", "0"))

# 2 ALGO covers ~500 more batch boxes — generous headroom for demo + soak.
DEFAULT_FUND_MICROALGO = 2_000_000


def fund(client, deployer_key: str, deployer_address: str,
         target_address: str, label: str, amount: int) -> None:
    before = client.account_info(target_address)["amount"] / 1e6
    print(f"\n{label}: {target_address}")
    print(f"  ALGO before: {before}")
    params = client.suggested_params()
    txn = transaction.PaymentTxn(
        sender=deployer_address,
        sp=params,
        receiver=target_address,
        amt=amount,
    )
    tx_id = client.send_transaction(txn.sign(deployer_key))
    transaction.wait_for_confirmation(client, tx_id, 4)
    after = client.account_info(target_address)["amount"] / 1e6
    print(f"  Sent:        {amount / 1e6} ALGO")
    print(f"  ALGO after:  {after}  (TX: {tx_id})")


def main() -> None:
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if ANCHOR_APP_ID == 0 or POLICY_APP_ID == 0:
        raise RuntimeError("ANCHOR_APP_ID and POLICY_APP_ID must be set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    anchor_address = logic.get_application_address(ANCHOR_APP_ID)
    policy_address = logic.get_application_address(POLICY_APP_ID)

    client = algod.AlgodClient("", ALGOD_URL)

    print(f"Deployer: {deployer_address}")
    print(f"  ALGO:   {client.account_info(deployer_address)['amount'] / 1e6}")

    fund(client, deployer_key, deployer_address,
         anchor_address, "AnchorContract", DEFAULT_FUND_MICROALGO)
    fund(client, deployer_key, deployer_address,
         policy_address, "PolicyContract", DEFAULT_FUND_MICROALGO)


if __name__ == "__main__":
    main()
