import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import {
  LayoutDashboard,
  Globe,
  Activity,
  Bell,
  FileText,
  Star,
  Settings,
  HelpCircle,
  ChevronRight,
  Search,
  User,
  Menu,
  X,
  ChevronDown,
} from "lucide-react";

const nav = [
  { label: "Overview", icon: LayoutDashboard, path: "/app/dashboard" },
  { label: "Websites", icon: Globe, path: "/app/websites" },
  { label: "Monitoring", icon: Activity, path: "/app/monitoring" },
  { label: "Reviews", icon: Star, path: "/app/reviews" },
  { label: "Reports", icon: FileText, path: "/app/reports" },
  { label: "Alerts", icon: Bell, path: "/app/alerts", badge: 2 },
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

export function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-full bg-slate-50">
      {/* Private app — never indexed */}
      <Helmet>
        <meta name="robots" content="noindex,nofollow" />
      </Helmet>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-slate-900/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex flex-col bg-white border-r border-slate-200 transition-all duration-300
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          lg:translate-x-0 lg:static lg:z-auto
          ${collapsed ? "w-16" : "w-56"}`}
      >
        {/* Sidebar header */}
        <div className={`flex items-center p-4 h-16 border-b border-slate-100 ${collapsed ? "justify-center" : "justify-between"}`}>
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
              className="hidden lg:flex absolute -right-3 top-7 w-6 h-6 items-center justify-center rounded-full bg-white border border-slate-200 text-slate-400 hover:text-slate-600 shadow-sm"
            >
              <ChevronRight size={12} style={{ transform: "rotate(180deg)" }} />
            </button>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 py-3 px-2 overflow-y-auto">
          <div className="flex flex-col gap-0.5">
            {nav.map(({ label, icon: Icon, path, badge }) => {
              const active = location.pathname.startsWith(path);
              return (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setSidebarOpen(false)}
                  title={collapsed ? label : undefined}
                  className={`relative flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150 group
                    ${active
                      ? "bg-indigo-50 text-indigo-700"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                    }
                    ${collapsed ? "justify-center" : ""}`}
                >
                  <Icon size={18} className="flex-shrink-0" />
                  {!collapsed && <span>{label}</span>}
                  {badge && !collapsed && (
                    <span className="ml-auto bg-red-500 text-white text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
                      {badge}
                    </span>
                  )}
                  {badge && collapsed && (
                    <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
                  )}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Sidebar footer */}
        <div className="p-2 border-t border-slate-100 flex flex-col gap-0.5">
          <Link
            to="/app/settings"
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-all ${collapsed ? "justify-center" : ""}`}
          >
            <Settings size={18} />
            {!collapsed && <span>Settings</span>}
          </Link>
          <button
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-all ${collapsed ? "justify-center" : ""}`}
          >
            <HelpCircle size={18} />
            {!collapsed && <span>Help</span>}
          </button>
          {!collapsed && (
            <div className="mt-2 p-3 bg-slate-50 rounded-xl flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
                <User size={14} className="text-indigo-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-900 truncate">Maria Schmidt</p>
                <p className="text-xs text-slate-500 truncate">Pro Plan</p>
              </div>
              <ChevronDown size={14} className="text-slate-400" />
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center px-4 lg:px-6 gap-4 flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden w-8 h-8 flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
          >
            <Menu size={20} />
          </button>

          <div className="flex-1 max-w-xs">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                placeholder="Search..."
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-slate-50 border border-slate-200 rounded-xl placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <button className="relative w-9 h-9 flex items-center justify-center rounded-xl text-slate-500 hover:bg-slate-100 transition-colors">
              <Bell size={18} />
              <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full" />
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-xs font-medium text-slate-600">EN</span>
              <ChevronDown size={12} className="text-slate-400" />
            </div>
            <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center">
              <User size={14} className="text-indigo-600" />
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
