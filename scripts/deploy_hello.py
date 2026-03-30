"""
Deploy HelloWorld contract to testnet — Day 1 sanity check.
Confirms Algokit deploy pipeline works before writing the real contract.

Usage: python scripts/deploy_hello.py
"""

import os
from algosdk import account, mnemonic
from algosdk.v2client import algod
from algosdk import transaction
from dotenv import load_dotenv

load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")

APPROVAL_TEAL_PATH = "contracts/artifacts/HelloWorld.approval.teal"
CLEAR_TEAL_PATH = "contracts/artifacts/HelloWorld.clear.teal"


def get_algod_client() -> algod.AlgodClient:
    """Return a connected algod client for testnet."""
    return algod.AlgodClient("", ALGOD_URL)


def compile_teal(client: algod.AlgodClient, teal_source: str) -> bytes:
    """Compile TEAL source to bytecode via algod."""
    result = client.compile(teal_source)
    import base64
    return base64.b64decode(result["result"])


def deploy_hello_world(client: algod.AlgodClient, deployer_key: str, deployer_address: str) -> int:
    """
    Deploy HelloWorld contract to testnet.
    Returns the app ID.
    """
    with open(APPROVAL_TEAL_PATH, "r") as f:
        approval_teal = f.read()
    with open(CLEAR_TEAL_PATH, "r") as f:
        clear_teal = f.read()

    approval_program = compile_teal(client, approval_teal)
    clear_program = compile_teal(client, clear_teal)

    params = client.suggested_params()

    txn = transaction.ApplicationCreateTxn(
        sender=deployer_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_program,
        clear_program=clear_program,
        global_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
        local_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    print(f"Transaction sent: {tx_id}")

    result = transaction.wait_for_confirmation(client, tx_id, 4)
    app_id = result["application-index"]
    print(f"HelloWorld deployed!")
    print(f"App ID:   {app_id}")
    print(f"TX ID:    {tx_id}")
    print(f"Explorer: https://testnet.explorer.perawallet.app/application/{app_id}")
    return app_id


def main() -> None:
    """Entry point: deploy hello world and confirm it's live."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    print(f"Deployer: {deployer_address}")

    client = get_algod_client()
    app_id = deploy_hello_world(client, deployer_key, deployer_address)
    print(f"\nDay 1 deploy check: PASSED ✅")
    print(f"Toolchain is working. App ID {app_id} is live on testnet.")


if __name__ == "__main__":
    main()
