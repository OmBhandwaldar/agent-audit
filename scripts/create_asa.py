"""
Create the AgentAudit Compliance Receipt ASA on Algorand Testnet.
Run once on Day 1. Saves the ASA ID to .env after creation.

Usage: python scripts/create_asa.py
"""

import os
import re
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")

ASA_NAME = "AgentAudit Compliance Receipt"
ASA_UNIT = "AACR"
ASA_TOTAL = 1_000_000
ASA_DECIMALS = 0


def get_algod_client() -> algod.AlgodClient:
    """Return a connected algod client for testnet."""
    return algod.AlgodClient("", ALGOD_URL)


def create_compliance_asa(client: algod.AlgodClient, deployer_key: str, deployer_address: str) -> int:
    """
    Create the non-transferable compliance receipt ASA.
    Returns the ASA ID.
    """
    params = client.suggested_params()

    txn = transaction.AssetConfigTxn(
        sender=deployer_address,
        sp=params,
        total=ASA_TOTAL,
        decimals=ASA_DECIMALS,
        default_frozen=True,
        unit_name=ASA_UNIT,
        asset_name=ASA_NAME,
        manager=deployer_address,
        reserve=deployer_address,
        freeze=deployer_address,
        clawback=deployer_address,  # Will update to contract address after deploy
        strict_empty_address_check=False,
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    print(f"Transaction sent: {tx_id}")

    result = transaction.wait_for_confirmation(client, tx_id, 4)
    asa_id = result["asset-index"]
    print(f"ASA created successfully!")
    print(f"ASA ID:   {asa_id}")
    print(f"TX ID:    {tx_id}")
    print(f"Explorer: https://testnet.explorer.perawallet.app/asset/{asa_id}")
    return asa_id


def save_asa_id_to_env(asa_id: int) -> None:
    """Write COMPLIANCE_ASA_ID into the existing .env file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path, "r") as f:
        content = f.read()

    updated = re.sub(r"COMPLIANCE_ASA_ID=.*", f"COMPLIANCE_ASA_ID={asa_id}", content)

    with open(env_path, "w") as f:
        f.write(updated)

    print(f".env updated with COMPLIANCE_ASA_ID={asa_id}")


def main() -> None:
    """Entry point: create ASA and save ID to .env."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    print(f"Deployer: {deployer_address}")

    client = get_algod_client()

    account_info = client.account_info(deployer_address)
    balance_algo = account_info["amount"] / 1_000_000
    print(f"Balance:  {balance_algo} ALGO")

    if balance_algo < 0.5:
        raise RuntimeError(f"Insufficient balance: {balance_algo} ALGO. Fund at https://bank.testnet.algorand.network")

    asa_id = create_compliance_asa(client, deployer_key, deployer_address)
    save_asa_id_to_env(asa_id)


if __name__ == "__main__":
    main()
