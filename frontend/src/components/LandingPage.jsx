/**
 * LandingPage — Production landing page for AgentAudit.
 * Design system: Material You dark · Space Grotesk headlines · Inter body.
 * Does NOT touch any existing app components.
 *
 * @param {function} onEnterApp - called when the user clicks "Initialize Audit"
 */

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import NavBar from "./NavBar"

/* ─── Hero ────────────────────────────────────────────────────────────────── */

function HeroSection({ onEnterApp }) {
  return (
    <section className="relative min-h-[88vh] flex flex-col items-center justify-center pt-28 pb-24 overflow-hidden bg-[#0e0e0e]">

      {/* Dot-grid background */}
      <div className="absolute inset-0 z-0 opacity-20 dot-grid pointer-events-none" />

      {/* Ambient blurs */}
      <div className="absolute bottom-1/3 left-1/4 w-[500px] h-[500px] bg-[#ff4f00]/10 blur-[130px] rounded-full pointer-events-none z-0" />
      <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] bg-[#26fedc]/5  blur-[140px] rounded-full pointer-events-none z-0" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-[#ff4f00]/8 blur-[120px] rounded-full pointer-events-none z-0" />

      {/* Content */}
      <div className="relative z-10 max-w-5xl px-6 text-center mt-16">

        {/* Pill badge */}
        {/* <div className="inline-flex items-center gap-2 bg-[#1a1919] border border-[#484847]/40 rounded-full px-4 py-1.5 mb-8 text-xs font-label font-medium text-[#adaaaa]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#26fedc] animate-pulse" />
          AlgoBharat Hack Series 3.0 · Round 2
        </div> */}

        <h1 className="headline text-5xl md:text-7xl lg:text-8xl font-bold tracking-tighter leading-[0.92] mb-8 text-white">
          SURVEIL YOUR <br />
          <span className="text-outlined">AUTONOMOUS</span> STACK
        </h1>

        <p className="max-w-2xl mx-auto text-white text-base md:text-lg mb-12 leading-relaxed font-body">
          AgentAudit provides tamper-proof observability for AI agents.
          Every decision and its entire trace is anchored on-chain via Algorand, independently
          verifiable, compliance-ready, and immutable by design.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button
            onClick={onEnterApp}
            className="w-full sm:w-auto bg-[#ff4f00] text-[#591800] px-8 py-4 rounded-lg font-bold text-base headline
              hover:scale-95 active:opacity-80 transition-all duration-200
              shadow-[0_8px_30px_-8px_rgba(255,79,0,0.45)]"
          >
            Initialize Audit
          </button>
          <a
            href="#how-it-works"
            className="w-full sm:w-auto bg-[#2c2c2c]/40 backdrop-blur-md border border-[#484847]/30
              text-white px-8 py-4 rounded-lg font-bold text-base headline
              hover:bg-[#2c2c2c]/60 transition-all duration-200"
          >
            See How It Works
          </a>
        </div>

        {/* Stat strip */}
        {/* <div className="mt-20 flex flex-col sm:flex-row items-center justify-center gap-6 sm:gap-12">
          {[
            { value: "< 2s",     label: "Audit latency"          },
            { value: "On-chain", label: "Tamper-proof records"   },
            { value: "IPFS",     label: "Off-chain evidence store"},
          ].map(({ value, label }) => (
            <div key={label} className="text-center">
              <div className="text-xl font-bold text-white headline tracking-tight">{value}</div>
              <div className="text-xs text-[#767575] mt-0.5 font-label uppercase tracking-wider">{label}</div>
            </div>
          ))}
        </div> */}

      </div>
    </section>
  )
}

/* ─── What it Does — Feature Cards ──────────────────────────────────────── */

const FEATURE_CARDS = [
  {
    icon: "receipt_long",
    title: "Audit Trail",
    description: "Every AI agent decision is captured in a tamper-proof log, timestamped, policy-checked, and anchored on Algorand forever.",
    highlight: true,
  },
  {
    icon: "verified",
    title: "Chain Verified",
    description: "Independent verifiers can check any audit record against the Algorand blockchain without trusting the deploying organization.",
  },
  {
    icon: "smart_toy",
    title: "Agent Memory",
    description: "LangChain-powered agents evaluate every transaction in real-time. Every tool call the agent makes — what it queried, what it returned — is captured as a structured reasoning trace inside the encrypted payload.",
  },
  {
    icon: "folder_open",
    title: "IPFS Evidence",
    description: "Full decision payloads are pinned to IPFS with SHA-256 fingerprints anchored on-chain for independent retrieval.",
  },
]

function FeatureCard({ icon, title, description }) {
  return (
    <div className="flex flex-col items-center text-center p-8 rounded-2xl bg-[#131313] border border-transparent hover:border-[#ff4f00]/60 transition-colors duration-200">
      <span
        className="material-symbols-outlined text-[40px] text-[#ff4f00] mb-5"
        style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
      >
        {icon}
      </span>
      <h3 className="headline text-lg font-bold text-white mb-3">{title}</h3>
      <p className="text-[#767575] text-sm leading-relaxed font-body">{description}</p>
    </div>
  )
}

function WhatItDoes() {
  return (
    <section className="py-20 bg-[#0e0e0e]">
      <div className="max-w-screen-xl mx-auto px-6 md:px-12">

        {/* Section header */}
        <div className="text-center mb-12">
          <h2 className="headline text-4xl md:text-5xl font-bold mb-4 text-white tracking-tighter">
            WHAT IT DOES
          </h2>
          <p className="text-[#adaaaa] text-base max-w-md mx-auto">
            From agent decision to on-chain proof — fully automated.
          </p>
        </div>

        {/* Cards row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURE_CARDS.map(card => (
            <FeatureCard key={card.title} {...card} />
          ))}
        </div>

      </div>
    </section>
  )
}

/* ─── How It Works ───────────────────────────────────────────────────────── */

const STEPS = [
  {
    num: "01",
    title: "Connect Stack",
    body: "Link your API provider and agent frameworks using our CLI or web-based dashboard. Works with LangChain, AutoGPT, CrewAI, and raw API calls.",
  },
  {
    num: "02",
    title: "Set Policies",
    body: "Define on-chain guardrails for cost limits, vendor whitelists, and agent behavior. Each policy is stored and enforced transparently.",
  },
  {
    num: "03",
    title: "Global Audit",
    body: "Every agent action triggers an immutable on-chain record and IPFS evidence packet. Verify any decision independently, at any time.",
  },
]

function HowItWorks() {
  return (
    <section id="how-it-works" className="py-28 bg-[#0e0e0e] relative overflow-hidden">
      {/* Ambient */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[300px] bg-[#ff4f00]/5 blur-[100px] rounded-full pointer-events-none" />

      <div className="max-w-screen-2xl mx-auto px-6 md:px-12 relative z-10">

        {/* Header */}
        <div className="text-center mb-20">
          <h2 className="headline text-4xl md:text-5xl font-bold mb-4 text-white tracking-tighter">
            DEPLOY IN SECONDS
          </h2>
          <p className="text-[#adaaaa] text-base max-w-md mx-auto">
            From development to high-availability production clusters.
          </p>
        </div>

        {/* Steps row */}
        <div className="flex flex-col md:flex-row items-stretch justify-between gap-10 md:gap-0 relative">
          {STEPS.map((step, i) => (
            <>
              <div key={step.num} className="relative flex-1 px-2 md:px-8">
                {/* Ghost large number */}
                <div className="absolute top-0 left-0 text-8xl md:text-9xl font-black text-[#262626]/80 -z-10 -mt-10 -ml-3 headline select-none">
                  {i + 1}
                </div>
                <div className="pt-8">
                  <h4 className="headline text-xl md:text-2xl font-bold mb-4 flex items-center gap-3 text-white">
                    <span className="w-8 h-8 rounded bg-[#ff4f00]/20 text-[#ff4f00] flex items-center justify-center text-xs font-label font-bold">
                      {step.num}
                    </span>
                    {step.title}
                  </h4>
                  <p className="text-[#adaaaa] leading-relaxed text-sm">
                    {step.body}
                  </p>
                </div>
              </div>
              {/* Connector beam between steps */}
              {i < STEPS.length - 1 && (
                <div key={`beam-${i}`} className="hidden md:flex flex-col justify-center items-center w-20 shrink-0">
                  <div className="step-beam w-full opacity-25" />
                </div>
              )}
            </>
          ))}
        </div>

        {/* Visual accent banner */}
        

      </div>
    </section>
  )
}

/* ─── Install / Quick-start terminal ─────────────────────────────────────── */

const INSTALL_TABS = ["API", "SDK", "Middleware/Decorator"]

const INSTALL_COMMANDS = {
  "API": {
    windows: `curl -X POST https://api.agentaudit.io/v1/audit ^^\n  -H "Authorization: Bearer <token>" ^^\n  -d "{ \\"amount\\": 3000, \\"vendor_id\\": \\"VENDOR_001\\" }"`,
    unix:    `curl -X POST https://api.agentaudit.io/v1/audit \\\n  -H "Authorization: Bearer <token>" \\\n  -d '{ "amount": 3000, "vendor_id": "VENDOR_001" }'`,
  },
  "SDK": {
    windows: `pip install agentaudit`,
    unix:    `pip install agentaudit`,
  },
  "Middleware/Decorator": {
    windows: `from agentaudit import audit_action\n\n@audit_action(policy="limit_5000", vendor_id="VENDOR_001")\ndef approve_payment(amount: int) -> str:\n    return "approved" if amount < 5000 else "rejected"`,
    unix:    `from agentaudit import audit_action\n\n@audit_action(policy="limit_5000", vendor_id="VENDOR_001")\ndef approve_payment(amount: int) -> str:\n    return "approved" if amount < 5000 else "rejected"`,
  },
}

const INSTALL_COMMENTS = {
  "API":                  "# Hit the REST API directly from any language or tool.",
  "SDK":                  "# Install the Python SDK — LangChain + Algorand + IPFS wired in.",
  "Middleware/Decorator": "# Wrap any function — audit records written automatically on every call.",
}

function InstallSection() {
  const [activeTab, setActiveTab] = useState("API")
  const [os, setOs]               = useState("windows")
  const [copied, setCopied]       = useState(false)

  const command = INSTALL_COMMANDS[activeTab][os]
  const comment = INSTALL_COMMENTS[activeTab]

  const handleCopy = () => {
    navigator.clipboard.writeText(command).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <section className="py-20 bg-[#0e0e0e]">
      <div className="max-w-3xl mx-auto px-6 md:px-12">

        {/* Section label */}
        <div className="text-center mb-10">
          <h2 className="headline text-4xl md:text-5xl font-bold tracking-tighter text-white mb-3">
            GET STARTED <span className="text-[#ff4f00]">FAST</span>
          </h2>
          <p className="text-[#adaaaa] text-sm max-w-md mx-auto">
            One command to install, one endpoint to audit. No infrastructure to manage.
          </p>
        </div>

        {/* Terminal window */}
        <div className="rounded-xl overflow-hidden border border-[#2a2a2a] terminal-glow bg-[#131313]">

          {/* Title bar */}
          <div className="flex items-center justify-between px-4 py-3 bg-[#1a1919] border-b border-[#252525]">

            {/* Traffic lights */}
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
              <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
              <div className="w-3 h-3 rounded-full bg-[#28c840]" />
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-1">
              {INSTALL_TABS.map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 rounded-full text-xs font-semibold font-label transition-all duration-150 cursor-pointer
                    ${activeTab === tab
                      ? "bg-[#26fedc] text-[#005d4f]"
                      : "text-[#767575] hover:text-white"
                    }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* OS switcher + beta badge */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setOs("unix")}
                className={`px-3 py-1 rounded-full text-xs font-semibold font-label transition-all duration-150 cursor-pointer
                  ${os === "unix" ? "bg-[#ff4f00] text-[#591800]" : "text-[#767575] hover:text-white"}`}
              >
                Langchain
              </button>
              <button
                onClick={() => setOs("windows")}
                className={`px-3 py-1 rounded-full text-xs font-semibold font-label transition-all duration-150 cursor-pointer
                  ${os === "windows" ? "bg-[#ff4f00] text-[#591800]" : "text-[#767575] hover:text-white"}`}
              >
                CrewAI
              </button>
              {/* <span className="text-[10px] font-mono text-[#767575] border border-[#484847]/40 rounded px-1.5 py-0.5">
                β BETA
              </span> */}
            </div>

          </div>

          {/* Terminal body */}
          <div className="px-6 py-6 relative group min-h-[120px]">

            {/* Comment line */}
            <p className="font-mono text-[13px] text-[#767575] mb-3 select-none">
              {comment}
            </p>

            {/* Command lines */}
            <div className="font-mono text-[13px] text-white leading-relaxed whitespace-pre">
              {command.split("\n").map((line, i) => (
                <div key={i} className="flex items-start gap-2">
                  {i === 0 && (
                    <span className="text-[#ff4f00] select-none shrink-0">$</span>
                  )}
                  {i > 0 && (
                    <span className="text-[#484847] select-none shrink-0 w-3"> </span>
                  )}
                  <span>{line}</span>
                </div>
              ))}
            </div>

            {/* Copy button */}
            <button
              onClick={handleCopy}
              title="Copy to clipboard"
              className={`absolute top-5 right-5 w-8 h-8 rounded-lg border flex items-center justify-center
                transition-all duration-150 cursor-pointer
                ${copied
                  ? "bg-[#26fedc]/20 border-[#26fedc]/40 text-[#26fedc]"
                  : "bg-[#1a1919] border-[#2a2a2a] text-[#767575] hover:border-[#484847] hover:text-white"
                }`}
            >
              <span className="material-symbols-outlined text-sm">
                {copied ? "check" : "content_copy"}
              </span>
            </button>

          </div>
        </div>

        {/* Footnote */}
        <p className="text-center text-[10px] font-mono text-[#484847] mt-4 tracking-wider uppercase">
          Algorand · IPFS · Agent runtime
        </p>

      </div>
    </section>
  )
}

/* ─── CTA ─────────────────────────────────────────────────────────────────── */

function CTASection({ onEnterApp }) {
  return (
    <section className="py-24 px-6 md:px-12 max-w-screen-2xl mx-auto">
      <div className="bg-gradient-to-br from-[#201f1f] to-[#1a1919] rounded-[2rem] p-10 md:p-20 relative overflow-hidden text-center border border-[#484847]/12">

        {/* Decorative radar icon */}
        <div className="absolute top-0 right-0 p-6 md:p-8 select-none pointer-events-none">
          <span className="material-symbols-outlined text-[#ff4f00]/8 text-[160px] md:text-[200px]">radar</span>
        </div>

        {/* Ambient glow */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[600px] h-[300px] bg-[#ff4f00]/5 blur-[80px] rounded-full" />
        </div>

        <h2 className="headline text-4xl md:text-6xl lg:text-7xl font-bold mb-6 relative z-10 tracking-tighter text-white">
          READY TO <span className="text-[#ff4f00]">INITIALIZE</span>?
        </h2>
        <p className="text-white text-base md:text-xl mb-10 max-w-lg mx-auto relative z-10 leading-relaxed">
          The autonomous future requires verifiable oversight. Deploy AgentAudit
          today and make every AI decision auditable.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-5 relative z-10">
          <button
            onClick={onEnterApp}
            className="w-full sm:w-auto bg-[#ff4f00] text-[#591800] px-10 py-4 rounded-lg font-bold text-base headline
              hover:scale-95 active:opacity-80 transition-all duration-200
              shadow-[0_8px_30px_-8px_rgba(255,79,0,0.45)]"
          >
            Initialize Audit Now
          </button>
          {/* <button className="text-white hover:text-[#ff4f00] transition-colors font-bold text-base headline flex items-center gap-2">
            Read Case Studies
            <span className="material-symbols-outlined text-base">arrow_forward</span>
          </button> */}
        </div>
      </div>
    </section>
  )
}

/* ─── Footer ─────────────────────────────────────────────────────────────── */

function Footer() {
  const colLinks = [
    ["Documentation", "Security", "Status"],
    ["Privacy Policy", "Terms of Service"],
  ]

  return (
    <footer className="w-full border-t border-[#484847]/20 bg-neutral-950 font-body text-sm">
      <div className="flex flex-col md:flex-row justify-between items-center px-6 md:px-12 py-14 max-w-screen-2xl mx-auto gap-10 md:gap-0">

        {/* Brand */}
        <div>
          <div className="text-xl font-black text-white mb-3 headline">
            AgentAudit<span className="text-[#ff4f00]">.</span>
          </div>
          {/* <div className="text-[#767575] text-xs">
            © 2024 AgentAudit. AlgoBharat Hack Series 3.0.
          </div> */}
        </div>

        {/* Links */}
        <div className="flex flex-wrap justify-center gap-8 md:gap-14">
          {colLinks.map((col, ci) => (
            <div key={ci} className="flex flex-col gap-3">
              {col.map(link => (
                <a
                  key={link}
                  href="#"
                  className="text-[#767575] hover:text-white transition-colors duration-200 text-xs"
                >
                  {link}
                </a>
              ))}
            </div>
          ))}
        </div>

        {/* Social icon buttons */}
        <div className="flex gap-3">
          {["terminal", "code"].map(icon => (
            <a
              key={icon}
              href="#"
              className="w-10 h-10 rounded-full border border-[#484847]/30 flex items-center justify-center
                hover:bg-[#ff4f00]/10 hover:border-[#ff4f00]/40 hover:text-[#ff4f00]
                text-[#767575] transition-all duration-200"
            >
              <span className="material-symbols-outlined text-base">{icon}</span>
            </a>
          ))}
        </div>

      </div>
    </footer>
  )
}

/* ─── Root export ─────────────────────────────────────────────────────────── */

function LandingPage({ onEnterApp }) {
  return (
    <div className="min-h-screen flex flex-col bg-[#0e0e0e] text-white">
      <NavBar    onEnterApp={onEnterApp} />
      <main className="flex-1">
        <HeroSection onEnterApp={onEnterApp} />
        <WhatItDoes />
        <HowItWorks />
        <InstallSection />
        <CTASection  onEnterApp={onEnterApp} />
      </main>
      <Footer />
    </div>
  )
}

export default LandingPage
