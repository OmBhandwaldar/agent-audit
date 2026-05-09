"""
Deploy AnchorContract only (Phase 2).

Run this after PolicyContract is already deployed and POLICY_APP_ID is in .env.
Saves ANCHOR_APP_ID to .env on success.

Usage:
  bash scripts/compile.sh contracts/anchor_contract.py
  python scripts/deploy_anchor.py
"""

import base64
import os
import re
import struct
import sys

from algosdk import abi, account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")

APPROVAL_PATH = "contracts/artifacts/AnchorContract.approval.teal"
CLEAR_PATH = "contracts/artifacts/AnchorContract.clear.teal"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def get_algod_client() -> algod.AlgodClient:
    """Return a connected algod client for testnet."""
    return algod.AlgodClient("", ALGOD_URL)


def compile_teal(client: algod.AlgodClient, teal_source: str) -> bytes:
    """Compile TEAL source string to bytecode via algod."""
    result = client.compile(teal_source)
    return base64.b64decode(result["result"])


def update_env(key: str, value: str) -> None:
    """Write or update a key=value line in .env."""
    with open(ENV_PATH) as f:
        content = f.read()
    pattern = rf"^{key}=.*"
    replacement = f"{key}={value}"
    if re.search(pattern, content, re.MULTILINE):
        updated = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    else:
        updated = content.rstrip("\n") + f"\n{replacement}\n"
    with open(ENV_PATH, "w") as f:
        f.write(updated)
    print(f".env updated: {key}={value}")


def main() -> None:
    """Deploy AnchorContract and save App ID to .env."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")

    if not os.path.exists(APPROVAL_PATH):
        raise FileNotFoundError(
            f"Artifact missing: {APPROVAL_PATH}\n"
            "Run: bash scripts/compile.sh contracts/anchor_contract.py"
        )

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    account_info = client.account_info(deployer_address)
    balance_algo = account_info["amount"] / 1_000_000
    print(f"Deployer: {deployer_address}")
    print(f"Balance:  {balance_algo:.3f} ALGO")

    with open(APPROVAL_PATH) as f:
        approval_teal = f.read()
    with open(CLEAR_PATH) as f:
        clear_teal = f.read()

    approval = compile_teal(client, approval_teal)
    clear = compile_teal(client, clear_teal)

    params = client.suggested_params()

    # No global state — only box storage for Merkle roots
    global_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)
    local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    # ABI-encode initialize()void — just the method selector
    selector = abi.Method.from_signature("initialize()void").get_selector()

    txn = transaction.ApplicationCreateTxn(
        sender=deployer_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=global_schema,
        local_schema=local_schema,
        app_args=[selector],
        extra_pages=1,
    )

    signed = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed)
    print(f"\nTX sent: {tx_id}")

    result = transaction.wait_for_confirmation(client, tx_id, 4)
    app_id = result["application-index"]

    print(f"✅ AnchorContract deployed!")
    print(f"   App ID:   {app_id}")
    print(f"   TX ID:    {tx_id}")
    print(f"   Explorer: https://testnet.explorer.perawallet.app/application/{app_id}")

    update_env("ANCHOR_APP_ID", str(app_id))

    print("\nAnchorContract is ready — no further setup needed.")
    print("(It only stores Merkle roots in box storage; no ASA, no vendors.)")


if __name__ == "__main__":
    main()
