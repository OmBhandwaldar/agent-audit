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
    description: "Drop-in integration for any Python agent. Two lines of code.",
    code: `from agentaudit import audit

result = await audit(
    agent_id="my_payment_agent",
    action="approve_payment",
    decision="approved",
    amount=3000,
    vendor_id="VENDOR_001",
    policy_id="limit_5000"
)
# Returns: action_id, ipfs_cid, algorand_tx_id, policy_result, asa_minted`,
  },
  {
    id: "rest_api",
    title: "REST API",
    lang: "http",
    description: "Language-agnostic. Works with LangChain, AutoGPT, CrewAI, or any custom agent.",
    code: `POST https://api.agentaudit.io/v1/audit
Authorization: Bearer <your_api_key>
Content-Type: application/json

{
  "agent_id": "my_agent",
  "action": "approve_payment",
  "decision": "approved",
  "amount": 3000,
  "vendor_id": "VENDOR_001"
}`,
  },
  {
    id: "decorator",
    title: "Python Decorator",
    lang: "python",
    description: "Zero changes to your existing agent code. Wrap the decision function.",
    code: `from agentaudit import agentaudit

@agentaudit(policy="payment_policy_v1")
async def my_agent_decision(amount: int, vendor_id: str) -> str:
    # Your existing agent logic — completely unchanged
    if amount < 5000:
        return "approved"
    return "rejected"

# AgentAudit captures, hashes, and records every call automatically`,
  },
  {
    id: "response",
    title: "What You Get Back",
    lang: "json",
    description: "Every audit call returns a fully verified, on-chain anchored record.",
    code: `{
  "action_id": "1775657876_7247",
  "decision": "approved",
  "ipfs_cid": "QmSukKcgHJ9KwyMV5PLWqqADrFfX8CfD4QWGE5hRezXzrG",
  "algorand_tx_id": "QCEXKCS4ZD2QXGQIP6HMELQLNOFKIKMNCWIFMXSHEVS7II7Q",
  "policy_result": "amount:pass|vendor:pass",
  "asa_minted": true
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
