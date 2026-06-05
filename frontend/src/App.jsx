import { Routes, Route, useNavigate } from "react-router-dom"
import ChatAgent from "./components/ChatAgent"
import LandingPage from "./components/LandingPage"
import AuditDashboardPage from "./components/AuditDashboardPage"
import SdkIntegration from "./components/SdkIntegration"
import OnboardPage from "./components/OnboardPage"
import "./index.css"

// Phase 2: point at the locally running FastAPI backend with v2 endpoints.
// Override via VITE_API_BASE at build/dev time if needed.
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000"

function AppShell() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-10 bg-[#0e0e0e] text-white font-sans">

      <header className="text-center mb-8 relative w-full max-w-2xl">
        <button
          onClick={() => navigate("/")}
          className="absolute left-0 top-0 flex items-center gap-1.5 text-xs text-[#484847] hover:text-[#adaaaa] transition-colors"
        >
          <span className="material-symbols-outlined text-sm">arrow_back</span>
          Home
        </button>
        <h1 className="headline text-3xl font-bold text-[#ff4f00] tracking-tight">AgentAudit</h1>
        <p className="mt-2 text-sm text-[#767575] font-label">Verifiable audit infrastructure for autonomous AI agents</p>
      </header>

      <main className="w-full max-w-2xl flex-1">
        <ChatAgent apiBase={API_BASE} />
      </main>

      <footer className="mt-12 text-xs text-[#2a2a2a] text-center font-mono tracking-wider uppercase">
        AgentAudit · AlgoBharat Hack Series 3.0 · Algorand Testnet
      </footer>

    </div>
  )
}

function LandingGate() {
  const navigate = useNavigate()
  return <LandingPage onEnterApp={() => navigate("/app")} />
}

function IntegratePage() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-10 bg-[#0e0e0e] text-white font-sans">
      <header className="text-center mb-8 relative w-full max-w-2xl">
        <button
          onClick={() => navigate("/")}
          className="absolute left-0 top-0 flex items-center gap-1.5 text-xs text-[#484847] hover:text-[#adaaaa] transition-colors"
        >
          <span className="material-symbols-outlined text-sm">arrow_back</span>
          Home
        </button>
        <h1 className="headline text-3xl font-bold text-[#ff4f00] tracking-tight">Integrate AgentAudit</h1>
        <p className="mt-2 text-sm text-[#767575] font-label">Drop the SDK into any agent — subscription or pay-per-call</p>
      </header>
      <main className="w-full max-w-2xl flex-1">
        <SdkIntegration />
      </main>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/"          element={<LandingGate />} />
      <Route path="/app"       element={<AppShell />} />
      <Route path="/dashboard" element={<AuditDashboardPage apiBase={API_BASE} />} />
      <Route path="/onboard"   element={<OnboardPage apiBase={API_BASE} />} />
      <Route path="/integrate" element={<IntegratePage />} />
      <Route path="*"          element={<LandingGate />} />
    </Routes>
  )
}

export default App
