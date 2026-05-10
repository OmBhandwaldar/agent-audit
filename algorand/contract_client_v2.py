"""
Algorand contract client for AgentAudit Phase 2.

Handles all interaction with the deployed PolicyContract and AnchorContract:
  - submit_policy_check() — call check_and_mint on PolicyContract
  - submit_anchor_root()  — call submit_root on AnchorContract
  - get_anchor_root()     — read stored Merkle root by batch ID
  - add_vendor_v2()       — add a vendor to the PolicyContract whitelist
"""

import base64
import hashlib
import logging
import os
import struct

from algosdk import abi, account, mnemonic, transaction
from dotenv import load_dotenv

from algorand.client import get_algod_client

load_dotenv()

logger = logging.getLogger(__name__)

DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
POLICY_APP_ID = int(os.getenv("POLICY_APP_ID", "0"))
ANCHOR_APP_ID = int(os.getenv("ANCHOR_APP_ID", "0"))
COMPLIANCE_ASA_ID = int(os.getenv("COMPLIANCE_ASA_ID", "0"))

# check_and_mint triggers one inner ASA transfer — outer tx must cover both fees
POLICY_CHECK_FEE = 2000


class PolicyCheckResult:
    """Result returned from a successful submit_policy_check call."""

    def __init__(self, tx_id: str, policy_result: str, asa_minted: bool) -> None:
        self.tx_id = tx_id
        self.policy_result = policy_result
        self.asa_minted = asa_minted


def _encode_string(value: str) -> bytes:
    """
    ARC4-encode a string: 2-byte big-endian length prefix + UTF-8 content.
    Matches arc4.String.bytes in the PuyaPy contract.
    """
    encoded = value.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def _compute_box_key(value: str, prefix: bytes) -> bytes:
    """
    Compute a box key: prefix + sha256(arc4_encoded_value).
    Matches op.sha256(x.bytes) in the PuyaPy contract with BoxMap key_prefix.

    Args:
        value: The string to hash (vendor_id, batch_id, etc.).
        prefix: The BoxMap key_prefix (b"v:" for vendors, b"root:" for roots).
    """
    hashed = hashlib.sha256(_encode_string(value)).digest()
    return prefix + hashed


def _decode_arc4_string(raw: bytes) -> str:
    """
    Decode an ARC4-encoded string from raw bytes.
    Strips the 2-byte length prefix and decodes UTF-8 content.
    """
    if len(raw) < 2:
        return ""
    length = struct.unpack(">H", raw[:2])[0]
    return raw[2 : 2 + length].decode("utf-8")


def _parse_policy_result(policy_result: str) -> dict:
    """
    Parse "amount:pass|vendor:pass" into {"amount_check": "pass", "vendor_check": "pass"}.

    Args:
        policy_result: The policy result string from the contract.
    """
    checks: dict = {}
    for part in policy_result.split("|"):
        if ":" in part:
            key, value = part.split(":", 1)
            checks[f"{key}_check"] = value
    return checks


async def submit_policy_check(
    action_id: str,
    ipfs_hash: str,
    amount: int,
    vendor_id: str,
    agent_id: str,
    timestamp: int,
) -> PolicyCheckResult:
    """
    Call check_and_mint on PolicyContract.

    Checks amount and vendor policies. Mints 1 AACR to caller if both pass.
    Does NOT store the audit record on-chain — records go to the Merkle batcher.

    Args:
        action_id: Unique identifier for this audit event (for caller tracking).
        ipfs_hash: SHA256 hex of the IPFS CID for the encrypted decision JSON.
        amount: Payment amount evaluated by the agent.
        vendor_id: Vendor identifier to check against the whitelist.
        agent_id: Identifier of the AI agent that made the decision.
        timestamp: Unix timestamp of the agent decision.

    Returns:
        PolicyCheckResult with tx_id, policy_result, and asa_minted flag.

    Raises:
        RuntimeError: If the transaction fails or required env vars are missing.
    """
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if POLICY_APP_ID == 0:
        raise RuntimeError("POLICY_APP_ID not set in .env")
    if COMPLIANCE_ASA_ID == 0:
        raise RuntimeError("COMPLIANCE_ASA_ID not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(
        "check_and_mint(string,string,uint64,string,string,uint64)string"
    ).get_selector()

    app_args = [
        selector,
        _encode_string(action_id),
        _encode_string(ipfs_hash),
        struct.pack(">Q", amount),
        _encode_string(vendor_id),
        _encode_string(agent_id),
        struct.pack(">Q", timestamp),
    ]

    vendor_box_key = _compute_box_key(vendor_id, b"v:")

    params = client.suggested_params()
    params.flat_fee = True
    params.fee = POLICY_CHECK_FEE

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=POLICY_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args,
        foreign_assets=[COMPLIANCE_ASA_ID],
        boxes=[
            (POLICY_APP_ID, vendor_box_key),
        ],
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    logger.info("submit_policy_check TX sent: %s", tx_id)

    try:
        result = transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"submit_policy_check transaction failed (TX: {tx_id}): {e}")

    logger.info("submit_policy_check confirmed in round %s", result.get("confirmed-round"))

    # Parse the ABI return value — last log entry contains the encoded result
    logs = result.get("logs", [])
    policy_result = "amount:fail|vendor:fail"
    if logs:
        raw = base64.b64decode(logs[-1])
        # ARC4 return prefix is 0x151f7c75 (4 bytes), followed by encoded string
        if len(raw) > 6:
            policy_result = _decode_arc4_string(raw[4:])

    asa_minted = policy_result == "amount:pass|vendor:pass"

    return PolicyCheckResult(
        tx_id=tx_id,
        policy_result=policy_result,
        asa_minted=asa_minted,
    )


