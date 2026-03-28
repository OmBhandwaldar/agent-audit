# Rule File: Git Rules
# Scope: Apply whenever writing commit messages, branching, or managing the repository.

## Repository Setup
- Repo name: agentaudit
- Visibility: Private during development. Make PUBLIC before April 15 submission.
- Default branch: main
- Always have a README.md at root before submission

## .gitignore (required entries)
```
.env
__pycache__/
*.pyc
*.pyo
.pytest_cache/
node_modules/
dist/
build/
.venv/
venv/
*.egg-info/
.DS_Store
*.log
sessions/
```

Never commit:
- .env (has mnemonics and API keys — treat as critical secret)
- Any file containing DEPLOYER_MNEMONIC
- Any file containing raw API keys

Always commit:
- .env.example (template with placeholder values, no real secrets)

## Branch Strategy (simple, solo-friendly)
```
main          → always working, demo-ready code only
dev           → active development
feature/xxx   → one branch per feature if needed
```

Day-to-day workflow:
- Work on dev branch
- Merge to main only when a full working milestone is confirmed
- Never push broken code to main

Milestone merges to main:
1. After Day 2: contract deployed and ASA setup confirmed
2. After Day 5: terminal checkpoint passes
3. After Day 9: full browser flow works
4. After Day 12: backup demo video recorded
5. Day 15: final submission state

## Commit Message Format
Use this format consistently:
```
<type>: <short description>

Types:
  feat     → new working feature
  fix      → bug fix
  chore    → setup, config, deps
  test     → test scripts
  docs     → README, comments
  refactor → code cleanup, no behavior change
```

Examples:
```
feat: deploy audit contract to testnet
feat: IPFS uploader with retry logic
feat: wire full pipeline in audit_flow.py
fix: box key collision using sha256 truncation
fix: ASA transfer after contract opt-in
chore: add .env.example and .gitignore
docs: update README with setup instructions
test: add Day 5 checkpoint script
```

## Commit Frequency
- Commit after every working unit. Do not batch days of work into one commit.
- Minimum one commit per day during build phase.
- If something breaks after a commit, use git revert — do not force push main.

## README Requirements (must have before submission)
```markdown
# AgentAudit

One-line description of the project.

## What it does
Brief explanation of the audit flow.

## Tech Stack
- LangChain (AI agent)
- Pinata / IPFS (off-chain storage)
- Algorand (immutable audit layer)
- FastAPI (backend)
- React (frontend)

## How to run locally
1. Clone the repo
2. Copy .env.example to .env and fill in values
3. Install dependencies: pip install -r requirements.txt
4. Run backend: uvicorn api.main:app --reload
5. Run frontend: cd frontend && npm install && npm run dev

## Demo
Link to backup demo video (YouTube unlisted or Google Drive)

## Hackathon
AlgoBharat Hack Series 3.0 — Round 2 MVP
```

## What Not To Do
- Do not force push to main under any circumstances.
- Do not commit node_modules or .venv.
- Do not use emoji in commit messages.
- Do not leave merge conflicts in committed files.
- Do not make large uncommitted changes — small frequent commits are safer for solo work.
