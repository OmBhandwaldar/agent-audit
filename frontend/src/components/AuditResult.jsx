/**
 * AuditResult — renders the result state after a successful audit flow.
 * Receives the full result object as props from App.jsx.
 */

const IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"
const TX_EXPLORER = "https://testnet.explorer.perawallet.app/tx"

function truncate(str, maxLength = 24) {
  if (!str || str.length <= maxLength) return str
  return str.slice(0, maxLength) + "..."
}

function PolicyBadge({ value }) {
  const pass = value === "pass"
  return (
    <span className={pass ? "text-green-400 text-sm font-medium" : "text-red-400 text-sm font-medium"}>
      {pass ? "✅ Pass" : "❌ Fail"}
    </span>
  )
}

function ResultRow({ label, children }) {
  return (
    <div className="flex justify-between items-center py-2.5 border-b border-[#1a1f2e] last:border-0">
      <span className="text-xs text-slate-500 uppercase tracking-wider flex-shrink-0">{label}</span>
      <span className="text-right ml-4">{children}</span>
    </div>
  )
}

function AuditResult({ result, onReset, agentType }) {
  const isApproved = result.decision === "approved"
  const checks = result.policy_checks || {}

  return (
    <div className="bg-[#1e2130] border border-[#2d3248] rounded-xl p-8 flex flex-col gap-6">

      {/* Decision badge */}
      <div className={`text-center text-2xl font-bold py-4 rounded-lg border
        ${isApproved
          ? "bg-green-950 text-green-400 border-green-800"
          : "bg-red-950 text-red-400 border-red-900"
        }`}>
        {isApproved ? "✅ Approved" : "❌ Rejected"}
      </div>

      {/* Result rows */}
      <div className="flex flex-col">

        <ResultRow label="Amount Check">
          <PolicyBadge value={checks.amount_check} />
        </ResultRow>

        <ResultRow label="Vendor Check">
          <PolicyBadge value={checks.vendor_check} />
        </ResultRow>

        <ResultRow label="Agent Type">
          <span className="text-sm text-violet-400 font-medium">{agentType?.label || result.agent_type_id}</span>
        </ResultRow>

        <ResultRow label={agentType?.field2Label || "Vendor ID"}>
          <span className="font-mono text-xs text-slate-200">{result.vendor_id}</span>
        </ResultRow>

        <ResultRow label="Compliance Receipt">
          <span className={result.asa_minted ? "text-green-400 text-sm" : "text-slate-500 text-sm"}>
            {result.asa_minted ? "Minted (1 AACR)" : "Not applicable"}
          </span>
        </ResultRow>

        <ResultRow label="IPFS CID">
          <a
            className="font-mono text-xs text-violet-400 hover:text-violet-300 hover:underline"
            href={`${IPFS_GATEWAY}/${result.ipfs_cid}`}
            target="_blank"
            rel="noreferrer"
            title={result.ipfs_cid}
          >
            {truncate(result.ipfs_cid)}
          </a>
        </ResultRow>

        <ResultRow label="Algorand TX">
          <a
            className="font-mono text-xs text-violet-400 hover:text-violet-300 hover:underline"
            href={`${TX_EXPLORER}/${result.algorand_tx_id}`}
            target="_blank"
            rel="noreferrer"
            title={result.algorand_tx_id}
          >
            {truncate(result.algorand_tx_id)}
          </a>
        </ResultRow>

        <ResultRow label="Action ID">
          <span className="font-mono text-xs text-slate-200" title={result.action_id}>
            {result.action_id}
          </span>
        </ResultRow>

      </div>

      <button
        className="border border-[#2d3248] text-slate-500 rounded-lg py-3 text-sm hover:text-slate-200 hover:border-slate-500 transition-colors cursor-pointer w-full"
        onClick={onReset}
      >
        Run Again
      </button>
    </div>
  )
}

export default AuditResult
