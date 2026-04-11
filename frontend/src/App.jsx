import { useState } from "react"
import AuditResult from "./components/AuditResult"
import VerifyAudit from "./components/VerifyAudit"
import Dashboard from "./components/Dashboard"
import SdkIntegration from "./components/SdkIntegration"
import "./index.css"

const API_BASE = "http://localhost:8000"

const AGENT_TYPES = [
  {
    id: "payment_approval",
    label: "Payment Approval",
    field1Label: "Payment Amount (₹)",
    field1Placeholder: "e.g. 3000",
    field2Label: "Vendor ID",
    field2Placeholder: "e.g. VENDOR_001",
    loadingText: "Agent is processing payment...",
    loadingSub: "Uploading to IPFS and recording on Algorand",
  },
  {
    id: "vendor_onboarding",
    label: "Vendor Onboarding",
    field1Label: "Contract Value (₹)",
    field1Placeholder: "e.g. 150000",
    field2Label: "Vendor ID",
    field2Placeholder: "e.g. VENDOR_002",
    loadingText: "Agent is evaluating vendor...",
    loadingSub: "Checking vendor whitelist and recording on Algorand",
  },
  {
    id: "expense_claim",
    label: "Expense Claim",
    field1Label: "Claim Amount (₹)",
    field1Placeholder: "e.g. 2500",
    field2Label: "Employee ID",
    field2Placeholder: "e.g. EMP_001",
    loadingText: "Agent is reviewing expense claim...",
    loadingSub: "Validating claim and recording on Algorand",
  },
]

const TABS = [
  { id: "run", label: "Run Agent" },
  { id: "verify", label: "Verify Audit" },
  { id: "dashboard", label: "Dashboard" },
  { id: "integrate", label: "Integrate" },
]

function App() {
  const [activeTab, setActiveTab] = useState("run")

  // Run Agent tab state
  const [agentType, setAgentType] = useState(AGENT_TYPES[0])
  const [amountInput, setAmountInput] = useState("")
  const [vendorInput, setVendorInput] = useState("")
  const [status, setStatus] = useState("input")  // "input" | "loading" | "result"
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleRunAgent = async () => {
    const amount = parseInt(amountInput, 10)
    if (!amountInput || isNaN(amount) || amount <= 0) {
      setError("Please enter a valid amount greater than 0")
      return
    }
    if (!vendorInput.trim()) {
      setError(`Please enter a ${agentType.field2Label}`)
      return
    }

    setStatus("loading")
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/api/audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount, vendor_id: vendorInput.trim() }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Request failed")
      }

      const data = await response.json()
      setResult(data)
      setStatus("result")
    } catch (err) {
      setError(err.message)
      setStatus("input")
    }
  }

  const handleReset = () => {
    setStatus("input")
    setResult(null)
    setError(null)
    setAmountInput("")
    setVendorInput("")
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && status === "input") handleRunAgent()
  }

  const handleTabSwitch = (tab) => {
    setActiveTab(tab)
    if (tab === "run") {
      handleReset()
      setAgentType(AGENT_TYPES[0])
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-10 bg-[#0f1117] text-slate-200 font-sans">

      <header className="text-center mb-8">
        <h1 className="text-3xl font-bold text-violet-400 tracking-tight">AgentAudit</h1>
        <p className="mt-2 text-sm text-slate-500">Verifiable audit infrastructure for autonomous AI agents</p>
      </header>

      {/* Tab bar */}
      <div className="flex gap-1 bg-[#1e2130] border border-[#2d3248] rounded-xl p-1 mb-6 w-full max-w-2xl">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => handleTabSwitch(tab.id)}
            className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-colors cursor-pointer
              ${activeTab === tab.id
                ? "bg-[#2d3248] text-violet-400"
                : "text-slate-500 hover:text-slate-200"
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <main className="w-full max-w-2xl flex-1">

        {/* Run Agent tab */}
        {activeTab === "run" && (
          <>
            {status === "input" && (
              <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-8 flex flex-col gap-4">

                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Agent Type</label>
                <select
                  className="bg-[#0f1117] border border-[#2d3248] rounded-lg px-4 py-3 text-slate-200 w-full outline-none focus:border-violet-400 transition-colors"
                  value={agentType.id}
                  onChange={(e) => {
                    setAgentType(AGENT_TYPES.find(t => t.id === e.target.value))
                    setAmountInput("")
                    setVendorInput("")
                    setError(null)
                  }}
                >
                  {AGENT_TYPES.map(t => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>

                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{agentType.field1Label}</label>
                <input
                  className="bg-[#0f1117] border border-[#2d3248] rounded-lg px-4 py-3 text-slate-200 w-full outline-none focus:border-violet-400 transition-colors [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none placeholder:text-slate-600"
                  type="number"
                  placeholder={agentType.field1Placeholder}
                  value={amountInput}
                  onChange={(e) => setAmountInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  min="1"
                  autoFocus
                />

                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{agentType.field2Label}</label>
                <input
                  className="bg-[#0f1117] border border-[#2d3248] rounded-lg px-4 py-3 text-slate-200 w-full outline-none focus:border-violet-400 transition-colors placeholder:text-slate-600"
                  type="text"
                  placeholder={agentType.field2Placeholder}
                  value={vendorInput}
                  onChange={(e) => setVendorInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                />

                {error && <p className="text-sm text-red-400">{error}</p>}

                <button
                  className="bg-violet-400 text-[#0f1117] rounded-lg py-3.5 font-bold text-base hover:bg-violet-300 transition-colors cursor-pointer"
                  onClick={handleRunAgent}
                >
                  Run Agent
                </button>
              </div>
            )}

            {status === "loading" && (
              <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-12 flex flex-col items-center gap-4">
                <div className="w-10 h-10 border-4 border-[#2d3248] border-t-violet-400 rounded-full animate-spin" />
                <p className="text-base font-semibold text-slate-200">{agentType.loadingText}</p>
                <p className="text-sm text-slate-500 text-center">{agentType.loadingSub}</p>
              </div>
            )}

            {status === "result" && result && (
              <AuditResult result={result} onReset={handleReset} agentType={agentType} />
            )}
          </>
        )}

        {activeTab === "verify" && <VerifyAudit apiBase={API_BASE} />}
        {activeTab === "dashboard" && <Dashboard apiBase={API_BASE} />}
        {activeTab === "integrate" && <SdkIntegration />}

      </main>

      <footer className="mt-12 text-xs text-slate-700 text-center">
        AgentAudit · AlgoBharat Hack Series 3.0 · Algorand Testnet
      </footer>

    </div>
  )
}

export default App
