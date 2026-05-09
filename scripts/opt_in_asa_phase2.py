"""
Opt the PolicyContract into the AACR compliance receipt ASA.

Must be run once after deploy_phase2.py, before sending AACR supply
to the PolicyContract address.

Usage:
    python scripts/opt_in_asa_phase2.py
"""

import os
import struct
import sys

from algosdk import abi, account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
POLICY_APP_ID = int(os.getenv("POLICY_APP_ID", "0"))
COMPLIANCE_ASA_ID = int(os.getenv("COMPLIANCE_ASA_ID", "0"))


def get_algod_client() -> algod.AlgodClient:
    """Return a connected algod client for testnet."""
    return algod.AlgodClient("", ALGOD_URL)


def get_app_address(app_id: int) -> str:
    """Derive the contract account address from App ID."""
    from algosdk import logic
    return logic.get_application_address(app_id)


def main() -> None:
    """Opt PolicyContract into AACR ASA so it can hold and send tokens."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if POLICY_APP_ID == 0:
        raise RuntimeError("POLICY_APP_ID not set in .env — run deploy_phase2.py first")
    if COMPLIANCE_ASA_ID == 0:
        raise RuntimeError("COMPLIANCE_ASA_ID not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    contract_address = get_app_address(POLICY_APP_ID)

    client = get_algod_client()

    print(f"Deployer:          {deployer_address}")
    print(f"PolicyContract:    {contract_address}")
    print(f"POLICY_APP_ID:     {POLICY_APP_ID}")
    print(f"COMPLIANCE_ASA_ID: {COMPLIANCE_ASA_ID}")

    # Step 1: Fund the contract account so it can hold an ASA (min balance = 0.2 ALGO)
    contract_info = client.account_info(contract_address)
    contract_balance = contract_info.get("amount", 0)
    print(f"\nContract balance:  {contract_balance / 1_000_000:.3f} ALGO")

    if contract_balance < 300_000:  # 0.3 ALGO — covers min balance + ASA opt-in + fees
        fund_amount = 500_000  # 0.5 ALGO
        print(f"Funding contract with 0.5 ALGO for min balance...")
        fund_params = client.suggested_params()
        fund_txn = transaction.PaymentTxn(
            sender=deployer_address,
            sp=fund_params,
            receiver=contract_address,
            amt=fund_amount,
        )
        signed_fund = fund_txn.sign(deployer_key)
        fund_tx_id = client.send_transaction(signed_fund)
        transaction.wait_for_confirmation(client, fund_tx_id, 4)
        print(f"✅ Funded contract (TX: {fund_tx_id})")
    else:
        print("Contract already funded — skipping fund step.")

    # Step 2: Call opt_in_asa() — inner tx costs an extra fee
    params = client.suggested_params()
    params.fee = 2000
    params.flat_fee = True

    # ABI-encode opt_in_asa()void — just the method selector
    selector = abi.Method.from_signature("opt_in_asa()void").get_selector()

    txn = transaction.ApplicationNoOpTxn(
        sender=deployer_address,
        sp=params,
        index=POLICY_APP_ID,
        app_args=[selector],
        foreign_assets=[COMPLIANCE_ASA_ID],
    )

    signed = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed)
    print(f"\nTX sent: {tx_id}")

    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"✅ PolicyContract opted into AACR (ASA {COMPLIANCE_ASA_ID})")
    print(f"\nNext: send AACR tokens to PolicyContract address:")
    print(f"  {contract_address}")
    print(f"\nThen: python scripts/seed_vendors_v2.py")


if __name__ == "__main__":
    main()
