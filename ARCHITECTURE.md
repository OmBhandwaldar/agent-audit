# AgentAudit Architecture

How a single agent decision becomes a tamper-evident, independently verifiable on-chain record.

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                  React UI (Vercel)                      │
└──────────────┬──────────────────────────────┬───────────┘
               │                              │
        Run Agent / Chat                Verify Action ID
               │                              │
               ▼                              ▼
       ┌─────────────────────────────────────────────┐
       │           FastAPI Backend (Railway)         │
       └─┬────────────────────────────────────────┬──┘
         │                                        │
         ▼                                        ▼
   ┌──────────────┐                       ┌───────────────┐
   │  LangChain   │                       │   Batcher     │
   │  Agent       │                       │   (SQLite +   │
   │  + trace     │                       │    Merkle)    │
   └──────┬───────┘                       └───────┬───────┘
          │                                       │
          ▼                                       ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
   │  AES-GCM-256 │──▶│  Pinata IPFS │   │  Algorand        │
   │  encryption  │   │  (ciphertext)│   │  PolicyContract  │
   └──────────────┘   └──────────────┘   │  AnchorContract  │
                                          └──────────────────┘
```

---

## Five Layers

### 1. Agent Layer - `agent/payment_agent.py`
LangChain + Groq. Two modes:
- **Direct** (`run_payment_agent`) — one tool, evaluates amount against policy limit.
- **Chat** (`run_chat_agent`) — agentic loop, picks vendor + amount autonomously.

Both return a **reasoning trace**: `[{step, tool, args, result}]` capturing every tool call. The trace lives inside the encrypted record, so tampering with it breaks the Merkle proof.

### 2. Crypto Layer - `crypto/payload.py`
AES-GCM-256. One symmetric key (`PAYLOAD_ENCRYPTION_KEY` in `.env`), fresh 96-bit nonce per encryption, 128-bit auth tag. Auditors decrypt by passing the key in the `X-Auditor-Key` HTTP header — used once and discarded.

### 3. Storage Layer - `ipfs/uploader.py`
Encrypted envelopes → Pinata IPFS → CID. Anyone can fetch the blob; without the key it's opaque. This is what lets us anchor a public hash without leaking record contents.

### 4. Smart Contract Layer - `contracts/`
Two contracts (see [CONTRACTS.md](CONTRACTS.md)):
- **PolicyContract** — per-action policy check (amount + vendor), mints 1 AACR receipt if both pass. No on-chain record storage.
- **AnchorContract** — stores Merkle roots of batched records. One transaction anchors many decisions.

Split rationale: per-action policy *must* be on-chain (independence from the agent). Per-record on-chain storage *doesn't scale*. Each contract does one job.

### 5. Batcher Layer - `batcher/`
- `store.py` — SQLite pending-leaf store.
- `merkle.py` — SHA256 Merkle tree. Canonical leaf = `sha256(json.dumps(record, sort_keys=True))`. Sorted sibling pairs → order-independent proofs.
- `anchor.py` — flushes the store, anchors the root, persists proofs.

---

## Three Pipelines

### A. Decision (`/api/chat`, `/api/audit`)
```
Agent decides + trace → encrypt → IPFS upload → sha256(CID)
→ PolicyContract.check_and_mint (amount + vendor checks, ASA mint)
→ Record added to batch store
```

### B. Batch Anchor (`/api/batch/submit`)
```
Flush store → compute Merkle root → AnchorContract.submit_root
→ Persist per-leaf proofs back to SQLite
```
One on-chain transaction per N decisions.

### C. Verification (`/api/verify`)
```
Lookup record + proof → AnchorContract.get_root(batch_id)
→ verify_proof(leaf_hash, proof, on_chain_root)
→ Fetch ciphertext from IPFS, check sha256(CID)
→ IF X-Auditor-Key header: decrypt → plaintext + reasoning trace
   ELSE: return ciphertext only (tamper-evidence proven without revealing data)
```

**Two verification tiers:** public tamper-evidence (anyone) + private decryption (auditor key holders).

---

## Trust Boundaries

| Boundary | Trusted? | Why |
|---|---|---|
| LangChain agent | No | Observed, not trusted - its tool calls are captured and anchored. |
| Backend (FastAPI) | Only by the deployer | Anyone can re-verify records independently. |
| IPFS / Pinata | Not for integrity | Anchored `sha256(cid)` detects any IPFS alteration. |
| Algorand contracts | **Yes - root of trust** | On-chain state is the immutable reference. |
| Auditor key holder | Trusted for plaintext reads only | Cannot alter records or anchored state. |

---

## Failure Modes

| Attack | Detected by |
|---|---|
| IPFS data altered after anchoring | `sha256(cid)` mismatch on verify |
| Anchored record dropped from batch | Merkle proof cannot be constructed |
| Anchored record swapped in batch | Leaf hash mismatch → proof fails |
| Reasoning trace tampered (post-decrypt) | GCM auth tag fails; even if re-encrypted, leaf hash changes → Merkle proof breaks |
| Agent decision overrides policy | On-chain `policy_result` is binding; ASA only mints when policy passes |

---

## Design Rationale

| Choice | Why |
|---|---|
| Two contracts (Policy + Anchor) | Policy enforcement and bulk anchoring have different cost models. Splitting lets each do one thing well. |
| AES-GCM-256, not ZK | Need confidentiality + tamper-evidence in one shot, no proving overhead. ZK is a future extension. |
| Symmetric encryption | One key per org is operationally trivial. Per-record keys would explode key management. |
| Merkle batching | Same model as Certificate Transparency, Bitcoin SPV, every L2 rollup. Minimal on-chain state, well-understood proofs. |
| SQLite batch store | Local, atomic, single-file. No infra to manage. Production scale would use Postgres. |
| Trace inside encrypted payload | Existing Merkle proof covers the trace for free - no second tamper-evidence story needed. |

---

## File Map

```
agent/payment_agent.py            - Agent + reasoning trace capture
crypto/payload.py                 - AES-GCM-256 encrypt/decrypt
ipfs/uploader.py                  - Pinata IPFS upload
contracts/policy_contract.py      - PolicyContract (per-action)
contracts/anchor_contract.py      - AnchorContract (batch anchor)
batcher/merkle.py                 - Merkle math
batcher/store.py                  - SQLite leaf store
batcher/anchor.py                 - flush_and_anchor
algorand/contract_client_v2.py    - Contract clients
sdk/audit_flow_v2.py              - Pipeline orchestrator
api/main.py                       - HTTP surface (FastAPI)
```

For contract-level reference (state, methods, ASA setup), see [CONTRACTS.md](CONTRACTS.md).
