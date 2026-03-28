# Rule File: Algorand
# Scope: Apply whenever writing smart contract code, ASA logic, or Algorand transactions.

## Network
- Always use Algorand TESTNET. Never mainnet.
- Node: https://testnet-api.algonode.cloud (free, no signup)
- Indexer: https://testnet-idx.algonode.cloud
- Faucet: https://bank.testnet.algorand.network
- Explorer: https://testnet.explorer.perawallet.app

## Tooling
- Use Algokit for contract development and deployment.
- Use algosdk (Python) for transaction construction.
- Do not use deprecated PyTeal patterns. Use ARC4 / Beaker style via Algokit.

## Smart Contract Rules
- Contract file: contracts/audit_contract.py
- Use box storage for audit records.
- Box key MUST be fixed length. Use sha256(action_id)[:32] — never raw string action_id.
- Keep contract logic minimal. Policy check is: amount < POLICY_LIMIT. Nothing more.
- Contract has two external methods only:
  - submit_audit() — write path
  - get_audit_record() — read only

## ASA Rules
- ASA must be created on Day 1 before any other contract work.
- Setup order (do not deviate):
  1. Create ASA (deployer wallet as creator)
  2. Deploy smart contract
  3. Opt contract account into ASA
  4. Transfer full supply to contract address
  5. Test manual ASA transfer from contract to deployer wallet
  6. Only proceed to writing submit_audit() after step 5 passes
- ASA is non-transferable by end users: clawback = contract address, freeze = contract address, default frozen = True
- Contract transfers ASA internally on policy pass. Do not move ASA logic to backend.

## Transaction Rules
- Always check transaction confirmation before returning TX ID to caller.
- Use algosdk wait_for_confirmation() — do not assume instant finality.
- Wrap all Algorand calls in try/except. Surface errors clearly.

## Action ID Rules
- action_id format: f"{int(time.time())}_{random.randint(1000, 9999)}"
- Never use action_id directly as box key. Always hash it first.
- action_id is stored in the box value for lookup purposes, not as the key.

## What Not To Do
- Do not suggest mainnet deployment at any point before Round 3.
- Do not suggest stateful global storage for audit records (boxes are correct here).
- Do not suggest TEAL directly — use Algokit abstractions.
- Do not add more contract methods than specified above.
