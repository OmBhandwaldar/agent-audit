# AgentAudit — Smart Contracts

Two **Algorand Python (Algokit ARC4)** contracts on **Algorand Testnet**.

| Contract | Role | Env var |
|---|---|---|
| `PolicyContract` | Per-action policy check + AACR mint | `POLICY_APP_ID` |
| `AnchorContract` | Merkle root anchoring for batched records | `ANCHOR_APP_ID` |

Split rationale: per-action policy must be on-chain (independence from the agent), but per-record on-chain storage doesn't scale. Each contract does one job.

For system-level context, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## PolicyContract — `contracts/policy_contract.py`

Stateless enforcer. Runs two policy checks per action, mints **1 AACR (AgentAudit Compliance Receipt)** to the caller if both pass. Does **not** store audit records.

### State

| Type | Name | Description |
|---|---|---|
| GlobalState `UInt64` | `compliance_asa_id` | AACR ASA ID |
| GlobalState `UInt64` | `policy_limit` | Max amount that passes (exclusive) |
| BoxMap `Bytes → arc4.Bool` | `vendors` (`b"v:"`) | Whitelist. Key = `sha256(vendor_id.bytes)`. |

Box keys are always `sha256(string.bytes)` — fixed 32 bytes.

### Methods

| Method | Access | Purpose |
|---|---|---|
| `initialize(compliance_asa_id, policy_limit)` | create-only | Set ASA ID + policy limit |
| `opt_in_asa()` | creator | Opt contract into AACR ASA (inner asset transfer, amount 0) |
| `add_vendor(vendor_id)` | creator | Add `sha256(vendor_id) → True` to whitelist |
| `remove_vendor(vendor_id)` | creator | Remove from whitelist |
| `check_and_mint(action_id, ipfs_hash, amount, vendor_id, agent_id, timestamp)` | public | **Main method** — run both checks, mint AACR if both pass, return result string |

### `check_and_mint` logic

1. `amount_passes = amount < policy_limit`
2. `vendor_passes = sha256(vendor_id.bytes) in vendors`
3. Build result string: `"amount:pass|vendor:pass"` (or `"fail"` per check)
4. If both pass: inner `AssetTransfer` of 1 AACR → `Txn.sender`
5. Return the result string

The caller must include the vendor box reference in the txn's `boxes` array so the runtime can resolve the BoxMap read.

### AACR ASA setup

The ASA is created **separately** (`scripts/create_asa.py`), then placed under contract control.

| Property | Value |
|---|---|
| Name / Unit | AgentAudit Compliance Receipt / AACR |
| Total supply | 1,000,000 |
| Decimals | 0 |
| Clawback / Freeze | Contract address |
| Default frozen | `True` (receipts non-transferable peer-to-peer) |

Sequence: create ASA → deploy contract → `opt_in_asa()` → send supply to contract address → test transfer.

---

## AnchorContract — `contracts/anchor_contract.py`

Tiny single-purpose contract. Stores Merkle roots of batched decisions. One box per batch anchors N records in one transaction.

### State

| Type | Name | Description |
|---|---|---|
| BoxMap `Bytes → AnchorRecord` | `roots` (`b"root:"`) | One box per batch. Key = `sha256(batch_id.bytes)`. |

#### `AnchorRecord` struct

| Field | Type |
|---|---|
| `merkle_root` | `arc4.String` (hex SHA256) |
| `leaf_count` | `arc4.UInt64` |
| `timestamp` | `arc4.UInt64` |
| `batch_id` | `arc4.String` |

### Methods

| Method | Access | Purpose |
|---|---|---|
| `initialize()` | create-only | No-op; creator captured via `Global.creator_address` |
| `submit_root(batch_id, merkle_root, leaf_count, timestamp)` | creator | Write batch box |
| `get_root(batch_id) -> arc4.String` | public (readonly) | Return hex Merkle root for the batch |

### Box minimum balance

Each box raises the contract's MBR. With many batches the contract eventually runs out — top up with `scripts/fund_anchor.py` (2 ALGO ≈ 500 more boxes).

---

## Merkle Leaf Format

Computed off-chain by the batcher (`batcher/merkle.py`):

```python
def leaf_hash(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
```

- **Sorted keys + compact separators** → canonical, insertion-order independent.
- The **entire** record is hashed — including `reasoning_trace`. Tampering with the trace breaks the proof identically to tampering with the decision.
- Sibling pairs are **sorted before hashing** at internal nodes → order-independent proofs.

---

## Verification Walkthrough

`/api/verify?action_id=...` does:

1. Look up record + `batch_id` + Merkle proof from SQLite.
2. `AnchorContract.get_root(batch_id)` → on-chain root.
3. Recompute `leaf_hash(record)`.
4. `verify_proof(leaf, proof, on_chain_root)` → cryptographic inclusion proof.
5. Fetch ciphertext from IPFS. Recompute `sha256(cid)`; compare to `ipfs_hash` from PolicyContract call.
6. **With `X-Auditor-Key` header:** decrypt envelope (GCM auth tag also verifies integrity) → return plaintext + reasoning trace.
**Without:** return ciphertext only — tamper-evidence proven without revealing record contents.

Step 4 is the rigorous part. A passing proof means the record was provably part of the specific anchored batch — stronger than hash equality alone.

---

## Deployment Order

```
1. python scripts/gen_encryption_key.py     # → PAYLOAD_ENCRYPTION_KEY
2. python scripts/create_asa.py             # → COMPLIANCE_ASA_ID
3. python scripts/deploy_phase2.py          # → POLICY_APP_ID, ANCHOR_APP_ID
4. python scripts/opt_in_asa_phase2.py      # PolicyContract.opt_in_asa()
5. python scripts/send_aacr_to_policy.py    # send ASA supply to contract
6. python scripts/seed_vendors_v2.py        # add VENDOR_001, VENDOR_002
7. python scripts/fund_anchor.py            # fund AnchorContract for box MBR
```

Smoke test: `python scripts/runFlow_v2.py 3000 VENDOR_001` should show `approved`, an IPFS CID, an Algorand TX, `amount:pass|vendor:pass`, and `ASA Minted: True`.

### Redeploy notes
- Update the corresponding `*_APP_ID` in `.env`.
- PolicyContract: re-opt-in, re-fund ASA, re-seed vendors.
- AnchorContract: re-fund for box MBR. Batches anchored on the old contract are no longer verifiable against the new one.
