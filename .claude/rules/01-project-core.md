# Rule File: Project Core
# Scope: Always active. Apply to every single conversation in this project.

## What This Project Is
AgentAudit is a verifiable audit and compliance infrastructure for autonomous AI agents.
Solo project. Hackathon: AlgoBharat Hack Series 3.0.
Round 2 MVP deadline: April 15, 2026.

## Non-Negotiable Facts
- Builder is solo. There is no team.
- Stack is fixed: Python backend, LangChain, Pinata IPFS, Algorand testnet, React frontend.
- Do not suggest alternative blockchains, storage layers, or agent frameworks.
- Do not suggest adding team members or splitting work.
- Algorand is the immutable audit layer. This is the core value proposition. Never route around it.

## Scope Lock
MVP is ONE use case: payment approval agent.

In scope (built or actively building):
- Two on-chain policy checks: amount limit + vendor whitelist
- Auditor/Verifier flow: independent hash verification of any audit record

Do not suggest expanding scope to:
- Multiple agent types
- Multiple action types
- Multiple frameworks
- Time-of-day or other additional policy checks (dropped — demo risk)
- ZK proofs (mention only, do not build)
- DID system (mention only, do not build)
- Multi-agent coordination

If asked about these, acknowledge they are in the full vision and move on.

## Tone
- Be direct. No excessive encouragement.
- Flag risks immediately when you see them.
- If something will take more than one day to build, say so upfront.
- If a suggestion adds complexity without demo value, say so and propose simpler alternative.
