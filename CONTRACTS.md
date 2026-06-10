# AgentAudit - Smart Contracts

Two **Algorand Python (Algokit ARC4)** contracts on **Algorand Testnet**.

| Contract | Role | Env var |
|---|---|---|
| `PolicyContract` | Multi-tenant per-agent policy check + AACR mint | `POLICY_APP_ID` |
| `AnchorContract` | Merkle root anchoring for batched records | `ANCHOR_APP_ID` |

Split rationale: per-action policy must be on-chain (independence from the agent), but per-record on-chain storage doesn't scale. Each contract does one job.

For system-level context, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## PolicyContract - `contracts/policy_contract.py`

Multi-tenant enforcer. Holds each org+agent's policy set on-chain and, per audit, evaluates the **whole set** against the reported decision, minting **1 AACR (AgentAudit Compliance Receipt)** if every rule passes. Does **not** store audit records.

### State

| Type | Name | Description |
|---|---|---|
| GlobalState `UInt64` | `compliance_asa_id` | AACR ASA ID |
| BoxMap `Bytes → PolicyRule` | `tenant_rules` (`b"r:"`) | One box per rule. Key = `sha256(org_id + agent_id + itob(idx))`. |
| BoxMap `Bytes → arc4.UInt64` | `rule_counts` (`b"rc:"`) | Rule count per agent. Key = `sha256(org_id + agent_id)`. |
| BoxMap `Bytes → arc4.Bool` | `sets` (`b"s:"`) | Membership sets for `in`/`not_in`. Key = `sha256(org_id + agent_id + field + value)`. |

There is **no global `policy_limit` and no `vendors` whitelist** — limits and whitelists are per-agent rules. Box keys are always `sha256(...)` (fixed 32 bytes), namespaced by `org_id + agent_id` so tenants never collide.

#### `PolicyRule` struct

| Field | Type | Meaning |
|---|---|---|
| `mode` | `arc4.UInt64` | `1` = on-chain (Mode 1), `2` = attested (Mode 2, private) |
| `operator` | `arc4.UInt64` | Mode-1 predicate: `1 <`, `2 <=`, `3 >`, `4 >=`, `5 ==`, `6 !=`, `7 in`, `8 not_in` |
| `value_num` | `arc4.UInt64` | Numeric threshold (Mode-1 numeric operators) |
| `field` | `arc4.String` | Decision field name (also namespaces the membership set) |
| `commitment` | `arc4.String` | Mode 2 only: `sha256(policy_doc)` hex; empty for Mode 1 |

- **Mode 1 (public):** the predicate is on-chain and the contract enforces it.
- **Mode 2 (private):** only `commitment` is on-chain; the rule stays encrypted off-chain and is enforced off-chain — the contract trusts the backend's attested per-rule result (the method is creator-gated).

### Methods

| Method | Access | Purpose |
|---|---|---|
| `initialize(compliance_asa_id)` | create-only | Set the AACR ASA ID. Creator = trusted backend/minter. |
| `opt_in_asa()` | creator | Opt contract into AACR ASA (inner asset transfer, amount 0) |
| `register_rule(org_id, agent_id, rule) -> idx` | creator | Append a `PolicyRule` to an agent's set; returns its index |
| `add_to_set(org_id, agent_id, field, value)` | creator | Add a value to an agent+field membership set (for `in`/`not_in`) |
| `remove_from_set(org_id, agent_id, field, value)` | creator | Remove a value from a membership set |
| `check_and_mint(org_id, agent_id, action_id, ipfs_hash, values_num[], values_str[], attested[]) -> result` | creator | **Main method** — evaluate the agent's whole rule set; mint AACR if all pass; return per-rule result string |

Every mutating method is **creator-only**: the backend (the contract creator) is the trusted submitter — it resolves the org from the API key / x402 payment and reports the agent's decision. `check_and_mint` is **not** public.

### `check_and_mint` logic

1. Look up `rule_count` for `(org_id, agent_id)`; assert it is > 0 and that the three input arrays (`values_num`, `values_str`, `attested`) are aligned to it by index.
2. `ensure_budget` proportional to the rule count (per-rule box reads + sha256 + compares exceed the base opcode budget).
3. For each rule `i`:
   - **Mode 1:** evaluate `operator` — numeric compare against `value_num`, or `in`/`not_in` against the `sets` box (`sha256(org_id+agent_id+field+values_str[i])`). Provenance = `onchain`.
   - **Mode 2:** take the backend's `attested[i]` result. Provenance = `attested`.
   - Append `"pass:<provenance>"` / `"fail:<provenance>"` to the result; track `all_pass`.
4. If `all_pass`: inner `AssetTransfer` of 1 AACR → `Txn.sender` (the backend, which is opted in).
5. Return the result string, e.g. `"pass:onchain|fail:attested"`.

The caller must include the relevant rule/count/set boxes in the txn's `boxes` array so the runtime can resolve the BoxMap reads.

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

## AnchorContract - `contracts/anchor_contract.py`

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
6. **With `X-Auditor-Key` header:** decrypt envelope (GCM auth tag also verifies integrity) → return plaintext + reasoning trace. For **Mode-2** rules, re-hash the decrypted policy doc, confirm it matches the on-chain `commitment`, and re-evaluate the rule — proving correct enforcement without the rule ever being public.
**Without:** return ciphertext only — tamper-evidence proven without revealing record contents.

Step 4 is the rigorous part. A passing proof means the record was provably part of the specific anchored batch — stronger than hash equality alone.

---

## Deployment Order

```
1. python scripts/gen_encryption_key.py     # → PAYLOAD_ENCRYPTION_KEY
2. python scripts/create_asa.py             # → COMPLIANCE_ASA_ID
3. python scripts/deploy_phase2.py          # → POLICY_APP_ID, ANCHOR_APP_ID
4. python scripts/opt_in_asa_phase2.py      # PolicyContract.opt_in_asa()
5. python scripts/send_aacr_to_policy.py    # send AACR supply to contract
6. python scripts/fund_anchor.py            # fund AnchorContract for box MBR
```

Policies are **not** seeded globally — they're per-tenant and registered at onboarding:
`python scripts/onboard_org.py <org_id> "<agent name>" <preset>` issues the org's credentials and calls `register_rule` / `add_to_set` on-chain for that agent. (The legacy `seed_vendors_v2.py` is stale — it calls the removed `add_vendor` method.)

Smoke test: onboard a demo org, then run an audit (e.g. via `runFlow_v2.py` or `POST /v1/audit`) — a passing decision returns a per-rule string like `pass:onchain|pass:attested` and `ASA Minted: True`, with an IPFS CID and an Algorand TX.

### Redeploy notes
- Update the corresponding `*_APP_ID` in `.env`.
- PolicyContract: re-opt-in and re-fund AACR. Rules live on-chain, so a fresh contract has **no policies** until each org re-onboards (`onboard_org.py`).
- AnchorContract: re-fund for box MBR. Batches anchored on the old contract are no longer verifiable against the new one.
