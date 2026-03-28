# CLAUDE.md — AgentAudit Project

## Project Overview

AgentAudit is a verifiable audit and compliance infrastructure for autonomous AI agents.
It creates a tamper-proof, independently verifiable audit layer for AI agent actions using
IPFS for off-chain storage and Algorand blockchain as the immutable verification layer.

**Hackathon:** AlgoBharat Hack Series 3.0
**Current Round:** Round 2 MVP
**Deadline:** April 15, 2026
**Builder:** Solo

---

## Big Vision

Any autonomous AI agent performing any real-world decision (financial, operational, strategic)
can have every action captured, stored, and verified in a way that is:
- Tamper-proof (blockchain anchored)
- Independently verifiable (not self-reported by the deploying org)
- Compliance-ready (policy checks on-chain, receipts as ASAs)

One-line vision: "AgentAudit becomes the trust layer for autonomous AI systems operating in the real world."

---

## MVP Scope (April 15 Deadline)

**One use case only:** AI agent approves or rejects a payment based on amount.

**Full end-to-end flow:**
1. User enters amount in UI → clicks "Run Agent"
2. LangChain agent decides: approve if amount < 5000, else reject
3. SDK captures: action, amount, decision, policy ID
4. Decision JSON uploaded to IPFS via Pinata → returns CID
5. Hash of IPFS data + metadata sent to Algorand smart contract
6. Smart contract: stores record, checks policy, mints ASA if approved
7. UI displays: decision result, IPFS CID, Algorand TX ID, ASA receipt status

**Do NOT build for MVP:**
- Multiple agent types
- Complex or dynamic policies
- ZK proofs
- DID system
- Multi-framework support
- Multiple action types

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| AI Agent | LangChain (Python) | One tool: check_payment_policy |
| Off-chain Storage | IPFS via Pinata REST API | Stores full decision JSON |
| Blockchain | Algorand Testnet | Immutable audit + policy layer |
| Smart Contracts | ARC4 via Algokit (Python) | Do NOT use raw PyTeal |
| Compliance Receipt | Algorand Standard Asset (ASA) | Pre-created, non-transferable |
| Backend API | FastAPI (Python) | Single endpoint: POST /api/audit |
| Frontend | React (JavaScript) | Plain React, no TypeScript |
| HTTP Client | httpx (async) | Never use requests in async context |
| Package Manager | pip + requirements.txt | Use python-dotenv for env vars |
| Contract Tooling | Algokit CLI | For deploy, test, interact |

---

## Project Structure

```
agentaudit/
├── CLAUDE.md                  # This file — always read at start of every session
├── .env                       # API keys and config (never commit)
├── .env.example               # Template with placeholder values (always commit)
├── .gitignore                 # See 08-git-rules.md for required entries
├── requirements.txt           # All Python dependencies
├── README.md                  # Required before submission
├── contracts/
│   └── audit_contract.py      # Algorand smart contract (ARC4 via Algokit)
├── sdk/
│   └── audit_flow.py          # Core pipeline: run_audit_flow()
├── agent/
│   └── payment_agent.py       # LangChain agent + decide_payment() fallback
├── ipfs/
│   └── uploader.py            # upload_to_ipfs() with retry logic
├── algorand/
│   ├── client.py              # get_algod_client(), get_indexer_client()
│   └── contract_client.py     # submit_audit(), get_audit_record()
├── api/
│   └── main.py                # FastAPI app — POST /api/audit only
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # All state lives here
│   │   └── components/
│   │       └── AuditResult.jsx  # Receives result as props, renders result state
│   ├── index.html
│   └── package.json
├── scripts/
│   └── runFlow.py             # Day 5 checkpoint — must pass before frontend
├── tests/
│   └── test_flow.py           # Basic pipeline tests
└── .claude/
    ├── rules/                 # All Claude rules files (01 through 09)
    ├── sessions/              # Session logs
    ├── contexts/              # Reusable context snippets
    └── skills/                # Reusable skill prompts
```

---

## Environment Variables (.env)

```
# Algorand
ALGORAND_NODE_URL=https://testnet-api.algonode.cloud
ALGORAND_INDEXER_URL=https://testnet-idx.algonode.cloud
DEPLOYER_MNEMONIC=your_25_word_mnemonic_here
CONTRACT_APP_ID=your_deployed_app_id        # Fill after Day 2 deployment
COMPLIANCE_ASA_ID=your_pre_created_asa_id  # Fill after Day 1 ASA creation

# IPFS / Pinata
PINATA_API_KEY=your_pinata_api_key
PINATA_SECRET_KEY=your_pinata_secret_key

# LangChain / OpenAI
OPENAI_API_KEY=your_openai_api_key

# App
POLICY_LIMIT=5000
AGENT_ID=agent_001
```

