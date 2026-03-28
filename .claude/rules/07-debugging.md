# Rule File: Debugging
# Scope: Apply whenever something is broken, an error is thrown, or the user is stuck.

## Debugging Priority Order
When something breaks, fix in this order:
1. Environment (missing .env vars, wrong keys, unfunded wallet)
2. Network (testnet connectivity, Pinata API availability)
3. Contract (deployment issues, opt-in missing, box storage errors)
4. SDK wiring (wrong arguments, async issues, missing awaits)
5. Agent (LangChain parsing failures — switch to fallback if persistent)
6. Frontend (only in Phase 2)

Always check the simplest thing first.

## Common Algorand Issues and Fixes

Problem: "overspend" error on transaction
Fix: Wallet is out of testnet ALGO. Refund from https://bank.testnet.algorand.network

Problem: "asset not opted in" error
Fix: Contract account is not opted into the ASA. Run opt-in transaction first.

Problem: "box not found" error on get_audit_record
Fix: Box key mismatch. Confirm you're using sha256(action_id)[:32] consistently in both write and read paths.

Problem: Transaction confirmed but ASA not transferred
Fix: Check contract ASA balance. If zero, the supply was never sent to the contract address.

Problem: "invalid program" on contract deploy
Fix: ARC4 syntax issue. Check Algokit docs for correct decorator usage.

## Common IPFS Issues and Fixes

Problem: Pinata returns 401
Fix: API key or secret key is wrong in .env. Double check against Pinata dashboard.

Problem: Pinata returns CID but IPFS gateway times out
Fix: Normal — propagation takes time. Use https://gateway.pinata.cloud/ipfs/{cid} instead of ipfs.io for faster access.

Problem: upload_to_ipfs hangs
Fix: httpx timeout is missing. Ensure timeout=10.0 is set on the client call.

## Common LangChain Issues and Fixes

Problem: Agent not calling the tool
Fix: Tool description is unclear. Make it more explicit. Or switch to fallback function.

Problem: Agent returns unexpected format
Fix: Add output parser or just use fallback function. Do not spend more than 30 minutes on LangChain parsing issues.

Problem: OpenAI API rate limit
Fix: Add time.sleep(1) between calls during testing. Not an issue for single demo calls.

## Fallback Decision (important)
If LangChain is causing issues within 72 hours of deadline:
- Switch to decide_payment() fallback in agent/payment_agent.py immediately
- Do not spend more time debugging LangChain
- The fallback is functionally identical for demo purposes
- Update the session log noting the switch

## When To Ask For Help
If stuck on the same problem for more than 2 hours:
1. Write down exactly what you tried
2. Copy the full error message
3. Start a new Claude conversation with CLAUDE.md + the error
Do not keep trying random things. Structured debugging is faster.
