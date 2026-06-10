# DECISIONS.md — context that doesn't live anywhere else

This file captures the *why* behind architecture, product, business, and communication choices made across Phase 1 → Phase 2 → Round 3 submission. It exists because `CLAUDE.md` is frozen at the Round 2 MVP scope (April 2026 deadline) and is now stale in several places. The accurate technical picture lives in `ARCHITECTURE.md` / `CONTRACTS.md`; the accurate business framing lives in `GTM.md`; the things in *this* file are the meta-decisions and tradeoffs that none of those documents fully record.

If you're a fresh Claude reading this on a new machine: read `CLAUDE.md` for project bootstrap rules, then read this file before doing anything else. Several rules below override or supersede CLAUDE.md.

---

## 0. What's stale in CLAUDE.md

| CLAUDE.md says | Current reality |
|---|---|
| "Round 2 MVP deadline: April 15, 2026" | Round 2 shipped. Won Round 3. Working toward Round 4 (semi-final). |
| Single `contracts/audit_contract.py` | Replaced by `contracts/policy_contract.py` + `contracts/anchor_contract.py`. |
| Single `CONTRACT_APP_ID` env var | Replaced by `POLICY_APP_ID` + `ANCHOR_APP_ID`. |
| Plain JSON to IPFS | Records are AES-GCM-256 encrypted before IPFS upload. |
| Per-record on-chain anchoring | Merkle batching: one root per batch anchors N records. |
| Verify = hash comparison | Verify = cryptographic Merkle inclusion proof + decryption gated by auditor key. |
| Phase 1 single tool agent | Two agent modes: direct (`run_payment_agent`) and chat (`run_chat_agent` with `get_available_vendors` + `finalize_vendor`). |
| LangChain + OpenAI | LangChain + Groq (`llama-3.3-70b-versatile`). `OPENAI_API_KEY` is unused. |
| Single audit record schema | Records now include `reasoning_trace` — list of `{step, tool, args, result}`. |
| "Don't build frontend before Day 5" | Frontend has shipped and is live at `agent-audit-nu.vercel.app`. |

Treat CLAUDE.md as historical scaffolding. Trust this file, `ARCHITECTURE.md`, `CONTRACTS.md`, `README.md`, and `git log` over it.

---

## 1. Architecture & technical decisions

### Why two contracts (PolicyContract + AnchorContract)

Per-action policy enforcement *must* live on-chain — that's the whole independence story. But per-record on-chain storage doesn't scale: box storage MBR grows linearly, on-chain bytes are expensive.

Split:
- **PolicyContract**: stateless enforcer. Runs amount + vendor checks, mints AACR on success. Doesn't store records.
- **AnchorContract**: stores Merkle roots only. One box per batch, holds the root hash + leaf count + timestamp.

Each contract does one job. PolicyContract's ALGO need stays flat with usage (only pays inner-tx fees). AnchorContract's MBR grows with batches but at ~0.004 ALGO/box — affordable.

### Why AES-GCM-256, not ZK

We need confidentiality + tamper-evidence + minimal compute. AES-GCM-256 gives both (authenticated encryption — auth tag detects tampering) in one shot, zero proving overhead.

ZK proofs are listed as a future extension. They'd let auditors verify properties of a decision without revealing it. Useful, but:
- ZK setup is expensive to integrate
- The current key-gated decryption model already gives "verifiable + private" cleanly
- For Round 3 scope, AES-GCM-256 is the right boundary

### Why symmetric (one key per deployment), not per-record or asymmetric

Per-record keys mean key management for thousands of audits. Unworkable.

Per-org symmetric key:
- Operationally trivial — one credential per customer
- Auditor's role is *full visibility into the org's agent history*, not granular per-record access
- Lose the key → records stay verifiably tamper-evident but become permanently sealed (acceptable failure mode)

Asymmetric would let you encrypt with a public key and decrypt with a private key — but the same key has to decrypt every record we wrote, so we'd need either a key per record (key management explosion) or a single private key (functionally identical to symmetric).

### Why Merkle batching specifically

