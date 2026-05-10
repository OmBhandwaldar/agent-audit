"""
SQLite-backed batch store for AgentAudit audit records.

Persists audit records across server restarts. Records accumulate as
pending leaves until flush() is called, at which point they are
bundled into a ReadyBatch for Merkle root computation and on-chain
anchoring.

After anchoring, mark_anchored() records the batch_id, leaf index,
and Merkle proof for each leaf so the verify endpoint can reconstruct
the proof without re-fetching all leaves.

Environment:
    BATCHER_DB_PATH — path to the SQLite file (default: ./data/batcher.db)
    BATCH_SIZE      — max leaves per batch before is_full() returns True (default: 8)
"""

import json
import logging
import os
import random
import sqlite3
import time
from dataclasses import dataclass, field

from batcher.merkle import compute_proof, compute_root, leaf_hash

logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))
DEFAULT_DB_PATH = os.getenv("BATCHER_DB_PATH", "./data/batcher.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leaves (
    action_id   TEXT PRIMARY KEY,
    leaf_hash   TEXT NOT NULL,
    record_json TEXT NOT NULL,
    batch_id    TEXT,
    leaf_index  INTEGER,
    proof_json  TEXT,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id      TEXT PRIMARY KEY,
    merkle_root   TEXT NOT NULL,
    leaf_count    INTEGER NOT NULL,
    anchor_tx_id  TEXT NOT NULL,
    submitted_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_leaves_batch ON leaves(batch_id);
"""


@dataclass
class BatchEntry:
    """One audit record held in the batch."""

    action_id: str
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
    anchor_tx_id: str = ""

    def proof_for(self, index: int) -> list[str]:
        """Return the Merkle inclusion proof for the entry at index."""
        return compute_proof(self.leaves, index)


class BatchStore:
    """
    SQLite-backed store that accumulates audit records and flushes them
    into ReadyBatch objects for on-chain Merkle anchoring.

    Usage:
        store = BatchStore()
        store.add(record)
        if store.is_full():
            batch = store.flush()
            # ... anchor on-chain ...
            store.mark_anchored(batch, anchor_tx_id)
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def add(self, record: dict) -> str:
        """
        Add an audit record to the pending batch.

        Computes the leaf hash from the record and inserts a row into
        the leaves table with batch_id=NULL (pending).

        Args:
            record: The audit decision record dict. Must contain action_id.

        Returns:
            The computed leaf hash hex string.

        Raises:
            ValueError: If action_id is missing from the record.
        """
        action_id = record.get("action_id")
        if not action_id:
            raise ValueError("record must contain action_id")

        lh = leaf_hash(record)
        now = int(time.time())

        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO leaves "
                "(action_id, leaf_hash, record_json, created_at) VALUES (?, ?, ?, ?)",
                (action_id, lh, json.dumps(record, sort_keys=True), now),
            )

        logger.debug("BatchStore.add: action_id=%s leaf=%s", action_id, lh[:16])
        return lh

    def size(self) -> int:
        """Return the number of pending (unanchored) leaves."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM leaves WHERE batch_id IS NULL"
            ).fetchone()
        return row[0]

    def is_full(self) -> bool:
        """Return True if the pending count has reached BATCH_SIZE."""
        return self.size() >= BATCH_SIZE

    def flush(self) -> ReadyBatch:
        """
        Read all pending leaves and return a ReadyBatch.

        Does NOT write the batch to the database — call mark_anchored()
        after the on-chain TX confirms.

        Returns:
            ReadyBatch with batch_id, entries, leaves, merkle_root, timestamp.

        Raises:
            RuntimeError: If there are no pending leaves.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT action_id, leaf_hash, record_json FROM leaves "
                "WHERE batch_id IS NULL ORDER BY created_at ASC"
            ).fetchall()

        if not rows:
            raise RuntimeError("Cannot flush an empty batch — no pending leaves")

        entries = [
            BatchEntry(
                action_id=row["action_id"],
                record=json.loads(row["record_json"]),
                leaf=row["leaf_hash"],
            )
            for row in rows
        ]
        leaves = [e.leaf for e in entries]
        root = compute_root(leaves)
        ts = int(time.time())
        batch_id = f"batch_{ts}_{random.randint(1000, 9999)}"

        logger.info(
            "BatchStore.flush: batch_id=%s leaves=%d root=%s",
            batch_id, len(leaves), root[:16],
        )
        return ReadyBatch(
            batch_id=batch_id,
            entries=entries,
            leaves=leaves,
            merkle_root=root,
            timestamp=ts,
        )

    def mark_anchored(self, batch: ReadyBatch, anchor_tx_id: str) -> None:
        """
        Persist the anchored batch and update each leaf with its proof.

        Called after submit_anchor_root() confirms on-chain.

        Args:
            batch: The ReadyBatch returned by flush().
            anchor_tx_id: The confirmed Algorand TX ID from AnchorContract.
        """
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO batches "
                "(batch_id, merkle_root, leaf_count, anchor_tx_id, submitted_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (batch.batch_id, batch.merkle_root, len(batch.leaves),
                 anchor_tx_id, batch.timestamp),
            )
            for i, entry in enumerate(batch.entries):
                proof = compute_proof(batch.leaves, i)
                conn.execute(
                    "UPDATE leaves SET batch_id=?, leaf_index=?, proof_json=? "
                    "WHERE action_id=?",
                    (batch.batch_id, i, json.dumps(proof), entry.action_id),
                )

        logger.info(
            "BatchStore.mark_anchored: batch_id=%s tx=%s leaves=%d",
            batch.batch_id, anchor_tx_id, len(batch.leaves),
        )

    def get_leaf(self, action_id: str) -> dict | None:
        """
        Fetch a leaf record by action_id.

        Returns dict with leaf_hash, record, batch_id, leaf_index, proof,
        or None if not found.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT action_id, leaf_hash, record_json, batch_id, "
                "leaf_index, proof_json FROM leaves WHERE action_id=?",
                (action_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "action_id": row["action_id"],
            "leaf_hash": row["leaf_hash"],
            "record": json.loads(row["record_json"]),
            "batch_id": row["batch_id"],
            "leaf_index": row["leaf_index"],
            "proof": json.loads(row["proof_json"]) if row["proof_json"] else None,
        }

    def get_batch(self, batch_id: str) -> dict | None:
        """Fetch batch metadata by batch_id, or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM batches WHERE batch_id=?", (batch_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def recent_batches(self, limit: int = 5) -> list[dict]:
        """Return the most recently submitted batches."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM batches ORDER BY submitted_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
