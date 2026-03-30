"""
Deploy AuditContract to Algorand Testnet and save the App ID to .env.

Must be run AFTER compile.sh produces fresh artifacts.
Calls initialize(compliance_asa_id, policy_limit) at creation.

Usage: python scripts/deploy_contract.py
"""

import base64
import os
import re

from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
COMPLIANCE_ASA_ID = int(os.getenv("COMPLIANCE_ASA_ID", "0"))
POLICY_LIMIT = int(os.getenv("POLICY_LIMIT", "5000"))

APPROVAL_TEAL_PATH = "contracts/artifacts/AuditContract.approval.teal"
CLEAR_TEAL_PATH = "contracts/artifacts/AuditContract.clear.teal"

# Box storage budget: 8 boxes covers typical audit record size (each box ~256 bytes)
# Adjust if box_budget errors appear on submit_audit calls.
BOX_MBR_EXTRA_PAGES = 1


def get_algod_client() -> algod.AlgodClient:
    """Return a connected algod client for testnet."""
    return algod.AlgodClient("", ALGOD_URL)


def compile_teal(client: algod.AlgodClient, teal_source: str) -> bytes:
    """Compile TEAL source string to bytecode via algod."""
    result = client.compile(teal_source)
    return base64.b64decode(result["result"])


def encode_initialize_args(compliance_asa_id: int, policy_limit: int) -> list[bytes]:
    """
    ABI-encode the initialize(uint64, uint64) call arguments.

    ARC4 method selector is SHA-512/256(method_signature)[:4] — NOT plain SHA-256.
    Use algosdk.abi.Method to compute the correct selector.
    Each uint64 arg is big-endian 8 bytes.
    """
    import struct

    from algosdk import abi

    selector = abi.Method.from_signature("initialize(uint64,uint64)void").get_selector()
    arg1 = struct.pack(">Q", compliance_asa_id)
    arg2 = struct.pack(">Q", policy_limit)
    return [selector, arg1, arg2]


def deploy_audit_contract(
    client: algod.AlgodClient,
    deployer_key: str,
    deployer_address: str,
) -> int:
    """
    Deploy AuditContract and call initialize on the same transaction.

    Returns the deployed App ID.
    """
    with open(APPROVAL_TEAL_PATH, "r") as f:
        approval_teal = f.read()
    with open(CLEAR_TEAL_PATH, "r") as f:
        clear_teal = f.read()

    approval_program = compile_teal(client, approval_teal)
    clear_program = compile_teal(client, clear_teal)

    params = client.suggested_params()

    # Global state: 2 uints (compliance_asa_id, policy_limit)
    # Local state: none
    global_schema = transaction.StateSchema(num_uints=2, num_byte_slices=0)
    local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    app_args = encode_initialize_args(COMPLIANCE_ASA_ID, POLICY_LIMIT)

    txn = transaction.ApplicationCreateTxn(
        sender=deployer_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_program,
        clear_program=clear_program,
        global_schema=global_schema,
        local_schema=local_schema,
        app_args=app_args,
        extra_pages=BOX_MBR_EXTRA_PAGES,
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    print(f"Transaction sent: {tx_id}")

    result = transaction.wait_for_confirmation(client, tx_id, 4)
    app_id = result["application-index"]

    print(f"\nAuditContract deployed!")
    print(f"App ID:        {app_id}")
    print(f"TX ID:         {tx_id}")
    print(f"ASA ID set:    {COMPLIANCE_ASA_ID}")
    print(f"Policy limit:  {POLICY_LIMIT}")
    print(f"Explorer:      https://testnet.explorer.perawallet.app/application/{app_id}")
    return app_id


def save_app_id_to_env(app_id: int) -> None:
    """Write CONTRACT_APP_ID into the existing .env file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path, "r") as f:
        content = f.read()

    updated = re.sub(r"CONTRACT_APP_ID=.*", f"CONTRACT_APP_ID={app_id}", content)

    with open(env_path, "w") as f:
        f.write(updated)

    print(f".env updated with CONTRACT_APP_ID={app_id}")


def main() -> None:
    """Entry point: validate env, deploy contract, save App ID."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if COMPLIANCE_ASA_ID == 0:
        raise RuntimeError("COMPLIANCE_ASA_ID not set in .env — run create_asa.py first")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    print(f"Deployer:  {deployer_address}")

    client = get_algod_client()

    account_info = client.account_info(deployer_address)
    balance_algo = account_info["amount"] / 1_000_000
    print(f"Balance:   {balance_algo} ALGO")

    if balance_algo < 1.0:
        raise RuntimeError(
            f"Insufficient balance: {balance_algo} ALGO. "
            "Fund at https://bank.testnet.algorand.network"
        )

    app_id = deploy_audit_contract(client, deployer_key, deployer_address)
    save_app_id_to_env(app_id)


if __name__ == "__main__":
    main()
