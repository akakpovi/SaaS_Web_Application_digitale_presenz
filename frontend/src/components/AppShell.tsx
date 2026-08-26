import React, { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import {
  LayoutDashboard, Globe, Activity, Bell, FileText,
  Star, Settings, ChevronRight, Menu, ChevronDown, LogOut,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const nav = [
  { label: "Overview",   icon: LayoutDashboard, path: "/app/dashboard" },
  { label: "Websites",   icon: Globe,           path: "/app/websites" },
  { label: "Monitoring", icon: Activity,        path: "/app/monitoring" },
  { label: "Reviews",    icon: Star,            path: "/app/reviews" },
  { label: "Reports",    icon: FileText,        path: "/app/reports" },
  { label: "Alerts",     icon: Bell,            path: "/app/alerts" },
];

const LANGUAGES = [
  { code: "en", label: "EN", full: "English" },
  { code: "fr", label: "FR", full: "Français" },
  { code: "de", label: "DE", full: "Deutsch" },
  { code: "es", label: "ES", full: "Español" },
];

function Logo({ collapsed }: { collapsed?: boolean }) {
  return (
    <Link to="/app/dashboard" className="flex items-center gap-2.5 group">
      <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-700 transition-colors">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="white" strokeWidth="1.5" opacity="0.5" />
          <circle cx="8" cy="8" r="3" fill="white" />
          <path d="M8 2v2M8 12v2M2 8h2M12 8h2" stroke="white" strokeWidth="1.5" strokeLinecap="round" opacity="0.7" />
        </svg>
      </div>
      {!collapsed && <span className="font-bold text-slate-900 text-base tracking-tight">Presence</span>}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed,   setCollapsed]   = useState(false);
  const [langOpen,    setLangOpen]    = useState(false);
  const [userOpen,    setUserOpen]    = useState(false);
  const [lang, setLang] = useState(() => localStorage.getItem("presence_lang") ?? "en");

  useEffect(() => {
    const handler = () => setLang(localStorage.getItem("presence_lang") ?? "en");
    window.addEventListener("presence_lang_change", handler);
    return () => window.removeEventListener("presence_lang_change", handler);
  }, []);

  useEffect(() => {
    const close = () => { setLangOpen(false); setUserOpen(false); };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  const handleLangChange = (code: string) => {
    setLang(code);
    localStorage.setItem("presence_lang", code);
    window.dispatchEvent(new Event("presence_lang_change"));
    setLangOpen(false);
  };

  const handleLogout = async () => {
    setUserOpen(false);
    try { await logout(); } catch { /* finally dans AuthContext garantit setUser(null) */ }
    navigate("/login", { replace: true });
  };

  const initials = user?.full_name
    ?.split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2) ?? "?";

  const currentLang = LANGUAGES.find((l) => l.code === lang) ?? LANGUAGES[0];

  return (
    <div className="flex h-full bg-slate-50">
      <Helmet><meta name="robots" content="noindex,nofollow" /></Helmet>

      {sidebarOpen && (
        <div className="fixed inset-0 z-20 bg-slate-900/40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-30 flex flex-col bg-white border-r border-slate-200 transition-all duration-300
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0 lg:static lg:z-auto
        ${collapsed ? "w-16" : "w-56"}`}>

        <div className={`flex items-center p-4 h-16 border-b border-slate-100 ${collapsed ? "justify-center" : "justify-between"}`}>
          <Logo collapsed={collapsed} />
          {!collapsed && (
            <button onClick={() => setCollapsed(true)}
              className="hidden lg:flex w-7 h-7 items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100">
              <ChevronRight size={14} />
            </button>
          )}
          {collapsed && (
            <button onClick={() => setCollapsed(false)}
              className="hidden lg:flex absolute -right-3 top-7 w-6 h-6 items-center justify-center rounded-full bg-white border border-slate-200 text-slate-400 shadow-sm">
              <ChevronRight size={12} style={{ transform: "rotate(180deg)" }} />
            </button>
          )}
        </div>

        <nav className="flex-1 py-3 px-2 overflow-y-auto">
          <div className="flex flex-col gap-0.5">
            {nav.map(({ label, icon: Icon, path }) => {
              const active = location.pathname.startsWith(path);
              return (
                <Link key={path} to={path} onClick={() => setSidebarOpen(false)}
                  title={collapsed ? label : undefined}
                  className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all
                    ${active ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}
                    ${collapsed ? "justify-center" : ""}`}>
                  <Icon size={18} className="flex-shrink-0" />
                  {!collapsed && <span>{label}</span>}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="p-2 border-t border-slate-100 flex flex-col gap-0.5">
          <Link to="/app/settings"
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-50 transition-all ${collapsed ? "justify-center" : ""}`}>
            <Settings size={18} />
            {!collapsed && <span>Settings</span>}
          </Link>

          <button onClick={handleLogout} title={collapsed ? "Sign out" : undefined}
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-red-50 hover:text-red-600 transition-all ${collapsed ? "justify-center" : ""}`}>
            <LogOut size={18} />
            {!collapsed && <span>Sign out</span>}
          </button>

          {!collapsed && (
            <div className="mt-2 p-3 bg-slate-50 rounded-xl flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-indigo-700">{initials}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-900 truncate">{user?.full_name ?? "—"}</p>
                <p className="text-xs text-slate-500 truncate">{user?.email ?? ""}</p>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-16 bg-white border-b border-slate-200 flex items-center px-4 lg:px-6 gap-4 flex-shrink-0">
          <button onClick={() => setSidebarOpen(true)}
            className="lg:hidden w-8 h-8 flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100">
            <Menu size={20} />
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-2">

            {/* Sélecteur langue */}
            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button onClick={() => { setLangOpen(!langOpen); setUserOpen(false); }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 hover:bg-slate-100 transition-colors">
                <Globe size={14} className="text-slate-400" />
                <span className="text-xs font-semibold text-slate-700">{currentLang.label}</span>
                <ChevronDown size={12} className={`text-slate-400 transition-transform ${langOpen ? "rotate-180" : ""}`} />
              </button>
              {langOpen && (
                <div className="absolute right-0 top-full mt-1 w-36 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-50">
                  {LANGUAGES.map((l) => (
                    <button key={l.code} onClick={() => handleLangChange(l.code)}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors text-left ${lang === l.code ? "bg-indigo-50 text-indigo-700 font-semibold" : "text-slate-700 hover:bg-slate-50"}`}>
                      {lang === l.code ? "✓ " : "  "}{l.full}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Menu utilisateur */}
            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button onClick={() => { setUserOpen(!userOpen); setLangOpen(false); }}
                className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-slate-100 transition-colors">
                <div className="w-7 h-7 bg-indigo-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-bold text-indigo-700">{initials}</span>
                </div>
                <ChevronDown size={12} className={`text-slate-400 transition-transform ${userOpen ? "rotate-180" : ""}`} />
              </button>
              {userOpen && (
                <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-50">
                  <div className="px-3 py-2 border-b border-slate-100">
                    <p className="text-xs font-semibold text-slate-900 truncate">{user?.full_name ?? "—"}</p>
                    <p className="text-xs text-slate-500 truncate">{user?.email ?? ""}</p>
                  </div>
                  <Link to="/app/settings" onClick={() => setUserOpen(false)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors">
                    <Settings size={14} /> Settings
                  </Link>
                  <button onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors">
                    <LogOut size={14} /> Sign out
                  </button>
                </div>
              )}
            </div>

          </div>
        </header>
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
