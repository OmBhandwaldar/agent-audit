"""
SHA256 Merkle tree for AgentAudit batch anchoring.

Leaf hashes are SHA256 of sorted-JSON canonical form of each audit record.
Sibling pairs are sorted before hashing so proofs are deterministic
regardless of insertion order.
"""

import hashlib
import json


def leaf_hash(record: dict) -> str:
    """
    Compute the canonical SHA256 leaf hash for an audit record.

    Uses sorted-key JSON so the hash is deterministic regardless of
    dict insertion order.

    Args:
        record: The audit decision record dict.

    Returns:
        Hex-encoded SHA256 hash.
    """
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    """Hash two sibling hex strings into one parent. Siblings are sorted first."""
    a, b = sorted([left, right])
    return hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()


def _next_level(nodes: list[str]) -> list[str]:
    """Compute parent level. Duplicate last node if count is odd."""
    if len(nodes) % 2 == 1:
        nodes = nodes + [nodes[-1]]
    return [_hash_pair(nodes[i], nodes[i + 1]) for i in range(0, len(nodes), 2)]


def compute_root(leaves: list[str]) -> str:
    """
    Compute the Merkle root from a list of leaf hashes.

    Args:
        leaves: Non-empty list of hex-encoded SHA256 leaf hashes.

    Returns:
        Hex-encoded SHA256 Merkle root.

    Raises:
        ValueError: If leaves is empty.
    """
    if not leaves:
        raise ValueError("Cannot compute Merkle root of empty list")
    level = list(leaves)
    while len(level) > 1:
        level = _next_level(level)
    return level[0]


def compute_proof(leaves: list[str], index: int) -> list[str]:
    """
    Compute a Merkle inclusion proof for the leaf at index.

    Args:
        leaves: Full list of leaf hashes used to build the tree.
        index: Zero-based index of the leaf to prove.

    Returns:
        List of sibling hashes from leaf level up to (not including) root.

    Raises:
        ValueError: If leaves is empty or index is out of range.
    """
    if not leaves:
        raise ValueError("Cannot compute proof for empty leaf list")
    if index < 0 or index >= len(leaves):
        raise ValueError(f"Index {index} out of range for {len(leaves)} leaves")

    proof: list[str] = []
    level = list(leaves)
    pos = index

    while len(level) > 1:
        if len(level) % 2 == 1:
            level = level + [level[-1]]
        proof.append(level[pos ^ 1])  # sibling index
        level = _next_level(level)
        pos //= 2

    return proof


def verify_proof(leaf: str, proof: list[str], root: str) -> bool:
    """
    Verify a Merkle inclusion proof.

    Args:
        leaf: Hex-encoded hash of the leaf being proved.
        proof: Sibling hashes from compute_proof().
        root: Expected Merkle root.

    Returns:
        True if proof is valid, False otherwise.
    """
    current = leaf
    for sibling in proof:
        current = _hash_pair(current, sibling)
    return current == root
