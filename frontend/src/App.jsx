import { useState } from "react"
import AuditResult from "./components/AuditResult"
import "./App.css"

const API_BASE = "http://localhost:8000"

function App() {
  const [amountInput, setAmountInput] = useState("")
  const [status, setStatus] = useState("input")   // "input" | "loading" | "result"
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleRunAgent = async () => {
    const amount = parseInt(amountInput, 10)
    if (!amountInput || isNaN(amount) || amount <= 0) {
      setError("Please enter a valid amount greater than 0")
      return
    }

    setStatus("loading")
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/api/audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount }),
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
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && status === "input") handleRunAgent()
  }

  return (
    <div className="app">

      <header className="header">
        <h1>AgentAudit</h1>
        <p className="subtitle">Verifiable audit infrastructure for autonomous AI agents</p>
      </header>

      <main className="main">

        {/* Input state */}
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
            {error && <p className="error-msg">{error}</p>}
            <button className="btn-run" onClick={handleRunAgent}>
              Run Agent
            </button>
          </div>
        )}

        {/* Loading state */}
        {status === "loading" && (
          <div className="loading-card">
            <div className="spinner" />
            <p className="loading-text">Agent is processing...</p>
            <p className="loading-sub">Uploading to IPFS and recording on Algorand</p>
          </div>
        )}

        {/* Result state */}
        {status === "result" && result && (
          <AuditResult result={result} onReset={handleReset} />
        )}

      </main>

      <footer className="footer">
        <span>AgentAudit · AlgoBharat Hack Series 3.0 · Algorand Testnet</span>
      </footer>

    </div>
  )
}

export default App