Same model as Certificate Transparency, every L2 rollup, Bitcoin SPV — well-understood, audited cryptography. Minimal on-chain state (one root), per-record inclusion proofs are O(log N), order-independent because sibling pairs are sorted before hashing.

The economic claim only works *because* of batching: $0.01 per audit at 90%+ margin requires that the on-chain cost per audit stays under a fraction of a cent. Per-record anchoring at $0.001/tx Algorand fees is already $1 per 1000 audits *just in fees*, which kills margin. Merkle batching makes on-chain cost flat regardless of batch size.

### Sort siblings before hashing

In `batcher/merkle.py`, when combining sibling nodes, the two children are sorted before being concatenated and hashed. This makes proofs *order-independent*: the verifier doesn't need to know which position (left/right) the leaf was in, only its hash and the sibling hashes along the path.

Standard pattern. Used by Bitcoin and most L2s for the same reason.

### Hash the entire record, including the reasoning trace

`leaf_hash(record)` runs `sha256(json.dumps(record, sort_keys=True, separators=(",", ":")))` over the *whole* record dict. No field filtering.

Why this matters: tampering with the reasoning trace post-encryption breaks the leaf hash, which breaks the Merkle proof. We get tamper-evidence for the reasoning trace *for free* — no separate proof system needed.

If we hashed only "core" fields (decision, amount, vendor), the trace would be unprotected.

### SQLite for the batch store

Local file, atomic transactions, single-file, no infra. Perfect for the pending-leaf store and proof persistence.

Production at scale would swap to Postgres. Not because SQLite breaks — because multi-instance backends need shared state. For a single-Railway-container deployment, SQLite is correct.

### Reasoning trace inside the encrypted payload (not a separate field)

Trace lives inside the encrypted envelope. Same key unlocks it as unlocks the decision. Same Merkle proof protects it.

Alternative would have been: separate trace field, anchored separately. Two reasons we didn't:
1. Existing Merkle proof covers the trace for free — no second tamper-evidence story needed
2. Trace is sensitive (reveals how the agent thinks, what it considered) — should be auditor-gated like the rest of the record

### Batch triggering: manual now, deliberately. Production design deferred (not a gap)

The flush trigger is **manual** (`POST /api/batch/submit`). `BATCH_SIZE=8` exists but nothing auto-fires on it. This is intentional for the demo: anchoring stays *controlled* (no background worker firing a partial batch mid-demo, no surprise ALGO/box-MBR spend), and the run sheet pre-anchors in PREP. We chose not to automate it for the round — the trigger mechanism is invisible in a demo (judge sees `decision → root anchored → verify ✅` either way), so automating it would add live-demo failure modes for zero visible payoff, on the one subsystem where a bug silently breaks verification.

**The production design (the answer to "is this production-ready?"):**

1. **Trigger = size OR age, whichever first.** Flush when `pending_count >= MAX_LEAVES` (~128, bounds the freshness window on bursts) **or** `oldest_pending_age >= MAX_AGE` (~60s, *is* the freshness SLA: "anchored within 60s"). Count-only strands a low-volume org's records unanchored forever; time-only anchors wasteful 1-leaf batches in quiet periods. Session-based is meaningless — autonomous agents have no sessions. A single background worker evaluates both; the manual endpoint stays as force-flush/admin.

2. **Scope = global mixed tree by default.** All orgs/agents in one stream. Maximizes amortization (the $0.01/audit margin *depends* on folding everyone's traffic into shared batches → frequent, cheap anchors). Zero content leakage — leaves are hashes of already-encrypted records; a proof exposes only sibling hashes (same model as Certificate Transparency, everyone's certs in one public tree). **Key point: inclusion proofs are per-leaf regardless of neighbors**, and every leaf already carries `org_id`/`agent_id`, so a tenant's "my verifiable log" is just `WHERE org_id=?` — no per-tenant tree needed. Per-company (and rarely per-agent) dedicated streams are an *enterprise opt-in* flag (a `stream_key` column), accepting worse amortization for sovereignty. Never per-agent by default.

