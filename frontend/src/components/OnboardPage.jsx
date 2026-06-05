/**
 * OnboardPage — /onboard
 *
 * Self-serve onboarding in one screen, matching the LandingPage design system
 * (#0e0e0e bg · #ff4f00 primary · #26fedc accent · Space Grotesk headlines).
 *
 * Flow: company + plan → agent → policy set (public/private) → Create →
 * shows the issued API key + encryption key (once) and a pre-filled SDK snippet
 * whose `fields` match the policy field names the agent must emit.
 */

import { useState } from "react"
import NavBar from "./NavBar"

const OPERATORS = [
  { code: 1, label: "<" },
  { code: 2, label: "≤" },
  { code: 3, label: ">" },
  { code: 4, label: "≥" },
  { code: 5, label: "==" },
  { code: 6, label: "≠" },
  { code: 7, label: "in" },
  { code: 8, label: "not in" },
]
const SET_OPS = [7, 8]

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text).catch(() => {}); setCopied(true); setTimeout(() => setCopied(false), 1400) }}
      className="text-[10px] font-label text-[#767575] border border-[#2a2a2a] rounded-md px-2 py-0.5
        hover:border-[#ff4f00]/40 hover:text-[#ff4f00] transition-colors cursor-pointer shrink-0"
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  )
}

function buildSnippet({ billing, orgId, agentId, apiKey, apiBase, fields }) {
  const fieldLines = (fields && fields.length ? fields : ["field"])
    .map((f) => `        "${f}": ...`)
    .join(",\n")
  const client = billing === "x402"
    ? `audit = AuditClient(\n    org_id="${orgId}",\n    x402_mnemonic="<payer wallet mnemonic>",  # pays $0.01 USDC per call\n    base_url="${apiBase}",\n)`
    : `audit = AuditClient(api_key="${apiKey}", base_url="${apiBase}")`
  return `from agentaudit import AuditClient

${client}

result = audit.audit(
    agent_id="${agentId}",
    action="your_action",
    decision="approved",
    fields={
${fieldLines}
    },
)`
}