## Requirements (requirements.txt)

```
# Algorand
algokit
py-algorand-sdk

# AI Agent
langchain
langchain-openai
openai

# HTTP
httpx

# API
fastapi
uvicorn[standard]
pydantic

# Utilities
python-dotenv

# Testing
pytest
pytest-asyncio
```

Install all: `pip install -r requirements.txt`

---

## Smart Contract Specification

**File:** `contracts/audit_contract.py`

**State (Box Storage):**
```
Box key: sha256(action_id)[:32]  # Always fixed length, avoids key size limits
Box value (audit record):
  - ipfs_hash: bytes       # SHA256 of IPFS CID
  - agent_id: bytes        # agent identifier
  - timestamp: uint64      # Unix timestamp
  - policy_id: bytes       # e.g. "limit_5000"
  - decision: bytes        # "approved" or "rejected"
  - policy_result: bytes   # "pass" or "fail"
  - amount: uint64         # payment amount
  - asa_id: uint64         # compliance receipt ASA ID (0 if rejected)
```

**Methods:**
```python
# Store audit record + run policy check + transfer ASA if approved
@app.external
def submit_audit(
    action_id: abi.String,
    ipfs_hash: abi.String,
    agent_id: abi.String,
    policy_id: abi.String,
    decision: abi.String,
    amount: abi.Uint64,
    timestamp: abi.Uint64,
) -> abi.String:
    # Policy check: amount < POLICY_LIMIT
    # Store record in box storage using sha256(action_id) as key
    # If pass: transfer 1 unit of ASA from contract's own holding to caller
    # Contract must be opted in and hold ASA supply — set this up on Day 1
    # Return: "pass" or "fail"

# Read audit record by action ID
@app.external(read_only=True)
def get_audit_record(action_id: abi.String) -> abi.String:
    # Hash action_id to get box key, return stored record as JSON string
```

**ASA Setup (do this on Day 1 — before writing any other code):**
- Create ASA with creator = deployer wallet
- Name: "AgentAudit Compliance Receipt"
- Unit: "AACR"
- Total supply: 1,000,000
- Decimals: 0
- Clawback = contract address
- Freeze = contract address
- Default frozen: True
- After contract is deployed: opt contract into ASA, send supply to contract address
- Test a manual ASA transfer from contract to your wallet before Day 2

---

## Core SDK Function

**File:** `sdk/audit_flow.py`

```python
import time, random
from hashlib import sha256

async def run_audit_flow(amount: int) -> dict:
    """
    Main pipeline. Call this from anywhere.
    Returns: {
        decision, ipfs_cid, algorand_tx_id,
        policy_result, asa_minted, action_id
    }
    """
    # 1. Run LangChain agent
    decision, reason = await run_payment_agent(amount)

    # 2. Build decision record
    record = {
        "action": "approve_payment",
        "amount": amount,
        "decision": decision,
        "reason": reason,
        "policy": "limit_5000",
        "agent_id": AGENT_ID,
        "timestamp": int(time.time())
    }

    # 3. Upload to IPFS
    cid = await upload_to_ipfs(record)

    # 4. Hash the CID
    ipfs_hash = sha256(cid.encode()).hexdigest()

    # 5. Submit to Algorand smart contract
    # Use timestamp + random suffix to avoid collision if called twice in same second
    action_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    tx_result = await submit_to_algorand(
        action_id, ipfs_hash, record
    )

    return {
        "decision": decision,
        "ipfs_cid": cid,
        "algorand_tx_id": tx_result.tx_id,
        "policy_result": tx_result.policy_result,
        "asa_minted": tx_result.asa_minted,
        "action_id": action_id
    }
```

---

## LangChain Agent

**File:** `agent/payment_agent.py`

Keep this simple. The agent's job is just to decide approve/reject.

```python
from langchain.agents import initialize_agent
from langchain.tools import tool

@tool
def check_payment_policy(amount: int) -> str:
    """Check if payment amount is within policy limits."""
    limit = int(os.getenv("POLICY_LIMIT", 5000))
    if amount < limit:
        return f"approved: amount {amount} is within limit {limit}"
    return f"rejected: amount {amount} exceeds limit {limit}"

# Agent prompt:
# "You are a payment approval agent.
#  Use the check_payment_policy tool to decide whether to approve
#  or reject the payment. Always use the tool."
```

**IMPORTANT — LangChain fallback (keep this in the file, always):**

If LangChain is causing issues close to deadline, swap in this function instantly.
Judges cannot tell the difference in a demo. Do not feel bad about using it.

