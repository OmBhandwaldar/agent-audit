/**
 * VerifyAudit — Tab 2. Independent audit record verification.
 *
 * Fetches the on-chain record by action ID, fetches the original IPFS data,
 * recomputes the SHA256 hash, and compares it to what is stored on-chain.
 * Shows Hash Verified or Hash Mismatch.
 *
 * After a successful verification, exposes a "Simulate Tampering" button
 * that calls /api/tamper-demo to prove the system detects any modification.
 */

import { useState } from "react"

const IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"

function truncate(str, maxLength = 32) {
  if (!str || str.length <= maxLength) return str
  return str.slice(0, maxLength) + "..."
}

function VerifyAudit({ apiBase }) {
  const [actionIdInput, setActionIdInput] = useState("")
  const [status, setStatus] = useState("input")  // "input" | "loading" | "result"
  const [verifyResult, setVerifyResult] = useState(null)
  const [error, setError] = useState(null)

  // Tamper demo state
  const [tamperStatus, setTamperStatus] = useState("idle")  // "idle" | "loading" | "result"
  const [tamperResult, setTamperResult] = useState(null)
  const [tamperError, setTamperError] = useState(null)

  const handleVerify = async () => {
    if (!actionIdInput.trim()) {
      setError("Please enter an action ID")
      return
    }

    setStatus("loading")
    setError(null)
    setTamperStatus("idle")
    setTamperResult(null)

    try {
      const response = await fetch(
        `${apiBase}/api/verify?action_id=${encodeURIComponent(actionIdInput.trim())}`
      )

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Verification failed")
      }

      const data = await response.json()
      setVerifyResult(data)
      setStatus("result")
    } catch (err) {
      setError(err.message)
      setStatus("input")
    }
  }

  const handleSimulateTamper = async () => {
    setTamperStatus("loading")
    setTamperError(null)

    try {
      const response = await fetch(
        `${apiBase}/api/tamper-demo?action_id=${encodeURIComponent(verifyResult.action_id)}`
      )

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Tamper demo failed")
      }

      const data = await response.json()
      setTamperResult(data)
      setTamperStatus("result")
    } catch (err) {
      setTamperError(err.message)
      setTamperStatus("idle")
    }
  }

  const handleReset = () => {
    setStatus("input")
    setVerifyResult(null)
    setError(null)
    setActionIdInput("")
    setTamperStatus("idle")
    setTamperResult(null)
    setTamperError(null)
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && status === "input") handleVerify()
  }

  return (
    <div>

      {status === "input" && (
        <div className="input-card">
          <label className="input-label">Action ID</label>
          <input
            className="input-field"
            type="text"
            placeholder="e.g. 1743600000_1234"
            value={actionIdInput}
            onChange={(e) => setActionIdInput(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          {error && <p className="error-msg">{error}</p>}
          <button className="btn-run" onClick={handleVerify}>
            Verify
          </button>
        </div>
      )}

      {status === "loading" && (
        <div className="loading-card">
          <div className="spinner" />
          <p className="loading-text">Fetching record from Algorand...</p>
          <p className="loading-sub">Verifying hash against IPFS data</p>
        </div>
      )}

      {status === "result" && verifyResult && (
        <div className="result-card">

          {/* Verification status — prominent */}
          <div className={`decision-badge ${verifyResult.hash_match ? "approved" : "rejected"}`}>
            {verifyResult.hash_match ? "✅ Hash Verified" : "❌ Hash Mismatch"}
          </div>

          <div className="result-rows">

            <div className="result-row">
              <span className="result-label">Action ID</span>
              <span className="result-value mono">{verifyResult.action_id}</span>
            </div>

            <div className="result-row">
              <span className="result-label">Hash (on-chain)</span>
              <span className="result-value mono" title={verifyResult.ipfs_hash_onchain}>
                {truncate(verifyResult.ipfs_hash_onchain, 28)}
              </span>
            </div>

            <div className="result-row">
              <span className="result-label">Hash (recomputed)</span>
              <span
                className={`result-value mono ${verifyResult.hash_match ? "pass" : "fail"}`}
                title={verifyResult.ipfs_hash_computed}
              >
                {truncate(verifyResult.ipfs_hash_computed || "—", 28)}
              </span>
            </div>

            {verifyResult.record && (
              <>
                <div className="result-row">
                  <span className="result-label">Decision</span>
                  <span className={`result-value ${verifyResult.record.decision === "approved" ? "pass" : "fail"}`}>
                    {verifyResult.record.decision}
                  </span>
                </div>

                <div className="result-row">
                  <span className="result-label">Policy Result</span>
                  <span className="result-value mono">{verifyResult.record.policy_result}</span>
                </div>

                <div className="result-row">
                  <span className="result-label">Vendor ID</span>
                  <span className="result-value mono">{verifyResult.record.vendor_id}</span>
                </div>

                <div className="result-row">
                  <span className="result-label">Agent ID</span>
                  <span className="result-value mono">{verifyResult.record.agent_id}</span>
                </div>
              </>
            )}

            {verifyResult.ipfs_data && verifyResult.ipfs_data.action_id && (
              <div className="result-row">
                <span className="result-label">IPFS Content</span>
                <a
                  className="result-link"
                  href={`${IPFS_GATEWAY}/${verifyResult.ipfs_data.ipfs_cid || ""}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View on IPFS ↗
                </a>
              </div>
            )}

          </div>

          {/* Tamper detection demo — only show after successful verification */}
          {verifyResult.hash_match && (
            <div className="tamper-section">
              <p className="tamper-intro">
                Prove the system detects any modification to this record.
              </p>

              {tamperStatus === "idle" && (
                <button className="btn-tamper" onClick={handleSimulateTamper}>
                  Simulate Tampering
                </button>
              )}

              {tamperStatus === "loading" && (
                <div className="tamper-loading">
                  <div className="spinner spinner-sm" />
                  <span>Simulating tampered record...</span>
                </div>
              )}

              {tamperError && (
                <p className="error-msg">{tamperError}</p>
              )}

              {tamperStatus === "result" && tamperResult && (
                <div className="tamper-result">
                  <div className="tamper-header">
                    Tamper Simulation Result
                  </div>

                  <div className="tamper-change">
                    Field modified: <span className="mono">{tamperResult.field_tampered}</span>
                    {" "}changed from{" "}
                    <span className="pass mono">₹{tamperResult.original_value}</span>
                    {" "}to{" "}
                    <span className="fail mono">₹{tamperResult.tampered_value}</span>
                  </div>

                  <div className="tamper-rows">
                    <div className="tamper-row">
                      <span className="tamper-label">Hash stored on-chain</span>
                      <span className="tamper-value mono" title={tamperResult.hash_onchain}>
                        {truncate(tamperResult.hash_onchain, 24)}
                      </span>
                    </div>

                    <div className="tamper-row">
                      <span className="tamper-label">Original record hash</span>
                      <span className="tamper-value pass mono" title={tamperResult.hash_original}>
                        {truncate(tamperResult.hash_original, 24)} ✅ Match
                      </span>
                    </div>

                    <div className="tamper-row">
                      <span className="tamper-label">Tampered record hash</span>
                      <span className="tamper-value fail mono" title={tamperResult.hash_tampered}>
                        {truncate(tamperResult.hash_tampered, 24)} ❌ Mismatch
                      </span>
                    </div>
                  </div>

                  <p className="tamper-conclusion">
                    Any modification to the audit record produces a different hash.
                    The on-chain hash is immutable — tampering is immediately detectable.
                  </p>
                </div>
              )}
            </div>
          )}

          <button className="btn-reset" onClick={handleReset}>
            Verify Another
          </button>
        </div>
      )}

    </div>
  )
}

export default VerifyAudit