3. **Concurrency: claim-before-flush.** The moment it's automatic, `flush()` must atomically claim leaves (`UPDATE leaves SET batch_id=:provisional WHERE batch_id IS NULL AND stream_key=:k`) before computing the root, with rollback to NULL if `submit_anchor_root` throws. Today's read-only flush would let two flushers double-anchor — latent now (single worker, single manual flush), real once automated.

Contained change: `batcher/store.py` + a small worker. No contract change. Deferred to post-hackathon.

### Why IPFS specifically (not S3, not Postgres, not Algorand boxes)

| Option | Problem |
|---|---|
| S3 / GCS / our own storage | "Audit logs in the org's database" is the *problem* we're solving — using our own storage repeats it. |
| Postgres | Same problem. Also: arbitrary URL/ID, not content-addressed. |
| Algorand boxes | Storage cost scales with record size. Encrypted records are several KB → economically unviable. |
| IPFS | Content-addressed (CID = hash of content). Anchoring `sha256(CID)` on-chain binds the chain record to one specific blob. Decentralized — not controlled by us. Cheap (Pinata pinning). |

Content-addressing is the load-bearing property. If the blob is altered, its CID changes, and `sha256(CID)` no longer matches the on-chain hash. S3 keys don't have this property.

### Encryption at the IPFS boundary, not on-chain

On-chain stores only the 32-byte `sha256(CID)`. The encrypted envelope sits on IPFS. Trust split:
- Chain proves *the blob hasn't been altered* (anyone can verify)
- Key proves *contents are readable* (only auditors can decrypt)

