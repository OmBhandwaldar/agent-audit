# Phase 2 Plan — Split Contracts + Merkle Batching + Encryption

**Goal:** Upgrade AgentAudit from a single-contract per-record flow to a privacy-preserving, batched architecture without breaking the existing demo.

**Timeline:** 10 days from start.
**Branch:** `phase-2-merkle` (do NOT merge to `main` until Day 9 testing passes).
**Validated by:** Office hours feedback — judges suggested this direction.

---

## 1. Why We Are Doing This

The current architecture works, but has three weaknesses that judges already flagged:

1. **Privacy** — IPFS payload is plaintext. Anyone with the CID sees the full decision.
2. **Scalability** — Every decision writes a box. On-chain storage cost grows linearly with usage.
3. **Cost narrative** — "Audit every AI decision" is undermined if each audit costs a full tx.

Phase 2 fixes all three:

| Problem | Fix |
|---|---|
| Plaintext IPFS | AES-GCM encryption — only auditor with key can read |
| Per-record on-chain storage | Merkle batching — one root anchors N records |
| Tx cost per audit | Amortized across batch — ~100x reduction at scale |

What stays the same: real-time on-chain policy enforcement + AACR receipt minting per decision. The killer demo feature is preserved.

---

## 2. Branch Strategy (CRITICAL)

The current `main` branch is a working, demo-ready system. We do NOT touch it.

```
main             ← frozen working demo (current single-contract flow)
└── phase-2-merkle    ← all Phase 2 work here
```

**Rules:**

- All work on `phase-2-merkle`.
- Do NOT delete or modify `contracts/audit_contract.py` — leave it as-is on this branch too.
- New contracts go in NEW files: `contracts/policy_contract.py` + `contracts/anchor_contract.py`.
- New env vars are ADDED, not replaced. Old `CONTRACT_APP_ID` stays in `.env` for fallback.
- If by Day 9 the new flow has bugs that risk the demo: switch back to `main`, demo the old version, pitch Phase 2 as roadmap.

**Commit cadence:** at least one commit per day, scoped to one piece (contracts, encryption, batcher, etc.).

**Merge criteria for `main`:** Day 9 testing must pass 20 consecutive end-to-end runs with zero errors. If not, do not merge — demo from `main`.

---

## 3. Architecture — Before vs. After

### Current (main branch)

```
Agent decision
  ↓
IPFS upload (plaintext JSON) → CID
  ↓
sha256(CID) = ipfs_hash
  ↓
AuditContract.submit_audit(action_id, ipfs_hash, amount, vendor_id, ...)
  ├─ Stores AuditRecord in box (sha256(action_id) → record)
  ├─ Checks: amount < limit AND vendor in whitelist
  └─ If both pass: mints 1 AACR to caller
```

One contract. One tx per decision. Plaintext payload. All record fields on-chain.

### Phase 2 (phase-2-merkle branch)

```
Agent decision
  ↓
ENCRYPT payload with AUDITOR_KEY (AES-GCM)
  ↓
IPFS upload (ciphertext) → CID
  ↓
sha256(CID) = ipfs_hash
  ↓
PolicyContract.check_and_mint(action_id, ipfs_hash, amount, vendor_id, ...)
  ├─ Checks: amount < limit AND vendor in whitelist
  ├─ If both pass: mints 1 AACR to caller
  └─ Emits log event with leaf data (no box storage)
  ↓
Batcher.add_leaf(leaf)  ← writes to SQLite
  ↓
[Pending leaves accumulate]
  ↓
[Manual trigger: POST /api/batch/submit]
  ↓
Build Merkle tree from pending leaves
  ↓
AnchorContract.submit_root(batch_id, merkle_root)
  └─ Stores root in box (sha256(batch_id) → root)
  ↓
Mark leaves as anchored in SQLite (with batch_id + proof path)
```

**Two contracts. ~1 anchor tx per N decisions. Encrypted payload. Records live in SQLite + Merkle tree, only root on-chain.**

### Verification flow (Phase 2)

