# Rule File: Frontend
# Scope: Apply only during Phase 2 (Days 8–14) when building the React UI.
# Do not apply during Phase 1. Do not suggest frontend work until Day 5 checkpoint passes.

## Stack
- React (Vite setup preferred — faster than CRA)
- No UI component library required. Plain CSS or Tailwind only.
- No Redux, no Zustand. useState is enough.
- Axios or fetch for API calls. No extra HTTP libraries.

## Two Tabs
Tab 1: "Run Agent" — submit a payment for audit
Tab 2: "Verify Audit" — independently verify any past audit record by action ID

Tab state lives in App.jsx as activeTab ("run" | "verify"). Simple button toggle, no routing library.

## Tab 1 — Run Agent (three states)
```
State 1: Input
  - Number input field (amount in ₹)
  - Vendor ID text input (placeholder: "e.g. VENDOR_001")
  - "Run Agent" button
  - Nothing else

State 2: Loading
  - Spinner or simple text: "Agent is processing..."
  - Disable button during loading

State 3: Result (AuditResult.jsx)
  - Decision badge (green ✅ Approved / red ❌ Rejected)
  - Amount Check: ✅ Pass / ❌ Fail
  - Vendor Check: ✅ Pass / ❌ Fail
  - Compliance Receipt: Minted (1 AACR) / Not applicable
  - IPFS CID (clickable → Pinata gateway)
  - Algorand TX ID (clickable → testnet explorer)
  - Action ID (monospace, copyable)
  - "Run Again" button to reset to State 1
```

## Tab 2 — Verify Audit (VerifyAudit.jsx)
```
  - Action ID text input
  - "Verify" button
  - Loading: "Fetching record from Algorand..."
  - Result:
    - ✅ Hash Verified / ❌ Hash Mismatch (prominent, top of card)
    - IPFS Hash (on-chain)
    - IPFS Hash (recomputed from fetched data)
    - Decision, Amount, Vendor ID, Agent ID, Policy Result
    - Timestamp (human readable)
    - IPFS CID link
```

## API Connection
- Backend runs at http://localhost:8000
- Tab 1: POST /api/audit with body { amount: parseInt(amountInput), vendor_id: vendorInput }
- Tab 2: GET /api/verify?action_id=<value>
- Handle loading state during both calls
- Handle error state if either call fails (show error message, do not crash)

## Component Structure (keep flat)
```
src/
├── App.jsx            # All state + tab toggle lives here
├── components/
│   ├── AuditResult.jsx   # Tab 1 result state — receives result as props
│   └── VerifyAudit.jsx   # Tab 2 — has own local state for input + result
```
Do not create more components than these three for the MVP.

## Styling Rules
- Functional over beautiful. Clean and readable is enough.
- Dark background preferred (easier to demo on projector).
- Make IPFS CID and Algorand TX ID visually distinct — monospace font, truncated with full value on hover.
- Mobile responsive is not required for hackathon demo.

## What Not To Do
- Do not add animations or transitions that could break during demo.
- Do not add authentication, login, or wallet connect for MVP.
- Do not add history/logs view for MVP.
- Do not add multiple pages or routing.
- Do not use a component library that requires complex setup.

## Demo Reliability
- Test the full browser flow at least 10 times before recording backup video.
- Keep browser console open during demo prep — fix all errors and warnings.
- Have backend running and confirmed working before opening browser.
