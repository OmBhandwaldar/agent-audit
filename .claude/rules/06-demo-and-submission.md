# Rule File: Demo and Submission
# Scope: Apply during final days (Days 12–15) and whenever discussing presentation or demo strategy.

## Demo Flow (memorize this order)
1. Open UI in browser (already loaded, do not refresh live)
2. Enter amount below limit (e.g. ₹3000) → click Run Agent
3. Show loading state briefly
4. Show result: Approved, IPFS CID, Algorand TX ID, ASA minted
5. Click Algorand TX link → show live transaction on testnet explorer
6. Click IPFS CID link → show stored decision JSON on IPFS gateway
7. Enter amount above limit (e.g. ₹7000) → show rejected flow
8. Say: "This payment approval is one example. The same infrastructure works for any agent decision — procurement, workflows, financial operations."

## Backup Video
Record a full demo video by Day 12. Keep it under 3 minutes.
Save it in: sessions/backup-demo.mp4
Upload to Google Drive or YouTube (unlisted) as backup link for submission.
If live demo fails, play this video. Do not try to debug live.

## Two Required Slides
Slide 1 — What we built:
- One AI agent (LangChain payment agent)
- One action type (payment approval)
- IPFS off-chain storage (Pinata)
- Algorand smart contract (audit record + policy check)
- Non-transferable ASA compliance receipt
- React UI with full verified flow

Slide 2 — Full vision:
- Any agent, any decision type
- Multi-policy engine
- Zero-knowledge proofs for private compliance verification
- Decentralized agent identity (DID)
- Regulatory compliance dashboard
- Enterprise integrations (EU AI Act, India DPDP Act)

## Answers to Hard Judge Questions

Q: "How do you ensure the agent isn't lying about what it did?"
A: "Right now AgentAudit ensures tamper-proof logging of agent-reported behavior —
once recorded, it cannot be altered by anyone including the organization that deployed
the agent. Verifying ground truth is a broader challenge known as the oracle problem.
We see this as a first step toward standardized auditability, with future extensions
like trusted execution environments providing stronger guarantees."

Q: "Why Algorand specifically?"
A: "Algorand gives us fast finality, very low transaction costs, and strong smart contract
support. For an audit system that may log thousands of agent decisions per day in production,
cost per transaction matters. Algorand testnet also has excellent developer tooling via Algokit."

Q: "Why not just use a centralized database?"
A: "A centralized log held by the same organization running the agent can be modified
by that organization. An auditor or regulator cannot independently verify it. Blockchain
anchoring means the record exists outside the deployer's control — that's the core value."

Q: "Is this production ready?"
A: "This is an MVP demonstrating the core audit pipeline. For production we would add
trusted execution for stronger oracle guarantees, enterprise key management, and ZK proofs
for compliance verification without exposing sensitive business data."

## Submission Checklist
- [ ] Full flow works in browser end to end
- [ ] Algorand testnet TX IDs are real and verifiable on explorer
- [ ] IPFS CIDs are real and accessible on IPFS gateway
- [ ] ASA minting confirmed in at least one transaction
- [ ] Backup demo video recorded and uploaded
- [ ] Two slides prepared
- [ ] Judge answers rehearsed
- [ ] GitHub repo is public with README explaining the project and how to run it
- [ ] .env.example committed (not .env)
