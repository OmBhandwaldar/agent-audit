"""
Algorand contract client for AgentAudit.

Handles all interaction with the deployed AuditContract:
  - submit_audit()     — write audit record + trigger ASA transfer if both policies pass
  - get_audit_record() — read stored audit record by action ID
  - add_vendor()       — add a vendor to the on-chain whitelist (creator only)
"""

import hashlib
import logging
import os
import struct
from dataclasses import dataclass

from algosdk import abi, account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

from algorand.client import get_algod_client

load_dotenv()

logger = logging.getLogger(__name__)

DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
CONTRACT_APP_ID = int(os.getenv("CONTRACT_APP_ID", "0"))
COMPLIANCE_ASA_ID = int(os.getenv("COMPLIANCE_ASA_ID", "0"))

# submit_audit triggers one inner ASA transfer — outer tx must cover both fees
SUBMIT_AUDIT_FEE = 2000


@dataclass
class AuditSubmitResult:
    """Result returned from a successful submit_audit call."""

    tx_id: str
    policy_result: str  # "amount:pass|vendor:pass" (or "fail" per check)
    asa_minted: bool    # True if 1 AACR was transferred to caller


def _encode_string(value: str) -> bytes:
    """
    ARC4-encode a string: 2-byte big-endian length prefix + UTF-8 content.
    Matches arc4.String.bytes in the PuyaPy contract.
    """
    encoded = value.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def _compute_box_key(value: str, prefix: bytes) -> bytes:
    """
    Compute a box key for a given value with the given prefix.
    Key = prefix + sha256(arc4_encoded_value).
    Matches op.sha256(x.bytes) in the PuyaPy contract with BoxMap key_prefix.

    Args:
        value: The string to hash (action_id or vendor_id).
        prefix: The BoxMap key_prefix (b"r:" for records, b"v:" for vendors).
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


async def submit_audit(
    action_id: str,
    ipfs_hash: str,
    record: dict,
) -> AuditSubmitResult:
    """
    Submit an audit record to the AuditContract on Algorand.

    Builds and signs the ABI-encoded submit_audit app call, waits for
    confirmation, and returns the result including per-policy outcome.

    Args:
        action_id: Unique identifier for this audit event.
        ipfs_hash: SHA256 hex of the IPFS CID for the decision JSON.
        record: The full decision record dict (used to extract fields).

    Returns:
        AuditSubmitResult with tx_id, policy_result, and asa_minted flag.

    Raises:
        RuntimeError: If the transaction fails or required env vars are missing.
    """
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if CONTRACT_APP_ID == 0:
        raise RuntimeError("CONTRACT_APP_ID not set in .env")
    if COMPLIANCE_ASA_ID == 0:
        raise RuntimeError("COMPLIANCE_ASA_ID not set in .env")

    vendor_id = record.get("vendor_id", "")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(
        "submit_audit(string,string,string,string,string,uint64,uint64,string)string"
    ).get_selector()

    app_args = [
        selector,
        _encode_string(action_id),
        _encode_string(ipfs_hash),
        _encode_string(record.get("agent_id", "")),
        _encode_string(record.get("policy", "")),
        _encode_string(record.get("decision", "")),
        struct.pack(">Q", int(record.get("amount", 0))),
        struct.pack(">Q", int(record.get("timestamp", 0))),
        _encode_string(vendor_id),
    ]

    record_box_key = _compute_box_key(action_id, b"r:")
    vendor_box_key = _compute_box_key(vendor_id, b"v:")

    params = client.suggested_params()
    params.flat_fee = True
    params.fee = SUBMIT_AUDIT_FEE

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=CONTRACT_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args,
        foreign_assets=[COMPLIANCE_ASA_ID],
        boxes=[
            (CONTRACT_APP_ID, record_box_key),
            (CONTRACT_APP_ID, vendor_box_key),
        ],
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    logger.info("submit_audit TX sent: %s", tx_id)

    try:
        result = transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"submit_audit transaction failed (TX: {tx_id}): {e}")

    logger.info("submit_audit confirmed in round %s", result.get("confirmed-round"))

    # Parse the ABI return value — last log entry contains the encoded result
    logs = result.get("logs", [])
    policy_result = "amount:fail|vendor:fail"
    if logs:
        import base64
        raw = base64.b64decode(logs[-1])
        # ARC4 return prefix is 0x151f7c75 (4 bytes), followed by encoded string
        if len(raw) > 6:
            policy_result = _decode_arc4_string(raw[4:])

    # Both checks must be "pass" for ASA to have been minted
    asa_minted = (policy_result == "amount:pass|vendor:pass")

    return AuditSubmitResult(
        tx_id=tx_id,
        policy_result=policy_result,
        asa_minted=asa_minted,
    )


async def get_audit_record(action_id: str) -> dict:
    """
    Retrieve a stored audit record from the AuditContract by action ID.

    Calls the read-only get_audit_record ABI method and parses the
    pipe-delimited response into a dict.

    Args:
        action_id: The action ID used when submit_audit was called.

    Returns:
        Dict with keys: ipfs_hash, agent_id, policy_id, decision,
        policy_result, vendor_id.

    Raises:
        RuntimeError: If the contract call fails or record is not found.
    """
    if CONTRACT_APP_ID == 0:
        raise RuntimeError("CONTRACT_APP_ID not set in .env")

    client = get_algod_client()
    selector = abi.Method.from_signature(
        "get_audit_record(string)string"
    ).get_selector()

    record_box_key = _compute_box_key(action_id, b"r:")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)

    params = client.suggested_params()

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=CONTRACT_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[selector, _encode_string(action_id)],
        boxes=[(CONTRACT_APP_ID, record_box_key)],
    )

    signed_txn = txn.sign(deployer_key)

    try:
        tx_id = client.send_transaction(signed_txn)
        result = transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"get_audit_record failed for action_id '{action_id}': {e}")

    logs = result.get("logs", [])
    if not logs:
        return {}

    import base64
    raw = base64.b64decode(logs[-1])
    if len(raw) <= 6:
        return {}

    response = _decode_arc4_string(raw[4:])

    # Parse "key=value|key=value" format returned by the contract
    parsed: dict = {}
    for pair in response.split("|"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            parsed[key] = value

    return parsed


async def add_vendor(vendor_id: str) -> str:
    """
    Add a vendor to the on-chain approved whitelist.

    Only callable by the contract creator (uses DEPLOYER_MNEMONIC).
    Used by scripts/seed_vendors.py to populate the whitelist after redeploy.

    Args:
        vendor_id: Vendor identifier string to approve (e.g. "VENDOR_001").

    Returns:
        Transaction ID of the confirmed add_vendor call.

    Raises:
        RuntimeError: If the transaction fails or required env vars are missing.
    """
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if CONTRACT_APP_ID == 0:
        raise RuntimeError("CONTRACT_APP_ID not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(
        "add_vendor(string)void"
    ).get_selector()

    vendor_box_key = _compute_box_key(vendor_id, b"v:")

    params = client.suggested_params()

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=CONTRACT_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[selector, _encode_string(vendor_id)],
        boxes=[(CONTRACT_APP_ID, vendor_box_key)],
    )

    signed_txn = txn.sign(deployer_key)

    try:
        tx_id = client.send_transaction(signed_txn)
        transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"add_vendor failed for vendor '{vendor_id}': {e}")

    logger.info("Vendor added: %s (TX: %s)", vendor_id, tx_id)
    return tx_id