```python
def decide_payment(amount: int) -> tuple[str, str]:
    """Fallback: simple rule-based decision. Drop-in replacement for LangChain agent."""
    limit = int(os.getenv("POLICY_LIMIT", 5000))
    if amount < limit:
        return "approved", f"Amount {amount} is within policy limit {limit}"
    return "rejected", f"Amount {amount} exceeds policy limit {limit}"
```

---

## IPFS Uploader

**File:** `ipfs/uploader.py`

```python
import httpx

async def upload_to_ipfs(data: dict) -> str:
    """Upload JSON to Pinata. Returns CID. Retries once on failure."""
    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {
        "pinata_api_key": os.getenv("PINATA_API_KEY"),
        "pinata_secret_api_key": os.getenv("PINATA_SECRET_KEY"),
    }
    for attempt in range(2):
        try:
            response = await httpx.AsyncClient().post(
                url, json={"pinataContent": data}, headers=headers, timeout=10.0
            )
            response.raise_for_status()
            return response.json()["IpfsHash"]
        except Exception as e:
            if attempt == 1:
                raise RuntimeError(f"IPFS upload failed after retry: {e}")
            await asyncio.sleep(2)
```

---

## Backend API (FastAPI)

**File:** `api/main.py`

Use FastAPI. It's minimal and async-native — perfect fit for this stack.

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sdk.audit_flow import run_audit_flow

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

class AuditRequest(BaseModel):
    amount: int

@app.post("/api/audit")
async def audit(req: AuditRequest):
    try:
        result = await run_audit_flow(req.amount)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Run with: `uvicorn api.main:app --reload`

---

## Day 5 Checkpoint Script

**File:** `scripts/runFlow.py`

```python
# Run this in terminal to verify full pipeline works
# Usage: python scripts/runFlow.py 3000
import asyncio, sys
from sdk.audit_flow import run_audit_flow

async def main():
    amount = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    print(f"\nRunning audit flow for amount: ₹{amount}\n")
    result = await run_audit_flow(amount)
    print("✅ Decision:      ", result["decision"])
    print("📦 IPFS CID:      ", result["ipfs_cid"])
    print("⛓  Algorand TX:   ", result["algorand_tx_id"])
    print("📋 Policy Result: ", result["policy_result"])
    print("🧾 ASA Minted:    ", result["asa_minted"])

asyncio.run(main())
```

**If this works → proceed to frontend. If not → fix before anything else.**

---

## Frontend Spec

**Keep it minimal. Function over form.**

Single page, three states:
1. **Input state:** Amount field + "Run Agent" button
2. **Loading state:** "Agent is processing..." spinner
3. **Result state:** Display all returned values

```jsx
// Result display fields:
// ✅ Decision: Approved / ❌ Rejected
// 📦 IPFS CID: <cid> (clickable link to ipfs.io gateway)
// ⛓  Algorand TX: <tx_id> (clickable link to testnet explorer)
// 🧾 Compliance Receipt: Minted / Not applicable
// 🕐 Timestamp: <human readable>
```

Backend API endpoint needed:
```
POST /api/audit
Body: { "amount": 3000 }
Response: { decision, ipfs_cid, algorand_tx_id, policy_result, asa_minted }
```

---

## Build Sequence (Non-Negotiable Order)

```
Day 1  → Algokit setup + testnet wallet + faucet funds + deploy hello world contract
         + Create ASA + opt contract in + send ASA supply to contract + test manual transfer
Day 2  → Full smart contract written + deployed on testnet (store + policy check + ASA transfer)
Day 3  → IPFS uploader working (test with dummy JSON, confirm CID returned)
Day 4  → LangChain agent working (test approve/reject in isolation)
Day 5  → Connect all via runFlow.py → CHECKPOINT ✅
Day 6  → Error handling, edge cases, clean up pipeline
Day 7  → Buffer / catch-up day
Day 8  → React frontend started (input + button + API call)
Day 9  → Frontend connected to backend, full flow in browser
Day 10 → Test full flow 10+ times, fix bugs
Day 11 → Polish UI minimally
Day 12 → Record backup demo video
Day 13 → Final testing, prepare slides
Day 14 → Rest, do not add features
Day 15 → Submit
```

---

## Two Presentation Slides

**Slide 1 — What we built:**
- One AI agent (LangChain payment agent)
- One action type (payment approval)
- IPFS off-chain storage (Pinata)
- Algorand smart contract (audit record + policy check)
- Non-transferable ASA compliance receipt
- React UI showing full verified flow

**Slide 2 — Full vision:**
- Any agent, any decision type
- Multi-policy engine
- Zero-knowledge proofs for private compliance
- Decentralized agent identity (DID)
- Regulatory dashboard
- Enterprise integrations (EU AI Act, DPDP compliance)

---

## Answer to the Hard Judge Questions