function OnboardPage({ apiBase }) {
  const [orgId, setOrgId]   = useState("")
  const [agentId, setAgentId] = useState("")
  const [billing, setBilling] = useState("api_key")  // "api_key" | "x402"
  const [policies, setPolicies] = useState([
    { field: "amount", operator: 1, value: "5000", private: false },
    { field: "vendor", operator: 7, value: "VENDOR_001, VENDOR_002", private: false },
  ])
  const [status, setStatus] = useState("idle")  // idle | loading | done | error
  const [result, setResult] = useState(null)
  const [error,  setError]  = useState(null)

  const updatePolicy = (i, patch) =>
    setPolicies((ps) => ps.map((p, idx) => (idx === i ? { ...p, ...patch } : p)))
  const addPolicy = () =>
    setPolicies((ps) => [...ps, { field: "", operator: 1, value: "", private: false }])
  const removePolicy = (i) =>
    setPolicies((ps) => ps.filter((_, idx) => idx !== i))

  const submit = async () => {
    if (!orgId.trim() || !agentId.trim()) { setError("Org and agent are required"); setStatus("error"); return }
    setStatus("loading"); setError(null)
    const payload = {
      org_id: orgId.trim(),
      agent_id: agentId.trim(),
      billing_mode: billing,
      policies: policies
        .filter((p) => p.field.trim())
        .map((p) => {
          const isSet = SET_OPS.includes(Number(p.operator))
          return {
            field: p.field.trim(),
            operator: Number(p.operator),
            value_num: isSet ? 0 : (parseInt(p.value, 10) || 0),
            set_values: isSet ? p.value.split(",").map((s) => s.trim()).filter(Boolean) : [],
            private: !!p.private,
          }
        }),
    }
    try {
      const res = await fetch(`${apiBase}/v1/onboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Onboarding failed") }
      setResult(await res.json())
      setStatus("done")
    } catch (e) {
      setError(e.message); setStatus("error")
    }
  }

  return (
    <div className="min-h-screen bg-[#0e0e0e] text-white font-sans">
      <NavBar />
      <div className="max-w-3xl mx-auto px-4 pt-28 pb-20">

        <header className="mb-8">
          <h1 className="headline text-3xl font-bold text-white tracking-tight">
            Onboard your company<span className="text-[#ff4f00]">.</span>
          </h1>
          <p className="mt-2 text-sm text-[#767575] font-label">
            Provision an org, define your agent's policies, and get the SDK code to connect — no sales cycle.
          </p>
        </header>

        {status !== "done" && (
          <div className="flex flex-col gap-6">

            {/* Step 1 — Company + plan */}
            <section className="rounded-2xl border border-[#2a2a2a] bg-[#131313] p-5">
              <span className="text-[11px] font-bold font-label uppercase tracking-widest text-[#adaaaa]">1 · Company &amp; plan</span>
              <div className="mt-3 flex flex-col gap-3">
                <input
                  className="bg-[#0e0e0e] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-white font-body
                    outline-none focus:border-[#ff4f00]/50 transition-colors placeholder:text-[#484847]"
                  placeholder="Company / org id (e.g. acme)"
                  value={orgId} onChange={(e) => setOrgId(e.target.value)}
                />
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: "api_key", title: "Subscription", sub: "API key · $99/seat · $2,500/mo" },
                    { id: "x402", title: "Pay-per-call", sub: "x402 · $0.01 USDC / decision" },
                  ].map((plan) => (
                    <button key={plan.id} onClick={() => setBilling(plan.id)}
                      className={`text-left rounded-xl border p-3 transition-all cursor-pointer
                        ${billing === plan.id
                          ? "border-[#ff4f00]/60 bg-[#ff4f00]/8"
                          : "border-[#2a2a2a] bg-[#0e0e0e] hover:border-[#3a3a3a]"}`}>
                      <div className="flex items-center gap-2">
                        <span className={`material-symbols-outlined text-sm ${billing === plan.id ? "text-[#ff4f00]" : "text-[#767575]"}`}
                          style={{ fontVariationSettings: billing === plan.id ? "'FILL' 1" : "'FILL' 0" }}>
                          {billing === plan.id ? "radio_button_checked" : "radio_button_unchecked"}
                        </span>
                        <span className="text-sm font-semibold text-white font-label">{plan.title}</span>
                      </div>
                      <p className="mt-1 text-[11px] text-[#767575] font-mono">{plan.sub}</p>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            {/* Step 2 — Agent */}
            <section className="rounded-2xl border border-[#2a2a2a] bg-[#131313] p-5">
              <span className="text-[11px] font-bold font-label uppercase tracking-widest text-[#adaaaa]">2 · Agent</span>
              <input
                className="mt-3 w-full bg-[#0e0e0e] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-white font-body
                  outline-none focus:border-[#ff4f00]/50 transition-colors placeholder:text-[#484847]"
                placeholder="Agent id (e.g. payment_agent, claims_agent)"
                value={agentId} onChange={(e) => setAgentId(e.target.value)}
              />
            </section>

            {/* Step 3 — Policies */}
            <section className="rounded-2xl border border-[#2a2a2a] bg-[#131313] p-5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold font-label uppercase tracking-widest text-[#adaaaa]">3 · Policies</span>
                <span className="text-[10px] text-[#484847] font-label">checked against each decision's fields</span>
              </div>
              <div className="mt-3 flex flex-col gap-2.5">
                {policies.map((p, i) => {
                  const isSet = SET_OPS.includes(Number(p.operator))
                  return (
                    <div key={i} className="flex items-center gap-2 flex-wrap">
                      <input
                        className="flex-1 min-w-[110px] bg-[#0e0e0e] border border-[#2a2a2a] rounded-lg px-3 py-2 text-xs text-white font-mono
                          outline-none focus:border-[#ff4f00]/50 placeholder:text-[#484847]"
                        placeholder="field (e.g. amount)"
                        value={p.field} onChange={(e) => updatePolicy(i, { field: e.target.value })}
                      />
                      <select
                        className="bg-[#0e0e0e] border border-[#2a2a2a] rounded-lg px-2 py-2 text-xs text-white font-mono outline-none focus:border-[#ff4f00]/50 cursor-pointer"
                        value={p.operator} onChange={(e) => updatePolicy(i, { operator: Number(e.target.value) })}>
                        {OPERATORS.map((op) => <option key={op.code} value={op.code} className="bg-[#131313]">{op.label}</option>)}
                      </select>
                      <input
                        className="flex-1 min-w-[110px] bg-[#0e0e0e] border border-[#2a2a2a] rounded-lg px-3 py-2 text-xs text-white font-mono
                          outline-none focus:border-[#ff4f00]/50 placeholder:text-[#484847]"
                        placeholder={isSet ? "values, comma-separated" : "number"}
                        value={p.value} onChange={(e) => updatePolicy(i, { value: e.target.value })}
                      />
                      <button onClick={() => updatePolicy(i, { private: !p.private })}
                        title={p.private ? "Private (Mode 2): encrypted off-chain, commitment-only" : "Public (Mode 1): enforced on-chain"}
                        className={`inline-flex items-center gap-1 px-2.5 py-2 rounded-lg text-[10px] font-label border transition-colors cursor-pointer
                          ${p.private
                            ? "border-[#26fedc]/30 text-[#26fedc] bg-[#26fedc]/8"
                            : "border-[#2a2a2a] text-[#767575] hover:text-[#adaaaa]"}`}>
                        <span className="material-symbols-outlined text-[12px]" style={{ fontVariationSettings: p.private ? "'FILL' 1" : "'FILL' 0" }}>
                          {p.private ? "lock" : "lock_open"}
                        </span>
                        {p.private ? "private" : "public"}
                      </button>
                      <button onClick={() => removePolicy(i)}
                        className="text-[#484847] hover:text-[#ff6d8e] transition-colors cursor-pointer">
                        <span className="material-symbols-outlined text-base">close</span>
                      </button>
                    </div>
                  )
                })}
              </div>
              <button onClick={addPolicy}
                className="mt-3 inline-flex items-center gap-1 text-[11px] font-label text-[#ff4f00] hover:text-white transition-colors cursor-pointer">
                <span className="material-symbols-outlined text-sm">add</span> Add policy
              </button>
            </section>

            {error && (
              <p className="text-sm text-[#ff6d8e] font-label">{error}</p>
            )}

            <button onClick={submit} disabled={status === "loading"}
              className="self-start bg-[#ff4f00] text-white rounded-xl px-6 py-3 font-bold text-sm headline
                hover:scale-95 active:opacity-80 transition-all duration-150 cursor-pointer
                disabled:opacity-40 disabled:cursor-not-allowed disabled:scale-100
                shadow-[0_4px_16px_-4px_rgba(255,79,0,0.5)]">
              {status === "loading" ? "Provisioning on-chain…" : "Create & provision"}
            </button>
          </div>
        )}

        {/* Result */}
        {status === "done" && result && (
          <div className="flex flex-col gap-5">
            <div className="flex items-center gap-2 text-[#26fedc] font-label">
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
              <span className="font-semibold">{result.org_id} / {result.agent_id} onboarded · {result.billing_mode === "x402" ? "pay-per-call" : "subscription"}</span>
            </div>

            {/* Credentials */}
            <section className="rounded-2xl border border-[#2a2a2a] bg-[#131313] p-5 flex flex-col gap-3">
              <span className="text-[11px] font-bold font-label uppercase tracking-widest text-[#adaaaa]">Credentials · shown once</span>

              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[#767575] font-label uppercase w-28 shrink-0">API key</span>
                <code className="flex-1 font-mono text-xs text-[#ff4f00] break-all">{result.api_key}</code>
                <CopyButton text={result.api_key} />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[#767575] font-label uppercase w-28 shrink-0">Encryption key</span>
                <code className="flex-1 font-mono text-xs text-[#26fedc] break-all">{result.encryption_key}</code>
                <CopyButton text={result.encryption_key} />
              </div>
              <p className="text-[10px] text-[#484847] leading-relaxed">
                The encryption key is your auditor key — store it safely. In production it's held only by you
                (client-side / self-host); here the processor holds it for the demo.
              </p>
            </section>

            {/* Integration snippet */}
            <section className="rounded-2xl border border-[#2a2a2a] bg-[#131313] p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-bold font-label uppercase tracking-widest text-[#adaaaa]">
                  Connect your agent · {result.billing_mode === "x402" ? "x402" : "API key"}
                </span>
                <CopyButton text={buildSnippet({ billing: result.billing_mode, orgId: result.org_id, agentId: result.agent_id, apiKey: result.api_key, apiBase, fields: result.fields })} />
              </div>
              <pre className="bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg p-4 font-mono text-[11px] text-slate-300 overflow-x-auto whitespace-pre leading-relaxed m-0">
                <code>{buildSnippet({ billing: result.billing_mode, orgId: result.org_id, agentId: result.agent_id, apiKey: result.api_key, apiBase, fields: result.fields })}</code>
              </pre>
              <p className="mt-2 text-[10px] text-[#484847] leading-relaxed">
                Your agent must emit exactly these fields ({(result.fields || []).join(", ") || "—"}) — they're the ones your policies check.
              </p>
            </section>

            <button onClick={() => { setStatus("idle"); setResult(null); setOrgId(""); setAgentId("") }}
              className="self-start text-[11px] font-label text-[#767575] hover:text-[#ff4f00] transition-colors cursor-pointer">
              ← Onboard another
            </button>
          </div>
        )}

      </div>
    </div>
  )
}

export default OnboardPage
