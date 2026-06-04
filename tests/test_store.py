"""Unit tests for the SQLite batch store (batcher/store.py)."""

import os
import tempfile

import pytest

from batcher.merkle import verify_proof
from batcher.store import BatchStore


def _store() -> BatchStore:
    d = tempfile.mkdtemp()
    return BatchStore(db_path=os.path.join(d, "batcher.db"))


def test_add_flush_anchor_and_proof():
    s = _store()
    for i in range(3):
        s.add({"action_id": f"a{i}", "amount": i * 100, "org_id": "acme"})
    assert s.size() == 3

    batch = s.flush()
    assert len(batch.leaves) == 3
    assert len(batch.merkle_root) == 64

    s.mark_anchored(batch, "TX_ABC")
    assert s.size() == 0  # anchored leaves are no longer pending

    leaf = s.get_leaf("a1")
    assert leaf["batch_id"] == batch.batch_id
    assert leaf["proof"] is not None
    assert leaf["record"]["org_id"] == "acme"
    # the persisted proof must verify against the anchored root
    assert verify_proof(leaf["leaf_hash"], leaf["proof"], batch.merkle_root) is True

    b = s.get_batch(batch.batch_id)
    assert b["anchor_tx_id"] == "TX_ABC" and b["leaf_count"] == 3


def test_get_leaf_missing_returns_none():
    assert _store().get_leaf("nope") is None


def test_add_requires_action_id():
    with pytest.raises(ValueError):
        _store().add({"amount": 1})


def test_flush_empty_raises():
    with pytest.raises(RuntimeError):
        _store().flush()
