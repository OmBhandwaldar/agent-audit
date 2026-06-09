# FINAL_PHASE.md — Locked decisions for the Round 4 platform build

This file is the single source of truth for the final-round build of AgentAudit:
the move from a single-tenant demo to a real multi-tenant platform with onboarding,
an SDK, x402 billing, and two enforcement modes (with a third in future scope).

Everything below is **decided and locked** unless a line explicitly says "future scope."
Read this together with `DECISIONS.md`, `ARCHITECTURE.md`, and `CONTRACTS.md`.
Treat `CLAUDE.md` as historical (frozen at Round 2) — see section M.5.

**Execution plan: see [FINAL_PHASE_PLAN.md](FINAL_PHASE_PLAN.md).** This file is the *what/why*; that file is the *how* (detailed step-by-step build order).

---

## 0. Branch

Do all of this work on a dedicated branch, not on `main`. `main` stays demo-ready at all times.

- **Branch name:** `feat/multi-tenant-platform`
  (encompasses multi-tenancy, onboarding + SDK, x402 billing, and Mode 2.)
- **Rule:** never push broken code to `main`. Merge to `main` only when a working
  milestone is confirmed and the existing Phase 2 demo still passes.
- **Commit convention:** scoped, one piece per commit
  (e.g. `feat: multi-tenant policy boxes`, `feat: x402 ingest endpoint`, `feat: agentaudit SDK`).
- **Safety net:** the current `main` (Phase 2 flow) must remain runnable as a fallback demo
  throughout. If the new flow is unstable near the event, demo from `main` and pitch the
  platform as the roadmap.

---

## A. Scope & approach

- Build for the **final round** (the day after the semifinal), as a real product — not a demo shim.
- Target bar = **complete and genuinely working on testnet, nothing mocked.**
  Not enterprise-hardened this round (no real KMS, fiat billing, or SOC2).
- Keep the existing Phase 2 flow intact and working while building the tenant layer alongside it.
  A working demo must exist at every step.

---

## B. Multi-tenancy & policy architecture

- **One shared multi-tenant `PolicyContract` is the default**, not a contract per org.
- Per-org **and per-agent** policies live in **on-chain box state (data, not code).**
- Tenant policy keyed by `sha256(org_id + agent_id [+ index])`;
  vendor/whitelist boxes namespaced `sha256(org_id + vendor_id)`.
- `check_and_mint` reads the **caller's own** policy boxes and enforces against them.
- Policy is a **generic predicate engine**: each rule is a predicate `{field, operator, value}` over the
  decision's declared fields (operators: `< <= > >= == != in not_in`), combined as a set of conditions.
  Orgs compose N predicates per agent as **data** — over **any field their agent emits** — so an org can
  author its **own custom policies ("add a new item to the menu") without new code or a redeploy.**
  Standard named policies (amount limit, whitelist, rate cap, allowed action) are just common predicates;
  agent-type selection (insurance / procurement / lending) pre-fills sensible defaults the org then edits.
- **Internal vs external boundary:** on-chain enforcement only covers policies over the
  decision's *own declared fields* (internal). Policies depending on external real-world facts
  are **recorded/anchored but not enforced** — that is the oracle problem, explicitly out of scope.

### B (refined) — what "custom policy" covers

With the generic predicate engine, "custom policy" is **data, not code**, in almost all cases:

- **Custom values / combinations** — pick fields, operators, and thresholds. Data. **In scope, all tiers.**
- **Custom checks over the org's own fields ("add a new item to the menu")** — any predicate over any
  field the agent emits, including fields no standard policy uses. Data. **In scope this round** — no new
  code, no redeploy, shared contract. (Complex/nested expressions run as Mode 2 off-chain; flat AND-ed
  predicates run on-chain as Mode 1.)
- **Out of scope (genuine limits, small residual):**
  - **combination logic beyond AND** — this round all selected predicates are AND-ed (all must pass).
    OR / "any N of M" / nested boolean groups are **future scope** (would run via Mode 2 off-chain first,
    then on-chain later).
  - logic **not expressible as predicates** (arbitrary computation, weighted ML scores, loops) — would
    need a custom evaluator; rare, enterprise/future.
  - checks depending on **external real-world facts** not in the decision — the oracle problem (see §B internal/external).
- **Dedicated contract instance** is for **isolation / data residency** — code identical, only deployment
  differs (apartment building vs private house). It is **not** needed for custom policy logic, which the
  shared predicate engine already handles as data.

---

## C. Enforcement modes

- **Mode 1 (transparent / public):** plaintext policy in on-chain boxes; the contract enforces
  directly; the chain is the **enforcer**; trustless; AACR = proof. For non-sensitive internal
  policies. **Status: have — keep and protect.**
