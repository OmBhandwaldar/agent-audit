"""
Seed the on-chain vendor whitelist on the Phase 2 PolicyContract.

Calls add_vendor() for VENDOR_001 and VENDOR_002.
Run once after deploy_phase2.py + opt_in_asa_phase2.py.

Usage:
    python scripts/seed_vendors_v2.py

Expected output:
    Seeding vendor whitelist on PolicyContract (App ID: XXXX)...
    [OK] VENDOR_001 added (TX: ...)
    [OK] VENDOR_002 added (TX: ...)
    Done. 2/2 vendors seeded.
    VENDOR_999 is intentionally NOT seeded — use for rejection demos.
"""

import hashlib
import os
import struct
import sys
import time

from algosdk import abi, account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
POLICY_APP_ID = int(os.getenv("POLICY_APP_ID", "0"))

APPROVED_VENDORS = ["VENDOR_001", "VENDOR_002"]


def get_algod_client() -> algod.AlgodClient:
    """Return a connected algod client for testnet."""
    return algod.AlgodClient("", ALGOD_URL)


def encode_arc4_string(value: str) -> bytes:
    """ARC4-encode a string: 2-byte big-endian length prefix + UTF-8 bytes."""
    encoded = value.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def compute_vendor_box_key(vendor_id: str) -> bytes:
    """
    Compute the box key for a vendor: sha256(arc4_encoded_vendor_id).
    Matches the contract: op.sha256(vendor_id.bytes) with key_prefix=b"v:".
    """
    return hashlib.sha256(encode_arc4_string(vendor_id)).digest()


def add_vendor(
    client: algod.AlgodClient,
    deployer_key: str,
    deployer_address: str,
    vendor_id: str,
) -> str:
    """
    Call add_vendor(vendor_id) on the PolicyContract.

    Returns the confirmed transaction ID.
    """
    params = client.suggested_params()

    # ABI-encode add_vendor(string)void
    selector = abi.Method.from_signature("add_vendor(string)void").get_selector()
    encoded_vendor = encode_arc4_string(vendor_id)

    # Box key for this vendor (used in boxes array for MBR)
    vendor_box_key = compute_vendor_box_key(vendor_id)
    box_ref = (POLICY_APP_ID, b"v:" + vendor_box_key)

    txn = transaction.ApplicationNoOpTxn(
        sender=deployer_address,
        sp=params,
        index=POLICY_APP_ID,
        app_args=[selector, encoded_vendor],
        boxes=[box_ref],
    )

    signed = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed)
    transaction.wait_for_confirmation(client, tx_id, 4)
    return tx_id


def main() -> None:
    """Seed all approved vendors into the Phase 2 PolicyContract whitelist."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if POLICY_APP_ID == 0:
        raise RuntimeError("POLICY_APP_ID not set in .env — run deploy_phase2.py first")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    print(f"\nSeeding vendor whitelist on PolicyContract (App ID: {POLICY_APP_ID})...")

    success_count = 0
    for vendor_id in APPROVED_VENDORS:
        try:
            tx_id = add_vendor(client, deployer_key, deployer_address, vendor_id)
            print(f"  [OK] {vendor_id} added (TX: {tx_id})")
            success_count += 1
            time.sleep(1)  # brief pause between txs
        except Exception as e:
            print(f"  [FAIL] {vendor_id} failed: {e}")

    print(f"\nDone. {success_count}/{len(APPROVED_VENDORS)} vendors seeded.")
    print("VENDOR_999 is intentionally NOT seeded — use for rejection demos.\n")


if __name__ == "__main__":
    main()
