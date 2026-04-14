/**
 * AuditDashboardPage — /dashboard
 *
 * Full-page premium dashboard using the LandingPage design system.
 * Design: Material You dark · coral-orange primary · Space Grotesk headlines.
 * Functionality: mirrors Dashboard.jsx — stats, recent audits, refresh, CSV export.
 */

import { useState, useEffect, useCallback } from "react"
import { Link } from "react-router-dom"
import NavBar from "./NavBar"

const IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"
const TX_EXPLORER  = "https://testnet.explorer.perawallet.app/tx"

function truncate(str, max = 16) {
  if (!str || str.length <= max) return str
  return str.slice(0, max) + "…"
}

function formatTime(timestamp) {
  return new Date(timestamp * 1000).toLocaleString([], {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  })
}

/* DashboardNav replaced by shared NavBar pill — see bottom of file */

/* ─── Skeleton loader ─────────────────────────────────────────────────────── */

function Skeleton({ className = "" }) {
  return (
    <div className={`bg-[#1a1919] rounded animate-pulse ${className}`} />
  )
}

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="bg-[#131313] border border-[#2a2a2a] rounded-2xl p-6 flex flex-col gap-4">
          <Skeleton className="w-10 h-10 rounded-xl" />
          <Skeleton className="h-8 w-16 rounded" />
          <Skeleton className="h-3 w-24 rounded" />
        </div>
      ))}
    </div>
  )
}

function TableSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(5)].map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-xl" />
      ))}
    </div>
  )
}

/* ─── Stat card ───────────────────────────────────────────────────────────── */

