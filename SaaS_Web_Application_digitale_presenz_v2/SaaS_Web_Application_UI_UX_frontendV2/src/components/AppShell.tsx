import React, { useState, useEffect, createContext, useContext } from "react"
import { Link, useLocation } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import { dropPreRenderedDuplicates } from "../lib/prerenderedHead"
import {
  LayoutDashboard,
  Globe,
  Activity,
  Bell,
  FileText,
  ScanSearch,
  Settings,
  HelpCircle,
  ChevronRight,
  Search,
  User,
  Menu,
  X,
  CreditCard,
  Moon,
  Sun,
  Command,
  LogOut,
  TrendingUp,
  Share2,
  Bot,
} from "lucide-react"
import { useAuth } from "../api/hooks/useAuth"
import { useApiList } from "../api/hooks/useApiResource"
import { usePlan } from "../contexts/PlanContext"
import LanguageSwitcher from "./LanguageSwitcher"
import { useI18n, type MessageKey } from "../i18n"
import type { Alert } from "../api/types"

// ─── Dark-mode context ────────────────────────────────────────────────────────
type Theme = "light" | "dark"
const ThemeCtx = createContext<{
  theme: Theme
  toggle: () => void
  setTheme: (theme: Theme) => void
}>({
  theme: "light",
  toggle: () => {},
  setTheme: () => {},
})
export function useTheme() {
  return useContext(ThemeCtx)
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    // `ThemeProvider` is part of the tree rendered at build time. Reading the
    // browser here would throw in Node before the page can be written.
    if (typeof window === "undefined") return "light"
    const stored = localStorage.getItem("presence-theme") as Theme | null
    if (stored) return stored
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
  })

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
    localStorage.setItem("presence-theme", theme)
  }, [theme])

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"))
  return (
    <ThemeCtx.Provider value={{ theme, toggle, setTheme }}>
      {children}
    </ThemeCtx.Provider>
  )
}

// ─── Navigation config ────────────────────────────────────────────────────────
const primaryNav: { labelKey: MessageKey; icon: typeof Globe; path: string }[] = [
  { labelKey: "app.navOverview", icon: LayoutDashboard, path: "/app/dashboard" },
  { labelKey: "app.navWebsites", icon: Globe, path: "/app/websites" },
  { labelKey: "app.navScans", icon: ScanSearch, path: "/app/scans" },
  { labelKey: "app.navMonitoring", icon: Activity, path: "/app/monitoring" },
  // The alert badge is the live count of firing alerts (see AppShell), never a
  // hardcoded number.
  { labelKey: "app.navAlerts", icon: Bell, path: "/app/alerts" },
  { labelKey: "app.navReports", icon: FileText, path: "/app/reports" },
  { labelKey: "app.navAdvisor", icon: Bot, path: "/app/advisor" },
  { labelKey: "app.navGrowth", icon: TrendingUp, path: "/app/growth" },
  {
    labelKey: "app.navIntegrations",
    icon: Share2,
    path: "/app/settings/integrations",
  },
]

const mobileNav: { labelKey: MessageKey; icon: typeof Globe; path: string }[] = [
  { labelKey: "app.navOverview", icon: LayoutDashboard, path: "/app/dashboard" },
  { labelKey: "app.navWebsites", icon: Globe, path: "/app/websites" },
  { labelKey: "app.navMonitoring", icon: Activity, path: "/app/monitoring" },
  { labelKey: "app.navAlerts", icon: Bell, path: "/app/alerts" },
  { labelKey: "app.navMore", icon: Menu, path: "/app/settings" },
]

// ─── Logo ─────────────────────────────────────────────────────────────────────
function Logo({ collapsed }: { collapsed?: boolean }) {
  return (
    <Link to="/app/dashboard" className="flex items-center gap-2.5 group">
      <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-700 transition-colors">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle
            cx="8"
            cy="8"
            r="6"
            stroke="white"
            strokeWidth="1.5"
            opacity="0.5"
          />
          <circle cx="8" cy="8" r="3" fill="white" />
          <path
            d="M8 2v2M8 12v2M2 8h2M12 8h2"
            stroke="white"
            strokeWidth="1.5"
            strokeLinecap="round"
            opacity="0.7"
          />
        </svg>
      </div>
      {!collapsed && (
        <span className="font-bold text-slate-900 text-base tracking-tight">
          Presence
        </span>
      )}
    </Link>
  )
}