async def submit_anchor_root(
    batch_id: str,
    merkle_root: str,
    leaf_count: int,
    timestamp: int,
) -> str:
    """
    Call submit_root on AnchorContract to store a Merkle root on-chain.

    Only the contract creator (batcher service wallet) can submit roots.

    Args:
        batch_id: Unique batch identifier (e.g. "batch_1746543300_8821").
        merkle_root: Hex-encoded SHA256 Merkle root of all leaves in the batch.
        leaf_count: Number of audit decisions included in this batch.
        timestamp: Unix timestamp when the batch was built.

    Returns:
        Transaction ID of the confirmed submit_root call.

    Raises:
        RuntimeError: If the transaction fails or required env vars are missing.
    """
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if ANCHOR_APP_ID == 0:
        raise RuntimeError("ANCHOR_APP_ID not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(
        "submit_root(string,string,uint64,uint64)void"
    ).get_selector()

    app_args = [
        selector,
        _encode_string(batch_id),
        _encode_string(merkle_root),
        struct.pack(">Q", leaf_count),
        struct.pack(">Q", timestamp),
    ]

    root_box_key = _compute_box_key(batch_id, b"root:")

    params = client.suggested_params()

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=ANCHOR_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args,
        boxes=[
            (ANCHOR_APP_ID, root_box_key),
        ],
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    logger.info("submit_anchor_root TX sent: %s", tx_id)

    try:
        transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"submit_anchor_root transaction failed (TX: {tx_id}): {e}")

    logger.info("submit_anchor_root confirmed — batch: %s, root: %s", batch_id, merkle_root)
    return tx_id


async def get_anchor_root(batch_id: str) -> str:
    """
    Retrieve the stored Merkle root from AnchorContract by batch ID.

    Args:
        batch_id: The batch ID used when submit_root was called.

    Returns:
        Hex-encoded SHA256 Merkle root string.

    Raises:
        RuntimeError: If the contract call fails or batch is not found.
    """
    if ANCHOR_APP_ID == 0:
        raise RuntimeError("ANCHOR_APP_ID not set in .env")
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(
        "get_root(string)string"
    ).get_selector()

    root_box_key = _compute_box_key(batch_id, b"root:")

    params = client.suggested_params()

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=ANCHOR_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[selector, _encode_string(batch_id)],
        boxes=[(ANCHOR_APP_ID, root_box_key)],
    )

    signed_txn = txn.sign(deployer_key)

    try:
        tx_id = client.send_transaction(signed_txn)
        result = transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"get_anchor_root failed for batch_id '{batch_id}': {e}")

    logs = result.get("logs", [])
    if not logs:
        raise RuntimeError(f"get_anchor_root: no return value for batch_id '{batch_id}'")

    raw = base64.b64decode(logs[-1])
    if len(raw) <= 6:
        raise RuntimeError(f"get_anchor_root: malformed return for batch_id '{batch_id}'")

    return _decode_arc4_string(raw[4:])


async def add_vendor_v2(vendor_id: str) -> str:
    """
    Add a vendor to the PolicyContract on-chain approved whitelist.

    Only callable by the contract creator (uses DEPLOYER_MNEMONIC).
    Used by scripts/seed_vendors_v2.py to populate the whitelist after redeploy.

    Args:
        vendor_id: Vendor identifier string to approve (e.g. "VENDOR_001").

    Returns:
        Transaction ID of the confirmed add_vendor call.

    Raises:
        RuntimeError: If the transaction fails or required env vars are missing.
    """
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if POLICY_APP_ID == 0:
        raise RuntimeError("POLICY_APP_ID not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature("add_vendor(string)void").get_selector()

    vendor_box_key = _compute_box_key(vendor_id, b"v:")

    params = client.suggested_params()

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=POLICY_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[selector, _encode_string(vendor_id)],
        boxes=[(POLICY_APP_ID, vendor_box_key)],
    )

    signed_txn = txn.sign(deployer_key)

    try:
        tx_id = client.send_transaction(signed_txn)
        transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"add_vendor_v2 failed for vendor '{vendor_id}': {e}")

    logger.info("Vendor added to PolicyContract: %s (TX: %s)", vendor_id, tx_id)
    return tx_id
