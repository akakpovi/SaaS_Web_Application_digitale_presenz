import React, { useState, useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import {
  LayoutDashboard, Globe, Activity, Bell, FileText,
  Star, Settings, ChevronRight, Menu, ChevronDown, LogOut,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";

const NAV_KEYS = [
  { key: "nav.overview",   icon: LayoutDashboard, path: "/app/dashboard" },
  { key: "nav.websites",   icon: Globe,           path: "/app/websites" },
  { key: "nav.monitoring", icon: Activity,        path: "/app/monitoring" },
  { key: "nav.reviews",    icon: Star,            path: "/app/reviews" },
  { key: "nav.reports",    icon: FileText,        path: "/app/reports" },
  { key: "nav.alerts",     icon: Bell,            path: "/app/alerts" },
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
      {!collapsed && (
        <span className="font-bold text-slate-900 text-base tracking-tight">Presence</span>
      )}
    </Link>
  );
}

// ─── Dropdown générique — s'auto-ferme proprement ─────────────────────────────
function useDropdown() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    // mousedown capture phase — avant que React traite les clics internes
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return { open, setOpen, ref };
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const location  = useLocation();
  const navigate  = useNavigate();
  const { user, logout } = useAuth();
  const { lang, setLang: setLangCtx, t } = useLang();

  const nav = NAV_KEYS.map(({ key, icon, path }) => ({
    label: t(key), icon, path,
  }));

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed,   setCollapsed]   = useState(false);
// Dropdowns indépendants avec fermeture propre
  const langDropdown = useDropdown();
  const userDropdown = useDropdown();

  // Sync langue si changée depuis Settings
  useEffect(() => {
    const handler = () => {
      setLangCtx((localStorage.getItem("presence_lang") ?? "en") as import("../i18n").Lang);
    };
    window.addEventListener("presence_lang_change", handler);
    return () => window.removeEventListener("presence_lang_change", handler);
  }, []);

  const handleLangChange = (code: string) => {
    setLangCtx(code as import("../i18n").Lang);
    langDropdown.setOpen(false);
  };

  const handleLogout = async () => {
    userDropdown.setOpen(false);
    try { await logout(); } catch { /* AuthContext gère setUser(null) */ }
    navigate("/login", { replace: true });
  };

  const initials = user?.full_name
    ?.split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) ?? "?";

  const currentLang = LANGUAGES.find((l) => l.code === lang) ?? LANGUAGES[0];

  return (
    <div className="flex h-full bg-slate-50">
      <Helmet>
        <meta name="robots" content="noindex,nofollow" />
      </Helmet>

      {/* Overlay mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-slate-900/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-30 flex flex-col bg-white border-r border-slate-200
          transition-all duration-300
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          lg:translate-x-0 lg:static lg:z-auto
          ${collapsed ? "w-16" : "w-56"}
        `}
      >
        {/* Logo */}
        <div
          className={`flex items-center p-4 h-16 border-b border-slate-100 ${
            collapsed ? "justify-center" : "justify-between"
          }`}
        >
          <Logo collapsed={collapsed} />
          {!collapsed && (
            <button
              onClick={() => setCollapsed(true)}
              className="hidden lg:flex w-7 h-7 items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
            >
              <ChevronRight size={14} />
            </button>
          )}
          {collapsed && (
            <button
              onClick={() => setCollapsed(false)}
              className="hidden lg:flex absolute -right-3 top-7 w-6 h-6 items-center justify-center rounded-full bg-white border border-slate-200 text-slate-400 shadow-sm"
            >
              <ChevronRight size={12} style={{ transform: "rotate(180deg)" }} />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 overflow-y-auto">
          <div className="flex flex-col gap-0.5">
            {nav.map(({ label, icon: Icon, path }) => {
              const active = location.pathname.startsWith(path);
              return (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setSidebarOpen(false)}
                  title={collapsed ? label : undefined}
                  className={`
                    flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium
                    transition-all
                    ${active
                      ? "bg-indigo-50 text-indigo-700"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}
                    ${collapsed ? "justify-center" : ""}
                  `}
                >
                  <Icon size={18} className="flex-shrink-0" />
                  {!collapsed && <span>{label}</span>}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Bas sidebar */}
        <div className="p-2 border-t border-slate-100 flex flex-col gap-0.5">
          <Link
            to="/app/settings"
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium
              text-slate-600 hover:bg-slate-50 transition-all
              ${collapsed ? "justify-center" : ""}`}
          >
            <Settings size={18} />
            {!collapsed && <span>{t("nav.settings")}</span>}
          </Link>

          <button
            onClick={handleLogout}
            title={collapsed ? "Sign out" : undefined}
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium
              text-slate-600 hover:bg-red-50 hover:text-red-600 transition-all
              ${collapsed ? "justify-center" : ""}`}
          >
            <LogOut size={18} />
            {!collapsed && <span>{t("nav.signout")}</span>}
          </button>

          {!collapsed && (
            <div className="mt-2 p-3 bg-slate-50 rounded-xl flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-indigo-700">{initials}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-900 truncate">
                  {user?.full_name ?? "—"}
                </p>
                <p className="text-xs text-slate-500 truncate">{user?.email ?? ""}</p>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-16 bg-white border-b border-slate-200 flex items-center px-4 lg:px-6 gap-4 flex-shrink-0">

          {/* Burger mobile */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden w-8 h-8 flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
          >
            <Menu size={20} />
          </button>

          <div className="flex-1" />

          <div className="flex items-center gap-2">

            {/* ── Sélecteur de langue ─────────────────────────────────────── */}
            <div ref={langDropdown.ref} className="relative">
              <button
                onClick={() => {
                  langDropdown.setOpen((o) => !o);
                  userDropdown.setOpen(false);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 hover:bg-slate-100 transition-colors"
              >
                <Globe size={14} className="text-slate-400" />
                <span className="text-xs font-semibold text-slate-700">
                  {currentLang.label}
                </span>
                <ChevronDown
                  size={12}
                  className={`text-slate-400 transition-transform ${
                    langDropdown.open ? "rotate-180" : ""
                  }`}
                />
              </button>

              {langDropdown.open && (
                <div className="absolute right-0 top-full mt-1 w-36 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-50">
                  {LANGUAGES.map((l) => (
                    <button
                      key={l.code}
                      onClick={() => handleLangChange(l.code)}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors text-left ${
                        lang === l.code
                          ? "bg-indigo-50 text-indigo-700 font-semibold"
                          : "text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      {lang === l.code ? "✓ " : "\u00A0\u00A0"}{l.full}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* ── Menu utilisateur ────────────────────────────────────────── */}
            <div ref={userDropdown.ref} className="relative">
              <button
                onClick={() => {
                  userDropdown.setOpen((o) => !o);
                  langDropdown.setOpen(false);
                }}
                className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-slate-100 transition-colors"
              >
                <div className="w-7 h-7 bg-indigo-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-bold text-indigo-700">{initials}</span>
                </div>
                <ChevronDown
                  size={12}
                  className={`text-slate-400 transition-transform ${
                    userDropdown.open ? "rotate-180" : ""
                  }`}
                />
              </button>

              {userDropdown.open && (
                <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-50">
                  <div className="px-3 py-2 border-b border-slate-100">
                    <p className="text-xs font-semibold text-slate-900 truncate">
                      {user?.full_name ?? "—"}
                    </p>
                    <p className="text-xs text-slate-500 truncate">{user?.email ?? ""}</p>
                  </div>
                  <Link
                    to="/app/settings"
                    onClick={() => userDropdown.setOpen(false)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <Settings size={14} /> {t("nav.settings")}
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut size={14} /> {t("nav.signout")}
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
