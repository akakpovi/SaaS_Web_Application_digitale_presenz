import { useState } from "react"
import { Link } from "react-router-dom"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Globe,
  MinusCircle,
  RefreshCw,
  XCircle,
} from "lucide-react"
import {
  Button,
  Card,
  EmptyState,
  ErrorBlock,
  LoadingBlock,
  StatusBadge,
  Tabs,
} from "../components/ui"
import { endpoints } from "../api/endpoints"
import { api } from "../api/client"
import { apiErrorMessage, useApiResource } from "../api/hooks/useApiResource"
import { useToast } from "../components/Toast"
import type {
  MonitoringEvent,
  MonitoringOverview,
  MonitoringWebsite,
} from "../api/types"
import { healthStatusTone, scoreTextClass } from "../lib/format"
import { useFormat, type Formatters } from "../lib/useFormat"
import { LOCALE_TAGS, type MessageKey } from "../i18n"

const PERIODS = ["24H", "7D", "30D", "90D"] as const
type Period = (typeof PERIODS)[number]

/** Interval value from the backend → catalogue key. */
const INTERVAL_LABELS: Record<string, MessageKey> = {
  "5m": "monitoring.interval5m",
  "15m": "monitoring.interval15m",
  "30m": "monitoring.interval30m",
  "1h": "monitoring.interval1h",
  "6h": "monitoring.interval6h",
  "24h": "monitoring.interval24h",
}

const PERIOD_LABELS: Record<Period, MessageKey> = {
  "24H": "monitoring.period24h",
  "7D": "monitoring.period7d",
  "30D": "monitoring.period30d",
  "90D": "monitoring.period90d",
}

type Translate = Formatters["t"]

function intervalLabel(interval: string | null, t: Translate): string {
  if (!interval) return t("monitoring.noSchedule")
  if (interval === "mixed") return t("monitoring.mixedIntervals")
  const key = INTERVAL_LABELS[interval]
  return key ? t(key) : interval
}

/** Chart axis label; the date/time format follows the interface language. */
function bucketLabel(iso: string, period: string, locale: Formatters["locale"]): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return "—"
  if (period === "24H") {
    return date.toLocaleTimeString(LOCALE_TAGS[locale], {
      hour: "2-digit",
      minute: "2-digit",
    })
  }
  return date.toLocaleDateString(LOCALE_TAGS[locale], {
    day: "2-digit",
    month: "short",
  })
}

function eventIcon(event: MonitoringEvent) {
  if (event.kind === "scan") {
    return event.severity === "critical" ? (
      <XCircle size={15} className="text-red-500" aria-hidden="true" />
    ) : (
      <CheckCircle2 size={15} className="text-emerald-500" aria-hidden="true" />
    )
  }
  if (event.severity === "critical") {
    return <XCircle size={15} className="text-red-500" aria-hidden="true" />
  }
  if (event.severity === "warning") {
    return <AlertTriangle size={15} className="text-amber-500" aria-hidden="true" />
  }
  return <MinusCircle size={15} className="text-slate-400" aria-hidden="true" />
}

