"""Unit tests for the SHA256 Merkle tree (batcher/merkle.py)."""

import pytest

from batcher.merkle import compute_proof, compute_root, leaf_hash, verify_proof


def test_leaf_hash_is_key_order_independent():
    assert leaf_hash({"b": 2, "a": 1}) == leaf_hash({"a": 1, "b": 2})


def test_single_leaf_root_is_itself():
    leaves = [leaf_hash({"i": 0})]
    assert compute_root(leaves) == leaves[0]


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 9])
def test_proof_verifies_for_every_leaf(n):
    leaves = [leaf_hash({"i": i}) for i in range(n)]
    root = compute_root(leaves)
    for i in range(n):
        assert verify_proof(leaves[i], compute_proof(leaves, i), root) is True


def test_tampered_leaf_fails_proof():
    leaves = [leaf_hash({"i": i}) for i in range(4)]
    root = compute_root(leaves)
    proof = compute_proof(leaves, 1)
    tampered = leaf_hash({"i": 999})
    assert verify_proof(tampered, proof, root) is False


def test_wrong_root_fails_proof():
    leaves = [leaf_hash({"i": i}) for i in range(4)]
    proof = compute_proof(leaves, 0)
    assert verify_proof(leaves[0], proof, "00" * 32) is False


def test_empty_leaves_raise():
    with pytest.raises(ValueError):
        compute_root([])
    with pytest.raises(ValueError):
        compute_proof([], 0)
