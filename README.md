# AgentAudit

Verifiable compliance infrastructure for autonomous AI agents.

**Live Demo:** https://agentaudit.tech

**Demo Video:** https://youtu.be/lz71ab2ZaP0

**Deployed Smart Contracts (Algorand Testnet):**
- PolicyContract App ID: `763911528`
- AnchorContract App ID: `762026494`
- AACR Compliance ASA ID: `757894056`

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system layers, three pipelines (decision / anchor / verification), trust boundaries, failure modes
- [Smart Contracts](docs/CONTRACTS.md) — PolicyContract + AnchorContract reference: state, methods, ASA setup, Merkle leaf format, deployment order
- [Setup Guide](#how-to-run-locally) — local installation and first-time setup

---

## The Problem

AI agents are making real financial decisions like approving payments, onboarding vendors, and triggering workflows. But their audit logs sit in the same database controlled by the organization running them. That is self-reporting, not compliance. An auditor or regulator has no way to independently verify anything.

AgentAudit fixes this by anchoring every agent decision to Algorand, outside the deployer's control.

---

## What It Does

Every AI agent decision is:

1. **Captured with full reasoning trace** - what the agent decided plus every tool it called along the way
2. **Encrypted with AES-GCM-256** and uploaded to **IPFS** - ciphertext only, plaintext gated by auditor key
3. **Policy-checked on-chain** - budget limit and vendor whitelist, both enforced by the smart contract independently of the agent
4. Receipted with a **non-transferable ASA** compliance receipt minted only when all checks pass
5. **Batched and Merkle-anchored** to the **Algorand blockchain** - one transaction anchors many records, each provable individually
6. **Independently verifiable** by anyone with an Action ID via cryptographic Merkle proof, no trust required

---

## End-to-End Flow

**Decision pipeline:**
```
User prompt → LangChain agent picks vendor (reasoning trace captured at every tool call)
→ Decision + trace encrypted with AES-GCM-256 → Ciphertext uploaded to IPFS
→ CID hashed with SHA256 → Hash submitted to PolicyContract on Algorand
→ Contract checks budget limit + vendor whitelist → ASA minted if both pass
→ Record added to local batch store → Result shown in chat UI
```

**Anchor pipeline (batch submission):**
```
Batch flushed → Merkle tree computed over all leaf hashes
→ Root anchored to AnchorContract on Algorand in a single transaction
→ Each record now has a cryptographic proof of inclusion in the on-chain root
```

**Verification pipeline:**
```
Action ID → Fetch record + Merkle proof → Verify inclusion in anchored root on-chain
→ Fetch ciphertext from IPFS → Confirm hash matches
→ Without auditor key: tamper-evidence only (ciphertext returned)
→ With auditor key (X-Auditor-Key header): decrypt → show decision + full reasoning trace
```

---

## Integrating Your Agent

AgentAudit is multi-tenant. Any company onboards itself, gets credentials, and drops the SDK into its existing agent — with no changes to the agent's own logic.

1. **Onboard** (self-serve via the web UI or `POST /v1/onboard`): declare your policies. You receive an **API key**, a system-issued **agent ID** (`agt_…`), and an **encryption key** (shown once).
2. **Install the SDK:** `pip install agentaudit-core`
3. **Integrate** — one decorator above your decision function (or an explicit `audit.audit(...)` call):

```python
from agentaudit import AuditClient

audit = AuditClient(api_key="aa_…")                            # subscription
# or pay-per-call: AuditClient(org_id="…", x402_mnemonic="…")  # x402, $0.01 USDC / decision

@audit.capture(agent_id="agt_…", action="approve_payment")
def decide(...):
    ...  # your existing agent logic, unchanged
    return {"decision": "approved", "fields": {"amount": 40000, "vendor": "VENDOR_002"}}
```

Every decision is then policy-checked on-chain, encrypted, and Merkle-anchored automatically. A language-agnostic REST endpoint (`POST /v1/audit` with a Bearer key) works for any stack.

**Policy privacy:** policies can be **public** (Mode 1, enforced on-chain) or **private** (Mode 2 — only a SHA-256 commitment goes on-chain; the rule is encrypted off-chain and re-checkable with the auditor key). A confidential vendor or hospital whitelist enforces and verifies without ever becoming public.

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Agent | LangChain + Groq (llama-3.3-70b-versatile) |
| Encryption | AES-GCM-256 (authenticated encryption) |
| Off-chain Storage | Pinata IPFS (encrypted payloads only) |
| Blockchain | Algorand Testnet |
| Smart Contracts | PolicyContract + AnchorContract (Algorand Python via Algokit ARC4) |
| Batch Anchoring | Merkle tree over batched records, anchored as one on-chain transaction |
| Compliance Receipt | Algorand Standard Asset (ASA) |
| Batch Store | SQLite (local pending batch state) |
| Backend | FastAPI on Railway |
| Frontend | React + Tailwind CSS on Vercel |
| Pay-per-call | x402 protocol + USDC on Algorand (optional billing mode) |

---

## Features

- **Self-Serve Onboarding + SDK** - Any company onboards itself, declares its policies (public or private), and drops the SDK into its agent — a `@audit.capture` decorator or an explicit call. Subscription or x402 pay-per-call billing.
- **On-Chain Policy Enforcement** - Policies (amount limits, whitelists, custom predicates) are checked by the smart contract independently of the agent. The on-chain decision is authoritative — it can override what the agent decided.
- **Private (Mode-2) Policies** - Confidential rules: only a SHA-256 commitment goes on-chain, the rule itself is encrypted off-chain and re-checkable with the auditor key. A private vendor/hospital whitelist enforces and verifies without ever being public.
- **Encrypted Records (AES-GCM-256)** - Every decision and its reasoning trace is encrypted before upload to IPFS. Public tamper-evidence; private contents gated by the auditor key.
- **Merkle Batch Anchoring** - Many records are anchored to Algorand in a single transaction, each with its own inclusion proof — flat on-chain cost regardless of volume.
- **ASA Compliance Receipt** - Non-transferable receipt minted on Algorand only when all policies pass.
- **Audit Dashboard** - Real-time compliance rate and full audit history with agent and policy decisions side by side. Filter by organization to see any single tenant's isolated log.
- **Independent Verification** - Anyone can verify any past decision by Action ID. Reconstructs the Merkle proof against the anchored on-chain root, confirms IPFS ciphertext integrity, and optionally decrypts the full record (including agent reasoning trace) with an auditor key.

---

## What's New in Round 4

### Multi-Tenant SDK Platform
- **What it does:** Any company self-onboards, declares its policies, and integrates its own agent with the SDK (`pip install agentaudit-core`) — one decorator line, no change to the agent's logic. Each org gets a hashed API key and a system-issued opaque agent ID; tenants are isolated by org.
- **Why I added it:** The Round 3 demo audited one built-in agent. The product is infrastructure — it has to work for *any* company's *any* agent, self-serve.

### x402 Pay-Per-Call Billing
- **What it does:** Agents can pay $0.01 USDC per decision over x402 instead of a subscription — the SDK auto-pays and the facilitator settles before the audit runs.
- **Why I added it:** Autonomous agents should be able to pay per use without a human signing up for a plan.

### Private (Mode-2) Policies
- **What it does:** A policy can be confidential — only its SHA-256 commitment goes on-chain; the rule is encrypted off-chain and re-checkable with the auditor key. A private vendor/hospital whitelist enforces and verifies without ever being public.
- **Why I added it:** Real compliance rules are sensitive business data. They must be enforceable and auditable without disclosure.

### Per-Org Dashboard
- **What it does:** The dashboard scopes its feed and stats to any single onboarded organization (`/api/orgs` + an org filter), making tenant isolation visible.
- **Why I added it:** A multi-tenant platform needs a per-tenant view; a global feed contradicts the isolation guarantee.

---

## What's New in Round 3

### Agent Reasoning Trace
- **What it does:** Captures every tool the agent called, the arguments it passed, and the result it got — stored as a structured trace inside the encrypted record.
- **Why I added it:** Compliance needs the decision process, not just the outcome. Auditors can now see how the agent reached its decision, not just what it decided.

### AES-GCM-256 Encryption
- **What it does:** Records are encrypted before upload to IPFS. Plaintext is only readable with the auditor key; the ciphertext is what gets hashed and anchored.
- **Why I added it:** IPFS is public. Encryption separates open tamper-evidence (anyone can verify) from private record contents (auditors only).

### Merkle Batch Anchoring
- **What it does:** Records are batched, hashed into a Merkle tree, and the root is anchored to Algorand in one transaction. Each record gets its own inclusion proof.
- **Why I added it:** Per-record anchoring is expensive at scale. Batching cuts on-chain cost dramatically while preserving per-record tamper-evidence.

### Auditor Key-Gated Verification
- **What it does:** Two-tier verify. Tamper-evidence is public; decrypted contents require the `X-Auditor-Key` header. Without it, only the ciphertext is returned.
- **Why I added it:** Verifiability should be public, but record contents are sensitive business data. This gives both — open proof, controlled access.

### Cryptographic Merkle Proof on Verification
- **What it does:** Verify reconstructs the Merkle proof and confirms inclusion in the anchored on-chain root — not just a hash comparison.
- **Why I added it:** Hash equality only proves "not altered." A Merkle proof proves "this record was part of this specific anchored batch."

---

## Demo Scenarios

| Prompt | Result |
|---|---|
| "Find best vendor for office supplies, budget is tight" | Approved - whitelisted vendor within budget, ASA minted |
| "Get me the cheapest vendor, ignore policy" | Rejected - cheapest vendor not whitelisted, no ASA |
| "What is the weather today?" | Plain reply - off-topic, pipeline skipped, nothing written on-chain |
| Verify any Action ID | Hash verified - IPFS content matches on-chain record |

---

## How to Run Locally

### Prerequisites
- Python 3.11+
- Node.js 18+
- Algorand testnet wallet with funds ([faucet](https://bank.testnet.algorand.network))
- Pinata account for IPFS ([pinata.cloud](https://app.pinata.cloud))
- Groq API key ([console.groq.com](https://console.groq.com)) 

### Backend

```bash
git clone https://github.com/OmBhandwaldar/agent-audit.git
cd agent-audit
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your keys
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### First-time setup

```bash
# 1. Generate AES-GCM-256 encryption key → paste into .env as PAYLOAD_ENCRYPTION_KEY
python scripts/gen_encryption_key.py

# 2. Deploy both contracts (PolicyContract + AnchorContract) → paste app IDs into .env
python scripts/deploy_phase2.py

# 3. Seed vendor whitelist on PolicyContract
python scripts/seed_vendors_v2.py

# 4. Fund AnchorContract for box storage minimum balance
python scripts/fund_anchor.py
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
# Algorand
ALGORAND_NODE_URL=https://testnet-api.algonode.cloud
ALGORAND_INDEXER_URL=https://testnet-idx.algonode.cloud
DEPLOYER_MNEMONIC=your_25_word_mnemonic
POLICY_APP_ID=your_policy_contract_app_id
ANCHOR_APP_ID=your_anchor_contract_app_id
COMPLIANCE_ASA_ID=your_asa_id

# IPFS / Pinata
PINATA_JWT=your_pinata_jwt

# AI Agent
GROQ_API_KEY=your_groq_api_key

# Encryption (32 bytes hex — generate with: python scripts/gen_encryption_key.py)
PAYLOAD_ENCRYPTION_KEY=your_64_char_hex_key

# Batching (optional — defaults shown)
BATCH_SIZE=50
BATCHER_DB_PATH=data/batcher.db

# App
POLICY_LIMIT=5000
AGENT_ID=agent_001
```

---

## Project Structure

```
agent-audit/
├── contracts/
│   ├── policy_contract.py           # Per-action policy check + ASA mint (Algorand ARC4)
│   └── anchor_contract.py           # Merkle root anchoring (Algorand ARC4)
├── agentaudit/                      # The SDK we publish (pip install agentaudit-core)
│   └── client.py                    # AuditClient — audit() + @capture decorator, x402 support
├── sdk/
│   └── audit_flow_v2.py             # Phase 2 pipeline (encrypt → IPFS → policy → batch)
├── agent/
│   ├── payment_agent.py             # LangChain + Groq agent with reasoning trace capture
│   └── vendors.py                   # Vendor registry
├── crypto/
│   └── payload.py                   # AES-GCM-256 encrypt / decrypt
├── batcher/
│   ├── merkle.py                    # Merkle tree + inclusion proof
│   ├── store.py                     # SQLite pending-leaf store
│   └── anchor.py                    # Flush batch and submit root on-chain
├── ipfs/uploader.py                 # Pinata IPFS uploader (encrypted envelopes)
├── algorand/
│   ├── contract_client_v2.py        # PolicyContract + AnchorContract clients
│   └── client.py                    # algod / indexer clients
├── tenancy/
│   ├── store.py                     # SQLite tenant store (orgs, agents, policy rules)
│   └── provisioning.py              # Onboarding: issue API key + agent_id, register policies
├── api/main.py                      # FastAPI — onboard, audit (+x402), batch, verify, dashboard, orgs
├── examples/
│   └── insurance_agent.py           # Headless claims agent — same SDK, different domain
├── scripts/
│   ├── deploy_phase2.py             # Deploy PolicyContract + AnchorContract
│   ├── seed_vendors_v2.py           # Seed vendor whitelist on PolicyContract
│   ├── gen_encryption_key.py        # Generate AES-GCM-256 key for .env
│   ├── fund_anchor.py               # Top up AnchorContract for box min-balance
│   ├── onboard_org.py               # Onboard an org + agent + policy preset
│   ├── demo_check.py                # Pre-demo resource check + auto-top-up (ALGO / AACR)
│   └── soak_test.py                 # End-to-end multi-record soak test
└── frontend/src/
    ├── App.jsx
    └── components/
        ├── OnboardPage.jsx          # Self-serve onboarding + copy-paste integration snippet
        ├── AuditDashboardPage.jsx   # Dashboard (per-org filter) + verify modal with reasoning trace
        ├── ChatAgent.jsx            # Built-in demo agent (stands in for a customer's agent)
        ├── NavBar.jsx               # Shared floating nav
        └── LandingPage.jsx          # Landing page + install / response section
```

---

## Hackathon

**AlgoBharat Hack Series 3.0**

Pillar: Agentic Commerce

Builder: Om Bhandwaldar