```
User enters action_id
  ↓
Backend SQLite lookup → leaf, batch_id, proof
  ↓
AnchorContract.get_root(batch_id) → on-chain root
  ↓
Verify: hash up the proof path → does it equal on-chain root?
  ↓
Fetch ciphertext from IPFS
  ↓
If auditor key provided: decrypt → return plaintext record
Else: return ciphertext + "encrypted" flag
```

---

## 4. New Components

| Component | Path | Purpose |
|---|---|---|
| Policy Contract | `contracts/policy_contract.py` | Stateless: check policy, mint ASA, emit log. No box storage. |
| Anchor Contract | `contracts/anchor_contract.py` | Holds Merkle roots in box storage, keyed by batch_id. |
| Encryption module | `crypto/payload.py` | AES-GCM encrypt/decrypt for IPFS payloads. |
| Batcher store | `batcher/store.py` | SQLite layer: pending leaves, anchored leaves, proofs. |
| Merkle tree | `batcher/merkle.py` | Pure Python SHA256 binary Merkle tree + proof generation. |
| Anchor submitter | `batcher/anchor.py` | Calls AnchorContract.submit_root with computed root. |
| Updated SDK | `sdk/audit_flow.py` | New `run_audit_flow_v2()` — calls policy contract + batcher add_leaf. |
| Batch endpoint | `api/main.py` | `POST /api/batch/submit`, updated `/api/verify`. |
| Frontend | `frontend/src/components/` | Submit Batch button, verify with proof + decryption status. |

---

## 5. 10-Day Schedule

| Day | Focus | Deliverable | Done = |
|---|---|---|---|
| 1 | Branch + contracts split | Two contracts written, deployed, App IDs in `.env` | Both contracts visible on testnet explorer |
| 2 | Reseed vendors + integration | `algorand/contract_client_v2.py` calls both contracts | Single audit run end-to-end on new contracts (no batching yet) |
| 3 | Encryption layer | `crypto/payload.py` + uploader updated | Pinata gateway shows ciphertext |
| 4 | Merkle batcher core | `batcher/merkle.py` + `batcher/store.py` | Unit test: add 5 leaves → build tree → verify proof |
| 5 | Anchor submission | `batcher/anchor.py` + `/api/batch/submit` endpoint | Manual run: click endpoint → root tx confirmed |
| 6 | Pipeline wiring | `run_audit_flow_v2` calls policy contract + add_leaf | Full path: chat → policy check → leaf in SQLite |
| 7 | Verify rewrite | `/api/verify` does Merkle proof + decryption | Verify returns hash_match + decrypted record |
| 8 | Frontend updates | Submit Batch button + verify UI updates | Browser flow works end-to-end |
| 9 | **Hard testing gate** | 20+ runs with zero errors | All edge cases tested, bugs fixed |
| 10 | Demo video + slides | Backup video recorded | Submission ready |

If Day 4–5 slips → cut frontend polish on Day 8, NOT testing on Day 9.

---

## 6. Smart Contract Changes

### Policy Contract (`contracts/policy_contract.py`)

**State:**
- `compliance_asa_id: GlobalState` — same as before
- `policy_limit: GlobalState` — same as before
- `vendors: BoxMap` — same as before (whitelist lives here)
- **No `records` BoxMap** — this is the key difference

**Methods:**
- `initialize(compliance_asa_id, policy_limit)` — same
- `opt_in_asa()` — same
- `add_vendor(vendor_id)` — same
- `remove_vendor(vendor_id)` — same
- `check_and_mint(action_id, ipfs_hash, amount, vendor_id, agent_id, timestamp) -> String`
  - Runs both policy checks
  - Mints 1 AACR to caller if both pass
  - Returns `"amount:pass|vendor:pass"` (or fail per check)
  - **Does NOT store record on-chain**
  - Logs the leaf data via `log()` opcode for off-chain indexing if needed

### Anchor Contract (`contracts/anchor_contract.py`)

**State:**
- `roots: BoxMap` — `key_prefix=b"root:"`, key = `sha256(batch_id.bytes)`, value = `arc4.StaticArray[Byte, 32]` (the Merkle root)

