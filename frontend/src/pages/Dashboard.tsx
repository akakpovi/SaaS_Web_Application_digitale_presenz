import React from "react";
import { Link } from "react-router-dom";
import { Globe, TrendingUp, Clock, AlertTriangle, ArrowRight } from "lucide-react";
import { Card, StatusBadge, ScoreRing } from "../components/ui";

const websites = [
  { id: "1", domain: "example.de", status: "healthy" as const, statusLabel: "Online", score: 92, uptime: "99.99%", ssl: "Valid", lastCheck: "2 min ago", issues: 0 },
  { id: "2", domain: "example.com", status: "healthy" as const, statusLabel: "Online", score: 82, uptime: "99.98%", ssl: "Valid", lastCheck: "5 min ago", issues: 1 },
  { id: "3", domain: "example-shop.de", status: "warning" as const, statusLabel: "Needs attention", score: 64, uptime: "98.91%", ssl: "Expires soon", lastCheck: "3 min ago", issues: 2 },
];

const kpis = [
  { label: "Digital Health Score", value: "82", unit: "/ 100", sub: "Good", trend: "+6 vs last month", icon: "🎯", color: "emerald" },
  { label: "Websites", value: "3", unit: "", sub: "2 healthy, 1 needs attention", trend: "", icon: "🌐", color: "indigo" },
  { label: "Uptime", value: "99.98%", unit: "", sub: "Last 30 days", trend: "", icon: "⬆️", color: "emerald" },
  { label: "Open issues", value: "2", unit: "", sub: "Needs your attention", trend: "", icon: "⚠️", color: "amber" },
];

export default function Dashboard() {
  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Greeting */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Good morning, Maria 👋</h1>
        <p className="text-slate-500 mt-1">Here's the health of your digital presence.</p>
      </div>

      {/* Alert banner */}
      <div className="flex items-center gap-4 p-4 bg-amber-50 border border-amber-200 rounded-2xl mb-6">
        <AlertTriangle size={18} className="text-amber-600 flex-shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-amber-800">2 issues need your attention</p>
          <p className="text-sm text-amber-700">SSL certificate on example-shop.de expires in 12 days. Email security needs improvement on example.com.</p>
        </div>
        <Link to="/app/alerts">
          <button className="flex items-center gap-1.5 text-sm font-medium text-amber-700 hover:text-amber-800">
            View alerts <ArrowRight size={14} />
          </button>
        </Link>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {kpis.map((kpi) => (
          <Card key={kpi.label} className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 mb-2">{kpi.label}</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-black text-slate-900">{kpi.value}</span>
                  {kpi.unit && <span className="text-sm text-slate-400">{kpi.unit}</span>}
                </div>
                <p className="text-xs text-slate-500 mt-1">{kpi.sub}</p>
              </div>
              <span className="text-2xl">{kpi.icon}</span>
            </div>
            {kpi.trend && (
              <p className="text-xs text-emerald-600 font-medium mt-2 flex items-center gap-1">
                <TrendingUp size={12} /> {kpi.trend}
              </p>
            )}
          </Card>
        ))}
      </div>

      {/* Main content grid */}
      <div className="grid xl:grid-cols-3 gap-6">
        {/* Website table */}
        <div className="xl:col-span-2">
          <Card>
            <div className="flex items-center justify-between p-5 pb-0">
              <h2 className="font-bold text-slate-900">Your websites</h2>
              <Link to="/app/websites" className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1">
                View all <ArrowRight size={14} />
              </Link>
            </div>

            {/* Table header */}
            <div className="hidden md:grid grid-cols-5 gap-4 px-5 pt-4 pb-2 text-xs font-semibold text-slate-400 uppercase tracking-wide border-b border-slate-100">
              <span className="col-span-2">Website</span>
              <span>Score</span>
              <span>Uptime</span>
              <span>SSL</span>
            </div>

            {/* Rows */}
            {websites.map((site) => (
              <Link to={`/app/websites/${site.id}`} key={site.id}>
                <div className="grid md:grid-cols-5 gap-4 px-5 py-4 border-b border-slate-50 hover:bg-slate-50 transition-colors items-center last:border-0">
                  <div className="md:col-span-2 flex items-center gap-3">
                    <div className="w-8 h-8 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0">
                      <Globe size={15} className="text-indigo-600" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{site.domain}</p>
                      <StatusBadge status={site.status} label={site.statusLabel} />
                    </div>
                  </div>
                  <div className="hidden md:block">
                    <span className={`text-sm font-bold ${site.score >= 80 ? "text-emerald-600" : site.score >= 60 ? "text-amber-600" : "text-red-600"}`}>
                      {site.score}
                    </span>
                    <span className="text-xs text-slate-400"> / 100</span>
                  </div>
                  <div className="hidden md:block text-sm text-slate-700">{site.uptime}</div>
                  <div className="hidden md:flex items-center gap-2">
                    <StatusBadge
                      status={site.ssl === "Valid" ? "healthy" : "warning"}
                      label={site.ssl}
                    />
                  </div>
                </div>
              </Link>
            ))}

            <div className="p-5 pt-3">
              <button className="w-full flex items-center justify-center gap-2 py-2.5 border border-dashed border-slate-300 rounded-xl text-sm text-slate-500 hover:border-indigo-400 hover:text-indigo-600 transition-colors">
                + Add website
              </button>
            </div>
          </Card>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4">
          {/* Health score overview */}
          <Card className="p-5">
            <h2 className="font-bold text-slate-900 mb-4">Digital Health Score</h2>
            <div className="flex items-center gap-4">
              <ScoreRing score={82} size={90} />
              <div className="flex-1">
                <p className="text-sm font-semibold text-emerald-600 mb-1">Good</p>
                <p className="text-xs text-slate-500 leading-relaxed">Your digital presence is healthy overall, with a few improvements recommended.</p>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {[
                { label: "Website", score: 20, max: 20 },
                { label: "SSL", score: 20, max: 20 },
                { label: "DNS", score: 15, max: 15 },
                { label: "Email", score: 10, max: 15 },
                { label: "Security", score: 9, max: 15 },
                { label: "Performance", score: 8, max: 15 },
              ].map(({ label, score, max }) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="text-xs text-slate-500 w-20 flex-shrink-0">{label}</span>
                  <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${score === max ? "bg-emerald-500" : score >= max * 0.7 ? "bg-amber-500" : "bg-red-500"}`}
                      style={{ width: `${(score / max) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-semibold text-slate-700 tabular-nums w-8 text-right">{score}/{max}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Recent alerts */}
          <Card className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-slate-900">Recent alerts</h2>
              <Link to="/app/alerts" className="text-sm text-indigo-600 hover:text-indigo-700">View all</Link>
            </div>
            <div className="space-y-3">
              {[
                { icon: "🔴", title: "SSL expires in 12 days", site: "example-shop.de", time: "2 hours ago" },
                { icon: "🟠", title: "Email security needs improvement", site: "example.com", time: "Yesterday" },
              ].map((alert, i) => (
                <div key={i} className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl">
                  <span className="text-base flex-shrink-0 mt-0.5">{alert.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 leading-tight">{alert.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{alert.site} · {alert.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Last check */}
          <Card className="p-5">
            <div className="flex items-center gap-3">
              <Clock size={18} className="text-slate-400" />
              <div>
                <p className="text-xs text-slate-500">Last check</p>
                <p className="text-sm font-semibold text-slate-800">2 minutes ago · All systems monitored</p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
