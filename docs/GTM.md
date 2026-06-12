# AgentAudit, Go-To-Market

The business case for AgentAudit: problem, target customer, why now, value proposition, why
blockchain, demand, competition, market size, revenue model, unit economics, go-to-market, cost
structure, dependencies, moat, and roadmap.

---

## 1. One line

AgentAudit is a verifiable compliance layer for autonomous AI agents. Every decision an agent makes,
with its reasoning trace, is policy-checked on-chain, encrypted, and Merkle-anchored to Algorand, so
a regulator, an auditor, or anyone else can independently verify it **without trusting the company
that ran the agent**.

## 2. Problem (one sentence)

Regulated companies running AI agents for payments, lending, and claims keep their decision logs in
databases **they themselves control** — self-reporting a regulator cannot independently verify, which
exposes them to failed audits and EU AI Act penalties of up to €15M or 3% of global annual turnover.

## 3. Target customer (specific, not "everyone")

- **Buyer:** the compliance/risk owner — CCO, Head of Risk, or VP of Engineering — at a Series B+
  fintech in digital lending and payments.
- **User:** often a compliance engineer or an auditor.
- **Prioritized by regulation, not geography:** RBI Digital Lending and DPDP are live now; EU AI Act
  Article 12 is effective 2 August 2026. A live mandate means the buyer must act now.

## 4. Why now (the three-regulation wedge)

| Regulation | Status | Who it forces to act |
|---|---|---|
| RBI Digital Lending guidelines | Live | Payment infra providers and lenders under RBI |
| DPDP Act, Section 8(5) | Live | Fintechs handling personal data under DPDP |
| EU AI Act, Article 12 (record-keeping for high-risk AI) | Effective 2 Aug 2026 | Any SaaS with EU exposure |

- Each regulation mandates **auditable records of automated decisions**; none is satisfied by a log
  the deployer can edit.
- Same product against all three — the wedge is whichever mandate already binds the buyer.
- Verifiable audit was optional until a regulator required it; three independent regulations now
  create a hard, dated trigger.

## 5. Customer value proposition (quantified)

- **Weeks → seconds:** audit-evidence prep drops from weeks of manually compiling and attesting logs
  to a per-decision lookup anyone can verify against the chain in seconds.
- **$0.01 per decision vs months of build:** an in-house verifiable pipeline is months of work — and
  still self-hosted, so the records stay self-certified. AgentAudit is one integration at a cent per
  decision.
- **Insures a large downside:** EU AI Act record-keeping breaches run to €15M or 3% of global
  turnover; one avoided finding exceeds the product's lifetime cost.

## 6. Why blockchain, not a database plus an API

- A database the deployer controls can be edited, reordered, or backfilled — so a regulator has to
  **trust the operator**.
- AgentAudit's entire value is removing that trust requirement: a hash anchored on a chain the
  deployer doesn't control is tamper-evident and verifiable by anyone.
- A database + API cannot deliver this no matter how well built — the operator still owns the store.
- **Why Algorand:** sub-cent, fast-final fees + Merkle batching make per-decision anchoring
  economical; the same design on Ethereum mainnet would be economically impossible.

## 7. Demand: regulatory signal plus early validation

- **Regulatory signal:** three live regulations (EU AI Act Article 12, RBI Digital Lending, DPDP
  §8(5)) force regulated AI deployers to produce independently verifiable audit logs — a capability
  no existing observability tool provides.
- **Early validation:** in June 2026, via an introduction routed through a major fintech's CEO
  office, a VP of Product who leads Risk Product at a major regulated fintech confirmed the problem
  is real and growing, most acute in the EU under the EU AI Act, and still evolving.
- **Honest framing:** early validation from one strong discovery conversation — not a fully
  validated market. Broad customer discovery is the open step.
- **Strategy:** the EU is where the problem is most acute and where we expand; the **beachhead is
  India and the Algorand ecosystem** (RBI and DPDP also bind). Next: a deeper technical walkthrough,
  further introductions, and formal discovery with ten compliance leads.

## 8. Competition and positioning

| Category | Examples | What they do | What they miss |
|---|---|---|---|
| AI observability | LangSmith, Langfuse, Arize | Trace and debug agent runs for the operator | Records stay inside the operator's trust boundary; not third-party verifiable |
| AI governance and GRC | Credo AI, Holistic AI | Policy, documentation, and risk workflows | Attestation and process, not cryptographically verifiable per-decision logs |
| In-house audit logs | Postgres, Datadog, S3 | Store whatever the application reports | The deployer can edit them — self-reporting |

- **Core hypothesis:** observability tells you *what happened*; AgentAudit *proves it to a third
  party*. We add independent verifiability, which none of these tools has.

