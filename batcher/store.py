"""
In-memory batch store for AgentAudit audit records.

Accumulates audit records until the batch is full (BATCH_SIZE reached)
or flush() is called manually. Each record is stored with its leaf hash
for Merkle tree construction.

Thread safety: not thread-safe — designed for single-threaded async use.
"""

import logging
import os
import random
import time
from dataclasses import dataclass, field

from batcher.merkle import compute_proof, compute_root, leaf_hash

logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))


@dataclass
class BatchEntry:
    """One audit record held in the pending batch."""

    record: dict
    leaf: str  # sha256 hex of canonical JSON


@dataclass
class ReadyBatch:
    """A completed batch ready to anchor on-chain."""

    batch_id: str
    entries: list[BatchEntry]
    leaves: list[str]
    merkle_root: str
    timestamp: int

    def proof_for(self, index: int) -> list[str]:
        """Return the Merkle inclusion proof for the entry at index."""
        return compute_proof(self.leaves, index)


class BatchStore:
    """
    Accumulates audit records and produces ReadyBatch objects on flush.

    Usage:
        store = BatchStore()
        store.add(record)           # add a record
        if store.is_full():
            batch = store.flush()   # returns ReadyBatch, clears internal state
    """

    def __init__(self) -> None:
        self._pending: list[BatchEntry] = []

    def add(self, record: dict) -> str:
        """
        Add an audit record to the pending batch.

        Args:
            record: The audit decision record dict. Must be JSON-serialisable.

        Returns:
            The computed leaf hash for this record.
        """
        lh = leaf_hash(record)
        self._pending.append(BatchEntry(record=record, leaf=lh))
        logger.debug("BatchStore.add: leaf=%s pending=%d", lh[:16], len(self._pending))
        return lh

    def is_full(self) -> bool:
        """Return True if the batch has reached BATCH_SIZE."""
        return len(self._pending) >= BATCH_SIZE

    def size(self) -> int:
        """Return the number of records currently pending."""
        return len(self._pending)

    def flush(self) -> ReadyBatch:
        """
        Finalise the current batch and return it.

        Computes the Merkle root from all pending leaf hashes.
        Clears internal state so the store is ready for the next batch.

        Returns:
            ReadyBatch with batch_id, entries, leaves, merkle_root, timestamp.

        Raises:
            RuntimeError: If the pending batch is empty.
        """
        if not self._pending:
            raise RuntimeError("Cannot flush an empty batch")

        entries = list(self._pending)
        leaves = [e.leaf for e in entries]
        root = compute_root(leaves)
        ts = int(time.time())
        batch_id = f"batch_{ts}_{random.randint(1000, 9999)}"

        self._pending = []

        batch = ReadyBatch(
            batch_id=batch_id,
            entries=entries,
            leaves=leaves,
            merkle_root=root,
            timestamp=ts,
        )
        logger.info(
            "BatchStore.flush: batch_id=%s leaves=%d root=%s",
            batch_id, len(leaves), root[:16],
        )
        return batch
