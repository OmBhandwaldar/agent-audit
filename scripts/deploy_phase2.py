"""
Deploy Phase 2 contracts (PolicyContract + AnchorContract) to Algorand Testnet.

Steps performed:
  1. Compile both contracts via puyapy (same compile.sh pipeline)
  2. Deploy PolicyContract — calls initialize(compliance_asa_id, policy_limit)
  3. Deploy AnchorContract — calls initialize()
  4. Save POLICY_APP_ID and ANCHOR_APP_ID to .env

Run AFTER compile.sh produces fresh artifacts for both contracts.

Usage:
  bash scripts/compile.sh contracts/policy_contract.py
  bash scripts/compile.sh contracts/anchor_contract.py
  python scripts/deploy_phase2.py
"""

import base64
import os
import re
import struct
import sys

from algosdk import abi, account, mnemonic, transaction
from algosdk.logic import get_application_address
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
COMPLIANCE_ASA_ID = int(os.getenv("COMPLIANCE_ASA_ID", "0"))
POLICY_LIMIT = int(os.getenv("POLICY_LIMIT", "5000"))

ARTIFACTS_DIR = "contracts/artifacts"

POLICY_APPROVAL_PATH = f"{ARTIFACTS_DIR}/PolicyContract.approval.teal"
POLICY_CLEAR_PATH = f"{ARTIFACTS_DIR}/PolicyContract.clear.teal"

ANCHOR_APPROVAL_PATH = f"{ARTIFACTS_DIR}/AnchorContract.approval.teal"
ANCHOR_CLEAR_PATH = f"{ARTIFACTS_DIR}/AnchorContract.clear.teal"

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_algod_client() -> algod.AlgodClient:
    """Return a connected algod client for testnet."""
    return algod.AlgodClient("", ALGOD_URL)


def compile_teal(client: algod.AlgodClient, teal_source: str) -> bytes:
    """Compile TEAL source string to bytecode via algod."""
    result = client.compile(teal_source)
    return base64.b64decode(result["result"])


def load_and_compile(client: algod.AlgodClient, approval_path: str, clear_path: str) -> tuple[bytes, bytes]:
    """Load TEAL files and compile to bytecode."""
    if not os.path.exists(approval_path):
        raise FileNotFoundError(
            f"Artifact not found: {approval_path}\n"
            "Run: bash scripts/compile.sh contracts/policy_contract.py"
        )
    if not os.path.exists(clear_path):
        raise FileNotFoundError(
            f"Artifact not found: {clear_path}\n"
            "Run: bash scripts/compile.sh contracts/anchor_contract.py"
        )

    with open(approval_path) as f:
        approval_teal = f.read()
    with open(clear_path) as f:
        clear_teal = f.read()

    return compile_teal(client, approval_teal), compile_teal(client, clear_teal)


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


def wait_and_get_app_id(client: algod.AlgodClient, tx_id: str) -> int:
    """Wait for confirmation and return the deployed app ID."""
    result = transaction.wait_for_confirmation(client, tx_id, 4)
    return result["application-index"]


# ---------------------------------------------------------------------------
# Deploy PolicyContract
# ---------------------------------------------------------------------------


def deploy_policy_contract(
    client: algod.AlgodClient,
    deployer_key: str,
    deployer_address: str,
) -> int:
    """
    Deploy PolicyContract and call initialize(compliance_asa_id, policy_limit).

    Returns the deployed App ID.
    """
    print("\n── Deploying PolicyContract ──")
    approval, clear = load_and_compile(client, POLICY_APPROVAL_PATH, POLICY_CLEAR_PATH)

    params = client.suggested_params()

    # Global state: 1 uint64 (compliance_asa_id). Policy is per-tenant in boxes now.
    global_schema = transaction.StateSchema(num_uints=1, num_byte_slices=0)
    local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    # ABI-encode initialize(uint64)void
    selector = abi.Method.from_signature("initialize(uint64)void").get_selector()
    app_args = [selector, struct.pack(">Q", COMPLIANCE_ASA_ID)]

    txn = transaction.ApplicationCreateTxn(
        sender=deployer_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=global_schema,
        local_schema=local_schema,
        app_args=app_args,
        extra_pages=1,  # extra memory for box storage (vendor whitelist)
    )

    signed = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed)
    print(f"TX sent: {tx_id}")

    app_id = wait_and_get_app_id(client, tx_id)
    print(f"✅ PolicyContract deployed!")
    print(f"   App ID:       {app_id}")
    print(f"   TX ID:        {tx_id}")
    print(f"   ASA ID set:   {COMPLIANCE_ASA_ID}")
    print(f"   Explorer:     https://testnet.explorer.perawallet.app/application/{app_id}")
    return app_id


