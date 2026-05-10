"""
Batch anchor: flushes BatchStore and submits the Merkle root to AnchorContract.
"""

import logging

from algorand.contract_client_v2 import submit_anchor_root
from batcher.store import BatchStore, ReadyBatch

logger = logging.getLogger(__name__)


async def flush_and_anchor(store: BatchStore) -> ReadyBatch:
    """
    Flush the pending batch, anchor its Merkle root on-chain, and persist proofs.

    Steps:
        1. Flush the BatchStore -> ReadyBatch (computes Merkle root from pending leaves)
        2. Submit the root to AnchorContract via submit_anchor_root()
        3. Call store.mark_anchored() to persist proofs and batch metadata
        4. Return the ReadyBatch with anchor_tx_id set

    Args:
        store: The BatchStore holding pending audit records.

    Returns:
        ReadyBatch with anchor_tx_id set.

    Raises:
        RuntimeError: If the store is empty or the Algorand call fails.
    """
    if store.size() == 0:
        raise RuntimeError("flush_and_anchor called on empty store")

    batch = store.flush()

    logger.info(
        "Anchoring batch %s: %d leaves, root=%s",
        batch.batch_id, len(batch.leaves), batch.merkle_root[:16],
    )

    tx_id = await submit_anchor_root(
        batch_id=batch.batch_id,
        merkle_root=batch.merkle_root,
        leaf_count=len(batch.leaves),
        timestamp=batch.timestamp,
    )

    batch.anchor_tx_id = tx_id
    store.mark_anchored(batch, tx_id)

    logger.info("Batch anchored and persisted: TX=%s", tx_id)
    return batch
