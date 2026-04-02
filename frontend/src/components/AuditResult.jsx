/**
 * AuditResult — renders the result state after a successful audit flow.
 * Receives the full result object as props from App.jsx.
 */

const IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"
const TX_EXPLORER = "https://testnet.explorer.perawallet.app/tx"

function truncate(str, maxLength = 20) {
  if (!str || str.length <= maxLength) return str
  return str.slice(0, maxLength) + "..."
}

function PolicyBadge({ value }) {
  const pass = value === "pass"
  return (
    <span className={`result-value ${pass ? "pass" : "fail"}`}>
      {pass ? "✅ Pass" : "❌ Fail"}
    </span>
  )
}

function AuditResult({ result, onReset }) {
  const isApproved = result.decision === "approved"
  const checks = result.policy_checks || {}

  return (
    <div className="result-card">

      {/* Decision badge */}
      <div className={`decision-badge ${isApproved ? "approved" : "rejected"}`}>
        {isApproved ? "✅ Approved" : "❌ Rejected"}
      </div>

      {/* Result rows */}
      <div className="result-rows">

        <div className="result-row">
          <span className="result-label">Amount Check</span>
          <PolicyBadge value={checks.amount_check} />
        </div>

        <div className="result-row">
          <span className="result-label">Vendor Check</span>
          <PolicyBadge value={checks.vendor_check} />
        </div>

        <div className="result-row">
          <span className="result-label">Vendor ID</span>
          <span className="result-value mono">{result.vendor_id}</span>
        </div>

        <div className="result-row">
          <span className="result-label">Compliance Receipt</span>
          <span className={`result-value ${result.asa_minted ? "pass" : "na"}`}>
            {result.asa_minted ? "Minted (1 AACR)" : "Not applicable"}
          </span>
        </div>

        <div className="result-row">
          <span className="result-label">IPFS CID</span>
          <a
            className="result-link"
            href={`${IPFS_GATEWAY}/${result.ipfs_cid}`}
            target="_blank"
            rel="noreferrer"
            title={result.ipfs_cid}
          >
            {truncate(result.ipfs_cid, 24)}
          </a>
        </div>

        <div className="result-row">
          <span className="result-label">Algorand TX</span>
          <a
            className="result-link"
            href={`${TX_EXPLORER}/${result.algorand_tx_id}`}
            target="_blank"
            rel="noreferrer"
            title={result.algorand_tx_id}
          >
            {truncate(result.algorand_tx_id, 24)}
          </a>
        </div>

        <div className="result-row">
          <span className="result-label">Action ID</span>
          <span className="result-value mono" title={result.action_id}>
            {result.action_id}
          </span>
        </div>

      </div>

      <button className="btn-reset" onClick={onReset}>
        Run Again
      </button>
    </div>
  )
}

export default AuditResult