// ─── AppShell ─────────────────────────────────────────────────────────────────
export function AppShell({
  children,
  onOpenCommand,
}: {
  children: React.ReactNode
  onOpenCommand?: () => void
}) {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const { theme, toggle } = useTheme()
  const { t } = useI18n()
  const { user, logout } = useAuth()
  const { isPaid } = usePlan()
  // Live count of firing alerts for the sidebar badge and the bell.
  const { count: openAlerts } = useApiList<Alert>("/alerts/?status=firing")

  // Close sidebar on route change
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  // The private shell is served from the pre-rendered public shell, whose head
  // says `index,follow`. The app's own tags win: the copies of the tags this
  // screen replaces are dropped (see src/lib/prerenderedHead.ts).
  useEffect(() => {
    dropPreRenderedDuplicates()
  })

  const darkCls = theme === "dark"

  return (
    <div className={`flex h-full ${darkCls ? "bg-[#0d1117]" : "bg-slate-50"}`}>
      {/* Private app — never indexed */}
      <Helmet>
        <meta name="robots" content="noindex,nofollow" />
      </Helmet>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-slate-900/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex flex-col border-r transition-all duration-300
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          lg:translate-x-0 lg:static lg:z-auto
          ${collapsed ? "w-16" : "w-56"}
          ${
            darkCls
              ? "bg-[#161b22] border-[#30363d]"
              : "bg-white border-slate-200"
          }`}
      >
        {/* Sidebar header */}
        <div
          className={`flex items-center p-4 h-16 border-b ${
            darkCls ? "border-[#30363d]" : "border-slate-100"
          } ${collapsed ? "justify-center" : "justify-between"}`}
        >
          <Logo collapsed={collapsed} />
          {!collapsed && (
            <button
              onClick={() => setCollapsed(true)}
              className={`hidden lg:flex w-7 h-7 items-center justify-center rounded-lg transition-colors ${
                darkCls
                  ? "text-slate-500 hover:text-slate-300 hover:bg-slate-700"
                  : "text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              }`}
              aria-label={t("app.collapseSidebar")}
            >
              <ChevronRight size={14} />
            </button>
          )}
          {collapsed && (
            <button
              onClick={() => setCollapsed(false)}
              className={`hidden lg:flex absolute -right-3 top-7 w-6 h-6 items-center justify-center rounded-full border shadow-sm transition-colors ${
                darkCls
                  ? "bg-[#161b22] border-[#30363d] text-slate-500 hover:text-slate-300"
                  : "bg-white border-slate-200 text-slate-400 hover:text-slate-600"
              }`}
              aria-label={t("app.expandSidebar")}
            >
              <ChevronRight size={12} style={{ transform: "rotate(180deg)" }} />
            </button>
          )}
        </div>

        {/* Primary nav */}
        <nav
          className="flex-1 py-3 px-2 overflow-y-auto"
          aria-label={t("app.mainNavigation")}
        >
          <div className="flex flex-col gap-0.5">
            {primaryNav.map(({ labelKey, icon: Icon, path }) => {
              const label = t(labelKey)
              const badge =
                labelKey === "app.navAlerts" && openAlerts > 0
                  ? openAlerts
                  : undefined
              const active =
                location.pathname === path ||
                (path !== "/app/dashboard" &&
                  location.pathname.startsWith(path))
              return (
                <Link
                  key={path}
                  to={path}
                  title={collapsed ? label : undefined}
                  aria-current={active ? "page" : undefined}
                  className={`relative flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150
                    ${
                      active
                        ? darkCls
                          ? "bg-indigo-900/50 text-indigo-300"
                          : "bg-indigo-50 text-indigo-700"
                        : darkCls
                          ? "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                    }
                    ${collapsed ? "justify-center" : ""}`}
                >
                  <Icon size={18} className="flex-shrink-0" />
                  {!collapsed && <span>{label}</span>}
                  {labelKey === "app.navGrowth" && !isPaid && !collapsed && (
                    <span className="ml-auto rounded-full border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-amber-700">
                      {t("app.planBadgePro")}
                    </span>
                  )}
                  {badge && !collapsed && (
                    <span className="ml-auto bg-red-500 text-white text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
                      {badge}
                    </span>
                  )}
                  {badge && collapsed && (
                    <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
                  )}
                </Link>
              )
            })}
          </div>
        </nav>

        {/* Sidebar footer */}
        <div
          className={`p-2 border-t flex flex-col gap-0.5 ${
            darkCls ? "border-[#30363d]" : "border-slate-100"
          }`}
        >
          <Link
            to="/app/billing"
            title={collapsed ? t("app.navBilling") : undefined}
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
              collapsed ? "justify-center" : ""
            } ${
              darkCls
                ? "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <CreditCard size={18} />
            {!collapsed && <span>{t("app.navBilling")}</span>}
          </Link>
          <Link
            to="/app/settings"
            title={collapsed ? t("app.navSettings") : undefined}
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
              collapsed ? "justify-center" : ""
            } ${
              darkCls
                ? "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <Settings size={18} />
            {!collapsed && <span>{t("app.navSettings")}</span>}
          </Link>
          <button
            title={collapsed ? t("app.navHelp") : undefined}
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
              collapsed ? "justify-center" : ""
            } ${
              darkCls
                ? "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <HelpCircle size={18} />
            {!collapsed && <span>{t("app.navHelp")}</span>}
          </button>
          {!collapsed && (
            <div
              className={`mt-2 p-3 rounded-xl flex items-center gap-2 ${
                darkCls ? "bg-slate-800" : "bg-slate-50"
              }`}
            >
              <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
                <User size={14} className="text-indigo-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p
                  className={`text-xs font-semibold truncate ${
                    darkCls ? "text-slate-200" : "text-slate-900"
                  }`}
                >
                  {user?.full_name || user?.email || t("app.userFallback")}
                </p>
                <p
                  className={`text-xs truncate ${
                    darkCls ? "text-slate-500" : "text-slate-500"
                  }`}
                >
                  {user?.is_email_verified
                    ? t("app.verified")
                    : t("app.unverified")}
                </p>
              </div>
              <button
                onClick={logout}
                className={`flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-lg transition-colors ${
                  darkCls
                    ? "text-slate-500 hover:text-slate-300 hover:bg-slate-700"
                    : "text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                }`}
                aria-label={t("common.logout")}
              >
                <LogOut size={14} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top header */}
        <header
          className={`h-16 border-b flex items-center px-4 lg:px-6 gap-4 flex-shrink-0 ${
            darkCls
              ? "bg-[#161b22] border-[#30363d]"
              : "bg-white border-slate-200"
          }`}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className={`lg:hidden w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${
              darkCls
                ? "text-slate-400 hover:bg-slate-700"
                : "text-slate-500 hover:bg-slate-100"
            }`}
            aria-label={t("app.openNavigation")}
          >
            <Menu size={20} />
          </button>

          {/* Search / command trigger */}
          <button
            onClick={onOpenCommand}
            className={`flex-1 max-w-xs flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm border transition-colors text-left ${
              darkCls
                ? "bg-slate-800 border-slate-700 text-slate-500 hover:border-slate-600"
                : "bg-slate-50 border-slate-200 text-slate-400 hover:border-slate-300"
            }`}
            aria-label={t("app.openCommandMenu")}
          >
            <Search size={14} />
            <span className="flex-1">{t("common.search")}</span>
            <kbd
              className={`hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs border font-mono ${
                darkCls
                  ? "border-slate-600 text-slate-500 bg-slate-800"
                  : "border-slate-200 text-slate-400 bg-white"
              }`}
            >
              <Command size={10} />K
            </kbd>
          </button>

          <div className="ml-auto flex items-center gap-2">
            {/* Dark mode toggle */}
            <button
              onClick={toggle}
              className={`w-9 h-9 flex items-center justify-center rounded-xl transition-colors ${
                darkCls
                  ? "text-slate-400 hover:bg-slate-700"
                  : "text-slate-500 hover:bg-slate-100"
              }`}
              aria-label={
                theme === "dark"
                  ? t("app.switchToLight")
                  : t("app.switchToDark")
              }
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            {/* Language — same control as on the public pages, so a German
                visitor keeps their choice inside the product. */}
            <LanguageSwitcher />

            {/* Notifications — the Alerts page is the in-app notification
                centre (history, filters, acknowledge = read). */}
            <Link
              to="/app/alerts"
              className={`relative w-9 h-9 flex items-center justify-center rounded-xl transition-colors ${
                darkCls
                  ? "text-slate-400 hover:bg-slate-700"
                  : "text-slate-500 hover:bg-slate-100"
              }`}
              aria-label={`${t("app.notifications")} (${openAlerts})`}
            >
              <Bell size={18} />
              {openAlerts > 0 && (
                <span
                  className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full"
                  aria-hidden="true"
                />
              )}
            </Link>

            {/* Avatar */}
            <div
              className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center"
              aria-label={t("app.userMenu")}
            >
              <User size={14} className="text-indigo-600" />
            </div>
            <div className="hidden lg:flex items-center gap-2 ml-3">
              <div className="text-right">
                <p
                  className={`text-xs font-semibold truncate max-w-xs ${
                    darkCls ? "text-slate-200" : "text-slate-900"
                  }`}
                >
                  {user?.full_name || user?.email || t("app.userFallback")}
                </p>
                <p className="text-[10px] text-slate-500">
                  {user?.is_email_verified
                    ? t("app.verified")
                    : t("app.unverified")}
                </p>
              </div>
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto pb-16 lg:pb-0">{children}</main>

        {/* Mobile bottom navigation */}
        <nav
          className={`lg:hidden fixed bottom-0 left-0 right-0 z-20 border-t flex ${
            darkCls
              ? "bg-[#161b22] border-[#30363d]"
              : "bg-white border-slate-200"
          }`}
          aria-label={t("app.mobileNavigation")}
        >
          {mobileNav.map(({ labelKey, icon: Icon, path }) => {
            const label = t(labelKey)
            const badge =
              labelKey === "app.navAlerts" && openAlerts > 0
                ? openAlerts
                : undefined
            const active =
              location.pathname === path ||
              (path !== "/app/dashboard" &&
                path !== "/app/settings" &&
                location.pathname.startsWith(path))
            return (
              <Link
                key={path}
                to={path}
                aria-current={active ? "page" : undefined}
                className={`flex-1 flex flex-col items-center justify-center gap-1 py-2 text-[10px] font-medium transition-colors relative ${
                  active
                    ? "text-indigo-600"
                    : darkCls
                      ? "text-slate-500"
                      : "text-slate-500"
                }`}
              >
                <Icon size={20} />
                <span>{label}</span>
                {badge && (
                  <span className="absolute top-1.5 left-1/2 ml-2 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                    {badge}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>
      </div>
    </div>
  )
}