def fund_app_account(client, deployer_key, deployer_address, app_id, microalgos=1_000_000):
    """Send ALGO to the app account so it can pay box MBR + ASA opt-in min balance."""
    app_addr = get_application_address(app_id)
    txn = transaction.PaymentTxn(deployer_address, client.suggested_params(), app_addr, microalgos)
    tx_id = client.send_transaction(txn.sign(deployer_key))
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"   Funded app {app_id} ({app_addr}) with {microalgos / 1_000_000} ALGO  TX {tx_id}")


# ---------------------------------------------------------------------------
# Deploy AnchorContract
# ---------------------------------------------------------------------------


def deploy_anchor_contract(
    client: algod.AlgodClient,
    deployer_key: str,
    deployer_address: str,
) -> int:
    """
    Deploy AnchorContract and call initialize().

    Returns the deployed App ID.
    """
    print("\n── Deploying AnchorContract ──")
    approval, clear = load_and_compile(client, ANCHOR_APPROVAL_PATH, ANCHOR_CLEAR_PATH)

    params = client.suggested_params()

    # Global state: 1 bool (initialized flag)
    global_schema = transaction.StateSchema(num_uints=1, num_byte_slices=0)
    local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    # ABI-encode initialize()void — just the method selector, no args
    selector = abi.Method.from_signature("initialize()void").get_selector()
    app_args = [selector]

    txn = transaction.ApplicationCreateTxn(
        sender=deployer_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=global_schema,
        local_schema=local_schema,
        app_args=app_args,
        extra_pages=1,  # extra memory for box storage (Merkle roots)
    )

    signed = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed)
    print(f"TX sent: {tx_id}")

    app_id = wait_and_get_app_id(client, tx_id)
    print(f"✅ AnchorContract deployed!")
    print(f"   App ID:   {app_id}")
    print(f"   TX ID:    {tx_id}")
    print(f"   Explorer: https://testnet.explorer.perawallet.app/application/{app_id}")
    return app_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Compile, deploy both contracts, save App IDs to .env."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if COMPLIANCE_ASA_ID == 0:
        raise RuntimeError("COMPLIANCE_ASA_ID not set in .env — run create_asa.py first")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)

    client = get_algod_client()

    account_info = client.account_info(deployer_address)
    balance_algo = account_info["amount"] / 1_000_000
    print(f"Deployer: {deployer_address}")
    print(f"Balance:  {balance_algo:.3f} ALGO")

    if balance_algo < 1.0:
        raise RuntimeError(
            f"Insufficient balance: {balance_algo} ALGO. "
            "Fund at https://bank.testnet.algorand.network"
        )

    # Deploy the multi-tenant PolicyContract only. AnchorContract is unchanged in this
    # phase, so its existing deployment (ANCHOR_APP_ID) is kept and old anchored batches
    # stay verifiable. Re-run deploy_anchor_contract() only if AnchorContract changes.
    print("\n═══ Deploy multi-tenant PolicyContract ═══")
    policy_app_id = deploy_policy_contract(client, deployer_key, deployer_address)
    update_env("POLICY_APP_ID", str(policy_app_id))

    print("\n── Funding PolicyContract for box storage + ASA opt-in ──")
    fund_app_account(client, deployer_key, deployer_address, policy_app_id, microalgos=1_000_000)

    print("\n═══ PolicyContract Deploy Complete ═══")
    print(f"POLICY_APP_ID = {policy_app_id}")
    print(f"ANCHOR_APP_ID = {os.getenv('ANCHOR_APP_ID')} (unchanged)")
    print("\nNext steps:")
    print("  1. python scripts/opt_in_asa_phase2.py    ← opt PolicyContract into AACR")
    print("  2. python scripts/send_aacr_to_policy.py  ← fund contract with AACR supply")
    print("  3. python scripts/check_phase1.py         ← register rules for a test org + run check_and_mint")


if __name__ == "__main__":
    main()
