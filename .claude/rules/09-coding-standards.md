# Rule File: Coding Standards
# Scope: Apply to all code written in this project — Python and JavaScript/React.
# Priority: Readability over cleverness. Solo builder debugging at 11pm is the test.

---

## Universal Rules (Python + JS)

- No magic numbers. Use named constants or environment variables.
  BAD:  if amount < 5000
  GOOD: if amount < int(os.getenv("POLICY_LIMIT", 5000))

- No commented-out code in commits. Delete it.

- No print() or console.log() left in production paths.
  Use structured logging in Python (import logging).
  Remove all console.log in React before final submission.

- Every function must have a docstring (Python) or JSDoc comment (JS) explaining
  what it does, its parameters, and what it returns.

- No function longer than 40 lines. If it is, split it.

- No file longer than 200 lines. If it is, split it.

---

## Python Standards

### Formatting
- Use Black for formatting. Run before every commit: `black .`
- Line length: 88 characters (Black default)
- Use isort for import ordering: `isort .`

### Import Order (enforced by isort)
```python
# 1. Standard library
import os
import time
import random
from hashlib import sha256

# 2. Third-party
import httpx
from langchain.agents import initialize_agent

# 3. Local
from sdk.audit_flow import run_audit_flow
```

### Type Hints
- Required on all function signatures. No exceptions.
```python
# GOOD
async def upload_to_ipfs(data: dict) -> str:

# BAD
async def upload_to_ipfs(data):
```

### Async Rules
- All I/O functions must be async. No synchronous blocking calls.
- Always await coroutines. Never fire-and-forget without explicit intent.
- Use httpx.AsyncClient() for HTTP. Never use requests in async context.

### Error Handling
```python
# GOOD — specific, informative
try:
    cid = await upload_to_ipfs(record)
except RuntimeError as e:
    raise RuntimeError(f"IPFS upload failed for action {action_id}: {e}")

# BAD — swallows error silently
try:
    cid = await upload_to_ipfs(record)
except:
    pass
```

### Logging
```python
import logging
logger = logging.getLogger(__name__)

# Use levels correctly:
logger.debug("Uploading to IPFS: %s", record)      # internal state
logger.info("IPFS upload successful: %s", cid)      # milestone reached
logger.warning("IPFS retry attempt 2")              # recoverable issue
logger.error("Algorand TX failed: %s", str(e))      # failure
```

### Constants
- Define at top of file in UPPER_SNAKE_CASE
- Prefer loading from env over hardcoding
```python
POLICY_LIMIT = int(os.getenv("POLICY_LIMIT", 5000))
AGENT_ID = os.getenv("AGENT_ID", "agent_001")
```

### Naming
```python
# Functions: verb_noun snake_case
async def upload_to_ipfs(data: dict) -> str
async def submit_audit_record(action_id: str, ...) -> dict
def decide_payment(amount: int) -> tuple[str, str]

# Variables: descriptive snake_case
ipfs_cid = ...
algorand_tx_id = ...
policy_result = ...

# Classes: PascalCase (rare in this project)
class AuditRecord:
```

---

## JavaScript / React Standards

### Formatting
- Use Prettier. Config: single quotes, 2-space indent, no semicolons optional but be consistent.
- Run before commit: `npx prettier --write src/`

### Component Rules
- Functional components only. No class components.
- One component per file.
- Component files: PascalCase (AuditResult.jsx)
- Utility files: camelCase (apiClient.js)

### State Management
- useState only. No Redux, no Zustand, no Context API for this project.
- Keep all state in App.jsx. Pass as props to AuditResult.jsx.

```jsx
// GOOD — clear state shape
const [status, setStatus] = useState("input") // "input" | "loading" | "result"
const [result, setResult] = useState(null)
const [error, setError] = useState(null)

// BAD — vague names
const [data, setData] = useState(null)
const [flag, setFlag] = useState(false)
```

### API Calls
```jsx
// GOOD — clear async handler with error state
const handleRunAgent = async () => {
  setStatus("loading")
  setError(null)
  try {
    const response = await fetch("http://localhost:8000/api/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: parseInt(amountInput) }),
    })
    if (!response.ok) throw new Error("API call failed")
    const data = await response.json()
    setResult(data)
    setStatus("result")
  } catch (err) {
    setError(err.message)
    setStatus("input")
  }
}
```

### Naming
```jsx
// Components: PascalCase
function AuditResult({ result }) {}

// Event handlers: handle + action
const handleRunAgent = async () => {}
const handleReset = () => {}

// State variables: descriptive
const [amountInput, setAmountInput] = useState("")
const [status, setStatus] = useState("input")
```

### No-Nos in React
- No inline styles beyond simple one-off overrides. Use CSS classes.
- No anonymous functions as props if they cause rerenders in critical paths.
- No hardcoded API URLs — use a constant at top of file:
  ```jsx
  const API_BASE = "http://localhost:8000"
  ```

---

## Pre-Commit Checklist
Before every commit, verify:
- [ ] Black formatting applied (Python)
- [ ] No .env file staged
- [ ] No print() or console.log() in production paths
- [ ] All functions have docstrings / JSDoc
- [ ] No hardcoded secrets or API keys
- [ ] Code runs without errors on your machine
- [ ] Commit message follows the format in 08-git-rules.md