**Methods:**
- `submit_root(batch_id: String, merkle_root: Bytes)` — creator only, stores root in box
- `get_root(batch_id: String) -> Bytes` — read-only, returns root for verification

That's it. Two methods. ~30 lines of code.

### Vendor reseed

After deploying Policy Contract, run `python scripts/seed_vendors_v2.py` to add VENDOR_001, VENDOR_002 to the new contract's whitelist. Keep VENDOR_999 unseeded for the rejection demo.

---

## 7. Encryption Layer (`crypto/payload.py`)

```python
# Pseudocode — actual implementation Day 3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, json, base64, secrets

def get_auditor_key() -> bytes:
    """Load 32-byte key from AUDITOR_KEY env (base64)."""
    key_b64 = os.getenv("AUDITOR_KEY")
    if not key_b64:
        raise RuntimeError("AUDITOR_KEY not set")
    return base64.b64decode(key_b64)

def encrypt_payload(record: dict) -> dict:
    """Returns {"ciphertext": ..., "nonce": ..., "encrypted": True}."""
    key = get_auditor_key()
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(record, sort_keys=True).encode()
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return {
        "ciphertext": base64.b64encode(ct).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "encrypted": True,
        "version": "v2-aesgcm",
    }

def decrypt_payload(blob: dict) -> dict:
    """Reverse of encrypt_payload."""
    key = get_auditor_key()
    nonce = base64.b64decode(blob["nonce"])
    ct = base64.b64decode(blob["ciphertext"])
    pt = AESGCM(key).decrypt(nonce, ct, None)
    return json.loads(pt)
```

**Generate the key once:** `python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` → save in `.env` as `AUDITOR_KEY=...`.

**Pinning:** the encrypted blob is itself a JSON object. Pin it via the existing `pinJSONToIPFS` endpoint — no special binary handling needed.

---

## 8. Merkle Batcher

### Leaf format

A leaf is the canonical hash of one decision. Use SHA256 of a sorted-JSON serialization:

```python
def leaf_hash(record: dict) -> bytes:
    canonical = json.dumps({
        "action_id": record["action_id"],
        "ipfs_hash": record["ipfs_hash"],
        "amount": record["amount"],
        "vendor_id": record["vendor_id"],
        "agent_id": record["agent_id"],
        "timestamp": record["timestamp"],
        "decision": record["decision"],
        "policy_result": record["policy_result"],
    }, sort_keys=True).encode()
    return hashlib.sha256(canonical).digest()
```

### Tree (binary, SHA256, duplicate-last for odd levels)

```python
def build_tree(leaves: list[bytes]) -> list[list[bytes]]:
    """Returns list of levels, level 0 = leaves, last level = [root]."""
    if not leaves:
        raise ValueError("cannot build tree from empty leaves")
    levels = [leaves]
    while len(levels[-1]) > 1:
        prev = levels[-1]
        if len(prev) % 2 == 1:
            prev = prev + [prev[-1]]  # duplicate last
        nxt = [hashlib.sha256(prev[i] + prev[i+1]).digest()
               for i in range(0, len(prev), 2)]
        levels.append(nxt)
    return levels

def get_proof(tree: list[list[bytes]], index: int) -> list[tuple[bytes, str]]:
    """Returns list of (sibling_hash, 'L' or 'R')."""
    proof = []
    for level in tree[:-1]:
        sibling_idx = index ^ 1  # XOR with 1 flips last bit
        if sibling_idx >= len(level):
            sibling_idx = index  # duplicate-last case
        side = "L" if sibling_idx < index else "R"
        proof.append((level[sibling_idx], side))
        index //= 2
    return proof

def verify_proof(leaf: bytes, proof: list, root: bytes) -> bool:
    h = leaf
    for sibling, side in proof:
        if side == "L":
            h = hashlib.sha256(sibling + h).digest()
        else:
            h = hashlib.sha256(h + sibling).digest()
    return h == root
```

