/**
 * VerifyAudit — Tab 2. Independent audit record verification.
 *
 * Fetches the on-chain record by action ID, fetches the original IPFS data,
 * recomputes the SHA256 hash, and compares it to what is stored on-chain.
 *
 * After successful verification, exposes a "Simulate Tampering" button
 * that proves the system detects any modification live.
 */

import { useState } from "react"

const IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"

function truncate(str, maxLength = 28) {
  if (!str || str.length <= maxLength) return str
  return str.slice(0, maxLength) + "..."
}

function ResultRow({ label, children }) {
  return (
    <div className="flex justify-between items-center py-2.5 border-b border-[#1a1f2e] last:border-0">
      <span className="text-xs text-slate-500 uppercase tracking-wider flex-shrink-0">{label}</span>
      <span className="text-right ml-4">{children}</span>
    </div>
  )
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
        <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-8 flex flex-col gap-4">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Action ID</label>
          <input
            className="bg-[#0f1117] border border-[#2d3248] rounded-lg px-4 py-3 text-slate-200 w-full outline-none focus:border-violet-400 transition-colors placeholder:text-slate-600"
            type="text"
            placeholder="e.g. 1743600000_1234"
            value={actionIdInput}
            onChange={(e) => setActionIdInput(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            className="bg-violet-400 text-[#0f1117] rounded-lg py-3.5 font-bold text-base hover:bg-violet-300 transition-colors cursor-pointer"
            onClick={handleVerify}
          >
            Verify
          </button>
        </div>
      )}

      {status === "loading" && (
        <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-12 flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-[#2d3248] border-t-violet-400 rounded-full animate-spin" />
          <p className="text-base font-semibold text-slate-200">Fetching record from Algorand...</p>
          <p className="text-sm text-slate-500 text-center">Verifying hash against IPFS data</p>
        </div>
      )}

      {status === "result" && verifyResult && (
        <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-8 flex flex-col gap-6">

          {/* Verification status */}
          <div className={`text-center text-2xl font-bold py-4 rounded-lg border
            ${verifyResult.hash_match
              ? "bg-green-950 text-green-400 border-green-800"
              : "bg-red-950 text-red-400 border-red-900"
            }`}>
            {verifyResult.hash_match ? "✅ Hash Verified" : "❌ Hash Mismatch"}
          </div>

          <div className="flex flex-col">

            <ResultRow label="Action ID">
              <span className="font-mono text-xs text-slate-200">{verifyResult.action_id}</span>
            </ResultRow>

            <ResultRow label="Hash (on-chain)">
              <span className="font-mono text-xs text-slate-200" title={verifyResult.ipfs_hash_onchain}>
                {truncate(verifyResult.ipfs_hash_onchain)}
              </span>
            </ResultRow>

            <ResultRow label="Hash (recomputed)">
              <span
                className={`font-mono text-xs ${verifyResult.hash_match ? "text-green-400" : "text-red-400"}`}
                title={verifyResult.ipfs_hash_computed}
              >
                {truncate(verifyResult.ipfs_hash_computed || "—")}
              </span>
            </ResultRow>

            {verifyResult.record && (
              <>
                <ResultRow label="Decision">
                  <span className={verifyResult.record.decision === "approved" ? "text-green-400 text-sm" : "text-red-400 text-sm"}>
                    {verifyResult.record.decision}
                  </span>
                </ResultRow>

                <ResultRow label="Policy Result">
                  <span className="font-mono text-xs text-slate-200">{verifyResult.record.policy_result}</span>
                </ResultRow>

                <ResultRow label="Vendor ID">
                  <span className="font-mono text-xs text-slate-200">{verifyResult.record.vendor_id}</span>
                </ResultRow>

                <ResultRow label="Agent ID">
                  <span className="font-mono text-xs text-slate-200">{verifyResult.record.agent_id}</span>
                </ResultRow>
              </>
            )}

            {verifyResult.ipfs_data && verifyResult.ipfs_data.action_id && (
              <ResultRow label="IPFS Content">
                <a
                  className="font-mono text-xs text-violet-400 hover:text-violet-300 hover:underline"
                  href={`${IPFS_GATEWAY}/${verifyResult.ipfs_data.ipfs_cid || ""}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View on IPFS ↗
                </a>
              </ResultRow>
            )}

          </div>

          {/* Tamper detection demo — only after successful verification */}
          {verifyResult.hash_match && (
            <div className="bg-[#161926] border border-[#2d3248] rounded-xl p-5 flex flex-col gap-3">
              <p className="text-sm text-slate-500">
                Prove the system detects any modification to this record.
              </p>

              {tamperStatus === "idle" && (
                <button
                  className="border border-amber-800 text-yellow-400 rounded-lg py-3 font-semibold text-sm hover:bg-amber-950 transition-colors cursor-pointer"
                  onClick={handleSimulateTamper}
                >
                  Simulate Tampering
                </button>
              )}

              {tamperStatus === "loading" && (
                <div className="flex items-center gap-3 text-slate-500 text-sm">
                  <div className="w-5 h-5 border-2 border-[#2d3248] border-t-violet-400 rounded-full animate-spin" />
                  <span>Simulating tampered record...</span>
                </div>
              )}

              {tamperError && <p className="text-sm text-red-400">{tamperError}</p>}

              {tamperStatus === "result" && tamperResult && (
                <div className="flex flex-col gap-3">

                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    Tamper Simulation Result
                  </span>

                  <p className="text-sm text-slate-300 leading-relaxed">
                    Field modified:{" "}
                    <span className="font-mono text-xs">{tamperResult.field_tampered}</span>
                    {" "}changed from{" "}
                    <span className="text-green-400 font-mono text-xs">₹{tamperResult.original_value}</span>
                    {" "}to{" "}
                    <span className="text-red-400 font-mono text-xs">₹{tamperResult.tampered_value}</span>
                  </p>

                  <div className="flex flex-col gap-2">
                    <div className="flex justify-between items-center py-2 border-b border-[#1e2130]">
                      <span className="text-xs text-slate-500">Hash stored on-chain</span>
                      <span className="font-mono text-xs text-slate-300" title={tamperResult.hash_onchain}>
                        {truncate(tamperResult.hash_onchain, 22)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-[#1e2130]">
                      <span className="text-xs text-slate-500">Original record hash</span>
                      <span className="font-mono text-xs text-green-400" title={tamperResult.hash_original}>
                        {truncate(tamperResult.hash_original, 22)} ✅
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2">
                      <span className="text-xs text-slate-500">Tampered record hash</span>
                      <span className="font-mono text-xs text-red-400" title={tamperResult.hash_tampered}>
                        {truncate(tamperResult.hash_tampered, 22)} ❌
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-500 leading-relaxed border-t border-[#2d3248] pt-3">
                    Any modification to the audit record produces a different hash.
                    The on-chain hash is immutable — tampering is immediately detectable.
                  </p>
                </div>
              )}
            </div>
          )}

          <button
            className="border border-[#2d3248] text-slate-500 rounded-lg py-3 text-sm hover:text-slate-200 hover:border-slate-500 transition-colors cursor-pointer w-full"
            onClick={handleReset}
          >
            Verify Another
          </button>

        </div>
      )}

    </div>
  )
}

export default VerifyAudit
