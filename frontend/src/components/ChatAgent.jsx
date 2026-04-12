/**
 * ChatAgent — Tab 1 (Run Agent) replacement.
 *
 * Replaces the structured form with a chat interface.
 * User types a natural language task. The autonomous agent picks
 * a vendor and price, runs the full audit pipeline, and replies in chat.
 */

import { useState, useEffect, useRef } from "react"

const IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"
const TX_EXPLORER = "https://testnet.explorer.perawallet.app/tx"

const EXAMPLE_PROMPTS = [
  "Find a vendor for office electronics and finalize the payment",
  "Get the cheapest vendor available and pay them",
  "Find a premium vendor for high-quality parts",
]

function truncate(str, max = 20) {
  if (!str || str.length <= max) return str
  return str.slice(0, max) + "..."
}

function AuditSummary({ audit }) {
  const isApproved = audit.decision === "approved"
  return (
    <div className={`mt-3 rounded-lg border p-3 flex flex-col gap-2 text-xs
      ${isApproved ? "bg-green-950 border-green-800" : "bg-red-950 border-red-900"}`}>
      <div className="flex items-center gap-2">
        <span className={`font-bold text-sm ${isApproved ? "text-green-400" : "text-red-400"}`}>
          {isApproved ? "✅ Approved" : "❌ Rejected"}
        </span>
        <span className="text-slate-500">·</span>
        <span className="text-slate-400 font-mono">{audit.policy_result}</span>
      </div>
      <div className="flex flex-col gap-1 text-slate-400">
        <div className="flex gap-2">
          <span className="text-slate-500 w-20 shrink-0">IPFS</span>
          <a
            href={`${IPFS_GATEWAY}/${audit.ipfs_cid}`}
            target="_blank"
            rel="noreferrer"
            className="text-violet-400 hover:underline font-mono"
          >
            {truncate(audit.ipfs_cid)}
          </a>
        </div>
        <div className="flex gap-2">
          <span className="text-slate-500 w-20 shrink-0">Algorand</span>
          <a
            href={`${TX_EXPLORER}/${audit.algorand_tx_id}`}
            target="_blank"
            rel="noreferrer"
            className="text-violet-400 hover:underline font-mono"
          >
            {truncate(audit.algorand_tx_id)}
          </a>
        </div>
        <div className="flex gap-2">
          <span className="text-slate-500 w-20 shrink-0">Action ID</span>
          <span className="font-mono text-slate-300">{audit.action_id}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-slate-500 w-20 shrink-0">ASA Minted</span>
          <span className={audit.asa_minted ? "text-green-400" : "text-slate-500"}>
            {audit.asa_minted ? "1 AACR minted" : "Not minted"}
          </span>
        </div>
      </div>
    </div>
  )
}

function UserBubble({ text }) {
  return (
    <div className="flex justify-end">
      <div className="bg-violet-400 text-[#0f1117] rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[80%] text-sm font-medium">
        {text}
      </div>
    </div>
  )
}

function AgentBubble({ text, auditResult, loading }) {
  // Render **bold** markdown in agent reply
  const renderText = (raw) => {
    const parts = raw.split(/(\*\*[^*]+\*\*)/)
    return parts.map((part, i) =>
      part.startsWith("**") && part.endsWith("**")
        ? <strong key={i} className="text-slate-100">{part.slice(2, -2)}</strong>
        : <span key={i}>{part}</span>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="flex flex-col gap-1 max-w-[85%]">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-6 h-6 rounded-full bg-violet-400 flex items-center justify-center text-[10px] font-bold text-[#0f1117]">
            AI
          </div>
          <span className="text-xs text-slate-500">AgentAudit</span>
        </div>
        <div className="bg-[#1e2130] border border-[#2d3248] rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-slate-300 leading-relaxed">
          {loading ? (
            <div className="flex items-center gap-3">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
              <span className="text-slate-500 text-xs">Searching vendors and processing...</span>
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

function ChatAgent({ apiBase }) {
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "agent",
      text: "I'm your autonomous procurement agent. Tell me what you need — I'll find the right vendor, negotiate the price, and record everything on-chain.\n\nTry: \"Find a vendor for office electronics and finalize the payment\"",
      auditResult: null,
    },
  ])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

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

  return (
    <div className="flex flex-col bg-[#1e2130] border border-[#2d3248] rounded-xl overflow-hidden" style={{ height: "600px" }}>

      {/* Header */}
      <div className="px-5 py-3.5 border-b border-[#2d3248] flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-green-400" />
        <span className="text-sm font-semibold text-slate-200">Autonomous Procurement Agent</span>
        <span className="ml-auto text-xs text-slate-600">Groq · LLaMA 3.3 70B</span>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
        {messages.map(msg =>
          msg.role === "user"
            ? <UserBubble key={msg.id} text={msg.text} />
            : <AgentBubble key={msg.id} text={msg.text} auditResult={msg.auditResult} />
        )}
        {loading && <AgentBubble loading text="" />}
        <div ref={bottomRef} />
      </div>

      {/* Example prompts — shown only when no user messages yet */}
      {messages.filter(m => m.role === "user").length === 0 && (
        <div className="px-4 pb-2 flex flex-wrap gap-2">
          {EXAMPLE_PROMPTS.map(p => (
            <button
              key={p}
              onClick={() => sendMessage(p)}
              className="text-xs bg-[#161926] border border-[#2d3248] text-slate-400 rounded-full px-3 py-1.5 hover:border-violet-400 hover:text-violet-400 transition-colors cursor-pointer"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="px-4 pb-4 pt-2 border-t border-[#2d3248] flex gap-2">
        <input
          ref={inputRef}
          type="text"
          className="flex-1 bg-[#0f1117] border border-[#2d3248] rounded-xl px-4 py-3 text-sm text-slate-200 outline-none focus:border-violet-400 transition-colors placeholder:text-slate-600"
          placeholder="Tell the agent what to do..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          autoFocus
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
          className="bg-violet-400 text-[#0f1117] rounded-xl px-4 py-3 font-bold text-sm hover:bg-violet-300 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>

    </div>
  )
}

export default ChatAgent