- **Mode 2 (private):** only `sha256(policy)` commitment on-chain; plaintext policy encrypted
  off-chain (under the org key); enforcement **off-chain by the backend**; the chain is a
  **notary**; the auditor re-verifies against the commitment. For sensitive internal policies.
  **Status: build this round.**
- **Mode 3 (ZK):** private + trustless; the backend proves and the contract verifies a Groth16
  proof on-chain (AVM pairing opcodes), Poseidon commitment, prover separate from the agent.
  Feasible on Algorand but multi-week. **Status: future scope, roadmap only; build post-event if ever.**
- Mode is chosen **per policy** (public vs sensitive). **Mixed-policy agents are supported.**

---

## D. ASA mint — Option B (attested mint) for Mode 2

- In Mode 2, mint the AACR via **backend assertion**, **bound to the policy commitment**,
  and **marked in the record** as `enforcement = "off-chain-attested"`.
- **Only an authorized minter** (the AgentAudit backend wallet) can trigger an attested mint
  (`assert Txn.sender == authorized_minter` on the attested path).
- The mint is **"trusted at mint time, auditable after the fact"** — the auditor re-verifies
  legitimacy via the commitment.
- The result string records provenance per check, e.g. `amount:pass(onchain)|kyc:pass(attested)`.
- Mixed agent: mint iff **(all Mode-1 checks pass on-chain) AND (all Mode-2 checks asserted pass).**
- AACR meaning by mode:
  - Mode 1 = trustless proof
  - Mode 2 = attested + auditable
  - Mode 3 = trustless proof for private policies

---

## E. Encryption & keys

- **Per-org stable encryption key (the auditor key), company-held.**
  Not per-audit (rejected as unworkable at scale), not one global key (current state, wrong for multi-tenant).
- **Versioned for rotation** (new records use the new key; old records still decrypt with the old key;
  never lose history).
- The same key encrypts **records and Mode-2 policy docs.**
- Fits the existing verify flow: the auditor passes the key via the `X-Auditor-Key` header at verify time.
- Onboarding issues a **per-org key** instead of the single global `PAYLOAD_ENCRYPTION_KEY`.

---

## F. Trust model

- Mode 2 = **private from the public chain, not invisible to AgentAudit.**
  The backend is a **trusted processor** (holds the key, encrypts, enforces Mode 2 off-chain);
  the chain only ever sees commitments/hashes.
- The "vendor-blind" version = client-side encryption + self-hosted + Mode 3 (enterprise / future).

---

## G. Onboarding

- Onboarding = **two separate acts:**
  1. **One-time human provisioning** — create org, register agent, define policies, issue key.
     Not autonomous; policy is a human decision.
  2. **Per-call autonomous payment** by the agent (x402) — the zero-touch part.
- Provisioning bundle: `org_id` (public), `api_key` (secret, shown once), `encryption_key v1` (company-held).
- Off-chain `tenants` row: `{org_id, api_key_hash, enc_key_ref, billing_mode, created_at}`;
  per-agent: `agent_id` + policy set.
- At policy registration, the org picks **Mode 1 or Mode 2 per policy.**
- Billing chosen at onboarding: subscription/metered (API key) **or** pay-per-call (x402).

### G (locked) — x402 flavor

**We go with Flavor 1: provisioned tenant + x402 billing = real compliance.**
A human provisions the org, agent, policies, and key once; thereafter the agent pays per call
via x402. The compliance guarantee holds because a human set the policies.

(Flavor 2 — anonymous x402 with no prior setup = tamper-evident notarization only, not compliance.
**Not pursued.** It is recorded here only so the distinction is clear.)

---

## H. Integration surfaces & auth

- **SDK call, decorator, and raw REST** are all conveniences over **one ingest endpoint**:
  `POST /v1/audit`.
- The ingest endpoint accepts an **external agent's already-made decision + trace**
  `{agent_id, action, decision, fields, reasoning_trace}` — distinct from the current demo
  endpoints that run AgentAudit's *own* internal agent.
- Auth: API key (Bearer) resolves to an org; an x402 payment authorizes and declares the org.
  The backend is the trusted submitter; the org is resolved off-chain from the API key (simple).