**Q: "How do you ensure the agent isn't lying about what it did?"**

> "Right now AgentAudit ensures tamper-proof logging of agent-reported behavior —
> meaning once a decision is recorded, it cannot be altered by anyone including
> the organization that deployed the agent. Verifying ground truth is a broader
> challenge known as the oracle problem. We see this as a first step toward
> standardized auditability, with future extensions like trusted execution
> environments or external verification layers providing stronger guarantees."

**Q: "Why Algorand specifically?"**

> "Algorand gives us fast finality, very low transaction costs, and strong smart
> contract support. For an audit system logging thousands of agent decisions per day
> in production, cost per transaction matters. Algorand testnet also has excellent
> developer tooling via Algokit."

**Q: "Why not just use a centralized database?"**

> "A centralized log held by the same organization running the agent can be modified
> by that organization. An auditor or regulator cannot independently verify it.
> Blockchain anchoring means the record exists outside the deployer's control —
> that's the core value."

**Q: "Is this production ready?"**

> "This is an MVP demonstrating the core audit pipeline end to end. For production
> we would add trusted execution for stronger oracle guarantees, enterprise key
> management, and ZK proofs for compliance verification without exposing sensitive
> business data."

---

## Key Links

**Algorand:**
- Testnet Explorer: https://testnet.explorer.perawallet.app
- Algokit Docs: https://developer.algorand.org/algokit
- AlgoNode (free testnet node): https://algonode.io
- Testnet Faucet: https://bank.testnet.algorand.network
- ARC4 Contract Guide: https://algorandfoundation.github.io/puya/

**IPFS:**
- Pinata API Docs: https://docs.pinata.cloud
- Pinata Dashboard: https://app.pinata.cloud
- IPFS Gateway: https://gateway.pinata.cloud/ipfs/{cid}

**LangChain:**
- LangChain Python Docs: https://python.langchain.com
- LangChain Tools Guide: https://python.langchain.com/docs/modules/agents/tools/

**FastAPI:**
- FastAPI Docs: https://fastapi.tiangolo.com

---

## Rules Files Index (.claude/rules/)

Load these at the start of each Claude session based on what you're working on.
Always load 01-project-core.md in every session.

| File | Load When |
|---|---|
| 01-project-core.md | Every session — always |
| 02-build-sequence.md | Planning, checking progress, next steps |
| 03-algorand.md | Writing contracts, ASA setup, transactions |
| 04-python-backend.md | Writing SDK, agent, IPFS, FastAPI code |
| 05-frontend.md | Phase 2 only — React UI work |
| 06-demo-and-submission.md | Days 12–15, submission prep |
| 07-debugging.md | Something is broken |
| 08-git-rules.md | Committing, branching, README |
| 09-coding-standards.md | Any code review or new file creation |

---

## Rules for Claude When Helping on This Project

### Scope Rules
1. **MVP scope is locked.** Do not suggest adding features beyond what is defined above. If asked about ZK proofs, DID, or multi-agent — acknowledge they are in the full vision and move on.
2. **Stack is locked.** Python + FastAPI + LangChain + Pinata + Algorand + React. Do not suggest alternatives to any layer.
3. **One framework.** LangChain only. Do not introduce AutoGPT, CrewAI, or any other agent framework.

### Build Phase Rules
4. **Backend first.** Do not write or suggest any frontend code until the user explicitly confirms the Day 5 checkpoint passes.
5. **Phase gate enforcement.** If user asks for frontend help before Day 5 checkpoint, respond: "Confirm the terminal flow works first. Run: python scripts/runFlow.py 3000"
6. **No feature additions after Day 11.** If user asks to add anything new after Day 11, respond: "Too close to deadline. Focus on making the existing flow flawless."

### Code Rules
7. **Prefer simple over clever.** A working simple solution beats an elegant broken one.
8. **Clean readable code.** Solo builder debugging at 11pm is the test. No one-liners, no clever tricks.
9. **Always include error handling.** Never write code that can silently fail.
10. **Always include the LangChain fallback.** Every version of payment_agent.py must contain decide_payment() fallback function.

### Algorand Rules
11. **Algorand is non-negotiable.** All audit records go on-chain. Do not suggest routing around it.
12. **ASA minting stays in.** Do not suggest removing or simplifying ASA logic.
13. **Testnet only.** Never suggest mainnet until after Round 3 finals.
14. **Box key is always hashed.** Never use raw action_id string as box key.

### Communication Rules
15. **Flag blockers immediately.** If something will take more than one day to build, say so before writing any code.
16. **Flag demo risks immediately.** If a suggested approach could break during a live demo, say so and propose a safer alternative.
17. **Be direct.** No excessive encouragement. Identify problems clearly and propose solutions.