### SQLite schema

```sql
CREATE TABLE leaves (
    action_id TEXT PRIMARY KEY,
    leaf_hash BLOB NOT NULL,
    record_json TEXT NOT NULL,        -- full leaf source for re-hashing/verification
    batch_id TEXT,                    -- NULL until anchored
    leaf_index INTEGER,               -- position in batch
    proof_json TEXT,                  -- JSON-encoded proof path
    created_at INTEGER NOT NULL
);

CREATE TABLE batches (
    batch_id TEXT PRIMARY KEY,
    merkle_root BLOB NOT NULL,
    leaf_count INTEGER NOT NULL,
    anchor_tx_id TEXT NOT NULL,
    submitted_at INTEGER NOT NULL
);

CREATE INDEX idx_leaves_batch ON leaves(batch_id);
```

### Submit batch flow

```
POST /api/batch/submit
  ↓
SELECT * FROM leaves WHERE batch_id IS NULL ORDER BY created_at
  ↓
If empty: return 400 "no pending leaves"
  ↓
batch_id = f"batch_{int(time.time())}_{random.randint(1000,9999)}"
  ↓
build_tree(leaf_hashes) → root + tree
  ↓
For each leaf: compute proof, store proof_json + batch_id + leaf_index
  ↓
AnchorContract.submit_root(batch_id, root) → tx_id
  ↓
INSERT INTO batches (...)
  ↓
Return { batch_id, root: hex, leaf_count, anchor_tx_id }
```

---

## 9. API Changes

### Existing endpoints (kept, but updated internally)

| Endpoint | Change |
|---|---|
| `POST /api/audit` | Calls `run_audit_flow_v2` → policy contract + batcher.add_leaf. Returns `pending_anchor: True` |
| `POST /api/chat` | Same — calls v2 flow |
| `GET /api/verify?action_id=...` | Now does Merkle proof verification + optional decryption |
| `GET /api/dashboard` | Add `pending_leaves_count`, `last_anchor_batch_id` |
| `GET /api/export/csv` | Same |
| `GET /api/tamper-demo` | Updated — show that tampering fails Merkle proof |

### New endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/batch/submit` | Manually trigger batch anchor |
| `GET /api/batch/status` | List pending leaves + recent batches |
| `GET /api/batch/:batch_id` | Inspect a specific batch (root, leaf count, tx) |

### Verify response (new shape)

```json
{
  "action_id": "1746543210_4521",
  "verification": {
    "merkle_proof_valid": true,
    "ipfs_hash_match": true,
    "batch_id": "batch_1746543300_8821",
    "merkle_root_onchain": "0xabcd...",
    "merkle_root_computed": "0xabcd..."
  },
  "decryption": {
    "encrypted": true,
    "decrypted": true,
    "record": { "action": "approve_payment", "amount": 4500, ... }
  }
}
```

If no auditor key header is provided: `decryption.decrypted = false`, `record` is omitted, ciphertext blob is returned.

---

## 10. Frontend Changes

| Page | Change |
|---|---|
| Chat / Audit form | After submission, show "✅ Policy passed, leaf pending anchor (batch will be submitted shortly)" |
| Dashboard | New widget: "Pending leaves: N — [Submit Batch] button" |
| Verify tab | Show Merkle proof verification (✅/❌) + decryption status (✅/❌) + record |
| Tamper demo | Updated copy: "Tampering changes the leaf hash → Merkle proof breaks → root mismatch" |

The Submit Batch button is part of the demo. Make it prominent.

---

## 11. Environment Variables

Add to `.env`:

```
# Phase 2 — new
POLICY_APP_ID=<deployed Day 1>
ANCHOR_APP_ID=<deployed Day 1>
AUDITOR_KEY=<base64 32-byte key>
BATCHER_DB_PATH=./data/batcher.db   # or /data/batcher.db on Railway with volume

# Phase 2 — kept for fallback
CONTRACT_APP_ID=758124440           # original single contract
COMPLIANCE_ASA_ID=<existing>
```

