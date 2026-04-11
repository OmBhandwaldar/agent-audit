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

function Dashboard({ apiBase }) {
  const [stats, setStats] = useState(null)
  const [status, setStatus] = useState("loading")  // "loading" | "ready" | "error"
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(null)  // action_id of last copied row

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

  useEffect(() => {
    fetchDashboard()
  }, [])

  const handleExport = () => {
    window.open(`${apiBase}/api/export/csv`)
  }

  const handleRowClick = (actionId) => {
    navigator.clipboard.writeText(actionId).catch(() => {})
    setCopied(actionId)
    setTimeout(() => setCopied(null), 1500)
  }

  const complianceClass = (rate) => {
    if (rate >= 80) return "pass"
    if (rate >= 50) return "warn"
    return "fail"
  }

  if (status === "loading") {
    return (
      <div className="loading-card">
        <div className="spinner" />
        <p className="loading-text">Loading dashboard...</p>
      </div>
    )
  }

  if (status === "error") {
    return (
      <div className="input-card">
        <p className="error-msg">{error}</p>
        <button className="btn-run" onClick={fetchDashboard}>Retry</button>
      </div>
    )
  }

  return (
    <div className="dashboard">

      {/* Stat cards */}
      <div className="dashboard-stats">
        <div className="stat-card">
          <span className="stat-label">Total Audits</span>
          <span className="stat-value">{stats.total_audits}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Approved</span>
          <span className="stat-value pass">{stats.approved_count}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Rejected</span>
          <span className="stat-value fail">{stats.rejected_count}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Compliance Rate</span>
          <span className={`stat-value ${complianceClass(stats.compliance_rate)}`}>
            {stats.compliance_rate}%
          </span>
        </div>
      </div>

      {/* Action buttons */}
      <div className="dashboard-actions">
        <button className="btn-reset" onClick={fetchDashboard}>
          Refresh
        </button>
        <button
          className="btn-reset"
          onClick={handleExport}
          disabled={stats.total_audits === 0}
          title={stats.total_audits === 0 ? "Run audits first" : "Download CSV"}
        >
          Export CSV
        </button>
      </div>

      {/* Recent audits table */}
      {stats.recent_audits.length === 0 ? (
        <div className="dashboard-empty">
          No audits yet. Run an audit to see history here.
        </div>
      ) : (
        <div className="audit-table-wrap">
          <p className="audit-table-hint">Click a row to copy its Action ID</p>
          <table className="audit-table">
            <thead>
              <tr>
                <th>Action ID</th>
                <th>Amount</th>
                <th>Vendor</th>
                <th>Decision</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_audits.map((audit) => (
                <tr
                  key={audit.action_id}
                  className={`audit-row ${copied === audit.action_id ? "copied" : ""}`}
                  onClick={() => handleRowClick(audit.action_id)}
                  title={`Click to copy: ${audit.action_id}`}
                >
                  <td className="mono">
                    {copied === audit.action_id ? "Copied!" : truncate(audit.action_id)}
                  </td>
                  <td>₹{audit.amount}</td>
                  <td className="mono">{audit.vendor_id}</td>
                  <td className={audit.decision === "approved" ? "pass" : "fail"}>
                    {audit.decision === "approved" ? "✅ Approved" : "❌ Rejected"}
                  </td>
                  <td>{formatTime(audit.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  )
}

export default Dashboard
