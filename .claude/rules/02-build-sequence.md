# Rule File: Build Sequence
# Scope: Apply whenever writing or reviewing code, suggesting next steps, or planning work.

## Phase Gate (Strict)
The project has two phases. Do not mix them.

### Phase 1: Backend Pipeline (Days 1–7)
Work only on:
- Algorand smart contract
- ASA setup
- IPFS uploader
- LangChain agent
- Core SDK (audit_flow.py)
- Terminal checkpoint script (runFlow.py)

Do NOT write any frontend code during Phase 1.
Do NOT suggest UI improvements during Phase 1.
If the user asks for frontend help before confirming Day 5 checkpoint passes, redirect:
"Confirm the terminal flow works first. Run: python scripts/runFlow.py 3000"

### Phase 2: Frontend + Polish (Days 8–14)
Only begin after user confirms Day 5 checkpoint output:
- Decision shown in terminal
- IPFS CID returned
- Algorand TX ID confirmed
- ASA minted

Frontend is React. Keep it minimal. Three states only: input, loading, result.

## Day 5 Checkpoint (Critical Gate)
Expected terminal output from `python scripts/runFlow.py 3000`:
```
✅ Decision:       approved
📦 IPFS CID:       Qm...
⛓  Algorand TX:    <tx_id>
📋 Policy Result:  pass
🧾 ASA Minted:     True
```
If any line is missing or erroring, stop and fix before moving forward.

## Build Order Within Phase 1
1. Algokit install + testnet wallet + faucet
2. ASA creation + contract opt-in + supply transfer + manual transfer test
3. Smart contract (store + policy check + ASA transfer)
4. IPFS uploader (with retry)
5. LangChain agent (with fallback function ready)
6. Wire everything in audit_flow.py
7. Run checkpoint script

Do not skip steps. Do not reorder.

## Final Days Rule
Days 12–14: No new features. Testing, demo video, slides only.
If user asks to add a feature after Day 11, respond:
"This is too close to the deadline. Focus on making the existing flow flawless."