`AUDITOR_KEY` generation:
```bash
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

---

## 12. Example End-to-End Flow

Concrete walkthrough with real-ish numbers.

### Step 1 — User submits a chat request

```
POST /api/chat
{ "message": "Pay VENDOR_001 ₹4500 for office laptop" }
```

### Step 2 — Agent picks vendor and amount

LangChain agent:
- amount: 4500
- vendor_id: VENDOR_001
- decision: approved
- reason: "Selected ABC Suppliers (VENDOR_001) at ₹4500 — within budget"

### Step 3 — Build record + encrypt

```python
record = {
  "action_id": "1746543210_4521",
  "action": "approve_payment",
  "amount": 4500,
  "vendor_id": "VENDOR_001",
  "agent_id": "payment_agent_001",
  "decision": "approved",
  "policy": "limit_5000",
  "timestamp": 1746543210,
  "reason": "...",
  "prompt": "Pay VENDOR_001 ₹4500 for office laptop"
}

encrypted_blob = encrypt_payload(record)
# → {"ciphertext": "qX9k...==", "nonce": "abc==", "encrypted": true, "version": "v2-aesgcm"}
```

### Step 4 — Pin to IPFS

```
cid = await upload_to_ipfs(encrypted_blob)
# → "QmZ9...XyZ"
ipfs_hash = sha256(cid.encode()).hexdigest()
# → "f4a2...c8d1"
```

### Step 5 — Call Policy Contract

```
PolicyContract.check_and_mint(
  action_id="1746543210_4521",
  ipfs_hash="f4a2...c8d1",
  amount=4500,
  vendor_id="VENDOR_001",
  agent_id="payment_agent_001",
  timestamp=1746543210,
)
→ returns "amount:pass|vendor:pass"
→ mints 1 AACR to deployer wallet
→ tx_id = "ALGO_TX_ABC123"
```

### Step 6 — Add leaf to batcher

```python
leaf = leaf_hash(record_with_policy_result)
batcher.store.add_leaf(
  action_id="1746543210_4521",
  leaf_hash=leaf,
  record_json=json.dumps(record_with_policy_result),
)
# SQLite now has 1 pending leaf
```

### Step 7 — Response to user

```json
{
  "reply": "I've selected ABC Suppliers (VENDOR_001) at ₹4,500. Payment approved.",
  "audit_result": {
    "decision": "approved",
    "ipfs_cid": "QmZ9...XyZ",
    "policy_tx_id": "ALGO_TX_ABC123",
    "asa_minted": true,
    "action_id": "1746543210_4521",
    "anchor_status": "pending",
    "encrypted": true
  }
}
```

### Step 8 — User runs 2 more requests

Now SQLite has 3 pending leaves.

### Step 9 — Click "Submit Batch"

```
POST /api/batch/submit
```

Backend:
- Reads 3 pending leaves
- Builds Merkle tree (3 leaves → root)
- For each leaf: computes proof, stores in `proof_json`, sets `batch_id`, `leaf_index`
- AnchorContract.submit_root(batch_id, root)
- Stores batch record

Response:
```json
{
  "batch_id": "batch_1746543300_8821",
  "merkle_root": "0xab12...cd34",
  "leaf_count": 3,
  "anchor_tx_id": "ALGO_TX_DEF456"
}
```

### Step 10 — Verify a record

```
GET /api/verify?action_id=1746543210_4521
Header: X-Auditor-Key: <base64 key>
```

Backend:
1. SQLite lookup → leaf, proof, batch_id
2. AnchorContract.get_root("batch_1746543300_8821") → on-chain root
3. verify_proof(leaf, proof, root) → True
4. Fetch ciphertext from IPFS via Pinata
5. decrypt_payload(blob) → plaintext record

Response: full verified + decrypted record.

---

## 13. Demo Flow (3 minutes)

1. **(20s) Show landing page** — "AgentAudit: tamper-proof audit for AI agents."
2. **(30s) Submit chat request** — "Pay VENDOR_001 ₹4500." Show approved + tx link.
3. **(20s) Click IPFS link** — show ciphertext gibberish on Pinata gateway. *"Public sees nothing."*
4. **(20s) Submit 2 more requests** — different amounts/vendors. One rejected (VENDOR_999).
5. **(15s) Dashboard** — "3 leaves pending anchor."
6. **(20s) Click Submit Batch** — show one tx anchoring all 3. Click tx link → testnet explorer.
7. **(30s) Verify tab** — paste action_id. With key: show Merkle proof valid + decrypted record. Without key: show ciphertext only.
8. **(15s) Tamper demo** — "Change one byte in IPFS → Merkle proof breaks."
9. **(10s) Close** — "Same infrastructure works for any agent decision."

---

## 14. Things to Remember (Pitfalls)

### Crypto / encryption
- AUDITOR_KEY must be 32 bytes exactly (256-bit AES). Validate on load.
- Never log the key. Never commit it. `.env` only.
- AES-GCM nonce must be unique per encryption. Use `secrets.token_bytes(12)`.
- Sort keys when serializing JSON for hashing — otherwise different machines produce different hashes.

### Merkle tree
- Always handle odd-leaf-count case. Standard convention: duplicate the last leaf.
- Use `hashlib.sha256(left + right).digest()` — raw bytes, not hex. Hex doubles size and breaks compatibility.
- Proof generation must match verification exactly. Test both with the same library.
- Leaf hashing must be deterministic — same input bytes always produce same hash. Sort JSON keys.

### Algorand / contracts
- Box keys MUST be fixed-length. Use `sha256(batch_id.bytes)` for anchor box keys, never raw strings.
- Anchor contract storage: use `arc4.StaticArray[arc4.Byte, 32]` for the root, not `Bytes`. Static arrays are cheaper and predictable.
- `submit_root` must be creator-only — `assert Txn.sender == Global.creator_address`.
- After redeploy, REMEMBER: opt the contract into ASA + send supply + reseed vendors. Three steps.

### SQLite
- Set `BATCHER_DB_PATH=./data/batcher.db` and create the `data/` folder before first run.
- Add `data/` to `.gitignore` immediately. Never commit the SQLite file.
- On Railway: mount a Volume at `/data` and set `BATCHER_DB_PATH=/data/batcher.db` to survive redeploys.
- Use `?` placeholders for SQL params. Never f-string into SQL.

### API / pipeline
- Make encryption and batching opt-in via env flag for the first few days. `USE_PHASE_2=true` toggles between v1 and v2 flow. Lets you compare side-by-side.
- Off-topic chat responses should NOT add a leaf to the batcher. Only real audit decisions.
- If policy check fails (rejected) — still add the leaf. Rejection is also auditable.
- `/api/verify` should gracefully handle: leaf not found, batch not anchored yet, key missing, proof invalid.

### Demo
- Keep the existing single-contract demo flow accessible via a feature flag. If the new flow breaks live, flip the flag.
- Pre-warm the demo: have at least 2 pending leaves before recording video.
- Practice the "Submit Batch" button moment. It's the visual centerpiece.
- Don't refresh the browser during the demo — keep all state in memory.

### Branch hygiene
- Never push `phase-2-merkle` to `main` until Day 9 testing passes.
- Tag the current `main` HEAD as `v1.0-demo-ready` before starting Phase 2 work. Easy rollback.
- Each commit message: `phase2: <what changed>`. Easy to filter later.

---

## 15. Rollback Plan

If by Day 9 the new flow has any of:
- Merkle proof verification failing intermittently
- Batch submission tx failures
- Decryption failures
- Frontend showing inconsistent state

→ Demo from `main` branch instead. Phase 2 becomes a roadmap slide.

```bash
git checkout main
# verify single-contract demo works end-to-end
python scripts/runFlow.py 3000 VENDOR_001
```

The existing `main` flow is the safety net. Treat it as sacred.

---

## 16. Success Criteria

By Day 10, the following must all be true:

- [ ] Both new contracts deployed on testnet, App IDs in `.env`
- [ ] VENDOR_001 + VENDOR_002 seeded on Policy Contract
- [ ] Encryption layer working — Pinata gateway shows ciphertext
- [ ] Batcher SQLite stores leaves, computes proofs, submits roots
- [ ] `POST /api/batch/submit` works and returns `{batch_id, root, tx_id}`
- [ ] `GET /api/verify` does Merkle proof + decryption with auditor key header
- [ ] Frontend shows pending count + Submit Batch button
- [ ] Frontend verify tab shows proof + decryption status
- [ ] Tamper demo updated to break Merkle proof
- [ ] 20+ consecutive end-to-end runs with zero errors
- [ ] Backup demo video recorded
- [ ] Slides updated (architecture diagram + roadmap)
- [ ] `main` branch untouched (or merged only after Day 9 gate)

---

## 17. Daily Standup Questions

Ask yourself at end of each day:

1. Did I complete today's deliverable?
2. Is the code committed to `phase-2-merkle`?
3. Is the next day's task clearly scoped?
4. Did I introduce any blocker for the demo?
5. Can I still fall back to `main` if needed?

If the answer to any is unclear, stop and reassess before adding code.

---

## Appendix A — File Tree (final state of phase-2-merkle branch)

```
agent-audit/
├── PHASE2_PLAN.md                       # this file
├── CLAUDE.md
├── .env
├── .env.example                         # add AUDITOR_KEY=, POLICY_APP_ID=, ANCHOR_APP_ID=
├── requirements.txt                     # + cryptography
├── data/                                # gitignored
│   └── batcher.db
├── contracts/
│   ├── audit_contract.py                # KEPT — original (fallback)
│   ├── policy_contract.py               # NEW
│   └── anchor_contract.py               # NEW
├── crypto/
│   └── payload.py                       # NEW — AES-GCM
├── batcher/
│   ├── __init__.py
│   ├── store.py                         # NEW — SQLite
│   ├── merkle.py                        # NEW — tree + proofs
│   └── anchor.py                        # NEW — submit_root caller
├── algorand/
│   ├── client.py
│   ├── contract_client.py               # KEPT — original
│   └── contract_client_v2.py            # NEW — calls policy + anchor
├── sdk/
│   └── audit_flow.py                    # UPDATED — adds run_audit_flow_v2
├── agent/
│   ├── payment_agent.py                 # unchanged
│   └── vendors.py                       # unchanged
├── ipfs/
│   └── uploader.py                      # UPDATED — encrypt before pin
├── api/
│   └── main.py                          # UPDATED — new endpoints + verify rewrite
├── scripts/
│   ├── runFlow.py                       # KEPT
│   ├── seed_vendors.py                  # KEPT
│   ├── seed_vendors_v2.py               # NEW
│   ├── deploy_phase2.py                 # NEW — deploys both new contracts
│   └── gen_auditor_key.py               # NEW — outputs base64 key
├── frontend/                            # UPDATED — UI changes per Day 8
└── tests/
    ├── test_flow.py
    ├── test_merkle.py                   # NEW
    └── test_encryption.py               # NEW
```

---

## Appendix B — Quick Reference Commands

```bash
# Generate auditor key
python scripts/gen_auditor_key.py

# Deploy Phase 2 contracts
python scripts/deploy_phase2.py

# Seed vendors on new policy contract
python scripts/seed_vendors_v2.py

# Run end-to-end checkpoint (Phase 2)
python scripts/runFlow.py 4500 VENDOR_001 --v2

# Submit pending batch via curl
curl -X POST http://localhost:8000/api/batch/submit

# Verify a record
curl "http://localhost:8000/api/verify?action_id=1746543210_4521" \
  -H "X-Auditor-Key: <base64>"

# Inspect SQLite
sqlite3 data/batcher.db "SELECT action_id, batch_id FROM leaves;"

# Branch ops
git checkout -b phase-2-merkle
git tag v1.0-demo-ready main
```

---

**Last reminder:** Day 9 is the gate. If testing reveals fragility, demo from `main`. Do not gamble the submission on a half-tested architecture.