function WebsiteRows({
  websites,
  onIntervalChange,
  onToggle,
  busySite,
}: {
  websites: MonitoringWebsite[]
  onIntervalChange: (site: MonitoringWebsite, interval: string) => void
  onToggle: (site: MonitoringWebsite, enabled: boolean) => void
  busySite: number | null
}) {
  const { t, relativeTime, healthStatusLabel } = useFormat()
  return (
    <Card className="overflow-hidden">
      <div className="p-5 pb-3">
        <h2 className="font-bold text-slate-900">
          {t("monitoring.monitoredWebsites")}
        </h2>
        <p className="text-sm text-slate-500">
          {t("monitoring.monitoredWebsitesSubtitle")}
        </p>
      </div>

      {websites.length === 0 ? (
        <EmptyState
          icon={<Globe size={26} />}
          title={t("monitoring.emptyTitle")}
          description={t("monitoring.emptyBody")}
          action={
            <Link to="/app/websites">
              <Button size="sm">{t("monitoring.addWebsite")}</Button>
            </Link>
          }
        />
      ) : (
        <>
          <div className="hidden lg:grid grid-cols-12 gap-4 px-5 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wide border-y border-slate-100 bg-slate-50/60">
            <span className="col-span-3">{t("monitoring.tableWebsite")}</span>
            <span className="col-span-2">{t("monitoring.tableStatus")}</span>
            <span className="col-span-2">{t("monitoring.tableFrequency")}</span>
            <span className="col-span-2">{t("monitoring.tableLastCheck")}</span>
            <span className="col-span-2">{t("monitoring.tableNextCheck")}</span>
            <span className="col-span-1 text-right">
              {t("monitoring.tableFails")}
            </span>
          </div>
          {websites.map((site) => (
            <div
              key={site.id}
              className="grid lg:grid-cols-12 gap-2 lg:gap-4 px-5 py-3.5 border-b border-slate-50 last:border-0 items-center text-sm"
            >
              <div className="lg:col-span-3 flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0">
                  <Globe size={15} className="text-indigo-600" />
                </div>
                <div className="min-w-0">
                  <Link
                    to={`/app/websites/${site.id}`}
                    className="font-semibold text-slate-900 font-mono truncate hover:text-indigo-600 block"
                  >
                    {site.domain}
                  </Link>
                  <p className="text-xs text-slate-400">
                    {site.health_score === null ? (
                      t("monitoring.noScore")
                    ) : (
                      <span className={scoreTextClass(site.health_score)}>
                        {site.health_score}/100
                      </span>
                    )}
                  </p>
                </div>
              </div>
              <div className="lg:col-span-2">
                <StatusBadge
                  status={
                    site.enabled
                      ? healthStatusTone(site.health_status)
                      : "neutral"
                  }
                  label={
                    site.enabled
                      ? healthStatusLabel(site.health_status)
                      : t("monitoring.monitoringOff")
                  }
                />
                <button
                  type="button"
                  disabled={busySite === site.id}
                  onClick={() => onToggle(site, !site.enabled)}
                  className="mt-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                >
                  {site.enabled
                    ? t("monitoring.pauseMonitoring")
                    : t("monitoring.activateMonitoring")}
                </button>
              </div>
              <div className="lg:col-span-2 text-slate-600">
                <select
                  aria-label={t("monitoring.frequencyFor", { domain: site.domain })}
                  value={site.interval}
                  disabled={busySite === site.id}
                  onChange={(event) =>
                    onIntervalChange(site, event.target.value)
                  }
                  className="w-full max-w-[170px] px-2 py-1.5 text-xs border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                >
                  {Object.entries(INTERVAL_LABELS).map(([value, key]) => (
                    <option key={value} value={value}>
                      {t(key)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="lg:col-span-2 text-slate-500">
                {site.last_check_at
                  ? relativeTime(site.last_check_at)
                  : t("monitoring.never")}
              </div>
              <div className="lg:col-span-2 text-slate-500">
                {site.next_scan_at
                  ? relativeTime(site.next_scan_at)
                  : t("monitoring.notScheduled")}
              </div>
              <div
                className={`lg:col-span-1 lg:text-right tabular-nums font-semibold ${
                  site.consecutive_failures > 0
                    ? "text-red-600"
                    : "text-slate-400"
                }`}
              >
                {site.consecutive_failures}
              </div>
            </div>
          ))}
        </>
      )}
    </Card>
  )
}

export default function Monitoring() {
  const { t, locale, relativeTime } = useFormat()
  const [period, setPeriod] = useState<Period>("24H")
  const [websiteId, setWebsiteId] = useState<number | null>(null)
  const [savingSite, setSavingSite] = useState<number | null>(null)
  const { showToast } = useToast()

  const overview = useApiResource<MonitoringOverview>(
    endpoints.monitoring.overview(period, websiteId),
  )

  const data = overview.data
  const summary = data?.summary
  const series = (data?.series ?? []).map((point) => ({
    time: bucketLabel(point.bucket_start, period, locale),
    uptime: point.uptime_percent,
    checks: point.checks,
    failed: point.downtime_checks,
  }))
  const selectedWebsite = data?.websites.find((site) => site.id === websiteId)

  const toggleMonitoring = async (
    site: MonitoringWebsite,
    enabled: boolean,
  ) => {
    setSavingSite(site.id)
    try {
      await api.patch(endpoints.monitoring.detail(site.id), { enabled })
      showToast(
        enabled
          ? t("monitoring.toastActivated", { domain: site.domain })
          : t("monitoring.toastPaused", { domain: site.domain }),
        "success",
      )
      overview.refetch()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setSavingSite(null)
    }
  }

  const updateInterval = async (site: MonitoringWebsite, interval: string) => {
    setSavingSite(site.id)
    try {
      await api.patch(endpoints.monitoring.detail(site.id), { interval })
      showToast(
        t("monitoring.toastInterval", {
          domain: site.domain,
          interval: intervalLabel(interval, t),
        }),
        "success",
      )
      overview.refetch()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
      overview.refetch()
    } finally {
      setSavingSite(null)
    }
  }

  if (overview.loading && !data) {
    return (
      <div className="p-6 lg:p-8 max-w-6xl mx-auto">
        <LoadingBlock label={t("monitoring.loading")} />
      </div>
    )
  }

  if (overview.error && !data) {
    return (
      <div className="p-6 lg:p-8 max-w-6xl mx-auto">
        <ErrorBlock message={overview.error} onRetry={() => overview.refetch()} />
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-start gap-4 mb-8">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">
            {t("monitoring.title")}
          </h1>
          <p className="text-slate-500 mt-1">{t("monitoring.subtitle")}</p>
          <p className="text-xs text-slate-400 mt-2 flex items-center gap-1.5">
            <Clock size={12} aria-hidden="true" />
            {summary?.last_check_at
              ? t("monitoring.lastMeasurement", {
                  time: relativeTime(summary.last_check_at),
                })
              : t("monitoring.noMeasurement")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            aria-label={t("monitoring.filterLabel")}
            value={websiteId ?? "all"}
            onChange={(event) => {
              const value = event.target.value
              setWebsiteId(value === "all" ? null : Number(value))
            }}
            className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">{t("monitoring.allWebsites")}</option>
            {(data?.websites ?? []).map((site) => (
              <option key={site.id} value={site.id}>
                {site.domain}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => overview.refetch()}
            disabled={overview.loading}
          >
            <RefreshCw
              size={13}
              className={overview.loading ? "animate-spin" : ""}
              aria-hidden="true"
            />
            {t("common.refresh")}
          </Button>
        </div>
      </div>

      {overview.error && data && (
        <p className="mb-4 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {t("monitoring.refreshError", { error: overview.error })}
        </p>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card className="p-4">
          <p className="text-xs text-slate-500 mb-1">
            {t("monitoring.statusTitle")}
          </p>
          <div className="flex items-center gap-2">
            <Activity
              size={16}
              className={
                (summary?.enabled_websites ?? 0) > 0
                  ? "text-emerald-500"
                  : "text-slate-400"
              }
              aria-hidden="true"
            />
            <span className="font-bold text-slate-900">
              {(summary?.enabled_websites ?? 0) > 0
                ? t("monitoring.statusActive")
                : t("monitoring.statusInactive")}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {t("monitoring.enabledOf", {
              enabled: summary?.enabled_websites ?? 0,
              total: summary?.monitored_websites ?? 0,
            })}
          </p>
        </Card>

        <Card className="p-4">
          <p className="text-xs text-slate-500 mb-1">
            {t("monitoring.frequencyTitle")}
          </p>
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-indigo-500" aria-hidden="true" />
            <span className="font-bold text-slate-900">
              {intervalLabel(summary?.interval ?? null, t)}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {summary?.interval === "mixed"
              ? t("monitoring.frequencyMixed")
              : t("monitoring.frequencyConfigured")}
          </p>
        </Card>

        <Card className="p-4">
          <p className="text-xs text-slate-500 mb-1">
            {t("monitoring.websiteCountTitle")}
          </p>
          <div className="flex items-center gap-2">
            <Globe size={16} className="text-indigo-500" aria-hidden="true" />
            <span className="font-bold text-slate-900">
              {summary?.monitored_websites ?? 0}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {t("monitoring.healthyNeedsAttention", {
              healthy: summary?.healthy_websites ?? 0,
              attention:
                (summary?.warning_websites ?? 0) +
                (summary?.critical_websites ?? 0),
            })}
          </p>
        </Card>

        <Card className="p-4">
          <p className="text-xs text-slate-500 mb-1">
            {t("monitoring.uptimeTitle", { period: t(PERIOD_LABELS[period]) })}
          </p>
          <div className="flex items-center gap-2">
            <span
              className={`font-bold ${
                summary?.uptime_percent === null ||
                summary?.uptime_percent === undefined
                  ? "text-slate-400"
                  : summary.uptime_percent >= 99
                    ? "text-emerald-600"
                    : summary.uptime_percent >= 95
                      ? "text-amber-600"
                      : "text-red-600"
              }`}
            >
              {summary?.uptime_percent === null ||
              summary?.uptime_percent === undefined
                ? t("monitoring.noData")
                : `${summary.uptime_percent.toFixed(2)}%`}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {summary?.uptime_checks
              ? t("monitoring.checksFailed", {
                  checks: summary.uptime_checks,
                  failed: summary.failed_checks,
                })
              : t("monitoring.noUptimeCheck")}
          </p>
        </Card>
      </div>

      <Card className="p-5 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-6">
          <div>
            <h2 className="font-bold text-slate-900">
              {t("monitoring.uptimeByCheck")}
            </h2>
            <p className="text-sm text-slate-500">
              {selectedWebsite
                ? selectedWebsite.domain
                : t("monitoring.allWebsites")}{" "}
              · {t(PERIOD_LABELS[period])}
            </p>
          </div>
          <div className="sm:ml-auto">
            <Tabs
              tabs={[...PERIODS]}
              active={period}
              onChange={(value) => setPeriod(value as Period)}
            />
          </div>
        </div>

        {series.length === 0 ? (
          <div className="py-10 text-center">
            <p className="text-sm font-medium text-slate-700">
              {t("monitoring.emptyPeriodTitle")}
            </p>
            <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
              {t("monitoring.emptyPeriodBody")}
            </p>
            <Link to="/app/websites" className="inline-block mt-4">
              <Button size="sm" variant="outline">
                {t("monitoring.openWebsites")}
              </Button>
            </Link>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={series}
              margin={{ top: 5, right: 5, bottom: 5, left: -10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 12,
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 4px 6px -1px rgba(0,0,0,0.07)",
                }}
                formatter={(value, name) => [
                  name === "uptime" ? `${Number(value).toFixed(2)}%` : String(value),
                  name === "uptime"
                    ? t("monitoring.chartUptime")
                    : t("monitoring.chartChecks"),
                ]}
              />
              <Bar dataKey="uptime" fill="#4f46e5" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <Card className="p-5">
          <h2 className="font-bold text-slate-900 mb-1">
            {t("monitoring.eventsTitle")}
          </h2>
          <p className="text-sm text-slate-500 mb-5">
            {t("monitoring.eventsSubtitle")}
          </p>
          {(data?.events ?? []).length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">
              {t("monitoring.noEvents")}
            </p>
          ) : (
            <div className="relative">
              <div className="absolute left-4 top-0 bottom-0 w-px bg-slate-200" />
              <div className="space-y-3">
                {(data?.events ?? []).map((event) => (
                  <div
                    key={event.id}
                    className="relative flex items-start gap-3 pl-9"
                  >
                    <div className="absolute left-2 top-2.5 w-5 h-5 rounded-full bg-white border border-slate-200 flex items-center justify-center">
                      {eventIcon(event)}
                    </div>
                    <div className="flex-1 bg-slate-50 rounded-xl px-3.5 py-2.5">
                      <div className="flex items-start justify-between gap-3 flex-wrap">
                        <p className="text-sm font-medium text-slate-900">
                          {event.title}
                        </p>
                        <span className="text-xs text-slate-400 flex-shrink-0">
                          {relativeTime(event.occurred_at)}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {event.detail}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-bold text-slate-900 mb-1">
            {t("monitoring.detailsTitle")}
          </h2>
          <p className="text-sm text-slate-500 mb-5">
            {t("monitoring.detailsSubtitle")}
          </p>
          <dl className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">{t("monitoring.detailPeriod")}</dt>
              <dd className="font-medium text-slate-900">
                {t(PERIOD_LABELS[period])}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">{t("monitoring.detailScope")}</dt>
              <dd className="font-medium text-slate-900">
                {selectedWebsite
                  ? selectedWebsite.domain
                  : t("monitoring.allWebsites")}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">{t("monitoring.detailChecks")}</dt>
              <dd className="font-medium text-slate-900 tabular-nums">
                {summary?.uptime_checks ?? 0}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">{t("monitoring.detailFailed")}</dt>
              <dd className="font-medium text-slate-900 tabular-nums">
                {summary?.failed_checks ?? 0}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">{t("monitoring.detailBuckets")}</dt>
              <dd className="font-medium text-slate-900 tabular-nums">
                {series.length}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-slate-400 mt-5 leading-relaxed">
            {t("monitoring.uptimeNote")}
          </p>
        </Card>
      </div>

      <WebsiteRows
        websites={data?.websites ?? []}
        onIntervalChange={(site, interval) =>
          void updateInterval(site, interval)
        }
        onToggle={(site, enabled) => void toggleMonitoring(site, enabled)}
        busySite={savingSite}
      />
    </div>
  )
}
