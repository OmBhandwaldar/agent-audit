# Rule File: Python Backend
# Scope: Apply whenever writing Python code for SDK, agent, IPFS, or API.

## Language and Style
- Python 3.11+
- Async throughout (asyncio, httpx, not requests)
- Type hints on all function signatures
- Descriptive variable names. No abbreviations except standard ones (tx, cid, abi).
- One function = one responsibility. Keep functions short and readable.
- Solo builder debugging at 11pm. Optimize for readability, not cleverness.

## Project Structure (enforce this)
```
agentaudit/
├── sdk/audit_flow.py          # Main pipeline — run_audit_flow()
├── agent/payment_agent.py     # LangChain agent + fallback function
├── ipfs/uploader.py           # upload_to_ipfs() only
├── algorand/
│   ├── client.py              # get_algod_client(), get_indexer_client()
│   └── contract_client.py     # submit_audit(), get_audit_record()
├── api/main.py                # FastAPI app — POST /api/audit only
└── scripts/runFlow.py         # Day 5 checkpoint script
```

Do not create files outside this structure without flagging it.

## Core SDK Rules (audit_flow.py)
- Single entry point: run_audit_flow(amount: int) -> dict
- Return dict always contains: decision, ipfs_cid, algorand_tx_id, policy_result, asa_minted, action_id
- Import random and use it for action_id generation
- Do not catch all exceptions silently. Let errors surface with clear messages.

## IPFS Rules (uploader.py)
- Use Pinata REST API only (https://api.pinata.cloud/pinning/pinJSONToIPFS)
- Always retry once on failure with 2 second delay before raising
- Set timeout=10.0 on all httpx calls
- Return only the IpfsHash string. Nothing else.
- Keep decision JSON minimal:
  ```json
  {
    "action": "approve_payment",
    "amount": 3000,
    "decision": "approved",
    "reason": "...",
    "policy": "limit_5000",
    "agent_id": "agent_001",
    "timestamp": 1234567890
  }
  ```

## LangChain Agent Rules (payment_agent.py)
- Use LangChain with one tool: check_payment_policy
- Keep the fallback function decide_payment() in the same file always
- Fallback signature: decide_payment(amount: int) -> tuple[str, str]
- If LangChain is causing issues within 3 days of deadline, switch to fallback without hesitation
- Never add more tools to the agent

## FastAPI Rules (api/main.py)
- One endpoint only: POST /api/audit
- Request body: { "amount": int }
- Response: the full dict from run_audit_flow()
- Add CORS middleware (allow_origins=["*"] for hackathon)
- Run with: uvicorn api.main:app --reload --port 8000

## Environment Variables
- Always load from .env using python-dotenv
- Never hardcode keys, mnemonics, or API credentials
- Required vars: ALGORAND_NODE_URL, ALGORAND_INDEXER_URL, DEPLOYER_MNEMONIC,
  CONTRACT_APP_ID, COMPLIANCE_ASA_ID, PINATA_API_KEY, PINATA_SECRET_KEY,
  OPENAI_API_KEY, POLICY_LIMIT, AGENT_ID

## Error Handling
- Wrap IPFS calls: retry once, then raise with clear message
- Wrap Algorand calls: catch and raise with TX context in message
- Never return partial results. If pipeline fails, raise — don't return empty fields.
- FastAPI endpoint catches all exceptions and returns HTTP 500 with detail string.

## Requirements
Core packages (requirements.txt):
```
algokit
algosdk
langchain
langchain-openai
openai
httpx
pinata (or use httpx directly)
fastapi
uvicorn
python-dotenv
pytest
pytest-asyncio
```
