# FINAL_PHASE_PLAN.md — Execution plan

Decisions & rationale: see [FINAL_PHASE.md](FINAL_PHASE.md). **This file is the *how*; that file is the *what/why*.**
Each step cites the FINAL_PHASE section it implements. Build start to end, in order.

---

## Ground rules (read once)

- All work on branch **`feat/multi-tenant-platform`** (FINAL_PHASE §0). `main` stays demo-ready.
- **Protected — ask before changing.** These *can* be changed if there's a real need, but because
  changing them risks breaking already-anchored records / existing proofs, **stop and ask for explicit
  approval, discuss the trade-off, and decide together before touching any of them:**
  - `AnchorContract` — currently left as-is so old batches stay verifiable. Only `PolicyContract`
    is rewritten in this plan.
  - `leaf_hash()` canonicalization in `batcher/merkle.py`.
  - `reasoning_trace` field name in records.
  - The global `PAYLOAD_ENCRYPTION_KEY` — currently kept as the **legacy/default tenant key** so old
    records still decrypt; new orgs get their own keys (FINAL_PHASE §E).
  Default assumption is "leave them alone," but they are not permanently frozen — flag the need and we decide.
- After each phase, re-run the existing Phase 2 flow as a regression check before moving on.
- Commit per piece; scoped messages (`feat: multi-tenant policy boxes`, etc.).

---

## Phase 0 — Branch + cleanup (FINAL_PHASE §M)

Goal: clean foundation before building. All pure-upside, low risk.

- [ ] Create branch: `git checkout -b feat/multi-tenant-platform`.
- [ ] Tag current main as a rollback point: `git tag v3-roundthree-demo`.
- [ ] **M.1** — delete the `/api/verify/v2` endpoint in `api/main.py` (leaks plaintext with no key).
- [ ] **M.2** — delete dead Phase 1 files: `contracts/audit_contract.py`, `algorand/contract_client.py`,
      `sdk/audit_flow.py`, `scripts/runFlow.py`, `scripts/seed_vendors.py`; and the `/api/tamper-demo`
      endpoint in `api/main.py`. Grep for imports of each first; fix any stale references.
- [ ] **M.3** — rewrite `get_anchor_root` in `algorand/contract_client_v2.py` to read the box state
      directly via algod (`application_box_by_name` / box read), no signed transaction, no fee.
      Decode the `AnchorRecord` struct off the raw box bytes.
- [ ] **M.5** — add a one-line pointer at the top of `CLAUDE.md` directing readers to `FINAL_PHASE.md`
      and `DECISIONS.md` as current truth. (M.4 is deferred to Phase 4, after the SDK exists.)
- **Done when:** dead code gone, `get_anchor_root` does a free read, existing `/api/verify` + chat/audit
  flow still works end-to-end (regression check).

---

## Phase 1 — Multi-tenant PolicyContract (FINAL_PHASE §B, §C, §D)

Goal: one shared contract that stores per-org/per-agent policies as data and enforces them.
Biggest, riskiest phase — do it first while fresh.

