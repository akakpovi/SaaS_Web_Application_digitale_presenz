import React from "react"
import { Link, useNavigate } from "react-router-dom"
import {
  Globe,
  TrendingUp,
  Clock,
  ArrowRight,
  Plus,
  AlertTriangle,
  CheckCircle,
  Zap,
  ScanSearch,
  Megaphone,
  ShieldAlert,
} from "lucide-react"
import { UpgradeBadge } from "../components/UpgradePrompt"
import {
  Card,
  StatusBadge,
  ScoreRing,
  Sparkline,
  SeverityBadge,
  Button,
  LoadingBlock,
  ErrorBlock,
  EmptyState,
} from "../components/ui"
import { endpoints } from "../api/endpoints"
import { useApiList, useApiResource } from "../api/hooks/useApiResource"
import { useAuth } from "../api/hooks/useAuth"
import type { Alert, Scan, Website } from "../api/types"
import {
  averageScore,
  healthStatusTone,
  scoreLabelKey,
  scoreTextClass,
} from "../lib/format"
import { useFormat } from "../lib/useFormat"

/** Time-of-day bucket for the greeting; the wording itself lives in the catalogue. */
function getHour(): "Morning" | "Afternoon" | "Evening" {
  const h = new Date().getHours()
  if (h < 12) return "Morning"
  if (h < 18) return "Afternoon"
  return "Evening"
}

const SEVERITY_ORDER: Record<Alert["severity"], number> = {
  critical: 0,
  warning: 1,
  info: 2,
}

/** Greeting variant → catalogue key (kept as a map so the key stays typed). */
const GREETING_KEYS = {
  Morning: "dashboard.greetingMorning",
  Afternoon: "dashboard.greetingAfternoon",
  Evening: "dashboard.greetingEvening",
} as const

