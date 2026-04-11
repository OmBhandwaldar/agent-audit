/**
 * Dashboard — Tab 3. Aggregate stats and recent audit history.
 *
 * Shows total audits, approved/rejected counts, compliance rate,
 * a recent audit table, and buttons to refresh or export CSV.
 */

import { useState, useEffect } from "react"

function truncate(str, maxLength = 18) {
  if (!str || str.length <= maxLength) return str
  return str.slice(0, maxLength) + "..."
}

function formatTime(timestamp) {
  return new Date(timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })
}

function StatCard({ label, value, valueClass = "text-slate-200" }) {
  return (
    <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-5 flex flex-col gap-2">
      <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
      <span className={`text-3xl font-bold leading-none ${valueClass}`}>{value}</span>
    </div>
  )
}

function Dashboard({ apiBase }) {
  const [stats, setStats] = useState(null)
  const [status, setStatus] = useState("loading")
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(null)

  const fetchDashboard = async () => {
    setStatus("loading")
    setError(null)
    try {
      const response = await fetch(`${apiBase}/api/dashboard`)
      if (!response.ok) throw new Error("Failed to fetch dashboard data")
      const data = await response.json()
      setStats(data)
      setStatus("ready")
    } catch (err) {
      setError(err.message)
      setStatus("error")
    }
  }

  useEffect(() => { fetchDashboard() }, [])

  const handleExport = () => window.open(`${apiBase}/api/export/csv`)

  const handleRowClick = (actionId) => {
    navigator.clipboard.writeText(actionId).catch(() => {})
    setCopied(actionId)
    setTimeout(() => setCopied(null), 1500)
  }

  const complianceClass = (rate) => {
    if (rate >= 80) return "text-green-400"
    if (rate >= 50) return "text-yellow-400"
    return "text-red-400"
  }

  if (status === "loading") {
    return (
      <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-12 flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-4 border-[#2d3248] border-t-violet-400 rounded-full animate-spin" />
        <p className="text-base font-semibold text-slate-200">Loading dashboard...</p>
      </div>
    )
  }

  if (status === "error") {
    return (
      <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-8 flex flex-col gap-4">
        <p className="text-sm text-red-400">{error}</p>
        <button
          className="bg-violet-400 text-[#0f1117] rounded-lg py-3 font-bold cursor-pointer hover:bg-violet-300 transition-colors"
          onClick={fetchDashboard}
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Total Audits" value={stats.total_audits} />
        <StatCard label="Approved" value={stats.approved_count} valueClass="text-green-400" />
        <StatCard label="Rejected" value={stats.rejected_count} valueClass="text-red-400" />
        <StatCard
          label="Compliance Rate"
          value={`${stats.compliance_rate}%`}
          valueClass={complianceClass(stats.compliance_rate)}
        />
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          className="flex-1 border border-[#2d3248] text-slate-500 rounded-lg py-3 text-sm hover:text-slate-200 hover:border-slate-500 transition-colors cursor-pointer"
          onClick={fetchDashboard}
        >
          Refresh
        </button>
        <button
          className={`flex-1 border border-[#2d3248] rounded-lg py-3 text-sm transition-colors
            ${stats.total_audits === 0
              ? "text-slate-700 cursor-not-allowed opacity-40"
              : "text-slate-500 hover:text-slate-200 hover:border-slate-500 cursor-pointer"
            }`}
          onClick={handleExport}
          disabled={stats.total_audits === 0}
          title={stats.total_audits === 0 ? "Run audits first" : "Download CSV"}
        >
          Export CSV
        </button>
      </div>

      {/* Recent audits table */}
      {stats.recent_audits.length === 0 ? (
        <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-10 text-center text-slate-500 text-sm">
          No audits yet. Run an audit to see history here.
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          <p className="text-xs text-slate-600 mb-1">Click a row to copy its Action ID</p>
          <div className="overflow-x-auto rounded-xl border border-[#2d3248]">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr>
                  {["Action ID", "Agent Type", "Amount", "Vendor", "Decision", "Time"].map(h => (
                    <th key={h} className="bg-[#161926] text-slate-500 text-xs uppercase tracking-wider px-3 py-2.5 text-left border-b border-[#2d3248]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stats.recent_audits.map((audit) => (
                  <tr
                    key={audit.action_id}
                    className={`cursor-pointer transition-colors border-b border-[#161926] last:border-0
                      ${copied === audit.action_id ? "bg-green-950" : "hover:bg-[#252a3d]"}`}
                    onClick={() => handleRowClick(audit.action_id)}
                    title={`Click to copy: ${audit.action_id}`}
                  >
                    <td className="px-3 py-2.5 font-mono text-xs text-slate-300">
                      {copied === audit.action_id ? "Copied!" : truncate(audit.action_id)}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-violet-400">
                      {audit.agent_type_id?.replace(/_/g, " ") || "payment approval"}
                    </td>
                    <td className="px-3 py-2.5 text-slate-300">₹{audit.amount}</td>
                    <td className="px-3 py-2.5 font-mono text-xs text-slate-300">{audit.vendor_id}</td>
                    <td className={`px-3 py-2.5 font-medium ${audit.decision === "approved" ? "text-green-400" : "text-red-400"}`}>
                      {audit.decision === "approved" ? "✅ Approved" : "❌ Rejected"}
                    </td>
                    <td className="px-3 py-2.5 text-slate-400 text-xs">{formatTime(audit.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  )
}

export default Dashboard
