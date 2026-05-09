"""
AgentAudit Phase 2 — Anchor Contract.

Stores Merkle roots of batched audit records.
Each root anchors N decisions in one on-chain transaction.

Flow:
  1. Batcher collects N audit decisions off-chain into a Merkle tree.
  2. Batcher calls submit_root(batch_id, merkle_root) — one tx per batch.
  3. Verifiers call get_root(batch_id) and verify their record's Merkle proof locally.

Box storage:
  roots BoxMap — key_prefix=b"root:"
    key:   sha256(batch_id.bytes) — fixed 32-byte key
    value: AnchorRecord struct (merkle_root hex string + leaf count + timestamp)
"""

from algopy import (
    ARC4Contract,
    BoxMap,
    Bytes,
    Global,
    Txn,
    UInt64,
    op,
)
from algopy import arc4


class AnchorRecord(arc4.Struct):
    """On-chain record for one anchored batch."""

    merkle_root: arc4.String   # hex-encoded 32-byte SHA256 Merkle root
    leaf_count: arc4.UInt64    # number of decisions in this batch
    timestamp: arc4.UInt64     # Unix timestamp when root was submitted
    batch_id: arc4.String      # batch identifier (stored for lookup convenience)


class AnchorContract(ARC4Contract):
    """
    AgentAudit Phase 2 Merkle anchor contract.

    Methods:
      initialize    — called once at creation to record creator
      submit_root   — store a Merkle root for a batch of audit decisions
      get_root      — retrieve stored root and metadata by batch ID (read only)
    """

    def __init__(self) -> None:
        """Declare roots box map. No global state needed — create guard is on initialize()."""
        self.roots = BoxMap(Bytes, AnchorRecord, key_prefix=b"root:")

    @arc4.abimethod(create="require")
    def initialize(self) -> None:
        """
        Called exactly once at contract creation.

        Creator address is implicitly stored via Global.creator_address.
        No setup needed — creator access is enforced via Global.creator_address.
        """

    @arc4.abimethod
    def submit_root(
        self,
        batch_id: arc4.String,
        merkle_root: arc4.String,
        leaf_count: UInt64,
        timestamp: UInt64,
    ) -> None:
        """
        Store a Merkle root anchoring a batch of audit decisions.

        Only the contract creator can submit roots (the batcher service wallet).
        Box key is sha256(batch_id.bytes) — always 32 bytes.

        Args:
            batch_id: Unique batch identifier (e.g. "batch_1746543300_8821").
            merkle_root: Hex-encoded SHA256 Merkle root of all leaves in the batch.
            leaf_count: Number of audit decisions included in this batch.
            timestamp: Unix timestamp when the batch was built.
        """
        assert Txn.sender == Global.creator_address, "Only creator can submit roots"
        box_key = op.sha256(batch_id.bytes)
        self.roots[box_key] = AnchorRecord(
            merkle_root=merkle_root,
            leaf_count=arc4.UInt64(leaf_count),
            timestamp=arc4.UInt64(timestamp),
            batch_id=batch_id,
        )

    @arc4.abimethod(readonly=True)
    def get_root(self, batch_id: arc4.String) -> arc4.String:
        """
        Retrieve the stored Merkle root by batch ID.

        Returns the hex-encoded SHA256 Merkle root for the batch.
        For full record metadata (leaf_count, timestamp), the client should
        read the box directly via algod's box_get API.

        Asserts if no record exists for the given batch ID.

        Args:
            batch_id: The batch ID used when submit_root was called.
        """
        box_key = op.sha256(batch_id.bytes)
        assert box_key in self.roots, "Batch root not found"
        record = self.roots[box_key].copy()
        return record.merkle_root