export default function Dashboard() {
  const { user } = useAuth()
  const {
    t,
    relativeTime,
    healthStatusLabel,
    checkCategoryLabel,
  } = useFormat()
  const navigate = useNavigate()
  const websites = useApiList<Website>(endpoints.websites.list)
  const scans = useApiList<Scan>(endpoints.scans.list)
  const alerts = useApiList<Alert>("/alerts/?status=firing")

  // The list endpoint omits check results, so the health breakdown is read
  // from the most recent scan's detail payload.
  const latestScanId = scans.data[0]?.id ?? null
  const latestScanDetail = useApiResource<Scan>(
    latestScanId === null ? null : endpoints.scans.detail(latestScanId),
  )

  const greetingName = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0]

  if (websites.loading) {
    return (
      <div className="p-6 lg:p-8 max-w-7xl mx-auto">
        <LoadingBlock label={t("dashboard.loading")} />
      </div>
    )
  }

  if (websites.error && !websites.data.length) {
    return (
      <div className="p-6 lg:p-8 max-w-7xl mx-auto">
        <ErrorBlock message={websites.error} onRetry={websites.refetch} />
      </div>
    )
  }

  const average = averageScore(websites.data.map((site) => site.health_score))
  const healthy = websites.data.filter((s) => s.health_status === "healthy").length
  const needsAttention = websites.data.filter(
    (s) => s.health_status === "warning" || s.health_status === "critical",
  ).length

  const completedScans = scans.data.filter((scan) => scan.status === "completed")
  const scoreHistory = completedScans
    .slice(0, 12)
    .reverse()
    .map((scan) => scan.health_score ?? 0)
  const latestScan = scans.data[0] ?? null
  const latestChecks = latestScanDetail.data?.check_results ?? []

  const openAlerts = [...alerts.data].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  )
  const criticalAlerts = openAlerts.filter((a) => a.severity === "critical")

  const kpis = [
    {
      label: t("dashboard.kpi.healthScore"),
      value: average === null ? "—" : String(average),
      unit: average === null ? "" : "/ 100",
      sub:
        websites.count > 0
          ? websites.count > 1
            ? t("dashboard.monitoredMany", { count: websites.count })
            : t("dashboard.monitoredOne")
          : t("dashboard.noWebsite"),
      trend:
        completedScans.length > 0
          ? completedScans.length > 1
            ? t("dashboard.completedScansMany", {
                count: completedScans.length,
              })
            : t("dashboard.completedScansOne")
          : "",
      spark: scoreHistory,
      sparkColor: "#059669",
    },
    {
      label: t("dashboard.kpi.websites"),
      value: String(websites.count),
      unit: "",
      sub: t("dashboard.onlineNeedsAttention", {
        online: healthy,
        attention: needsAttention,
      }),
      trend: "",
      spark: [] as number[],
      sparkColor: "#4f46e5",
    },
    {
      label: t("dashboard.kpi.scans"),
      value: String(scans.count),
      unit: "",
      sub: latestScan
        ? t("dashboard.lastRun", {
            time: relativeTime(latestScan.created_at),
          })
        : t("dashboard.noScan"),
      trend: "",
      spark: [] as number[],
      sparkColor: "#4f46e5",
    },
    {
      label: t("dashboard.kpi.openAlerts"),
      value: String(openAlerts.length),
      unit: "",
      sub:
        openAlerts.length === 0
          ? t("dashboard.noAttention")
          : t("dashboard.criticalCount", { count: criticalAlerts.length }),
      trend: "",
      spark: [] as number[],
      sparkColor: "#d97706",
    },
  ]

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Greeting + CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-8">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">
            {t(GREETING_KEYS[getHour()])}
            {greetingName ? `, ${greetingName}` : ""}
          </h1>
          <p className="text-slate-500 mt-1">{t("dashboard.subtitle")}</p>
        </div>
        <Link to="/app/websites">
          <Button className="gap-2 self-start">
            <Zap size={15} />
            {t("dashboard.runScan")}
          </Button>
        </Link>
      </div>

      {/* KPI Cards with sparklines */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {kpis.map((kpi) => (
          <Card key={kpi.label} className="p-5">
            <div className="flex items-start justify-between mb-3">
              <p className="text-xs font-medium text-slate-500">{kpi.label}</p>
              {kpi.spark.length > 1 && (
                <Sparkline
                  data={kpi.spark}
                  color={kpi.sparkColor}
                  height={28}
                  width={64}
                />
              )}
            </div>
            <div className="flex items-baseline gap-1 mb-1">
              <span className="text-2xl sm:text-3xl font-black text-slate-900 tabular-nums">
                {kpi.value}
              </span>
              {kpi.unit && (
                <span className="text-sm text-slate-400">{kpi.unit}</span>
              )}
            </div>
            <p className="text-xs text-slate-500">{kpi.sub}</p>
            {kpi.trend && (
              <p className="text-xs font-medium mt-1.5 flex items-center gap-1 text-emerald-600">
                <TrendingUp size={11} aria-hidden="true" /> {kpi.trend}
              </p>
            )}
          </Card>
        ))}
      </div>

      {/* Growth suite — always visible; a locked action opens the upgrade modal */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-3 gap-3">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <TrendingUp size={16} className="text-indigo-600" aria-hidden="true" />
            {t("dashboard.growthTitle")}
          </h2>
          <Link
            to="/app/growth"
            className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"
          >
            {t("dashboard.growthOpen")} <ArrowRight size={13} aria-hidden="true" />
          </Link>
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            {
              tab: "seo",
              icon: ScanSearch,
              title: t("dashboard.growthSeoTitle"),
              description: t("dashboard.growthSeoBody"),
              feature: "seo.audit" as const,
            },
            {
              tab: "reputation",
              icon: Megaphone,
              title: t("dashboard.growthReputationTitle"),
              description: t("dashboard.growthReputationBody"),
              feature: "social.sync" as const,
            },
            {
              tab: "security",
              icon: ShieldAlert,
              title: t("dashboard.growthSecurityTitle"),
              description: t("dashboard.growthSecurityBody"),
              feature: "security.scan" as const,
            },
          ].map((module) => {
            const Icon = module.icon
            return (
              <Card
                key={module.tab}
                className="p-5 h-full"
                onClick={() => navigate(`/app/growth?tab=${module.tab}`)}
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="w-9 h-9 rounded-xl bg-indigo-50 flex items-center justify-center">
                    <Icon size={17} className="text-indigo-600" aria-hidden="true" />
                  </div>
                  <UpgradeBadge feature={module.feature} />
                </div>
                <p className="text-sm font-semibold text-slate-900">
                  {module.title}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {module.description}
                </p>
              </Card>
            )
          })}
        </div>
      </div>

      {/* Critical issues — real firing alerts */}
      {openAlerts.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2">
              <AlertTriangle
                size={16}
                className="text-amber-500"
                aria-hidden="true"
              />
              {openAlerts.length > 1
                ? t("dashboard.attentionMany", { count: openAlerts.length })
                : t("dashboard.attentionOne")}
            </h2>
            <Link
              to="/app/alerts"
              className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"
            >
              {t("dashboard.viewAll")} <ArrowRight size={13} aria-hidden="true" />
            </Link>
          </div>
          <div className="flex flex-col gap-3">
            {openAlerts.slice(0, 3).map((alert) => (
              <div
                key={alert.id}
                className="flex flex-col sm:flex-row sm:items-start gap-4 p-4 bg-white border border-amber-200 rounded-2xl shadow-sm"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <SeverityBadge severity={alert.severity} />
                    <span className="text-sm font-semibold text-slate-900">
                      {alert.title}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mb-1 font-mono">
                    {alert.website_domain} · {relativeTime(alert.created_at)}
                  </p>
                  <p className="text-sm text-slate-600">{alert.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main grid */}
      <div className="grid xl:grid-cols-3 gap-6">
        {/* Website table */}
        <div className="xl:col-span-2">
          <Card>
            <div className="flex items-center justify-between p-5 pb-0">
              <h2 className="font-bold text-slate-900">
                {t("dashboard.yourWebsites")}
              </h2>
              <Link
                to="/app/websites"
                className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"
              >
                {t("dashboard.viewAll")} <ArrowRight size={13} aria-hidden="true" />
              </Link>
            </div>

            {websites.data.length === 0 ? (
              <EmptyState
                icon={<Globe size={26} />}
                title={t("dashboard.emptyTitle")}
                description={t("dashboard.emptyBody")}
                action={
                  <Link to="/app/websites">
                    <Button size="sm" className="gap-1.5">
                      <Plus size={14} /> {t("websites.add")}
                    </Button>
                  </Link>
                }
              />
            ) : (
              <>
                {/* Table header */}
                <div className="hidden md:grid grid-cols-5 gap-4 px-5 pt-4 pb-2 text-xs font-semibold text-slate-400 uppercase tracking-wide border-b border-slate-100">
                  <span className="col-span-2">
                    {t("dashboard.table.website")}
                  </span>
                  <span>{t("dashboard.table.score")}</span>
                  <span>{t("dashboard.table.status")}</span>
                  <span>{t("dashboard.table.lastScan")}</span>
                </div>

                {websites.data.slice(0, 5).map((site) => (
                  <Link to={`/app/websites/${site.id}`} key={site.id}>
                    <div className="grid md:grid-cols-5 gap-4 px-5 py-3.5 border-b border-slate-50 hover:bg-slate-50 transition-colors items-center last:border-0">
                      <div className="md:col-span-2 flex items-center gap-3">
                        <div className="w-8 h-8 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0">
                          <Globe size={15} className="text-indigo-600" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-900 font-mono">
                            {site.domain}
                          </p>
                          <StatusBadge
                            status={healthStatusTone(site.health_status)}
                            label={healthStatusLabel(site.health_status)}
                          />
                        </div>
                      </div>
                      <div className="hidden md:block">
                        <span
                          className={`text-sm font-bold tabular-nums ${scoreTextClass(site.health_score)}`}
                        >
                          {site.health_score ?? "—"}
                        </span>
                        {site.health_score !== null && (
                          <span className="text-xs text-slate-400"> / 100</span>
                        )}
                      </div>
                      <div className="hidden md:flex items-center gap-2">
                        <StatusBadge
                          status={healthStatusTone(site.health_status)}
                          label={healthStatusLabel(site.health_status)}
                        />
                      </div>
                      <div className="hidden md:block text-sm text-slate-500">
                        {relativeTime(site.last_scan_at)}
                      </div>
                    </div>
                  </Link>
                ))}
              </>
            )}

            <div className="p-5 pt-3">
              <Link to="/app/websites">
                <button className="w-full flex items-center justify-center gap-2 py-2.5 border border-dashed border-slate-300 rounded-xl text-sm text-slate-500 hover:border-indigo-400 hover:text-indigo-600 transition-colors">
                  <Plus size={14} aria-hidden="true" /> {t("websites.add")}
                </button>
              </Link>
            </div>
          </Card>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4">
          {/* Health score */}
          <Card className="p-5">
            <h2 className="font-bold text-slate-900 mb-4">
              {t("dashboard.overallHealth")}
            </h2>
            {average === null ? (
              <p className="text-sm text-slate-500">{t("dashboard.noScore")}</p>
            ) : (
              <>
                <div className="flex items-center gap-4 mb-4">
                  <ScoreRing score={average} size={88} />
                  <div>
                    <p
                      className={`text-sm font-semibold mb-1 ${
                        average >= 80 ? "text-emerald-600" : "text-amber-600"
                      }`}
                    >
                      {t(scoreLabelKey(average))}
                    </p>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      {websites.count > 1
                        ? t("dashboard.averageMany", { count: websites.count })
                        : t("dashboard.averageOne")}
                    </p>
                  </div>
                </div>
                {latestScan && latestChecks.length > 0 && (
                  <div className="space-y-2.5">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                      {t("dashboard.latestScan", { domain: latestScan.domain })}
                    </p>
                    {latestChecks.map((check) => {
                      const max = check.max_score || 20
                      const score = check.score ?? 0
                      return (
                        <div key={check.id} className="flex items-center gap-3">
                          <span className="text-xs text-slate-500 w-28 flex-shrink-0 capitalize">
                            {checkCategoryLabel(check.category)}
                          </span>
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${
                                score === max
                                  ? "bg-emerald-500"
                                  : score >= max * 0.7
                                    ? "bg-amber-500"
                                    : "bg-red-500"
                              }`}
                              style={{ width: `${(score / max) * 100}%` }}
                            />
                          </div>
                          <span className="text-xs font-semibold text-slate-700 tabular-nums w-10 text-right font-mono">
                            {score}/{max}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </>
            )}
          </Card>

          {/* Recent alerts */}
          <Card className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-slate-900">
                {t("dashboard.recentAlerts")}
              </h2>
              <Link
                to="/app/alerts"
                className="text-sm text-indigo-600 hover:text-indigo-700"
              >
                {t("dashboard.viewAll")}
              </Link>
            </div>
            {alerts.loading ? (
              <p className="text-sm text-slate-400">
                {t("dashboard.loadingAlerts")}
              </p>
            ) : openAlerts.length === 0 ? (
              <div className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl">
                <CheckCircle
                  size={15}
                  className="text-emerald-500 flex-shrink-0 mt-0.5"
                  aria-hidden="true"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 leading-tight">
                    {t("dashboard.noOpenAlert")}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {t("dashboard.allHealthy")}
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {openAlerts.slice(0, 3).map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl"
                  >
                    <AlertTriangle
                      size={15}
                      className={`flex-shrink-0 mt-0.5 ${
                        alert.severity === "critical"
                          ? "text-red-500"
                          : "text-amber-500"
                      }`}
                      aria-hidden="true"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-800 leading-tight">
                        {alert.title}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5 font-mono">
                        {alert.website_domain} ·{" "}
                        {relativeTime(alert.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Last check */}
          <div className="flex items-center gap-3 px-4 py-3 bg-white border border-slate-200 rounded-2xl shadow-sm">
            <Clock size={15} className="text-slate-400 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">
                {t("dashboard.lastCheck")}
              </p>
              <p className="text-sm font-semibold text-slate-800">
                {latestScan
                  ? `${relativeTime(latestScan.created_at)} · ${latestScan.domain}`
                  : t("dashboard.noCheck")}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
