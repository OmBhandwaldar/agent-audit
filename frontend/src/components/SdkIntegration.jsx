/**
 * SdkIntegration — Tab 4. Static integration guide.
 *
 * Shows how any AI agent can plug into AgentAudit with 2 lines of code.
 * No API calls, no loading states. Pure presentation.
 */

import { useState } from "react"

const CODE_SECTIONS = [
  {
    id: "python_sdk",
    title: "Python SDK",
    lang: "python",
    description: "Drop-in for any Python agent. Submit a decision under your org's API key.",
    code: `from agentaudit import AuditClient

audit = AuditClient(api_key="aa_live_...", base_url="https://your-agentaudit-host")

result = audit.audit(
    agent_id="claims_agent",
    action="approve_claim",
    decision="approved",
    fields={"claim_amount": 150000, "hospital": "HOSP_001"},
    reasoning_trace=trace,
)
# result: action_id, decision (on-chain), asa_minted, policy_result, ipfs_cid, algorand_tx_id`,
  },
  {
    id: "rest_api",
    title: "REST API",
    lang: "http",
    description: "Language-agnostic. Any stack POSTs to /v1/audit with its API key.",
    code: `POST https://your-agentaudit-host/v1/audit
Authorization: Bearer <your_api_key>
Content-Type: application/json

{
  "agent_id": "claims_agent",
  "action": "approve_claim",
  "decision": "approved",
  "fields": { "claim_amount": 150000, "hospital": "HOSP_001" },
  "reasoning_trace": []
}`,
  },
  {
    id: "decorator",
    title: "Python Decorator",
    lang: "python",
    description: "Zero changes to your decision logic — wrap the function and it's audited.",
    code: `from agentaudit import AuditClient
audit = AuditClient(api_key="aa_live_...")

@audit.capture(agent_id="claims_agent", action="approve_claim")
def decide(claim_amount, hospital):
    # your existing agent logic — unchanged
    decision = "approved" if claim_amount < 200000 else "rejected"
    return {"decision": decision,
            "fields": {"claim_amount": claim_amount, "hospital": hospital}}

# every call is policy-checked on-chain, encrypted, and anchored automatically`,
  },
  {
    id: "response",
    title: "What You Get Back",
    lang: "json",
    description: "The on-chain decision is authoritative — it can override the agent's own.",
    code: `{
  "action_id": "1780562533_3364",
  "decision": "approved",
  "asa_minted": true,
  "policy_result": "pass:onchain|pass:onchain",
  "ipfs_cid": "QmUrXohg1AXQxacEMJ4LTvxvVCi6U4zAWQ7NtmMUfHom6Q",
  "algorand_tx_id": "GO4XEN3Z2WGS34AFC5RS7S4F2YHMMA5I22GEQNQHBR4D3R72FVRA"
}`,
  },
]

const WHY_POINTS = [
  {
    icon: "🔒",
    title: "Tamper-proof",
    body: "On-chain SHA256 hash. Nobody — including you — can alter the record after it's written.",
  },
  {
    icon: "🔍",
    title: "Independently verifiable",
    body: "Any auditor or regulator can verify any decision by Action ID without trusting the deploying org.",
  },
  {
    icon: "⚡",
    title: "Drop-in",
    body: "2 lines of code. Your agent doesn't change. AgentAudit sits between the decision and the world.",
  },
  {
    icon: "📋",
    title: "Compliance-ready",
    body: "CSV export, per-policy breakdown, and ASA compliance receipt for regulatory submissions.",
  },
]

function CodeBlock({ code }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="relative">
      <button
        className="absolute top-2 right-2 bg-[#2d3248] text-slate-400 text-xs px-2.5 py-1 rounded hover:bg-[#3d4460] hover:text-slate-200 transition-colors cursor-pointer"
        onClick={handleCopy}
      >
        {copied ? "Copied!" : "Copy"}
      </button>
      <pre className="bg-[#0f1117] border border-[#2d3248] rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto whitespace-pre leading-relaxed m-0">
        <code>{code}</code>
      </pre>
    </div>
  )
}

function SdkIntegration() {
  return (
    <div className="flex flex-col gap-4">

      <div className="text-center py-2">
        <h2 className="text-xl font-bold text-slate-200">Integrate AgentAudit</h2>
        <p className="mt-2 text-sm text-slate-500 leading-relaxed">
          Any AI agent can plug into AgentAudit. The agent doesn't change —
          AgentAudit wraps around every decision and makes it tamper-proof.
        </p>
      </div>

      {/* Code sections */}
      {CODE_SECTIONS.map((section) => (
        <div key={section.id} className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-5 flex flex-col gap-3">
          <div className="flex justify-between items-center">
            <span className="text-sm font-bold text-violet-400">{section.title}</span>
            <span className="text-xs text-slate-500 bg-[#0f1117] border border-[#2d3248] rounded px-2 py-0.5 font-mono uppercase">
              {section.lang}
            </span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">{section.description}</p>
          <CodeBlock code={section.code} />
        </div>
      ))}

      {/* Why AgentAudit */}
      <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-5">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Why AgentAudit?</h3>
        <div className="grid grid-cols-2 gap-3">
          {WHY_POINTS.map((point) => (
            <div key={point.title} className="bg-[#161926] border border-[#2d3248] rounded-lg p-3 flex flex-col gap-1.5">
              <span className="text-xl">{point.icon}</span>
              <span className="text-sm font-bold text-slate-200">{point.title}</span>
              <p className="text-xs text-slate-500 leading-relaxed">{point.body}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}

export default SdkIntegration