## 9. Total addressable market (with sources)

- **Category:** agentic-AI governance and policy management.
- **Primary source (Mordor Intelligence):** $7.28B in 2025 → $38.94B by 2030, a 39.85% CAGR.
- **Corroboration:** MarketsandMarkets $0.89B (2024) → $5.78B (2029) at 45.3% CAGR; Gartner expects
  AI-governance platforms to surpass $1B by 2030; Forrester forecasts $15.8B AI-governance software
  spend by 2030.
- **TAM:** the category, roughly **$38.9B by 2030**.
- **SAM:** the regulated slice needing verifiable per-decision logs — fintech, insurance, healthcare
  under record-keeping mandates.
- **SOM (3-year):** ~**$6M ARR** as a bottom-up check — ~200 organizations on the SaaS lane at
  $2,500/mo, plus the per-audit long tail.

## 10. Revenue model (three lanes)

The unit of value across all lanes is the **regulated decision audited**, not human seats.

| Lane | Who pays and how | Price | Role |
|---|---|---|---|
| Per-decision via x402 (land) | The agent pays per call in USDC via x402, after a one-time human provision | $0.01 USDC per decision | Adoption lane: no sales cycle, zero-touch billing. Lands the long tail; not the revenue engine. |
| SaaS, platform + usage (revenue engine) | Monthly platform fee bundling a block of decisions + a few seats; overage metered; extra seats add-on | From ~$2,500/mo (decisions + 3–5 seats), overage ~$0.01/decision, extra seat ~$99 (anchor: LangSmith $39) | Recurring revenue. Priced as a compliance line item. |
| Enterprise / self-hosted (target) | Banks, insurers, regulators sign an annual contract via sales | $75K–250K/yr, priced once SOC 2 + ISO 42001 certified (anchor: Credo AI $75K–400K/yr) | High ACV at the top of the funnel; certifications gate this price. |

- The lanes are a **funnel**, not three products: per-decision lands the long tail → some grow into
  SaaS → the regulated few move up to enterprise.
- **x402 is primary by adoption; SaaS and enterprise are primary by revenue** — a compliance buyer
  wants a predictable budget line, not a variable per-call bill.
- Usage (decisions audited) is the value meter; seats are only a dashboard add-on, because the
  product is consumed by agents, not by people at keyboards.

## 11. Unit economics

- **Worked example:** 10,000 audits/day × $0.01 = $100/day ≈ **$3,000/mo** revenue.
- **Cost 1 — per-audit policy check (PolicyContract), the floor:** one app call + an inner mint on
  pass; ~0.001–0.002 ALGO/audit ≈ $0.0004–0.0008 ≈ **4–8% of the $0.01**; scales linearly (real-time
  enforcement); writes no per-audit box.
- **Cost 2 — anchoring (AnchorContract):** one Merkle root per flush, regardless of batch size →
  **flat, a rounding error**.
- **Gross margin:** low-to-mid 90s — not ~100%, because the policy check is a real few-percent floor.
- **Why it works:** the per-audit transaction must be sub-cent, which only Algorand provides; on
  Ethereum, gas would make $0.01 impossible. Batching solves the *separate* anchoring cost, not the
  per-audit floor.

## 12. Go-to-market and the first 100 users

Sales motion — Entry, Land, Expand, Move up, Move out:
1. **Entry:** a single agent integrates via x402 or a free API key, no procurement.
2. **Land:** one regulated agent (e.g., payment approval) goes to production on a seat plan.
3. **Expand:** more agents and decision types (lending, claims, KYC) run on the same audit layer.
4. **Move up:** compliance adopts AgentAudit as the system of record for a review; the account
   converts to enterprise.
5. **Move out:** usage spreads into adjacent regulated verticals within the account.

**First 100 = onboarded organizations** (a team/company sending audits), not raw agents or end-users:
- **~40** from the Algorand and AlgoBharat ecosystem — agent/x402 builders integrating per call with
  zero friction.
- **~30** from regulated-fintech / RegTech communities and direct outreach to digital-lending and
  payments founders and compliance leads already under a live mandate (LinkedIn, founder communities,
  warm intros).
- **~20** from agent-framework communities (LangChain, CrewAI, AutoGPT) — "make your agent auditable
  in two lines."
- **~10** from events and content — the hackathon network, a technical write-up, and a RegTech or
  compliance webinar or two.

Weighted first toward the no-sales-cycle x402 channel and toward segments already under a live
mandate, because those buyers must act now.

## 13. Monthly infrastructure cost, burn, and COGS

- **Burn** = fixed monthly cost regardless of volume (hosting, domain).
- **COGS** = cost that scales with audits (IPFS pinning + the two on-chain costs); COGS sets the margin.

