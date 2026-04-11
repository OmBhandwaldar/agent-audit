import { useState } from "react"
import AuditResult from "./components/AuditResult"
import VerifyAudit from "./components/VerifyAudit"
import Dashboard from "./components/Dashboard"
import "./App.css"

const API_BASE = "http://localhost:8000"

function App() {
  const [activeTab, setActiveTab] = useState("run")  // "run" | "verify" | "dashboard"

  // Run Agent tab state
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
      setError("Please enter a vendor ID")
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
    if (tab === "run") handleReset()
  }

  return (
    <div className="app">

      <header className="header">
        <h1>AgentAudit</h1>
        <p className="subtitle">Verifiable audit infrastructure for autonomous AI agents</p>
      </header>

      {/* Tab toggle */}
      <div className="tab-bar">
        <button
          className={`tab-btn ${activeTab === "run" ? "active" : ""}`}
          onClick={() => handleTabSwitch("run")}
        >
          Run Agent
        </button>
        <button
          className={`tab-btn ${activeTab === "verify" ? "active" : ""}`}
          onClick={() => handleTabSwitch("verify")}
        >
          Verify Audit
        </button>
        <button
          className={`tab-btn ${activeTab === "dashboard" ? "active" : ""}`}
          onClick={() => handleTabSwitch("dashboard")}
        >
          Dashboard
        </button>
      </div>

      <main className="main">

        {/* Run Agent tab */}
        {activeTab === "run" && (
          <>
            {status === "input" && (
              <div className="input-card">
                <label className="input-label">Payment Amount (₹)</label>
                <input
                  className="input-field"
                  type="number"
                  placeholder="e.g. 3000"
                  value={amountInput}
                  onChange={(e) => setAmountInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  min="1"
                  autoFocus
                />
                <label className="input-label" style={{ marginTop: "12px" }}>Vendor ID</label>
                <input
                  className="input-field"
                  type="text"
                  placeholder="e.g. VENDOR_001"
                  value={vendorInput}
                  onChange={(e) => setVendorInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
                {error && <p className="error-msg">{error}</p>}
                <button className="btn-run" onClick={handleRunAgent}>
                  Run Agent
                </button>
              </div>
            )}

            {status === "loading" && (
              <div className="loading-card">
                <div className="spinner" />
                <p className="loading-text">Agent is processing...</p>
                <p className="loading-sub">Uploading to IPFS and recording on Algorand</p>
              </div>
            )}

            {status === "result" && result && (
              <AuditResult result={result} onReset={handleReset} />
            )}
          </>
        )}

        {/* Verify Audit tab */}
        {activeTab === "verify" && (
          <VerifyAudit apiBase={API_BASE} />
        )}

        {/* Dashboard tab */}
        {activeTab === "dashboard" && (
          <Dashboard apiBase={API_BASE} />
        )}

      </main>

      <footer className="footer">
        <span>AgentAudit · AlgoBharat Hack Series 3.0 · Algorand Testnet</span>
      </footer>

    </div>
  )
}

export default App
