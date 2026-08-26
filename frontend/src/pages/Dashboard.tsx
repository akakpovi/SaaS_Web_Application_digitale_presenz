import React from "react";
import { Link } from "react-router-dom";
import { Globe, TrendingUp, Clock, AlertTriangle, ArrowRight, RefreshCw } from "lucide-react";
import { Card, StatusBadge, ScoreRing } from "../components/ui";
import { useDashboard } from "../hooks/useDashboard";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";

function AlertIcon({ severity }: { severity: string }) {
  if (severity === 'critical') return <span className="text-base flex-shrink-0 mt-0.5">🔴</span>;
  if (severity === 'warning') return <span className="text-base flex-shrink-0 mt-0.5">🟠</span>;
  return <span className="text-base flex-shrink-0 mt-0.5">🔵</span>;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { websites, kpis, recentAlerts, scoreBreakdown, isLoading, error, refetch } = useDashboard();
  const { t } = useLang();

  const firstName = user?.full_name?.split(' ')[0] ?? 'there';
  const hour = new Date().getHours();
  const greeting = hour < 12
    ? t('dashboard.greeting.morning')
    : hour < 18
    ? t('dashboard.greeting.afternoon')
    : t('dashboard.greeting.evening');

  const kpiCards = [
    {
      label: t("kpi.health_score"),
      value: isLoading ? '—' : String(kpis.avgScore),
      unit: "/ 100",
      sub: kpis.avgScore >= 80
        ? t("status.healthy")
        : kpis.avgScore >= 60
        ? t("status.warning")
        : kpis.avgScore > 0
        ? t("status.critical")
        : t("status.no_data"),
      icon: "🎯",
    },
    {
      label: t("kpi.websites"),
      value: isLoading ? '—' : String(kpis.totalWebsites),
      unit: "",
      sub: isLoading ? '' : `${kpis.healthyCount} ${t("status.healthy").toLowerCase()}, ${kpis.totalWebsites - kpis.healthyCount} ${t("status.needs_attention").toLowerCase()}`,
      icon: "🌐",
    },
    {
      label: t("kpi.uptime"),
      value: "—",
      unit: "",
      sub: "Last 30 days",
      icon: "⬆",
    },
    {
      label: t("kpi.open_issues"),
      value: isLoading ? '—' : String(kpis.openIssues),
      unit: "",
      sub: kpis.openIssues > 0 ? t("status.needs_attention") : t("websites.all_good"),
      icon: "⚠",
    },
  ];

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Greeting */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{greeting}, {firstName} 👋</h1>
          <p className="text-slate-500 mt-1">{t("dashboard.title")}</p>
        </div>
        <button
          onClick={refetch}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          {t("dashboard.refresh")}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-2xl mb-6">
          <AlertTriangle size={18} className="text-red-600 flex-shrink-0" />
          <p className="text-sm text-red-700">{t("common.error")}</p>
        </div>
      )}

      {/* Alert banner */}
      {!isLoading && kpis.openIssues > 0 && (
        <div className="flex items-center gap-4 p-4 bg-amber-50 border border-amber-200 rounded-2xl mb-6">
          <AlertTriangle size={18} className="text-amber-600 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-amber-800">
              {kpis.openIssues} issue{kpis.openIssues > 1 ? 's' : ''} {t("status.needs_attention").toLowerCase()}
            </p>
            {recentAlerts[0] && (
              <p className="text-sm text-amber-700">{recentAlerts[0].title}</p>
            )}
          </div>
          <Link to="/app/alerts">
            <button className="flex items-center gap-1.5 text-sm font-medium text-amber-700 hover:text-amber-800">
              {t("alerts.view")} <ArrowRight size={14} />
            </button>
          </Link>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && kpis.totalWebsites === 0 && (
        <div className="flex flex-col items-center justify-center py-16 bg-white border border-slate-200 rounded-2xl mb-6">
          <Globe size={40} className="text-slate-300 mb-4" />
          <p className="text-slate-900 font-semibold mb-1">{t("dashboard.no_websites")}</p>
          <p className="text-slate-500 text-sm mb-4">{t("dashboard.add_website")}</p>
          <Link to="/app/websites">
            <button className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors">
              {t("dashboard.add_btn")}
            </button>
          </Link>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {kpiCards.map((kpi) => (
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
          </Card>
        ))}
      </div>

      {/* Main content grid */}
      <div className="grid xl:grid-cols-3 gap-6">
        {/* Website table */}
        <div className="xl:col-span-2">
          <Card>
            <div className="flex items-center justify-between p-5 pb-0">
              <h2 className="font-bold text-slate-900">{t("websites.title")}</h2>
              <Link to="/app/websites" className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1">
                {t("common.edit")} <ArrowRight size={14} />
              </Link>
            </div>

            <div className="hidden md:grid grid-cols-5 gap-4 px-5 pt-4 pb-2 text-xs font-semibold text-slate-400 uppercase tracking-wide border-b border-slate-100">
              <span className="col-span-2">Website</span>
              <span>Score</span>
              <span>{t("websites.last_check")}</span>
              <span>SSL</span>
            </div>

            {isLoading ? (
              <div className="p-8 flex items-center justify-center">
                <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : websites.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-400">
                {t("dashboard.no_websites")}
              </div>
            ) : (
              websites.map((site) => (
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
                        {site.score > 0 ? site.score : '—'}
                      </span>
                      {site.score > 0 && <span className="text-xs text-slate-400"> / 100</span>}
                    </div>
                    <div className="hidden md:block text-sm text-slate-700">{site.lastCheck}</div>
                    <div className="hidden md:flex items-center gap-2">
                      <StatusBadge
                        status={site.ssl === "Valid" ? "healthy" : site.ssl === "Expires soon" ? "warning" : "neutral"}
                        label={site.ssl}
                      />
                    </div>
                  </div>
                </Link>
              ))
            )}

            <div className="p-5 pt-3">
              <Link to="/app/websites">
                <button className="w-full flex items-center justify-center gap-2 py-2.5 border border-dashed border-slate-300 rounded-xl text-sm text-slate-500 hover:border-indigo-400 hover:text-indigo-600 transition-colors">
                  + {t("dashboard.add_btn")}
                </button>
              </Link>
            </div>
          </Card>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4">
          {/* Health score */}
          <Card className="p-5">
            <h2 className="font-bold text-slate-900 mb-4">{t("kpi.health_score")}</h2>
            <div className="flex items-center gap-4">
              <ScoreRing score={isLoading ? 0 : kpis.avgScore} size={90} />
              <div className="flex-1">
                <p className={`text-sm font-semibold mb-1 ${kpis.avgScore >= 80 ? 'text-emerald-600' : kpis.avgScore >= 60 ? 'text-amber-600' : 'text-red-600'}`}>
                  {kpis.avgScore >= 80
                    ? t("status.healthy")
                    : kpis.avgScore >= 60
                    ? t("status.warning")
                    : kpis.avgScore > 0
                    ? t("status.critical")
                    : t("status.no_data")}
                </p>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {kpis.avgScore > 0
                    ? t("dashboard.title")
                    : t("dashboard.add_website")}
                </p>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {(scoreBreakdown.length > 0 ? scoreBreakdown : [
                { label: "Website", score: 0, max: 20 },
                { label: "SSL",     score: 0, max: 20 },
                { label: "DNS",     score: 0, max: 15 },
                { label: "Email",   score: 0, max: 15 },
                { label: "Security",score: 0, max: 15 },
                { label: "Performance", score: 0, max: 15 },
              ]).map(({ label, score, max }) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="text-xs text-slate-500 w-20 flex-shrink-0">{label}</span>
                  <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        score === max ? "bg-emerald-500"
                        : score >= max * 0.7 ? "bg-amber-500"
                        : score > 0 ? "bg-red-500"
                        : "bg-slate-200"
                      }`}
                      style={{ width: `${max > 0 ? (score / max) * 100 : 0}%` }}
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
              <h2 className="font-bold text-slate-900">{t("alerts.title")}</h2>
              <Link to="/app/alerts" className="text-sm text-indigo-600 hover:text-indigo-700">{t("alerts.view")}</Link>
            </div>
            {isLoading ? (
              <div className="flex items-center justify-center py-4">
                <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : recentAlerts.length === 0 ? (
              <div className="text-center py-4 text-sm text-slate-400">
                ✅ {t("alerts.no_alerts")}
              </div>
            ) : (
              <div className="space-y-3">
                {recentAlerts.map((alert) => (
                  <div key={alert.id} className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl">
                    <AlertIcon severity={alert.severity} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-800 leading-tight">{alert.title}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{timeAgo(alert.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Last check */}
          <Card className="p-5">
            <div className="flex items-center gap-3">
              <Clock size={18} className="text-slate-400" />
              <div>
                <p className="text-xs text-slate-500">{t("websites.last_check")}</p>
                <p className="text-sm font-semibold text-slate-800">
                  {isLoading ? '...' : `${kpis.lastCheck} · ${t("websites.all_good")}`}
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
