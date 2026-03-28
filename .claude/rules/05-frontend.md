# Rule File: Frontend
# Scope: Apply only during Phase 2 (Days 8–14) when building the React UI.
# Do not apply during Phase 1. Do not suggest frontend work until Day 5 checkpoint passes.

## Stack
- React (Vite setup preferred — faster than CRA)
- No UI component library required. Plain CSS or Tailwind only.
- No Redux, no Zustand. useState is enough.
- Axios or fetch for API calls. No extra HTTP libraries.

## Single Page. Three States Only.
```
State 1: Input
  - Number input field (amount in ₹)
  - "Run Agent" button
  - Nothing else

State 2: Loading
  - Spinner or simple text: "Agent is processing..."
  - Disable button during loading

State 3: Result
  - Decision badge (green ✅ Approved / red ❌ Rejected)
  - IPFS CID (clickable → https://ipfs.io/ipfs/{cid})
  - Algorand TX ID (clickable → https://testnet.explorer.perawallet.app/tx/{tx_id})
  - Policy Result (Pass / Fail)
  - ASA Minted (Yes / No)
  - Timestamp (human readable)
  - "Run Again" button to reset to State 1
```

Do not add more UI elements than listed above.

## API Connection
- Backend runs at http://localhost:8000
- Single call: POST /api/audit with body { amount: parseInt(inputValue) }
- Handle loading state during call
- Handle error state if call fails (show error message, do not crash)

## Component Structure (keep flat)
```
src/
├── App.jsx          # All state lives here
└── AuditResult.jsx  # Receives result as props, renders State 3
```
Do not create more components than these two for the MVP.

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
