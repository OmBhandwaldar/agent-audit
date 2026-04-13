/**
 * ChatAgent — Tab 1 (Run Agent).
 * Restyled to match LandingPage design system:
 * #0e0e0e bg · #ff4f00 primary · Space Grotesk headlines · Inter body.
 */

import { useState, useEffect, useRef } from "react"

const IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"
const TX_EXPLORER  = "https://testnet.explorer.perawallet.app/tx"

const EXAMPLE_PROMPTS = [
  "Find a vendor for office electronics and finalize the payment",
  "Get the cheapest vendor available and pay them",
  "Find a premium vendor for high-quality parts",
]

function truncate(str, max = 20) {
  if (!str || str.length <= max) return str
  return str.slice(0, max) + "…"
}

/* ─── Audit summary card ─────────────────────────────────────────────────── */

function AuditSummary({ audit }) {
  const approved = audit.decision === "approved"
  return (
    <div className="mt-3 rounded-xl border border-[#2a2a2a] bg-[#0e0e0e] p-4 flex flex-col gap-3">

      {/* Decision badge */}
      <div className="flex items-center gap-2.5">
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold font-label border
          ${approved
            ? "bg-[#26fedc]/8 text-[#26fedc] border-[#26fedc]/20"
            : "bg-[#ff4f00]/8 text-[#ff4f00]  border-[#ff4f00]/20"
          }`}>
          <span className="material-symbols-outlined text-[10px]"
            style={{ fontVariationSettings: "'FILL' 1" }}>
            {approved ? "check_circle" : "cancel"}
          </span>
          {approved ? "Approved" : "Rejected"}
        </span>
        <span className="font-mono text-[10px] text-[#484847]">{audit.policy_result}</span>
      </div>

      {/* Links grid */}
      <div className="grid grid-cols-[72px_1fr] gap-x-3 gap-y-1.5 text-[11px]">
        <span className="text-[#767575] font-label uppercase tracking-wider self-center">IPFS</span>
        <a href={`${IPFS_GATEWAY}/${audit.ipfs_cid}`} target="_blank" rel="noreferrer"
          className="font-mono text-[#ff4f00]/70 hover:text-[#ff4f00] transition-colors truncate">
          {truncate(audit.ipfs_cid, 24)}
        </a>

        <span className="text-[#767575] font-label uppercase tracking-wider self-center">Algorand</span>
        <a href={`${TX_EXPLORER}/${audit.algorand_tx_id}`} target="_blank" rel="noreferrer"
          className="font-mono text-[#ff4f00]/70 hover:text-[#ff4f00] transition-colors truncate">
          {truncate(audit.algorand_tx_id, 24)}
        </a>

        <span className="text-[#767575] font-label uppercase tracking-wider self-center">Action ID</span>
        <span className="font-mono text-[#adaaaa] truncate">{audit.action_id}</span>

        <span className="text-[#767575] font-label uppercase tracking-wider self-center">Receipt</span>
        <span className={`font-label font-medium ${audit.asa_minted ? "text-[#26fedc]" : "text-[#484847]"}`}>
          {audit.asa_minted ? "1 AACR minted" : "Not minted"}
        </span>
      </div>
    </div>
  )
}

/* ─── Message bubbles ────────────────────────────────────────────────────── */

function UserBubble({ text }) {
  return (
    <div className="flex justify-end">
      <div className="bg-[#ff4f00] text-white rounded-2xl rounded-tr-sm px-4 py-2.5
        max-w-[78%] text-sm font-label font-medium leading-relaxed
        shadow-[0_4px_20px_-6px_rgba(255,79,0,0.45)]">
        {text}
      </div>
    </div>
  )
}

function AgentBubble({ text, auditResult, loading }) {
  const renderText = (raw) => {
    const parts = raw.split(/(\*\*[^*]+\*\*)/)
    return parts.map((part, i) =>
      part.startsWith("**") && part.endsWith("**")
        ? <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>
        : <span key={i}>{part}</span>
    )
  }

  return (
    <div className="flex justify-start gap-2.5">

      {/* Avatar */}
      <div className="w-7 h-7 rounded-lg bg-[#ff4f00]/15 border border-[#ff4f00]/25
        flex items-center justify-center shrink-0 mt-0.5">
        <span className="material-symbols-outlined text-[13px] text-[#ff4f00]"
          style={{ fontVariationSettings: "'FILL' 1" }}>
          smart_toy
        </span>
      </div>

      <div className="flex flex-col gap-1 max-w-[84%]">
        <span className="text-[10px] text-[#767575] font-label uppercase tracking-wider mb-0.5">
          AgentAudit
        </span>

        <div className="bg-[#131313] border border-[#2a2a2a] rounded-2xl rounded-tl-sm
          px-4 py-3 text-sm text-[#adaaaa] leading-relaxed font-body">
          {loading ? (
            <div className="flex items-center gap-3 py-0.5">
              <div className="flex gap-1">
                {[0, 150, 300].map(delay => (
                  <span key={delay}
                    className="w-1.5 h-1.5 bg-[#ff4f00] rounded-full animate-bounce"
                    style={{ animationDelay: `${delay}ms` }}
                  />
                ))}
              </div>
              <span className="text-[#767575] text-xs">Searching vendors and processing…</span>
            </div>
          ) : (
            renderText(text)
          )}
        </div>

        {auditResult && <AuditSummary audit={auditResult} />}
      </div>

    </div>
  )
}

/* ─── Main component ─────────────────────────────────────────────────────── */

function ChatAgent({ apiBase }) {
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "agent",
      text: "I'm your autonomous procurement agent. Tell me what you need — I'll find the right vendor and negotiate the price.",
      auditResult: null,
    },
  ])
  const [input,   setInput]   = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  const sendMessage = async (text) => {
    const userText = text.trim()
    if (!userText || loading) return

    setInput("")
    setMessages(prev => [...prev, { id: Date.now(), role: "user", text: userText }])
    setLoading(true)

    try {
      const response = await fetch(`${apiBase}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText, agent_type_id: "payment_approval" }),
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || "Request failed")
      }
      const data = await response.json()
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "agent",
        text: data.reply,
        auditResult: data.audit_result,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "agent",
        text: `Something went wrong: ${err.message}`,
        auditResult: null,
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const hasUserMessages = messages.some(m => m.role === "user")

  return (
    <div className="flex flex-col rounded-2xl overflow-hidden border border-[#2a2a2a] bg-[#0e0e0e]
      shadow-[0_0_40px_-10px_rgba(255,79,0,0.12)]"
      style={{ height: "600px" }}>

      {/* ── Header ── */}
      <div className="px-5 py-3.5 bg-[#0a0a0a] border-b border-[#1a1919] flex items-center gap-3 shrink-0">
        {/* Traffic lights */}
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
          <div className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
          <div className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        </div>

        <div className="w-px h-4 bg-[#2a2a2a] mx-1" />

        <span className="text-sm font-semibold text-white headline tracking-tight">
          Autonomous Procurement Agent
        </span>

        <div className="ml-auto flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#28c840] animate-pulse" />
          {/* <span className="text-[10px] text-[#767575] font-mono">Groq · LLaMA 3.3 70B</span> */}
        </div>
      </div>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-5">
        {messages.map(msg =>
          msg.role === "user"
            ? <UserBubble    key={msg.id} text={msg.text} />
            : <AgentBubble   key={msg.id} text={msg.text} auditResult={msg.auditResult} />
        )}
        {loading && <AgentBubble loading text="" />}
        <div ref={bottomRef} />
      </div>

      {/* ── Example prompts ── */}
      {!hasUserMessages && (
        <div className="px-5 pb-3 flex flex-wrap gap-2 shrink-0">
          {EXAMPLE_PROMPTS.map(p => (
            <button
              key={p}
              onClick={() => sendMessage(p)}
              className="text-[11px] font-label bg-[#131313] border border-[#2a2a2a]
                text-[#767575] rounded-full px-3 py-1.5
                hover:border-[#ff4f00]/40 hover:text-[#ff4f00]
                transition-all duration-150 cursor-pointer"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* ── Input bar ── */}
      <div className="px-4 pb-4 pt-3 border-t border-[#1a1919] flex gap-2 shrink-0 bg-[#0a0a0a]">
        <input
          ref={inputRef}
          type="text"
          className="flex-1 bg-[#131313] border border-[#2a2a2a] rounded-xl px-4 py-3
            text-sm text-white font-body outline-none
            focus:border-[#ff4f00]/50 transition-colors duration-150
            placeholder:text-[#484847]
            disabled:opacity-50"
          placeholder="Tell the agent what to do…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          autoFocus
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
          className="bg-[#ff4f00] text-white rounded-xl px-5 py-3 font-bold text-sm headline
            hover:scale-95 active:opacity-80 transition-all duration-150 cursor-pointer
            disabled:opacity-30 disabled:cursor-not-allowed disabled:scale-100
            shadow-[0_4px_16px_-4px_rgba(255,79,0,0.5)]"
        >
          <span className="material-symbols-outlined text-base" style={{ fontVariationSettings: "'FILL' 1" }}>
            send
          </span>
        </button>
      </div>

    </div>
  )
}

export default ChatAgent