- [ ] **Design the predicate rule** (FINAL_PHASE §B — generic predicate engine, not a fixed enum).
      Define a `PolicyRule` ARC4 struct as a predicate `{field, operator, value}`:
  - `field: arc4.String` (any field the agent emits, e.g. "amount", "vendor", "rate", "exposure")
  - `operator: UInt64` (1=`<` 2=`<=` 3=`>` 4=`>=` 5=`==` 6=`!=` 7=`in` 8=`not_in`)
  - `value_num: UInt64`, `value_str: arc4.String` (the comparison operand; `in`/`not_in` use a
    namespaced set, see box layout)
  - `mode: UInt64` (1 = public/on-chain, 2 = sensitive/commitment) (FINAL_PHASE §C)
  - Orgs compose N predicates per agent over **any** field -> custom policies ("add a new item to the
    menu") as data, no new code. Standard policies (amount limit, whitelist, rate cap, allowed action)
    are just common predicates; agent-type selection pre-fills defaults the org edits.
  - **On-chain (Mode 1)** evaluates a **flat list of predicates AND-ed together** (incl. `in`/`not_in`
    via boxes). Richer/nested expressions (OR, groups, ranges) are enforced via **Mode 2 off-chain**.
- [ ] **Box layout** in the rewritten `contracts/policy_contract.py`:
  - `tenant_rules` BoxMap: key `sha256(org_id + agent_id + index)` -> `PolicyRule`. For Mode-2 rules the
    box stores the **commitment** (`sha256(policy_doc)`) instead of the plaintext predicate (FINAL_PHASE §C, §D).
  - `sets` BoxMap (generalizes the old vendor whitelist): for `in`/`not_in` predicates, membership is a box
    `sha256(org_id + agent_id + field + value)` -> `arc4.Bool`. (A vendor whitelist is just `field="vendor"`.)
  - `rule_count` per `(org, agent)` so `check_and_mint` knows how many predicates to read.
  - global state: `compliance_asa_id`, `authorized_minter` address (FINAL_PHASE §D).
- [ ] **Methods:**
  - `initialize(compliance_asa_id, authorized_minter)` — create-only.
  - `opt_in_asa()` — creator only (unchanged).
  - `register_rule(org_id, agent_id, index, rule)` — authorized only; writes a tenant predicate box.
  - `add_to_set(org_id, agent_id, field, value)` / `remove_from_set(...)` — authorized only; namespaced
    set membership for `in`/`not_in` predicates (a vendor whitelist is `field="vendor"`).
  - `check_and_mint(org_id, agent_id, action_id, ipfs_hash, fields..., attested_results, commitments)`:
    - loop the `(org, agent)` predicates; for **Mode 1** evaluate the predicate on-chain against `fields`
      (apply `operator` to the field value vs the rule's operand; `in`/`not_in` via the set box);
      for **Mode 2** accept the backend's `attested_results` + verify the `commitment` matches the
      stored box (FINAL_PHASE §C, §D).
    - mint 1 AACR iff (all Mode-1 pass on-chain) AND (all Mode-2 asserted pass); **gate the attested path
      with `assert Txn.sender == authorized_minter`** (FINAL_PHASE §D).
    - return the provenance result string, e.g. `amount:pass(onchain)|kyc:pass(attested)`.
- [ ] Compile (`scripts/compile.sh` / algokit), deploy to testnet -> new `POLICY_APP_ID`.
- [ ] Post-deploy: `opt_in_asa()`, send AACR supply to the new contract (`scripts/send_aacr_to_policy.py`),
      set `authorized_minter` to the backend wallet. (AnchorContract + ASA unchanged — no re-deploy there.)
- [ ] Update `algorand/contract_client_v2.py`: new `check_and_mint` signature, namespaced box keys
      (`_compute_box_key` with `org_id+agent_id+index` / `org_id+agent_id+field+value`), `register_rule`,
      `add_to_set`/`remove_from_set`. Reuse the ARC4 length-prefix encoding (`_encode_string`).
- **Done when:** can register two orgs with different predicate sets (incl. a **custom predicate over a
  non-standard field**); `check_and_mint` for org A enforces A's predicates only; org B's higher limit /
  different sets do not leak into A; AACR mints correctly per org.

---

## Phase 2 — Tenant store + provisioning (FINAL_PHASE §G)

Goal: the one-time human provisioning act — create org, agent, policies, key.

- [ ] Add a `tenants` store (extend the SQLite `batcher.db` or a new `data/tenants.db`):
  - `tenants(org_id PK, api_key_hash, enc_key_ref, key_version, billing_mode, created_at)`
  - `agents(org_id, agent_id, created_at)`
  - `agent_rules(org_id, agent_id, index, rule_type, field, param_num, param_str, mode, commitment, doc_ref)`
- [ ] **Per-org key** (FINAL_PHASE §E): generate a 32-byte key per org (reuse `crypto.payload.generate_key`),
      versioned; store a reference (for this round: encrypted-at-rest in the tenant DB or wrapped; document
      that a real KMS is the production upgrade). The legacy global key = the "default" tenant's key.
- [ ] Provisioning functions: `create_org()`, `register_agent()`, `register_policy()`
      (writes the on-chain rule box via Phase 1 client; for Mode 2, encrypts the policy doc under the org
      key, stores ciphertext off-chain, writes the commitment on-chain), `issue_api_key()` (store hash, return once).
- [ ] `scripts/onboard_org.py` — CLI that runs the full provisioning for an org+agent+policies.
      (Self-serve dashboard UI is future scope; CLI is the honest interim — note this in the demo.)
- **Done when:** running `onboard_org.py` creates the tenant rows AND the on-chain policy/vendor boxes,
  and prints the api_key + encryption key once.

---

## Phase 3 — Ingest endpoint + auth (FINAL_PHASE §H)

Goal: the real product endpoint an external agent calls.

- [ ] `POST /v1/audit` in `api/main.py` accepting `{agent_id, action, decision, fields, reasoning_trace}`.
- [ ] Bearer API-key auth dependency: hash the presented key, look up the org, load its enc_key + rules.
      Reject unknown keys with 401.
- [ ] Pipeline (reuse `_execute_v2_pipeline`, generalized): build record -> encrypt under the **org key**
      (pass `key=` to `encrypt_payload`; it already supports an explicit key) -> IPFS -> call multi-tenant
      `check_and_mint(org_id, agent_id, ...)` -> add leaf to batch store **with `org_id`**.
- [ ] Add `org_id` to the `leaves` table + `get_leaf` so verify/dashboard can scope per org.
- [ ] Keep `/api/audit` and `/api/chat` as the demo endpoints that run AgentAudit's own internal agent
      (they coexist with `/v1/audit`).
- **Done when:** an external `curl`/script with a valid API key submits a decision -> recorded under the
  right org, encrypted under the org key, policy enforced; bad/missing key -> 401.

---

## Phase 4 — Real SDK + decorator + example agent (FINAL_PHASE §H, §M.4)

Goal: make the "2 lines of code" real, not mocked.

- [ ] Create the `agentaudit` client package (a real importable module, e.g. `agentaudit/__init__.py`):
  - `AuditClient(api_key, base_url).submit(agent_id, action, decision, fields, reasoning_trace)` -> result.
  - `@capture(agent_id, ...)` decorator wrapping a decision function: captures args, return, and trace,
    then calls `submit`.
- [ ] `examples/insurance_agent.py` — a standalone non-payment agent (claims approval) that imports the
      SDK and logs a decision. Proves the boundary: their agent, our audit layer (FINAL_PHASE §L generality).
- [ ] **M.4** — rewire `frontend/src/components/SdkIntegration.jsx` to the real package + real endpoint;
      mark anything not yet shipped as roadmap instead of presenting it as working.
- **Done when:** the example agent logs a decision through the SDK and it appears in dashboard + verify;
  the SDK tab reflects reality.

---

## Phase 5 — x402 pay-per-call, Flavor 1 (FINAL_PHASE §G, §I)

Goal: provisioned agent pays $0.01 USDC per audit. Highest-risk phase — flag + backup.

- [ ] Use the bundled skills (`create-python-x402-server`, `create-python-x402-client`).
- [ ] Add x402 protection to `/v1/audit` (or a parallel `/v1/audit` mode): respond `402` with terms
      (amount, USDC testnet ASA, recipient), verify payment, then run the audit. The x402 request still
      declares `org_id`, so the org's key + policies apply (Flavor 1, FINAL_PHASE §G).
- [ ] Testnet USDC + facilitator/wrap setup; recipient = the AgentAudit wallet.
- [x] x402 pay-per-call is folded into the SDK (`AuditClient`), not a separate payer: any working
      agent constructs `AuditClient(org_id=..., x402_mnemonic=...)` and pays $0.01 USDC per decision.
      `examples/insurance_agent.py` runs in subscription OR x402 mode (same agent, billing is config).
      Verified live: the insurance agent paid per claim (payer USDC dropped 3x$0.01).
- [ ] Put x402 **behind a flag** so the API-key path stays the safe default.
- [ ] **Record a backup demo video of the x402 flow** in case live payment is flaky.
- **Done when:** an agent with no API key (but a known org) hits `/v1/audit`, auto-pays USDC, and the audit
  runs; backup recording exists. If unstable near the event, demote to roadmap.

---

## Phase 6 — Mode 2: private policy + attested mint (FINAL_PHASE §C, §D, §F)

Goal: sensitive policies committed (not revealed) on-chain, enforced off-chain, auditor-verifiable.

- [ ] Per-policy `mode` already in the rule (Phase 1). At registration (Phase 2), a Mode-2 policy:
      encrypt the policy doc under the org key -> store ciphertext off-chain -> write `sha256(policy_doc)`
      commitment in the rule box.
- [ ] At decision time, the backend reads the plaintext policy (it holds/decrypts via the org key, as the
      trusted processor — FINAL_PHASE §F), evaluates Mode-2 rules off-chain, and calls `check_and_mint`
      with `attested_results` + `commitments`. The contract verifies the commitment matches the stored box
      and mints under the authorized-minter gate (FINAL_PHASE §D).
- [ ] Record marks `enforcement = "off-chain-attested"` + the commitment per Mode-2 rule.
- [ ] Extend `/api/verify`: when the auditor key is supplied, for each Mode-2 rule decrypt the policy doc,
      confirm it hashes to the on-chain commitment, and re-run the check -> report whether the attested
      result was legitimate (in addition to the existing Merkle proof + record decryption).
- **Done when:** a sensitive policy shows only a commitment on-chain/IPFS; the auditor key re-verifies that
  the recorded enforcement was correct; mixed-mode agents (some Mode 1, some Mode 2) mint correctly.

### Phase 6 — STATUS: DONE, verified on testnet

Mode 2 now covers **both** policy shapes, each keeping its secret entirely off-chain (only a
`sha256` commitment on-chain), enforced off-chain with an attested mint, and re-verifiable with
the org auditor key (commitment match + re-run):

- **Private threshold** — a secret number, e.g. `risk_tier <= 3` (`register_sensitive_policy`).
- **Private set / whitelist** — a confidential list, e.g. approved hospitals
  (`register_sensitive_set_policy`). Members are never on-chain, not even as hashed box keys.

Unified off-chain evaluator `_eval_doc` (numeric + set) backs both enforcement and the
`/api/verify` `mode2_reverify` section. Verified e2e on testnet (in/out cases) plus edge branches
(out-of-set fail, wrong key cannot decrypt → no valid re-check). Onboarding presets:
`lending_private` (private threshold), `insurance_private` (private whitelist).

The only still-deferred policy capability is **non-AND combination logic** (OR / "any N of M"),
unchanged from the out-of-scope note below.

---

## Phase 7 — Tests (FINAL_PHASE §L step 5)

Goal: cover the parts that must be correct.

- [ ] `tests/test_payload.py` — encrypt/decrypt roundtrip, wrong key fails, tampered ciphertext fails (GCM).
- [ ] `tests/test_merkle.py` — root, proof, verify, tamper -> proof fails, order-independence.
- [ ] `tests/test_store.py` — add/flush/mark_anchored/get_leaf, per-org scoping.
- [ ] `tests/test_policy_engine.py` — each rule type evaluates correctly; mixed rules; **org isolation**
      (org A's rules never apply to org B); commitment match/mismatch for Mode 2.
- [ ] `pytest-asyncio` for any async paths. Add a `pytest` run note to the README.
- **Done when:** `pytest` is green with meaningful coverage of crypto + merkle + policy engine.

---

## Phase 8 — Demo agents + frontend (FINAL_PHASE §L generality)

Goal: show two industries side by side to prove the platform claim.

- [ ] Second demo agent already exists from Phase 4 (insurance). Optionally add a third (lending) if cheap.
- [ ] Frontend: a minimal onboarding view (or just demo the CLI), an agent picker, and verify-modal updates
      to show per-policy provenance (onchain vs attested) and Mode-2 commitment re-verification.
- [ ] Pre-seed a few audits per agent so the dashboard is populated for the demo.
- **Done when:** procurement + insurance agents both run end-to-end through the same platform, on stage.

---

## Phase 9 — Business case, slides, rehearsal (FINAL_PHASE §I, §J, §K)

Goal: cover the 40%-weight Business table and the Scalability table; be demo-ready.

- [ ] Write `GTM.md` (currently missing): 1-line problem statement, TAM with a cited source,
      first-100-users plan (named channels), monthly infra cost, third-party dependency failure story
      (Groq -> fallback; Pinata / algonode -> mitigation), and the honest "demand signal, not validation" framing.
- [ ] 5-slide deck on their template (branding untouched): one slide each for Technical / Business /
      Scalability, drawing from FINAL_PHASE §I/§J/§K and the three-regulation wedge.
- [ ] Rehearse the 3-min pitch per table; repo + demo open and ready; backup recordings prepared.
- **Done when:** deck done, GTM.md done, demo rehearsed 10+ times, backups recorded.

---

## Phase 10 — Mode 3 (future scope, FINAL_PHASE §C)

- [ ] **Not built this round.** Keep the talking points: AVM BN254 pairing opcodes -> on-chain Groth16;
      Poseidon commitment (not SHA256) for circuit-friendliness; prover separate from the agent;
      opcode-budget pooling; the oracle boundary. One roadmap slide only.

---

## Phase 11 — UX / UI overhaul (post-build)

**Source: feedback from an AlgoBharat member that the UX needs to be better.**

- [ ] Improve the UX and **redesign the UI** once the platform is functionally complete (Phases 0–10).
- [ ] Tighten the core flows so they read clearly to a non-technical judge: onboard -> agent connects ->
      audit -> verify; the chat agent; the verify modal (proof + decryption + per-policy provenance).
- **Done when:** the UI is visibly cleaner and the end-to-end demo is easy to follow live.

---

## Out of scope this build (intentional — not omissions)

These are decided in FINAL_PHASE but deliberately **not built this round**; they are referenced so the
plan is honestly complete, not silently missing them:

- **Enterprise tier delivery** (FINAL_PHASE §J, §K): dedicated contract instance, self-hosted deployment,
  client-side encryption, ISO 42001, and **bespoke policy logic that is not expressible as predicates**
  (arbitrary computation / custom evaluator code). We build the shared tier; enterprise is a
  deployment/packaging exercise on the same code, done per-customer later.
  Note: **custom predicate policies over any field are in scope this round, all tiers** (FINAL_PHASE §B refined) —
  only non-predicate logic is deferred here.
- **Mode 3 (ZK)** — Phase 10, future scope.
- **Fully-trustless on-chain identity** (bind `org_id` to a wallet address, contract checks `Txn.sender`) —
  FINAL_PHASE §H future refinement. This round resolves org from the API key off-chain.
- **Self-serve onboarding dashboard UI** — Phase 2 ships a provisioning CLI (`onboard_org.py`); the web
  signup flow is future.
- **Policy combination logic beyond AND** — this round all selected predicates are AND-ed (all must pass).
  OR / "any N of M" / nested boolean groups are future scope (Mode 2 off-chain first, then on-chain later).

## Env var additions (.env / .env.example)

- `POLICY_APP_ID` — updated after the Phase 1 redeploy.
- `AUTHORIZED_MINTER` — backend wallet address allowed to trigger attested mints.
- `TENANTS_DB_PATH` — tenant/agent/rules store (or reuse the batcher DB).
- x402: `USDC_ASSET_ID` (testnet), `X402_RECIPIENT`, facilitator config, `X402_ENABLED` flag.
- Keep `PAYLOAD_ENCRYPTION_KEY` (legacy/default tenant key) and `ANCHOR_APP_ID`, `COMPLIANCE_ASA_ID` unchanged.

## Milestones / merge points to `main`

1. After Phase 0–1: multi-tenant contract deployed + verified (regression: old flow still works).
2. After Phase 3: external agent can audit via `/v1/audit` with an API key.
3. After Phase 4: SDK real, example agent working.
4. After Phase 6: Mode 2 + attested mint working and auditor-verifiable.
5. Before the event: Phases 7–9 done, demo rehearsed.

## Rollback

If the new flow is unstable near the event: `git checkout main` (tag `v3-roundthree-demo`) and demo the
Round 3 system; pitch the platform (multi-tenant, x402, Mode 2) as the roadmap with this plan as evidence.

---

*Last updated: start of Round 4 / final-phase planning.*
