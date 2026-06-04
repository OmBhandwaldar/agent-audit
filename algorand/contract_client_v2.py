"""
Algorand contract client for AgentAudit multi-tenant platform.

PolicyContract (multi-tenant predicate engine):
  - register_rule()       — add a predicate rule for an org+agent
  - add_to_set()          — add a value to an org+agent+field membership set
  - remove_from_set()     — remove a value from a set
  - submit_policy_check() — call check_and_mint (multi-tenant)

AnchorContract (unchanged):
  - submit_anchor_root()  — store a Merkle root on-chain
  - get_anchor_root()     — free box read, no fee

Box key construction mirrors the contract exactly. All .bytes values are
ARC4-encoded: 2-byte big-endian length prefix + UTF-8 content.
  tenant_rules  b"r:"    sha256(org.bytes + agent.bytes + itob(index))
  rule_counts   b"rc:"   sha256(org.bytes + agent.bytes)
  sets          b"s:"    sha256(org.bytes + agent.bytes + field.bytes + value.bytes)
  anchor roots  b"root:" sha256(batch_id.bytes)
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

# check_and_mint runs a per-rule loop (ensure_budget) + one inner ASA transfer;
# outer tx covers all via fee pooling.
POLICY_CHECK_FEE = 3000

# Operator codes (mirror the contract constants)
OP_LT = 1
OP_LE = 2
OP_GT = 3
OP_GE = 4
OP_EQ = 5
OP_NE = 6
OP_IN = 7
OP_NOT_IN = 8

MODE_ONCHAIN = 1
MODE_ATTESTED = 2


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------


def _encode_string(value: str) -> bytes:
    """ARC4-encode a string: 2-byte big-endian length prefix + UTF-8 content."""
    encoded = value.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def _encode_uint64(value: int) -> bytes:
    """ABI-encode a uint64: 8-byte big-endian."""
    return struct.pack(">Q", value)


def _sha256_bytes(*parts: bytes) -> bytes:
    """SHA256 over the concatenation of all parts."""
    return hashlib.sha256(b"".join(parts)).digest()


def _rule_box_key(org_id: str, agent_id: str, index: int) -> bytes:
    return b"r:" + _sha256_bytes(_encode_string(org_id), _encode_string(agent_id), _encode_uint64(index))


def _count_box_key(org_id: str, agent_id: str) -> bytes:
    return b"rc:" + _sha256_bytes(_encode_string(org_id), _encode_string(agent_id))


def _set_box_key(org_id: str, agent_id: str, field: str, value: str) -> bytes:
    return b"s:" + _sha256_bytes(
        _encode_string(org_id), _encode_string(agent_id), _encode_string(field), _encode_string(value)
    )


def _anchor_box_key(batch_id: str) -> bytes:
    return b"root:" + _sha256_bytes(_encode_string(batch_id))


def _decode_arc4_string(raw: bytes) -> str:
    """Decode an ARC4-encoded string: strip 2-byte length prefix, decode UTF-8."""
    if len(raw) < 2:
        return ""
    length = struct.unpack(">H", raw[:2])[0]
    return raw[2:2 + length].decode("utf-8")


def _read_rule_count(client, org_id: str, agent_id: str) -> int:
    """Read the current rule count for an org+agent from the rule_counts box (0 if absent)."""
    try:
        raw = base64.b64decode(client.application_box_by_name(POLICY_APP_ID, _count_box_key(org_id, agent_id))["value"])
        return struct.unpack(">Q", raw[-8:])[0] if len(raw) >= 8 else 0
    except Exception:
        return 0


# ---- ARC4 dynamic array encoders --------------------------------------------


def _encode_array_uint64(values: list[int]) -> bytes:
    """ARC4 DynamicArray[UInt64]: 2-byte count + each element 8-byte big-endian."""
    return struct.pack(">H", len(values)) + b"".join(struct.pack(">Q", v) for v in values)


def _encode_array_string(values: list[str]) -> bytes:
    """ARC4 DynamicArray[String]: 2-byte count + N 2-byte offsets + N ARC4 strings."""
    count = len(values)
    encoded = [_encode_string(v) for v in values]
    head_size = count * 2
    offsets, running = [], 0
    for e in encoded:
        offsets.append(head_size + running)
        running += len(e)
    return struct.pack(">H", count) + b"".join(struct.pack(">H", o) for o in offsets) + b"".join(encoded)


def _encode_array_bool(values: list[bool]) -> bytes:
    """ARC4 DynamicArray[Bool]: 2-byte count + bits packed 8-per-byte, MSB first."""
    count = len(values)
    packed = bytearray((count + 7) // 8)
    for i, v in enumerate(values):
        if v:
            packed[i // 8] |= 1 << (7 - (i % 8))
    return struct.pack(">H", count) + bytes(packed)


def _parse_policy_result(policy_result: str) -> dict:
    """
    Parse "pass:onchain|fail:attested" into per-rule keys plus legacy amount/vendor keys
    (first two rules) for backward compatibility with the existing dashboard/frontend.
    """
    parts = policy_result.split("|")
    checks: dict = {f"rule_{i}": p for i, p in enumerate(parts)}
    if len(parts) >= 1:
        checks["amount_check"] = "pass" if parts[0].startswith("pass") else "fail"
    if len(parts) >= 2:
        checks["vendor_check"] = "pass" if parts[1].startswith("pass") else "fail"
    return checks


def build_policy_rule(mode: int, operator: int, value_num: int, field: str, commitment: str = "") -> bytes:
    """
    ARC4-encode a PolicyRule struct (mode, operator, value_num : uint64; field, commitment : string).
    Head = 3*8 fixed + 2*2 dynamic offsets = 28 bytes; tail = field + commitment.
    """
    field_bytes = _encode_string(field)
    commitment_bytes = _encode_string(commitment)
    head_size = 28
    head = (
        struct.pack(">Q", mode)
        + struct.pack(">Q", operator)
        + struct.pack(">Q", value_num)
        + struct.pack(">H", head_size)
        + struct.pack(">H", head_size + len(field_bytes))
    )
    return head + field_bytes + commitment_bytes


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class PolicyCheckResult:
    """Result from a multi-tenant submit_policy_check call."""

    def __init__(self, tx_id: str, policy_result: str, asa_minted: bool) -> None:
        self.tx_id = tx_id
        self.policy_result = policy_result
        self.asa_minted = asa_minted


# ---------------------------------------------------------------------------
# PolicyContract — management
# ---------------------------------------------------------------------------


async def register_rule(
    org_id: str,
    agent_id: str,
    mode: int,
    operator: int,
    value_num: int,
    field: str,
    commitment: str = "",
) -> tuple[str, int]:
    """Append a predicate rule to an org+agent policy set. Returns (tx_id, rule_index)."""
    _require_env()
    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(
        "register_rule(string,string,(uint64,uint64,uint64,string,string))uint64"
    ).get_selector()

    next_index = _read_rule_count(client, org_id, agent_id)
    app_args = [
        selector,
        _encode_string(org_id),
        _encode_string(agent_id),
        build_policy_rule(mode, operator, value_num, field, commitment),
    ]

    params = client.suggested_params()
    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=POLICY_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args,
        boxes=[
            (POLICY_APP_ID, _count_box_key(org_id, agent_id)),
            (POLICY_APP_ID, _rule_box_key(org_id, agent_id, next_index)),
        ],
    )

    signed_txn = txn.sign(deployer_key)
    try:
        tx_id = client.send_transaction(signed_txn)
        result = transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"register_rule failed for {org_id}/{agent_id}: {e}")

    assigned_index = next_index
    logs = result.get("logs", [])
    if logs:
        raw = base64.b64decode(logs[-1])
        if len(raw) >= 12:
            assigned_index = struct.unpack(">Q", raw[4:12])[0]

    logger.info("register_rule: %s/%s index=%d tx=%s", org_id, agent_id, assigned_index, tx_id)
    return tx_id, assigned_index


async def add_to_set(org_id: str, agent_id: str, field: str, value: str) -> str:
    """Add a value to an org+agent+field membership set (for in/not_in predicates)."""
    return await _set_op("add_to_set(string,string,string,string)void", org_id, agent_id, field, value)


async def remove_from_set(org_id: str, agent_id: str, field: str, value: str) -> str:
    """Remove a value from an org+agent+field membership set."""
    return await _set_op("remove_from_set(string,string,string,string)void", org_id, agent_id, field, value)


async def _set_op(signature: str, org_id: str, agent_id: str, field: str, value: str) -> str:
    _require_env()
    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(signature).get_selector()
    params = client.suggested_params()
    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=POLICY_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[
            selector,
            _encode_string(org_id),
            _encode_string(agent_id),
            _encode_string(field),
            _encode_string(value),
        ],
        boxes=[(POLICY_APP_ID, _set_box_key(org_id, agent_id, field, value))],
    )
    signed_txn = txn.sign(deployer_key)
    try:
        tx_id = client.send_transaction(signed_txn)
        transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"set op failed ({org_id}/{agent_id}/{field}/{value}): {e}")
    logger.info("set op %s: %s/%s %s=%s tx=%s", signature.split("(")[0], org_id, agent_id, field, value, tx_id)
    return tx_id


# ---------------------------------------------------------------------------
# PolicyContract — audit submission
# ---------------------------------------------------------------------------


async def submit_policy_check(
    org_id: str,
    agent_id: str,
    action_id: str,
    ipfs_hash: str,
    values_num: list[int],
    values_str: list[str],
    attested: list[bool],
    fields: list[str],
) -> PolicyCheckResult:
    """
    Call check_and_mint on the multi-tenant PolicyContract.

    All five per-rule lists are aligned to the org+agent's rules by index:
      - Mode-1 numeric rule i   -> values_num[i] is the decision's field value
      - Mode-1 in/not_in rule i -> values_str[i] is the field value to test
      - Mode-2 attested rule i  -> attested[i] is the backend's pass/fail result
      - fields[i]               -> the rule's field name (needed to reference the
                                   correct set box for in/not_in rules)
    The off-chain caller fills unused slots with 0 / "" / False.
    """
    _require_env()
    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature(
        "check_and_mint(string,string,string,string,uint64[],string[],bool[])string"
    ).get_selector()

    app_args = [
        selector,
        _encode_string(org_id),
        _encode_string(agent_id),
        _encode_string(action_id),
        _encode_string(ipfs_hash),
        _encode_array_uint64(values_num),
        _encode_array_string(values_str),
        _encode_array_bool(attested),
    ]

    rule_count = len(values_num)
    boxes = [(POLICY_APP_ID, _count_box_key(org_id, agent_id))]
    for i in range(rule_count):
        boxes.append((POLICY_APP_ID, _rule_box_key(org_id, agent_id, i)))
    for i, val in enumerate(values_str):
        if val:
            boxes.append((POLICY_APP_ID, _set_box_key(org_id, agent_id, fields[i], val)))
    boxes = boxes[:8]  # AVM caps box references per txn

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
        boxes=boxes,
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    logger.info("submit_policy_check TX sent: %s", tx_id)

    try:
        result = transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"submit_policy_check failed (TX: {tx_id}): {e}")

    logger.info("submit_policy_check confirmed round %s", result.get("confirmed-round"))

    logs = result.get("logs", [])
    policy_result = "|".join(["fail:unknown"] * rule_count) if rule_count else "fail:unknown"
    if logs:
        raw = base64.b64decode(logs[-1])
        if len(raw) > 6:
            policy_result = _decode_arc4_string(raw[4:])

    asa_minted = bool(policy_result) and all(p.startswith("pass") for p in policy_result.split("|"))
    return PolicyCheckResult(tx_id=tx_id, policy_result=policy_result, asa_minted=asa_minted)


# ---------------------------------------------------------------------------
# AnchorContract (unchanged)
# ---------------------------------------------------------------------------


async def submit_anchor_root(batch_id: str, merkle_root: str, leaf_count: int, timestamp: int) -> str:
    """Store a Merkle root in AnchorContract. Returns confirmed TX ID."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if ANCHOR_APP_ID == 0:
        raise RuntimeError("ANCHOR_APP_ID not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    client = get_algod_client()

    selector = abi.Method.from_signature("submit_root(string,string,uint64,uint64)void").get_selector()

    params = client.suggested_params()
    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=ANCHOR_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[
            selector,
            _encode_string(batch_id),
            _encode_string(merkle_root),
            _encode_uint64(leaf_count),
            _encode_uint64(timestamp),
        ],
        boxes=[(ANCHOR_APP_ID, _anchor_box_key(batch_id))],
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    logger.info("submit_anchor_root TX sent: %s", tx_id)

    try:
        transaction.wait_for_confirmation(client, tx_id, 4)
    except Exception as e:
        raise RuntimeError(f"submit_anchor_root failed (TX: {tx_id}): {e}")

    logger.info("submit_anchor_root confirmed: batch=%s root=%s", batch_id, merkle_root)
    return tx_id


async def get_anchor_root(batch_id: str) -> str:
    """Read the Merkle root for a batch directly from AnchorContract box state. Free, no fee."""
    if ANCHOR_APP_ID == 0:
        raise RuntimeError("ANCHOR_APP_ID not set in .env")

    client = get_algod_client()
    try:
        box = client.application_box_by_name(ANCHOR_APP_ID, _anchor_box_key(batch_id))
    except Exception as e:
        raise RuntimeError(f"get_anchor_root: box not found for batch_id '{batch_id}': {e}")

    raw = base64.b64decode(box["value"])
    if len(raw) < 2:
        raise RuntimeError(f"get_anchor_root: empty box for batch_id '{batch_id}'")

    offset = int.from_bytes(raw[0:2], "big")
    if offset + 2 > len(raw):
        raise RuntimeError(f"get_anchor_root: malformed box for batch_id '{batch_id}'")
    return _decode_arc4_string(raw[offset:])


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _require_env() -> None:
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if POLICY_APP_ID == 0:
        raise RuntimeError("POLICY_APP_ID not set in .env")
    if COMPLIANCE_ASA_ID == 0:
        raise RuntimeError("COMPLIANCE_ASA_ID not set in .env")