- Fully trustless identity (bind `org_id` to the org's wallet address, contract checks `Txn.sender`)
  is a **future refinement.**

---

## I. Revenue model (3 lanes, locked)

| Model | Who pays & how | Price (anchor) | What it provides | Why it works |
|---|---|---|---|---|
| **Per-audit / x402** (primary) | The agent pays per call in USDC via x402, after a human provisions it once (org, policies, key) | **$0.01 USDC / audit** | Self-serve provisioning (no salesperson); shared multi-tenant contract; Mode 1 + Mode 2; encrypt -> IPFS -> Merkle-anchor -> AACR; verify-by-Action-ID | **No sales cycle** (self-serve) + **zero-touch per-call billing**. Algorand fees <$0.001 -> **90%+ margin**. |
| **SaaS subscription** (secondary) | Mid-market companies, post-paid; agent authenticates with an API key, calls metered | **$99 / seat · $2,500 / mo** (anchor: LangSmith $39/seat) | API key + SDK/decorator; self-serve dashboard; multi-tenant contract; per-org key; Mode 1 + Mode 2; dashboard, CSV export, metered usage | Recurring revenue. The 2.5x premium over LangSmith holds because observability tells you what happened — AgentAudit proves it to a third party. |
| **Enterprise / self-hosted** (tertiary) | Banks, insurers, regulators; annual contract via sales | **$75K–$250K / yr** (anchor: Credo AI $75K–$400K/yr) | Dedicated contract instance (isolation); self-hosted option; client-side encryption; priority Mode 3 roadmap; SLA, ISO 42001, dedicated support, custom policy types | High ACV anchors the top of the funnel. Isolation + compliance certs are what regulated buyers pay for. |

Two billing mechanics under the usage lane:

| Mechanic | When | How | Human setup first? |
|---|---|---|---|
| **x402 (prepaid, per call)** | Provisioned agent, no per-call human | Agent gets `402` -> pays $0.01 USDC -> audit runs | Yes — policies + key set once by a human |
| **Metered API (post-paid)** | Onboarded SaaS orgs | API key authenticates; calls counted -> monthly invoice | Yes — same one-time provisioning |

- **Funnel, not three products.** Self-serve per-audit lands the long tail of autonomous agents ->
  some grow into SaaS seats -> the regulated few move up to enterprise.
- **Onboarding is one-time and human; operation is continuous and autonomous.**
- **Anchors are load-bearing:** LangSmith $39/seat justifies the SaaS 2.5x; Credo AI bounds enterprise.
- **Architecture = unit economics:** there are two on-chain costs. The per-audit policy check
  (`PolicyContract.check_and_mint` -> one app call plus an inner AACR mint on pass, ~0.001-0.002 ALGO,
  no per-audit box) is the linear floor, kept sub-cent by Algorand fees. Merkle batching keeps the
  *separate* anchoring (`AnchorContract`) flat so it never becomes a second per-audit transaction.
  $0.01/audit holds 90%+ margin because the per-audit transaction is sub-cent (impossible on Ethereum),
  not because all on-chain cost is flat.
- **Honest framing:** this is the revenue *model*, not validated revenue. Pair with the
  three-regulation demand signal; never claim paying customers unless true.

---

## J. Capability matrix (locked)

The core audit guarantee is identical across all tiers; tiers differ only in delivery,
isolation, support, and billing.

| Capability | Per-audit (x402) | SaaS | Enterprise |
|---|:---:|:---:|:---:|
| **— Core audit guarantee (same for everyone) —** | | | |
| Merkle anchoring on Algorand | ✅ | ✅ | ✅ |
| AES-GCM-256 record encryption | ✅ | ✅ | ✅ |
| Mode 1 — transparent on-chain enforcement | ✅ | ✅ | ✅ |
| Mode 2 — private commitment enforcement | ✅ | ✅ | ✅ |
| AACR compliance receipt | ✅ | ✅ | ✅ |
| Two-tier verify (public proof + auditor-key decrypt) | ✅ | ✅ | ✅ |
| Decision / reasoning trace capture | ✅ | ✅ | ✅ |
| Verify by Action ID | ✅ | ✅ | ✅ |
| SDK / decorator / REST integration | ✅ | ✅ | ✅ |
| Per-org encryption key | ✅ | ✅ | ✅ |
| Custom predicate policies (any field, as data) | ✅ | ✅ | ✅ |
| **— Differs by tier —** | | | |
| Self-serve provisioning (no salesperson) | ✅ | ✅ | ❌ |
| Pay-per-call via x402 (USDC, no subscription) | ✅ | ❌ | ❌ |
| Subscription / metered API-key billing | ❌ | ✅ | ✅ |
| Web dashboard + CSV export | ➖ | ✅ | ✅ |
| Shared multi-tenant contract | ✅ | ✅ | ❌ |
| Dedicated contract instance (physical isolation) | ❌ | ❌ | ✅ |
| Self-hosted deployment | ❌ | ❌ | ✅ |
| Client-side encryption (we never see plaintext) | ❌ | ➖ | ✅ |
| Bespoke policy logic (non-predicate / custom evaluator code) | ❌ | ❌ | ✅ |
| Dedicated support + SLA | ❌ | ❌ | ✅ |
| ISO 42001 / compliance certifications | ❌ | ❌ | ✅ |
| Priority on Mode 3 (ZK) roadmap | ❌ | ❌ | ✅ |

Legend: ✅ included · ❌ not included · ➖ limited/optional

**Message:** the trust guarantee is identical at every tier. A $0.01-per-call agent and a
$250K/yr bank get the same tamper-proof, encrypted, independently-verifiable audit. You pay
more for **delivery and control** (isolation, self-hosting, SLA, ISO 42001, dashboard, custom
policy types), not for a stronger audit.

Note on policy customization: per section B (refined), **custom predicate policies over any field are
available to all tiers** as data ("add a new item to the menu"). Only logic that cannot be expressed as
predicates (arbitrary computation) or needs bespoke evaluator code is enterprise-only.

---

## K. Self-hosted vs isolation

- **Isolation (own contract)** = on-chain layer; a dedicated contract instance (own App ID/boxes);
  the backend is still AgentAudit-run. Answers: "is my on-chain footprint mine alone?"
- **Self-hosted** = off-chain layer; the company runs the backend itself; data/keys never touch
  AgentAudit. Answers: "does my data ever leave my walls?"
- Orthogonal; they combine. Mid-market typically wants isolation; a bank wants both.
- **Honest caveat:** the dedicated-contract isolation tier is designed/inferred, not validated demand.
  The self-hosted / data-residency rationale is standard, hard enterprise reality.

---

## L. Build priority for the week

1. Mode 1 working + polished (have — protect it)
2. Multi-tenant + onboarding + real SDK
3. x402 pay-per-audit (Flavor 1)
4. Mode 2 (private commitment + attested mint, Option B)
5. Tests + business case + slides + **rehearsal**
6. Mode 3 (post-event; roadmap slide only)

Mode 3 sits **below rehearsal** deliberately. If Mode 2 starts to balloon, cut it to a roadmap
slide without hesitation — a rehearsed demo and a tight business case win more points than an
unfinished mode.

### Platform generality (do after the points above)
Once the platform is built, any agent — insurance, procurement, lending, or anything else —
onboards and connects the same way, with **zero changes to the audit layer**. Plan one extra
demo agent (e.g. an insurance claims agent) so two distinct industries can be shown side by side
to prove the platform claim live. Constraints: you still write the thin domain agent + its entity
registry; the agent's emitted fields must match the policy field names; external-fact policies are
record-only (oracle boundary).

### UX / UI overhaul (post-build)
After the platform is functionally complete, improve the UX and **redesign the UI.** This is **feedback
from an AlgoBharat member** that the UX needs to be better. Tracked as **Phase 11** in FINAL_PHASE_PLAN.md.

---

## M. Cleanup & fixes (now locked)

These were flagged during the repo analysis and are now confirmed for this branch.

### M.1 — Remove `/api/verify/v2` (confirmed correct)
The `/api/verify/v2` endpoint in `api/main.py` decrypts with the server's own
`PAYLOAD_ENCRYPTION_KEY` and returns plaintext to **anyone**, with no auditor key. This directly
violates the two-tier privacy model. The real endpoint is `/api/verify`.
**Action: delete `/api/verify/v2`.**

### M.2 — Remove dead Phase 1 files and the orphaned tamper-demo endpoint
**Action: delete**
- `contracts/audit_contract.py`
- `algorand/contract_client.py`
- `sdk/audit_flow.py`
- `scripts/runFlow.py`
- `scripts/seed_vendors.py`
- the `/api/tamper-demo` endpoint in `api/main.py` (the tamper-demo button was already removed
  from the frontend in Round 3; the backend endpoint is orphaned)

(Confirm nothing still imports these before deleting; update any stale references.)

### M.3 — Fix the verify read-path (`get_anchor_root`)
`get_anchor_root` in `algorand/contract_client_v2.py` currently sends a **signed, fee-paying
transaction** to read a readonly value, so every verify costs a fee and does not scale.
**Action: replace it with a free box read via algod (read the box state directly), no transaction.**
This is also the answer to the "data/indexer at 10X" scalability question.

### M.4 — Make the SDK Integration tab real
`frontend/src/components/SdkIntegration.jsx` currently shows a fictional `agentaudit` package,
a fake `api.agentaudit.io` URL, and a decorator that does not exist (the component's own docstring
says it is "pure presentation").
**Action: back it with the real SDK + real endpoint built in this phase.** Point it at the real
ingest endpoint; mark anything not yet built as roadmap rather than presenting it as working.

### M.5 — Treat CLAUDE.md as stale
`CLAUDE.md` is frozen at the Round 2 MVP and is inaccurate in several places.
**Action: trust `DECISIONS.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, this file, and `git log` over
`CLAUDE.md`.** (Optionally add a one-line pointer at the top of `CLAUDE.md` directing readers here.)

---

*Last updated: start of Round 4 / final-phase planning.*