| Item | Monthly cost | Type | Notes |
|---|---|---|---|
| Backend hosting (Railway, Hobby) | $5 | Burn (fixed) | A single service. |
| Frontend hosting (Vercel, Hobby) | $0 | Burn (fixed) | Free tier. |
| Algorand API (algonode / Nodely) | $0 | Burn (fixed) | Free public nodes. |
| Domain | ~$1 | Burn (fixed) | Amortized over the year. |
| IPFS pinning (Pinata) | $0–~$20 | COGS (scales with records) | Free tier at MVP; usage-based as records grow. |
| On-chain policy check (PolicyContract) | ~0.001–0.002 ALGO/audit | COGS (linear) | App call + inner mint on pass; the per-audit floor; near zero at MVP. |
| On-chain anchoring (AnchorContract) | ~$1–2 | COGS (flat, batched) | One Merkle root per flush, kept flat by design. |
| Total (MVP scale) | ~$6–28 | | Plus negligible per-audit policy-check fees at MVP volume. |

- **At MVP/testnet:** total burn under ~$30/mo (per-audit fees negligible at low volume).
- **At production:** dominant COGS is the per-audit policy check — a few percent of the $0.01,
  affordable only because it's sub-cent on Algorand — while anchoring stays flat via batching. The
  two keep the margin in the 90s.
- The agent's LLM cost belongs to the **customer's** agent, not our platform — never on our bill.

## 14. Third-party dependency failure story

- **Groq (demo LLM):** the agent falls back to a built-and-tested deterministic rule, so the demo
  never stalls; in production the model is the customer's agent, not our dependency at all.
- **Pinata (IPFS):** retry-with-backoff for transient errors; IPFS is multi-provider (web3.storage,
  Filebase, self-host), and the encrypted blob + on-chain commitment can be re-pinned anywhere
  without losing verifiability.
- **algonode / Nodely (Algorand API):** multiple free public endpoints, plus self-hostable algod —
  an outage is an endpoint switch with low lock-in.
- **x402 facilitator:** if down, the API-key billing path is unaffected, and the facilitator is
  self-hostable.
- The trust-critical artifact — the **on-chain commitment** — depends on no single off-chain provider.

## 15. Moat and defensibility

- **Trust position:** the record lives outside the deployer's control; a competitor storing logs
  inside the operator's own boundary cannot match that claim by adding a feature.
- **Economics:** the per-audit price depends on sub-cent finality + batching — hard to match without
  the same chain-level cost structure.
- **Standard / network effect:** if regulators and auditors learn to verify AgentAudit receipts,
  being the format they already check is durable.
- **Privacy ladder:** Mode 1 (public on-chain), Mode 2 (private — commitment + auditor-key re-check),
  Mode 3 roadmap (zero-knowledge) — the same product serves public and confidential policies without
  a redesign.

## 16. Roadmap

- **Now:** Modes 1 and 2 live on testnet; multi-tenant; integration via SDK, REST, and x402;
  verifiable end to end.
- **Next:** deepen validation toward ten compliance leads; ship billing-mode enforcement and
  org-scoped dashboard authentication; move to mainnet.
- **Later:** Mode 3 (zero-knowledge) to enforce private policies without trusting our backend;
  expand into healthcare and public-sector verticals; build a regulator-facing verification portal.

## 17. Honest gaps and open items

- Demand is a regulatory signal plus early validation (one strong discovery call), not a fully
  validated market — broad customer interviews are the open step.
- The system is on testnet, not mainnet — economics are demonstrated, not run at production volume.
- Multi-tenant billing enforcement and org-scoped dashboard authentication are designed, not shipped.
- Ground truth is out of scope (the oracle problem): we prove the agent's *reported* decision is
  tamper-proof and policy-checked, not that the report matches physical reality. Future work: trusted
  execution or external attestation.

---

## Sources (TAM)

- Mordor Intelligence, Agentic AI Governance and Policy Management Market: https://www.mordorintelligence.com/industry-reports/agentic-artificial-intelligence-governance-and-policy-management-market
- MarketsandMarkets, AI Governance Market: https://www.marketsandmarkets.com/Market-Reports/ai-governance-market-176187291.html
- Gartner via Nemko, AI Governance Platforms to surpass 1 billion US dollars by 2030: https://digital.nemko.com/news/ai-governance-platforms-market-to-surpass-1-billion-by-2030
- Forrester, AI governance software spend at a 30 percent CAGR to 2030: https://www.forrester.com/blogs/ai-governance-software-spend-will-see-30-cagr-from-2024-to-2030/
- Grand View Research, AI Governance Market: https://www.grandviewresearch.com/industry-analysis/ai-governance-market-report
