"""
Algorand contract client for AgentAudit.

Handles all interaction with the deployed AuditContract:
  - submit_audit()     — write audit record + trigger ASA transfer if approved
  - get_audit_record() — read stored audit record by action ID
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
    policy_result: str   # "pass" or "fail"
    asa_minted: bool     # True if 1 AACR was transferred to caller


def _encode_string(value: str) -> bytes:
    """
    ARC4-encode a string: 2-byte big-endian length prefix + UTF-8 content.
    Matches arc4.String.bytes in the PuyaPy contract.
    """
    encoded = value.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def _compute_box_key(action_id: str) -> bytes:
    """
    Compute the box key for a given action ID.
    Matches op.sha256(action_id.bytes) in the PuyaPy contract.
    Box key = sha256(arc4_encoded_action_id).
    """
    return hashlib.sha256(_encode_string(action_id)).digest()


def _decode_arc4_string(raw: bytes) -> str:
    """
    Decode an ARC4-encoded string from raw bytes.
    Strips the 2-byte length prefix and decodes UTF-8 content.
    """
    if len(raw) < 2:
        return ""
    length = struct.unpack(">H", raw[:2])[0]
    return raw[2 : 2 + length].decode("utf-8")


async def submit_audit(
    action_id: str,
    ipfs_hash: str,
    record: dict,
) -> AuditSubmitResult:
    """
    Submit an audit record to the AuditContract on Algorand.

    Builds and signs the ABI-encoded submit_audit app call, waits for
    confirmation, and returns the result including policy outcome.

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

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(
        "submit_audit(string,string,string,string,string,uint64,uint64)string"
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
    ]

    box_key = _compute_box_key(action_id)

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
        boxes=[(CONTRACT_APP_ID, box_key)],
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
    policy_result = "fail"
    if logs:
        import base64
        raw = base64.b64decode(logs[-1])
        # ARC4 return prefix is 0x151f7c75 (4 bytes), followed by the encoded string
        if len(raw) > 6:
            policy_result = _decode_arc4_string(raw[4:])

    asa_minted = policy_result == "pass"

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
        Dict with keys: ipfs_hash, agent_id, policy_id, decision, policy_result.

    Raises:
        RuntimeError: If the contract call fails or record is not found.
    """
    if CONTRACT_APP_ID == 0:
        raise RuntimeError("CONTRACT_APP_ID not set in .env")

    client = get_algod_client()
    selector = abi.Method.from_signature(
        "get_audit_record(string)string"
    ).get_selector()

    box_key = _compute_box_key(action_id)

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)

    params = client.suggested_params()

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=CONTRACT_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[selector, _encode_string(action_id)],
        boxes=[(CONTRACT_APP_ID, box_key)],
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