function StatCard({ icon, label, value, sub, accent = "#ff4f00", iconBg = "rgba(255,79,0,0.12)" }) {
  return (
    <div className="bg-[#131313] border border-[#2a2a2a] rounded-2xl p-6 flex flex-col gap-4
      hover:border-[#484847]/60 transition-colors duration-200 group">
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center"
        style={{ background: iconBg }}
      >
        <span className="material-symbols-outlined text-lg" style={{ color: accent }}>{icon}</span>
      </div>
      <div>
        <div className="text-3xl font-bold headline text-white tracking-tighter leading-none mb-1">
          {value}
        </div>
        <div className="text-xs text-[#767575] uppercase tracking-wider font-label">{label}</div>
      </div>
      {sub && (
        <div className="text-[11px] font-label" style={{ color: accent }}>
          {sub}
        </div>
      )}
    </div>
  )
}

/* ─── Decision badge ──────────────────────────────────────────────────────── */

function DecisionBadge({ decision }) {
  const approved = decision === "approved"
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold font-label
      ${approved
        ? "bg-[#26fedc]/10 text-[#26fedc] border border-[#26fedc]/20"
        : "bg-[#f61468]/10 text-[#ff6d8e] border border-[#f61468]/20"
      }`}
    >
      <span className="material-symbols-outlined text-[10px]"
        style={{ fontVariationSettings: "'FILL' 1" }}>
        {approved ? "check_circle" : "cancel"}
      </span>
      {approved ? "Approved" : "Rejected"}
    </span>
  )
}

/* ─── Audit row ───────────────────────────────────────────────────────────── */

function AuditRow({ audit, copied, onCopy }) {
  const isCopied = copied === audit.action_id
  return (
    <tr
      className={`border-b border-[#1a1919] last:border-0 transition-colors duration-150 cursor-pointer
        ${isCopied ? "bg-[#26fedc]/5" : "hover:bg-[#1a1919]"}`}
      onClick={() => onCopy(audit.action_id)}
      title={`Click to copy Action ID: ${audit.action_id}`}
    >
      {/* Action ID */}
      <td className="px-5 py-3.5">
        <span className={`font-mono text-[11px] transition-colors ${isCopied ? "text-[#26fedc]" : "text-[#767575]"}`}>
          {isCopied ? "Copied!" : truncate(audit.action_id)}
        </span>
      </td>

      {/* Agent type */}
      <td className="px-5 py-3.5">
        <span className="text-[11px] font-label text-[#ff4f00] bg-[#ff4f00]/8 border border-[#ff4f00]/15 px-2 py-0.5 rounded-full">
          {(audit.agent_type_id ?? "payment_approval").replace(/_/g, " ")}
        </span>
      </td>

      {/* Amount */}
      <td className="px-5 py-3.5 font-label text-sm text-white font-medium">
        ₹{audit.amount?.toLocaleString()}
      </td>

      {/* Vendor */}
      <td className="px-5 py-3.5 font-mono text-[11px] text-[#adaaaa]">
        {audit.vendor_id}
      </td>

      {/* Agent decision */}
      <td className="px-5 py-3.5">
        <DecisionBadge decision={audit.agent_decision} />
      </td>

      {/* Policy decision */}
      <td className="px-5 py-3.5">
        <DecisionBadge decision={audit.decision} />
      </td>

      {/* IPFS */}
      <td className="px-5 py-3.5">
        {audit.ipfs_cid ? (
          <a
            href={`${IPFS_GATEWAY}/${audit.ipfs_cid}`}
            target="_blank"
            rel="noreferrer"
            onClick={e => e.stopPropagation()}
            className="font-mono text-[11px] text-[#ff4f00]/70 hover:text-[#ff4f00] transition-colors"
            title={audit.ipfs_cid}
          >
            {truncate(audit.ipfs_cid, 12)}
          </a>
        ) : (
          <span className="text-[#484847] text-[11px]">—</span>
        )}
      </td>

      {/* TX */}
      <td className="px-5 py-3.5">
        {audit.algorand_tx_id ? (
          <a
            href={`${TX_EXPLORER}/${audit.algorand_tx_id}`}
            target="_blank"
            rel="noreferrer"
            onClick={e => e.stopPropagation()}
            className="font-mono text-[11px] text-[#ff4f00]/70 hover:text-[#ff4f00] transition-colors"
            title={audit.algorand_tx_id}
          >
            {truncate(audit.algorand_tx_id, 12)}
          </a>
        ) : (
          <span className="text-[#484847] text-[11px]">—</span>
        )}
      </td>

      {/* Time */}
      <td className="px-5 py-3.5 text-[11px] text-[#767575] whitespace-nowrap font-label">
        {formatTime(audit.timestamp)}
      </td>
    </tr>
  )
}

/* ─── Empty state ─────────────────────────────────────────────────────────── */

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-5">
      <div className="w-16 h-16 rounded-2xl bg-[#131313] border border-[#2a2a2a] flex items-center justify-center">
        <span className="material-symbols-outlined text-3xl text-[#484847]">inbox</span>
      </div>
      <div className="text-center">
        <p className="text-white font-label font-semibold mb-1">No audits yet</p>
        <p className="text-[#767575] text-sm font-label">
          Run your first audit to see the history here.
        </p>
      </div>
      <Link
        to="/app"
        className="flex items-center gap-2 bg-[#ff4f00] text-[#591800] px-5 py-2.5 rounded-lg
          font-bold text-sm headline hover:scale-95 transition-all duration-150
          shadow-[0_4px_20px_-6px_rgba(255,79,0,0.4)]"
      >
        <span className="material-symbols-outlined text-sm">play_arrow</span>
        Run First Audit
      </Link>
    </div>
  )
}

/* ─── Error state ─────────────────────────────────────────────────────────── */

function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-5">
      <div className="w-16 h-16 rounded-2xl bg-[#f61468]/10 border border-[#f61468]/20 flex items-center justify-center">
        <span className="material-symbols-outlined text-3xl text-[#ff6d8e]">error</span>
      </div>
      <div className="text-center">
        <p className="text-white font-label font-semibold mb-1">Failed to load dashboard</p>
        <p className="text-[#767575] text-sm font-label max-w-xs">{message}</p>
      </div>
      <button
        onClick={onRetry}
        className="flex items-center gap-2 bg-[#ff4f00] text-[#591800] px-5 py-2.5 rounded-lg
          font-bold text-sm headline hover:scale-95 transition-all duration-150"
      >
        <span className="material-symbols-outlined text-sm">refresh</span>
        Retry
      </button>
    </div>
  )
}

/* ─── Compliance bar ──────────────────────────────────────────────────────── */

function ComplianceBar({ rate }) {
  const color = rate >= 80 ? "#26fedc" : rate >= 50 ? "#febc2e" : "#ff6d8e"
  return (
    <div className="w-full h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${rate}%`, background: color }}
      />
    </div>
  )
}

/* ─── Verify modal ───────────────────────────────────────────────────────── */

const VERIFY_STEPS = [
  "Fetching audit record from Algorand",
  "Retrieving evidence from IPFS",
  "Verifying hash integrity",
]

