/**
 * NavBar — shared floating pill navbar.
 * Used on LandingPage (/) and AuditDashboardPage (/dashboard).
 *
 * @param {function} [onEnterApp] - called when "Log in" is clicked.
 *   If omitted, falls back to navigating to /app via React Router.
 */

import { useState, useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"

const NAV_LINKS = [
  { label: "Features",     to: null,            hash: true  },
  { label: "How it Works", to: "#how-it-works",  hash: true  },
  { label: "Dashboard",    to: "/dashboard",     hash: false },
]

function NavBar({ onEnterApp }) {
  const navigate   = useNavigate()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  const handleLogin = onEnterApp ?? (() => navigate("/app"))

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex justify-center pt-4 px-4 pointer-events-none">
      <nav
        className={`pointer-events-auto flex items-center gap-2 md:gap-6 px-3 py-2.5 rounded-full
          border transition-all duration-300 select-none
          ${scrolled
            ? "bg-[#111116]/95 backdrop-blur-2xl border-[#2e2e36] shadow-[0_8px_40px_-12px_rgba(0,0,0,0.7)]"
            : "bg-[#111116]/80 backdrop-blur-xl border-[#2a2a32]"
          }`}
      >

        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 pr-3 md:pr-5 border-r border-[#2a2a32] no-underline">
          <div className="w-7 h-7 rounded-lg bg-[#1e1e28] border border-[#3a3a48] flex items-center justify-center shrink-0">
            <span
              className="material-symbols-outlined text-[14px] text-[#ff4f00]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              deployed_code
            </span>
          </div>
          <span className="headline font-bold text-white text-sm tracking-tight whitespace-nowrap">
            AgentAudit<span className="text-[#ff4f00]">.</span>
          </span>
        </Link>

        {/* Links */}
        <div className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map(({ label, to, hash }) => {
            const cls = `px-3 py-1.5 rounded-full text-sm font-label font-medium transition-all duration-150
              text-[#adaaaa] hover:text-white hover:bg-white/5 cursor-pointer`
            if (!hash && to) {
              return <Link key={label} to={to} className={cls}>{label}</Link>
            }
            return <a key={label} href={to ?? "#"} className={cls}>{label}</a>
          })}
        </div>

        {/* CTA */}
        <button
          onClick={handleLogin}
          className="ml-1 bg-[#ff4f00] text-[#591800] px-4 py-2 rounded-full font-bold text-sm headline
            hover:scale-95 active:opacity-80 transition-all duration-200 whitespace-nowrap
            shadow-[0_0_20px_-4px_rgba(255,79,0,0.55)] cursor-pointer"
        >
          Log in
        </button>

      </nav>
    </div>
  )
}

export default NavBar
