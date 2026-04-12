import { useState } from "react"
import ChatAgent from "./components/ChatAgent"
import VerifyAudit from "./components/VerifyAudit"
import Dashboard from "./components/Dashboard"
import SdkIntegration from "./components/SdkIntegration"
import "./index.css"

const API_BASE = "http://localhost:8000"

const TABS = [
  { id: "run", label: "Run Agent" },
  { id: "verify", label: "Verify Audit" },
  { id: "dashboard", label: "Dashboard" },
  { id: "integrate", label: "Integrate" },
]

function App() {
  const [activeTab, setActiveTab] = useState("run")

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
            onClick={() => setActiveTab(tab.id)}
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
        {activeTab === "run"       && <ChatAgent apiBase={API_BASE} />}
        {activeTab === "verify"    && <VerifyAudit apiBase={API_BASE} />}
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