function VerifyModal({ apiBase, onClose }) {
  const [actionIdInput, setActionIdInput] = useState("")
  const [verifyStatus,  setVerifyStatus]  = useState("input")   // "input"|"loading"|"result"
  const [verifyResult,  setVerifyResult]  = useState(null)
  const [verifyError,   setVerifyError]   = useState(null)
  const [steps,         setSteps]         = useState([])
  const [tamperStatus,  setTamperStatus]  = useState("idle")    // "idle"|"loading"|"result"
  const [tamperResult,  setTamperResult]  = useState(null)
  const [tamperError,   setTamperError]   = useState(null)

  const handleVerify = async () => {
    if (!actionIdInput.trim()) { setVerifyError("Please enter an action ID"); return }
    setVerifyStatus("loading")
    setVerifyError(null)
    setTamperStatus("idle")
    setTamperResult(null)

    // Initialise steps — first one starts loading immediately
    setSteps(VERIFY_STEPS.map((label, i) => ({ label, status: i === 0 ? "loading" : "pending" })))

    // Advance step 1 → done, step 2 → loading after 1.8s
    const t1 = setTimeout(() => {
      setSteps(prev => prev.map((s, i) => {
        if (i === 0) return { ...s, status: "done" }
        if (i === 1) return { ...s, status: "loading" }
        return s
      }))
    }, 1800)

    // Advance step 2 → done, step 3 → loading after 3.6s
    const t2 = setTimeout(() => {
      setSteps(prev => prev.map((s, i) => {
        if (i === 1) return { ...s, status: "done" }
        if (i === 2) return { ...s, status: "loading" }
        return s
      }))
    }, 3600)

    try {
      const res = await fetch(
        `${apiBase}/api/verify?action_id=${encodeURIComponent(actionIdInput.trim())}`
      )
      clearTimeout(t1)
      clearTimeout(t2)
      if (!res.ok) {
        const d = await res.json()
        throw new Error(d.detail || "Verification failed")
      }
      const data = await res.json()

      // Mark all steps done, then reveal result after brief pause
      setSteps(VERIFY_STEPS.map(label => ({ label, status: "done" })))
      await new Promise(r => setTimeout(r, 500))
      setVerifyResult(data)
      setVerifyStatus("result")
    } catch (err) {
      clearTimeout(t1)
      clearTimeout(t2)
      setVerifyError(err.message)
      setVerifyStatus("input")
      setSteps([])
    }
  }

  const handleSimulateTamper = async () => {
    setTamperStatus("loading")
    setTamperError(null)
    try {
      const res = await fetch(
        `${apiBase}/api/tamper-demo?action_id=${encodeURIComponent(verifyResult.action_id)}`
      )
      if (!res.ok) {
        const d = await res.json()
        throw new Error(d.detail || "Tamper demo failed")
      }
      const data = await res.json()
      setTamperResult(data)
      setTamperStatus("result")
    } catch (err) {
      setTamperError(err.message)
      setTamperStatus("idle")
    }
  }

  const handleReset = () => {
    setVerifyStatus("input")
    setVerifyResult(null)
    setVerifyError(null)
    setActionIdInput("")
    setTamperStatus("idle")
    setTamperResult(null)
    setTamperError(null)
  }

  const verified = verifyResult?.hash_match

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      {/* Modal card */}
      <div className="bg-[#0e0e0e] border border-[#2a2a2a] rounded-2xl w-full max-w-lg
        shadow-[0_0_80px_-20px_rgba(255,79,0,0.25)] flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="relative flex items-center justify-center px-5 py-4 border-b border-[#1a1919] shrink-0">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base text-[#ff4f00]"
              style={{ fontVariationSettings: "'FILL' 1" }}>verified_user</span>
            <h2 className="headline font-bold text-white tracking-tight">Verify Audit Record</h2>
          </div>
          <button
            onClick={onClose}
            className="absolute right-4 w-7 h-7 flex items-center justify-center rounded-lg
              text-[#484847] hover:text-white hover:bg-[#1a1919] transition-all duration-150 cursor-pointer"
          >
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="p-6 overflow-y-auto flex-1">

        {/* ── Input ── */}
        {verifyStatus === "input" && (
          <div className="flex flex-col gap-3">
            <label className="text-[10px] font-label font-semibold text-[#484847] uppercase tracking-wider">
              Action ID
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                className="flex-1 bg-[#131313] border border-[#2a2a2a] rounded-xl px-4 py-3
                  text-sm text-white font-body outline-none
                  focus:border-[#ff4f00]/50 transition-colors duration-150
                  placeholder:text-[#484847]"
                placeholder="e.g. 1743600000_1234"
                value={actionIdInput}
                onChange={e => setActionIdInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleVerify()}
                autoFocus
              />
              <button
                onClick={handleVerify}
                disabled={!actionIdInput.trim()}
                className="flex items-center gap-2 bg-[#ff4f00] text-[#591800] px-5 py-3 rounded-xl
                  font-bold text-sm headline hover:scale-95 active:opacity-80 transition-all duration-150
                  cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed disabled:scale-100
                  shadow-[0_4px_16px_-4px_rgba(255,79,0,0.5)] shrink-0"
              >
                <span className="material-symbols-outlined text-base"
                  style={{ fontVariationSettings: "'FILL' 1" }}>search</span>
                Verify
              </button>
            </div>
            {verifyError && (
              <p className="text-sm text-[#ff6d8e] font-label flex items-center gap-1.5">
                <span className="material-symbols-outlined text-sm">error</span>
                {verifyError}
              </p>
            )}
          </div>
        )}

        {/* ── Steps ── */}
        {verifyStatus === "loading" && (
          <div className="flex flex-col gap-5 py-4">
            {steps.map((step, i) => (
              <div key={i} className="flex items-center gap-4">
                {step.status === "done" ? (
                  <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center shrink-0">
                    <span className="material-symbols-outlined text-[13px] text-white"
                      style={{ fontVariationSettings: "'FILL' 1" }}>check</span>
                  </div>
                ) : step.status === "loading" ? (
                  <div className="w-6 h-6 shrink-0 border-2 border-[#2a2a2a] border-t-[#ff4f00] rounded-full animate-spin" />
                ) : (
                  <div className="w-6 h-6 rounded-full border border-[#2a2a2a] shrink-0" />
                )}
                <span className={`text-sm font-body transition-colors duration-300
                  ${step.status === "pending"  ? "text-[#484847]" : ""}
                  ${step.status === "loading"  ? "text-white"     : ""}
                  ${step.status === "done"     ? "text-[#adaaaa]" : ""}`}>
                  {step.label}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* ── Result ── */}
        {verifyStatus === "result" && verifyResult && (
          <div className="flex flex-col gap-5">

            {/* Hash status banner */}
            <div className={`flex items-center gap-3 px-5 py-4 rounded-xl border ${
              verified
                ? "bg-[#ff4f00]/8 border-[#ff4f00]/20"
                : "bg-[#f61468]/8 border-[#f61468]/20"
            }`}>
              <span className="material-symbols-outlined text-2xl"
                style={{
                  color: verified ? "#ff4f00" : "#ff6d8e",
                  fontVariationSettings: "'FILL' 1",
                }}>
                {verified ? "verified" : "gpp_bad"}
              </span>
              <div>
                <p className="font-bold headline text-lg tracking-tight"
                  style={{ color: verified ? "#ff4f00" : "#ff6d8e" }}>
                  {verified ? "Hash Verified" : "Hash Mismatch"}
                </p>
                <p className="text-[11px] font-label text-[#767575] mt-0.5">
                  {verified
                    ? "On-chain hash matches IPFS record — audit is authentic"
                    : "On-chain hash does not match IPFS data — record may have been tampered"}
                </p>
              </div>
            </div>

            {/* Record details */}
            <div className="grid grid-cols-[130px_1fr] gap-x-4 gap-y-2.5 text-[11px]
              bg-[#131313] rounded-xl p-5 border border-[#2a2a2a]">

              <span className="text-[#484847] font-label uppercase tracking-wider text-[10px] self-center">Action ID</span>
              <span className="font-mono text-[#adaaaa] break-all">{verifyResult.action_id}</span>

              <span className="text-[#484847] font-label uppercase tracking-wider text-[10px] self-center">Hash (on-chain)</span>
              <span className="font-mono text-[#adaaaa] break-all" title={verifyResult.ipfs_hash_onchain}>
                {truncate(verifyResult.ipfs_hash_onchain, 36)}
              </span>

              <span className="text-[#484847] font-label uppercase tracking-wider text-[10px] self-center">Hash (recomputed)</span>
              <span className="font-mono break-all"
                style={{ color: verified ? "#ff4f00" : "#ff6d8e" }}
                title={verifyResult.ipfs_hash_computed}>
                {truncate(verifyResult.ipfs_hash_computed || "—", 36)}
              </span>

              {verifyResult.record && (
                <>
                  <span className="text-[#484847] font-label uppercase tracking-wider text-[10px] self-center">Decision</span>
                  <span className="font-label font-semibold"
                    style={{ color: verifyResult.record.decision === "approved" ? "#26fedc" : "#ff6d8e" }}>
                    {verifyResult.record.decision}
                  </span>

                  <span className="text-[#484847] font-label uppercase tracking-wider text-[10px] self-center">Policy Result</span>
                  <span className="font-mono text-[#adaaaa]">{verifyResult.record.policy_result}</span>

                  <span className="text-[#484847] font-label uppercase tracking-wider text-[10px] self-center">Vendor ID</span>
                  <span className="font-mono text-[#adaaaa]">{verifyResult.record.vendor_id}</span>

                  <span className="text-[#484847] font-label uppercase tracking-wider text-[10px] self-center">Agent ID</span>
                  <span className="font-mono text-[#adaaaa]">{verifyResult.record.agent_id}</span>
                </>
              )}

              {verifyResult.ipfs_data?.action_id && (
                <>
                  <span className="text-[#484847] font-label uppercase tracking-wider text-[10px] self-center">IPFS Content</span>
                  <a href={`${IPFS_GATEWAY}/${verifyResult.ipfs_data.ipfs_cid || ""}`}
                    target="_blank" rel="noreferrer"
                    className="font-mono text-[#ff4f00]/70 hover:text-[#ff4f00] transition-colors">
                    View on IPFS ↗
                  </a>
                </>
              )}
            </div>

            {/* Tamper detection demo */}
            {/* {verified && (
              <div className="bg-[#131313] border border-[#2a2a2a] rounded-xl p-5 flex flex-col gap-4">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm text-[#febc2e]">science</span>
                  <span className="text-[10px] font-label font-semibold text-[#febc2e] uppercase tracking-wider">
                    Tamper Detection Demo
                  </span>
                </div>
                <p className="text-[12px] text-[#767575] font-label leading-relaxed">
                  Prove the system instantly detects any modification to this record.
                </p>

                {tamperStatus === "idle" && (
                  <button
                    onClick={handleSimulateTamper}
                    className="flex items-center justify-center gap-2 border border-[#febc2e]/30 text-[#febc2e]
                      bg-[#febc2e]/5 rounded-xl py-3 font-semibold text-sm headline
                      hover:bg-[#febc2e]/10 hover:border-[#febc2e]/50 transition-all duration-150 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-sm">security</span>
                    Simulate Tampering
                  </button>
                )}

                {tamperStatus === "loading" && (
                  <div className="flex items-center gap-3 text-[#767575] text-sm font-label py-1">
                    <span className="w-4 h-4 border-2 border-[#2a2a2a] border-t-[#febc2e] rounded-full animate-spin" />
                    Simulating tampered record…
                  </div>
                )}

                {tamperError && (
                  <p className="text-sm text-[#ff6d8e] font-label">{tamperError}</p>
                )}

                {tamperStatus === "result" && tamperResult && (
                  <div className="flex flex-col gap-3">
                    <p className="text-[12px] text-[#adaaaa] font-label leading-relaxed">
                      Field modified:{" "}
                      <span className="font-mono text-[11px]">{tamperResult.field_tampered}</span>
                      {" "}changed from{" "}
                      <span className="font-mono text-[11px] text-[#26fedc]">₹{tamperResult.original_value}</span>
                      {" "}to{" "}
                      <span className="font-mono text-[11px] text-[#ff6d8e]">₹{tamperResult.tampered_value}</span>
                    </p>
                    <div className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-2 text-[11px]
                      bg-[#0e0e0e] rounded-lg p-4 border border-[#2a2a2a]">
                      <span className="text-[#484847] font-label">Hash (on-chain)</span>
                      <span className="font-mono text-[#adaaaa] break-all" title={tamperResult.hash_onchain}>
                        {truncate(tamperResult.hash_onchain, 26)}
                      </span>
                      <span className="text-[#484847] font-label">Original hash</span>
                      <span className="font-mono text-[#26fedc] break-all" title={tamperResult.hash_original}>
                        {truncate(tamperResult.hash_original, 26)} ✓
                      </span>
                      <span className="text-[#484847] font-label">Tampered hash</span>
                      <span className="font-mono text-[#ff6d8e] break-all" title={tamperResult.hash_tampered}>
                        {truncate(tamperResult.hash_tampered, 26)} ✗
                      </span>
                    </div>
                    <p className="text-[11px] text-[#484847] font-label leading-relaxed pt-1">
                      Any modification produces a different hash. The on-chain hash is immutable — tampering is immediately detectable.
                    </p>
                  </div>
                )}
              </div>
            )} */}

            {/* Reset */}
            <button
              onClick={handleReset}
              className="flex items-center justify-center gap-2 border border-[#2a2a2a] text-[#767575]
                rounded-xl py-3 text-sm font-label hover:text-white hover:border-[#484847]
                transition-all duration-150 cursor-pointer w-full"
            >
              <span className="material-symbols-outlined text-sm">restart_alt</span>
              Verify Another
            </button>

          </div>
        )}

        </div>
      </div>
    </div>
  )
}

/* ─── Main page ───────────────────────────────────────────────────────────── */

function AuditDashboardPage({ apiBase }) {
  const [stats,           setStats]           = useState(null)
  const [status,          setStatus]          = useState("loading")
  const [error,           setError]           = useState(null)
  const [copied,          setCopied]          = useState(null)
  const [refreshing,      setRefreshing]      = useState(false)
  const [verifyModalOpen, setVerifyModalOpen] = useState(false)

  const fetchDashboard = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else           setStatus("loading")
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/dashboard`)
      if (!res.ok) throw new Error("Failed to fetch dashboard data")
      const data = await res.json()
      setStats(data)
      setStatus("ready")
    } catch (err) {
      setError(err.message)
      setStatus("error")
    } finally {
      setRefreshing(false)
    }
  }, [apiBase])

  useEffect(() => { fetchDashboard() }, [fetchDashboard])

  const handleExport = () => window.open(`${apiBase}/api/export/csv`)

  const handleCopy = (actionId) => {
    navigator.clipboard.writeText(actionId).catch(() => {})
    setCopied(actionId)
    setTimeout(() => setCopied(null), 1500)
  }

  const complianceColor = (rate) =>
    rate >= 80 ? "#26fedc" : rate >= 50 ? "#febc2e" : "#ff6d8e"

  const isReady = status === "ready" && stats

  return (
    <div className="min-h-screen flex flex-col bg-[#0e0e0e] text-white">

      {/* Ambient decorations */}
      <div className="fixed top-0 left-1/4 w-[600px] h-[400px] bg-[#ff4f00]/5 blur-[120px] rounded-full pointer-events-none z-0" />
      <div className="fixed bottom-1/4 right-1/4 w-[500px] h-[400px] bg-[#26fedc]/3 blur-[120px] rounded-full pointer-events-none z-0" />

      {/* Shared floating pill nav */}
      <NavBar />

      {/* Verify modal */}
      {verifyModalOpen && (
        <VerifyModal apiBase={apiBase} onClose={() => setVerifyModalOpen(false)} />
      )}

      <main className="flex-1 relative z-10 max-w-screen-xl mx-auto w-full px-6 md:px-10 pt-24 pb-10">

        {/* Page header */}
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-10">
          <div>
            <h1 className="headline text-4xl md:text-5xl font-bold tracking-tighter text-white mb-2">
              Audit <span className="text-[#ff4f00]">Dashboard</span>
            </h1>
            <p className="text-[#767575] text-sm font-label">
              Real-time audit telemetry · Algorand Testnet · IPFS via Pinata
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => fetchDashboard(true)}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-[#2a2a32]
                text-[#adaaaa] hover:text-white hover:border-[#484847] text-xs font-label font-medium
                transition-all duration-150 cursor-pointer disabled:opacity-40 bg-[#111116]/60 backdrop-blur-md"
            >
              <span className={`material-symbols-outlined text-sm ${refreshing ? "animate-spin" : ""}`}>
                refresh
              </span>
              Refresh
            </button>
            <button
              onClick={() => setVerifyModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-[#ff4f00]/30
                text-[#ff4f00] hover:border-[#ff4f00]/60 hover:bg-[#ff4f00]/8 text-xs font-label font-medium
                transition-all duration-150 cursor-pointer bg-[#111116]/60 backdrop-blur-md"
            >
              <span className="material-symbols-outlined text-sm"
                style={{ fontVariationSettings: "'FILL' 1" }}>verified_user</span>
              Verify Audit
            </button>
            <button
              onClick={handleExport}
              disabled={!isReady || stats.total_audits === 0}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-[#2a2a32]
                text-[#adaaaa] hover:text-white hover:border-[#484847] text-xs font-label font-medium
                transition-all duration-150 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed
                bg-[#111116]/60 backdrop-blur-md"
              title={!isReady || stats.total_audits === 0 ? "Run audits first" : "Download CSV"}
            >
              <span className="material-symbols-outlined text-sm">download</span>
              Export CSV
            </button>
          </div>
        </div>

        {/* ── Stat cards ── */}
        {status === "loading" ? <StatsSkeleton /> : status === "error" ? null : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard
              icon="analytics"
              label="Total Audits"
              value={stats.total_audits}
              sub={`All time records`}
              accent="#ff4f00"
              iconBg="rgba(255,79,0,0.12)"
            />
            <StatCard
              icon="check_circle"
              label="Approved"
              value={stats.approved_count}
              sub={stats.total_audits > 0
                ? `${Math.round(stats.approved_count / stats.total_audits * 100)}% of total`
                : "No audits yet"}
              accent="#26fedc"
              iconBg="rgba(38,254,220,0.10)"
            />
            <StatCard
              icon="cancel"
              label="Rejected"
              value={stats.rejected_count}
              sub={stats.total_audits > 0
                ? `${Math.round(stats.rejected_count / stats.total_audits * 100)}% of total`
                : "No audits yet"}
              accent="#ff6d8e"
              iconBg="rgba(246,20,104,0.10)"
            />
            <div className="bg-[#131313] border border-[#2a2a2a] rounded-2xl p-6 flex flex-col gap-4
              hover:border-[#484847]/60 transition-colors duration-200">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ background: `${complianceColor(stats.compliance_rate)}15` }}>
                <span className="material-symbols-outlined text-lg"
                  style={{ color: complianceColor(stats.compliance_rate) }}>verified</span>
              </div>
              <div>
                <div className="text-3xl font-bold headline text-white tracking-tighter leading-none mb-1"
                  style={{ color: complianceColor(stats.compliance_rate) }}>
                  {stats.compliance_rate}%
                </div>
                <div className="text-xs text-[#767575] uppercase tracking-wider font-label mb-3">
                  Compliance Rate
                </div>
                <ComplianceBar rate={stats.compliance_rate} />
              </div>
            </div>
          </div>
        )}

        {/* ── Audit history table ── */}
        <div className="bg-[#0e0e0e] border border-[#2a2a2a] rounded-2xl overflow-hidden">

          {/* Table header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-[#1a1919]">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-base text-[#ff4f00]">history</span>
              <h2 className="headline font-bold text-white tracking-tight">Recent Audits</h2>
              {isReady && stats.recent_audits.length > 0 && (
                <span className="text-[10px] font-mono text-[#767575] border border-[#2a2a2a] rounded px-2 py-0.5">
                  {stats.recent_audits.length} records
                </span>
              )}
            </div>
            {isReady && stats.recent_audits.length > 0 && (
              <span className="text-[10px] text-[#484847] font-label">
                Click any row to copy its Action ID
              </span>
            )}
          </div>

          {/* Content */}
          {status === "loading" ? (
            <div className="p-6"><TableSkeleton /></div>
          ) : status === "error" ? (
            <ErrorState message={error} onRetry={() => fetchDashboard()} />
          ) : stats.recent_audits.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-[#1a1919]">
                    {["Action ID", "Agent", "Amount", "Vendor", "Agent Decision", "Policy Decision", "IPFS", "Algorand TX", "Time"].map(h => (
                      <th key={h}
                        className="px-5 py-3 text-left text-[10px] font-label font-semibold
                          text-[#484847] uppercase tracking-widest whitespace-nowrap bg-[#0a0a0a]">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_audits.map(audit => (
                    <AuditRow
                      key={audit.action_id}
                      audit={audit}
                      copied={copied}
                      onCopy={handleCopy}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

        </div>

        {/* Testnet footnote */}
        <p className="text-center text-[10px] font-mono text-[#2a2a2a] mt-8 tracking-wider uppercase">
          Algorand Testnet · Data is live — not mocked
        </p>

      </main>
    </div>
  )
}

export default AuditDashboardPage
