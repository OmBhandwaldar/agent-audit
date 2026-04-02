/**
 * VerifyAudit — Tab 2. Independent audit record verification.
 *
 * Fetches the on-chain record by action ID, fetches the original IPFS data,
 * recomputes the SHA256 hash, and compares it to what is stored on-chain.
 * Shows ✅ Hash Verified or ❌ Hash Mismatch.
 */

import { useState } from "react"

const IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"

function truncate(str, maxLength = 32) {
  if (!str || str.length <= maxLength) return str
  return str.slice(0, maxLength) + "..."
}

function VerifyAudit({ apiBase }) {
  const [actionIdInput, setActionIdInput] = useState("")
  const [status, setStatus] = useState("input")  // "input" | "loading" | "result" | "error"
  const [verifyResult, setVerifyResult] = useState(null)
  const [error, setError] = useState(null)

  const handleVerify = async () => {
    if (!actionIdInput.trim()) {
      setError("Please enter an action ID")
      return
    }

    setStatus("loading")
    setError(null)

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

  const handleReset = () => {
    setStatus("input")
    setVerifyResult(null)
    setError(null)
    setActionIdInput("")
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

            {/* On-chain record fields */}
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

            {/* IPFS content link if available */}
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

          <button className="btn-reset" onClick={handleReset}>
            Verify Another
          </button>
        </div>
      )}

    </div>
  )
}

export default VerifyAudit