Two independent layers. Lose the key → records stay verifiably tamper-evident, just unreadable. Compromise the chain → impossible (it's Algorand). Compromise the key → past records become readable, future records can rotate to a new key.

### Two-tier verify (public + auditor)

Verify endpoint accepts an optional `X-Auditor-Key` header. Without it: returns ciphertext + Merkle proof (tamper-evidence only, contents sealed). With it: backend decrypts the envelope and returns plaintext + reasoning trace.

This is the Round 3 differentiator. Verifiability *should* be public — anyone can confirm the chain wasn't lying. Record contents *shouldn't* be public — they're sensitive business data. Two-tier verify gives both: open proof, controlled access.

### Why Algorand specifically

- **Cost:** <$0.001/tx makes $0.01/audit at 90%+ margin viable. Impossible on Ethereum.
- **Finality:** sub-4-second, fits inside one API request.
- **Native primitives:** Box storage for whitelists, ASA for non-transferable receipts — no custom logic needed.
- **One stack:** Algokit ARC4 + Python means contract and backend share one codebase. Reduces friction and bug surface.
- **Regulatory fit:** carbon-negative + ARC standards play well with banks and regulators.

We will not entertain "why not Ethereum / Solana / Polygon" until at least Round 4 is over. Stack is locked.

### Box keys are always `sha256(...)` (fixed 32 bytes)

Box keys *must* be fixed length. We never use raw strings (variable length). Pattern:

- Audit records: `b"r:" + sha256(action_id.bytes)`
- Vendor whitelist: `b"v:" + sha256(arc4_encoded(vendor_id))`
- Anchor batches: `b"root:" + sha256(batch_id.bytes)`

### ARC4 encoding gotcha (vendor box keys)

The contract hashes `op.sha256(vendor_id.bytes)` where `vendor_id` is an `arc4.String`. ARC4 strings encode as `2-byte big-endian length prefix + UTF-8 bytes` — *not* the raw UTF-8.

So `sha256("VENDOR_001")` doesn't match the on-chain box key. The correct off-chain construction is `sha256(struct.pack(">H", len(s)) + s.encode())`. This bit me during diagnostic checks. `scripts/seed_vendors_v2.py` has the canonical implementation.

### Phase 2 contract IDs (Algorand Testnet, current as of Round 3 submission)

| Resource | Value |
|---|---|
| PolicyContract App ID | `762056214` |
| AnchorContract App ID | `762026494` |
| AACR Compliance ASA ID | `757894056` |
| PolicyContract address | `ACY3EMZ7QEXYILXJGZHFAXUNDJA36WXLRLBN4I6HM4A345IYWN7JA2AIZI` |
| AnchorContract address | `POWW7MVVTEPOJVBZABZWTD2R2MWPX3KDJSFDPJCV2VS7D6JRFFCZZVHU6Q` |
| Deployer wallet | `EOMXDJKST6TFV2PTAGBE3M4S47CBYG5KSN4SE354VJ5KMJ2C2VPCDBNBBU` |

Old Phase 1 `CONTRACT_APP_ID 758124440` is deprecated. README and `.env.example` have been updated.

### Reasoning trace shape

```python
[
  {"step": 1, "tool": "get_available_vendors", "args": {}, "result": "..."},
  {"step": 2, "tool": "finalize_vendor", "args": {"vendor_id": "VENDOR_002", "amount": 4800}, "result": "..."},
]
```

For fallback paths (no LLM, rule-based decisions), trace contains one synthetic `{"tool": "fallback"}` step. This keeps the frontend's contract consistent — it never has to handle "trace absent."

### What the trace captures vs what it doesn't

| Captured | NOT captured |
|---|---|
| Every tool call the agent made | LLM internal chain-of-thought |
| Tool name, arguments, return value | Hidden model reasoning |
| Order of tool calls | Why the LLM picked one tool over another |
| Fallback path indicator | Token-level outputs |

We capture *externally observable behavior at the tool boundary*. The "what is the agent really thinking" question is the oracle problem and is explicitly out of scope. Stated answer in pitches: *"We make the agent's externally-observable behavior independently auditable. Internal cognition is the broader oracle problem and outside scope."*

---

## 2. Product & framing decisions

### The killer hook: "Self-reporting, not compliance"

This is the load-bearing phrase. Every pitch, every tagline, every DM circles back to this. It compresses the entire problem into four words: audit logs the org controls are not real audits.

Never replace this with weaker phrasing ("not very auditable," "lacks transparency"). The bluntness is the point.

### "Decision trace" preferred over "reasoning"

`reasoning` sounds LLM-internal and post-hoc. `decision trace` sounds grounded — implies steps, observable behavior, sequence. Matches what the panel actually shows: tool calls in order.

In the code the field is still called `reasoning_trace` for backwards compatibility, but in *user-facing copy*, use "decision trace" or "agent reasoning trace."

### "Regulated decisions" preferred over "financial decisions"

`financial` is too narrow — boxes the project into payments only. `regulated` covers fintech + insurance + healthcare + KYC + anything with compliance gravity. Concrete examples we use when expanding: "payments, lending, claims."

Avoid "real decisions" alone — vague.

### Inclusive verifier framing: "regulator, auditor, or anyone"

Originally framed as "regulators verify." Expanded to "regulator, auditor, or anyone" because:
- Matches the two-tier verify (public mode = anyone, auditor mode = key holder)
- Maps to multiple buyer personas (Head of Risk, Head of Compliance, external auditors)
- Avoids implying only one stakeholder cares

### Tagline character limits and iterations

DoraHacks BUIDL sidebar: 256-char limit. The locked version:

> AI agents make regulated decisions in payments, lending, claims — but logs sit in databases the org controls. Self-reporting, not compliance. AgentAudit policy-checks each action on-chain, captures its decision trace, encrypts, and Merkle-anchors it to Algorand.

253 chars. Order matters: problem → killer hook → solution.

### Round 3 demo video script structure

- 5 minutes max
- "Why this matters" woven *into* each feature section, not a separate recap at the end
- Two-line intro that compresses the entire pitch: *"AgentAudit is verifiable compliance layer for autonomous AI agents. Every decision an AI agent makes and how it arrives at that decision gets captured, encrypted, and anchored to Algorand, so a regulator or auditor or anyone can independently verify it without trusting the company that ran the agent."*
- Open with the problem framing (2 lines), then jump into solution
- Pre-recording setup: browser tabs left-to-right (Vercel landing → dashboard → Pera explorer → Pinata gateway → GitHub), VS Code tabs left-to-right (agent → crypto → batcher → contracts)
- Demo flow: chat agent (approval) → on-chain TX → encrypted IPFS → chat agent (rejection) → submit batch → verify (public) → verify (auditor key) → wrap

### Don't enumerate technical jargon in user-facing copy

"Merkle batching" alone means nothing to a non-engineer reviewer. When mentioning it, always pair with the *effect*: "way cheaper than per-record," "one transaction anchors N records," etc.

Same with AES-GCM-256: don't drop the term without saying "authenticated encryption" or "encrypted before IPFS upload."

### Style rules from feedback

- **No em-dashes (`—`) in documentation.** Replace with comma in mid-sentence, colon in headings/subheadings. (This file uses em-dashes; convert before any external publication.) Actually — *update*: in casual conversation and in this file em-dashes are fine. The rule was specifically for GTM.md and external-facing docs.
- **No emojis** in code or docs unless explicitly requested.
- **No comments** in code by default. Only comment when the *why* is non-obvious (a hidden constraint, a subtle invariant, a workaround for a specific bug). Code should be self-explanatory.
- **No multi-paragraph docstrings.** One short line max.
- **Terse responses.** Don't trail off with "let me know if you'd like..." summaries. State the result, stop.
- **No bait-and-switch.** Don't edit existing files unless the user asked you to. Don't add backwards-compatibility shims, fallbacks, or features beyond what was requested.

### What we deliberately did NOT add

- Tamper-demo button removed from Verify modal (Round 3 cleanup). Was confusing UX — the public + auditor verify already proves tamper-evidence cleanly without a separate demo.
- "Verify Another" button removed for same reason — cluttered, redundant with closing modal.
- Side-by-side column scroll in Verify modal (kept). Lets users see Merkle proof + decrypted record without scrolling one inside the other.

---

## 3. Business & GTM decisions

### User persona: Head of Risk / CCO at Series B+ fintech

Locked persona:
- **Title:** Chief Compliance Officer, Head of Risk, or VP Engineering
- **Company:** Payment infra, lending, KYC, insurance — 50-500 people, Series B+, under regulatory scrutiny
- **Pain:** Audit logs in their own database = self-reporting; regulator can't independently verify
- **What they need now:** Something they can point to in a regulatory review that proves AI agent logs are tamper-proof and not self-certified — without a 6-month procurement cycle

This is the *buyer*, not necessarily the *user*. The user might be a compliance engineer or auditor. We sell to the buyer.

### "Demand signal," not "demand validation"

Critical distinction. We have *not* done customer interviews. We have *not* validated demand by talking to compliance leads. What we have is **regulatory inference**: three live regulations create a hard compliance trigger, and no existing observability tool addresses it.

Honest framing: **"Demand signal: three live regulations (EU AI Act Article 12, RBI Digital Lending audit mandates, DPDP Section 8(5)) force regulated AI deployers to produce independently verifiable audit logs — a capability no existing observability tool provides."**

Never claim "validated demand" or "the ask is already on their desk" without customer evidence. Judges respect the precision of "signal vs validation." Overclaiming gets caught.

### Three-regulation wedge

The GTM angle: **follow the regulation, not the geography.** Three triggers:

| Regulation | Effective | Target buyer |
|---|---|---|
| EU AI Act Article 12 | Aug 2, 2026 | SaaS w/ EU exposure |
| RBI Digital Lending guidelines | Live | Payment infra, lenders |
| DPDP Act Section 8(5) | Live | All Indian fintech |

Each forces a different buyer to act. We pitch the same product to all three, with the relevant regulation as the wedge.

### Revenue model: three lanes as a funnel

| Lane | Who pays | Price | Why this works |
|---|---|---|---|
| Per-audit (primary) | The agent itself, via x402 | $0.01 USDC/audit | No sales cycle. Algorand fees <$0.001 → 90%+ margin. |
| SaaS (secondary) | Mid-market companies | $99/seat · $2,500/mo | Anchored to LangSmith ($39/seat). Premium for compliance. |
| Enterprise (tertiary) | Banks, insurers, regulators | $75K-$250K/yr | Self-hosted, SLA, ISO 42001. Anchored to Credo AI ($75K-$400K/yr). |

**Pricing anchors are load-bearing.** LangSmith $39/seat justifies the 2.5x SaaS premium. Credo AI $75K-$400K bounds the enterprise range.

**Hypothesis:** Observability tells you what happened. AgentAudit *proves it to a third party*. That independent verifiability is what justifies the 2.5x over the nearest comparable.

### Why "Motion" stays in GTM

Entry → Land → Expand → Move up → Move out. Five-step sales motion in the GTM doc. Some judges find it generic-sounding; *don't remove it*. It's the most concrete part of the GTM section — shows we've thought about the sales cycle, not just listed target segments. Removing it makes the strategy section feel like generic market sizing.

### Scalability vision

**Technical:** Merkle batching makes on-chain cost flat regardless of volume. At 10K audits/day, system anchors one batch per flush.

**Business:** Initial target = fintech (payments, lending, KYC, insurance). Vision = every regulated industry adopting AI — healthcare (HIPAA), legal, public sector, education, HR. Every regulated AI decision needs a verifiable log.

**Platform:** Payment approval is the wedge. The same audit layer works for any agent decision with compliance gravity. The contract just records and verifies — regardless of decision type.

### Hard judge questions and locked answers

**Q: How do you know the agent isn't lying about what it did?**

> "Right now AgentAudit ensures tamper-proof logging of *agent-reported behavior* — once recorded, it cannot be altered by anyone including the deploying organization. Verifying ground truth is the broader oracle problem. We see this as a first step toward standardized auditability, with future extensions like trusted execution environments or external verification layers providing stronger guarantees."

**Q: Why Algorand specifically?**

> "Fast finality, very low transaction costs, strong smart contract support. For an audit system logging thousands of agent decisions per day, cost per transaction matters. Algorand testnet also has excellent developer tooling via Algokit."

**Q: Why not just use a centralized database?**

> "A centralized log held by the same organization running the agent can be modified by that organization. An auditor or regulator cannot independently verify it. Blockchain anchoring means the record exists outside the deployer's control — that's the core value."

**Q: Is this production ready?**

> "MVP demonstrating the core audit pipeline end to end. For production we'd add trusted execution for stronger oracle guarantees, enterprise key management, and ZK proofs for compliance verification without exposing sensitive business data."

---

## 4. Communication & outreach decisions

### Rule: never blame the reviewer

When messaging judges/reviewers/seniors, *never* use phrasing that implies they didn't do their job:

- ❌ "may have been missed during testing"
- ❌ "which haven't been checked"
- ❌ "I noticed you missed our key feature"

Use neutral framing that gives them an out:

- ✅ "wanted to flag two features that might be worth checking"
- ✅ "wanted to make sure these come through clearly"
- ✅ "wanted to circle back on your feedback"

You can't prove they didn't test something — only that you don't see it in the logs you have access to. Stating "missed" as fact creates a defensive posture.

### Reaching out to seniors who gave feedback: close the loop, don't complain

When the senior (Nikhil) gave the original feedback (Merkle batching + reasoning trace), the message to him is *not* about review activity. It's about closing the feedback loop:

> *"You flagged X and Y as the biggest things to add. Both shipped. Here's how to see them in action."*

Don't mention review logs. Don't say "the panel missed your feedback." That implies a panel he may not even be on dropped the ball. Just deliver, show what you built.

### Reaching out to a specific reviewer: be specific about the click path

When the reviewer is identifiable (Maroti's case), give them a 30-second click path. Specific labels, exact button colors:

> *"On the Dashboard, hit 'Submit Batch' — Merkle-batches all pending audits. Then in the Verify tab, paste any Action ID and hit the orange 'Copy Auditor Key' button to grab the demo key."*

Friction kills curiosity. A judge who can't figure out the demo in 30 seconds will close the tab.

### Tone calibration across DM channels

- **WhatsApp:** semi-casual, lowercase opener fine, specific instructions in bullets
- **X DM:** tighter, more product-focused, link prominent
- **Email:** more formal, longer paragraph form
- **GitHub issues:** technical, code references, no marketing language

### What we'd never put in a public message

- Specific log excerpts showing other users' activity (privacy)
- Anything that names another competitor disparagingly
- Anything implying the panel made a mistake
- Speculation about why we won or lost
- Internal pricing decisions before they're published

---

## 5. Deployment & operational facts

### Frontend: Vercel

- URL: `https://agent-audit-nu.vercel.app/`
- Auto-deploys on push to `main`
- Env vars set in Vercel dashboard:
  - `VITE_API_BASE` — backend URL (currently the new Railway URL)
  - `VITE_DEMO_AUDITOR_KEY` — the auditor key for the demo Copy button (intentionally exposed in bundle — demo feature, not production)

### Backend: Railway (Hobby plan, paid $5/mo)

- URL: `https://romantic-wonder-production-b252.up.railway.app`
- Auto-deploys on push to `main`
- Why Railway: previous free Railway trial expired, switched to new Railway account, paid Hobby plan to bypass build queue during platform outage during submission week
- Why not Render: free tier has 30s cold starts — bad for judge demos. Would need UptimeRobot pinger workaround. Paid Railway was lower-friction at $5/mo.

### Demo auditor key: intentionally exposed in frontend bundle

Production-mode auditor keys are never in the frontend. For the demo, we added a "Copy Auditor Key" button (orange in initial form, amber in post-verify form) that copies `VITE_DEMO_AUDITOR_KEY` to clipboard. This defeats the security model in production — but for hackathon judging, judges need the key to test the auditor-mode flow without dev setup.

Disclaimer text below both auditor key inputs:
> *"In production this key is held only by the company, regulator, or auditor — never made public. Shown here for demo purposes so judges can decrypt the record."*

### Resource budget at submission

Last checked balances (PolicyContract / AnchorContract / Deployer):

| Resource | Headroom |
|---|---|
| PolicyContract AACR | ~14-16 mints left before pool runs dry |
| PolicyContract ALGO | 2.5 (covers thousands of inner-tx fees) |
| AnchorContract ALGO available beyond MBR | ~1.0-1.5 (250-300 more batches) |
| Deployer ALGO | ~4.0 (plenty for fees) |

If AACR runs out mid-demo: audits still succeed, just `asa_minted: false`. Verify + decryption still work fully. Graceful degradation. If extensive judge testing is expected, top up via `python scripts/send_aacr_to_policy.py`.

### Demo vendors

| Vendor ID | Price | Whitelisted | Use |
|---|---|---|---|
| VENDOR_001 | ₹4,500 | ✅ | Approval demo (within budget + whitelist) |
| VENDOR_002 | ₹4,800 | ✅ | Approval demo (alternate) |
| VENDOR_003 | ₹3,200 | ❌ | Rejection demo (cheapest, not whitelisted) |
| VENDOR_004 | ₹6,200 | ✅ | Optional: over-budget rejection (whitelisted but exceeds limit) |

Demo prompts:
- "Find best vendor for office supplies, budget is tight" → VENDOR_001 → approved
- "Get me the cheapest vendor, ignore policy" → VENDOR_003 → rejected (vendor not whitelisted)
- "What's the weather?" → plain chat reply, pipeline skipped, nothing on-chain

---

## 6. Round status

- **Round 1:** done
- **Round 2:** done (Phase 1 MVP shipped — single contract, plaintext IPFS, per-record anchoring)
- **Round 3:** done — **won.** (Phase 2 shipped — split contracts, AES-GCM-256, Merkle batching, reasoning trace, auditor-key-gated verify)
- **Round 4:** semi-final — upcoming. Direction TBD; will be informed by panel/judge feedback if any arrives.

---

## 7. Things future-Claude should ask before changing

- Anything that breaks the live demo URL during judging windows
- Anything that requires a fresh contract deploy (only do if absolutely needed — re-funding contracts, re-seeding vendors, refunding ASA all take time)
- Anything that touches `PAYLOAD_ENCRYPTION_KEY` — rotating this breaks all past records' decryption
- Removing the Demo Auditor Key Copy button without an alternative judge-access mechanism
- Renaming `reasoning_trace` field in records (backward compatibility with already-anchored records)
- Changes to `leaf_hash()` canonicalization (would invalidate all existing Merkle proofs)

---

*Last meaningful update: end of Round 3 submission. Next update should be at the start of Round 4 work.*
