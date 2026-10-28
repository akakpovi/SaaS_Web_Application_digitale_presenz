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
  Download,
  FileText,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from "lucide-react"
import {
  Button,
  Card,
  EmptyState,
  ErrorBlock,
  LoadingBlock,
  ScoreRing,
} from "../components/ui"
import { UpgradeBadge, useUpgrade } from "../components/UpgradePrompt"
import { endpoints } from "../api/endpoints"
import { api } from "../api/client"
import {
  apiErrorMessage,
  useApiList,
} from "../api/hooks/useApiResource"
import type { Report, ReportCheckCategory } from "../api/types"
import { LOCALE_TAGS, type Locale } from "../i18n"
import { useFormat } from "../lib/useFormat"

/**
 * Month names follow the active interface language: a German report titled
 * "October 2026" reads like a US export, "Oktober 2026" is what a German user
 * expects. Category labels go through the shared `checks.*` catalogue entries
 * so a new backend category is de-underscored rather than dropped.
 */
function monthLabel(value: string, locale: Locale): string {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(LOCALE_TAGS[locale], {
    month: "long",
    year: "numeric",
  })
}

function shortMonth(value: string, locale: Locale): string {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(LOCALE_TAGS[locale], { month: "short" })
}

function breakdownRows(report: Report) {
  return Object.entries(report.check_breakdown)
    .map(([key, value]) => ({ key, ...value }))
    .filter(
      (row): row is { key: string } & ReportCheckCategory =>
        row.max_score !== null && row.max_score > 0,
    )
}

function breakdownColor(score: number, max: number): string {
  if (score >= max * 0.9) return "bg-emerald-500"
  if (score >= max * 0.7) return "bg-amber-500"
  return "bg-red-500"
}

export default function Reports() {
  const { t, locale, formatDateTime, checkCategoryLabel } = useFormat()
  const reports = useApiList<Report>(endpoints.reports.list)
  const { guard } = useUpgrade()
  const [websiteId, setWebsiteId] = useState<number | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const websiteIds = Array.from(
    new Set(reports.data.map((report) => report.website_id)),
  )
  const effectiveWebsiteId = websiteId ?? websiteIds[0] ?? null
  const websiteReports = reports.data.filter(
    (report) => report.website_id === effectiveWebsiteId,
  )
  const current = websiteReports[0] ?? null
  const rows = current ? breakdownRows(current) : []
  const history = current
    ? current.score_history
        .filter((point) => point.score !== null)
        .map((point) => ({
          name: shortMonth(point.date, locale),
          score: point.score as number,
        }))
    : []

  const refresh = async () => {
    setRefreshing(true)
    setDownloadError(null)
    try {
      await api.get(endpoints.reports.refresh)
      reports.refetch()
    } catch (err) {
      setDownloadError(apiErrorMessage(err))
    } finally {
      setRefreshing(false)
    }
  }

  const download = async (report: Report) => {
    // Intercepted before the request: a Free account gets the upgrade panel
    // instead of a 403 from the PDF endpoint.
    if (!guard("reports.pdf")) return
    if (!report.latest_scan_id) {
      setDownloadError("No completed scan exists for this report period.")
      return
    }
    setDownloading(report.id)
    setDownloadError(null)
    try {
      const blob = await api.download(endpoints.reports.pdf(report.latest_scan_id))
      if (!blob.type.includes("application/pdf")) {
        throw new Error(
          "The PDF renderer returned a non-PDF response. Check the server logs for WeasyPrint.",
        )
      }
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `presence-${report.website_domain}-${report.period_start}.pdf`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setDownloadError(apiErrorMessage(err))
    } finally {
      setDownloading(null)
    }
  }

  if (reports.loading && !reports.data.length) {
    return (
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <LoadingBlock label={t("reports.loading")} />
      </div>
    )
  }

  if (reports.error && !reports.data.length) {
    return (
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <ErrorBlock message={reports.error} onRetry={() => reports.refetch()} />
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-start gap-4 mb-8">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">{t("reports.title")}</h1>
          <p className="text-slate-500 mt-1">{t("reports.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          {websiteIds.length > 1 && (
            <select
              aria-label={t("reports.filterAria")}
              value={effectiveWebsiteId ?? ""}
              onChange={(event) => setWebsiteId(Number(event.target.value))}
              className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {websiteIds.map((id) => {
                const report = reports.data.find((row) => row.website_id === id)
                return (
                  <option key={id} value={id}>
                    {report?.website_domain ?? `Website ${id}`}
                  </option>
                )
              })}
            </select>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refresh()}
            disabled={refreshing || reports.loading}
          >
            <RefreshCw
              size={13}
              className={refreshing ? "animate-spin" : ""}
              aria-hidden="true"
            />
            {t("common.refresh")}
          </Button>
        </div>
      </div>

      {reports.error && reports.data.length > 0 && (
        <p className="mb-4 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {t("reports.refreshFailed")} {reports.error}
        </p>
      )}

      {downloadError && (
        <p className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {downloadError}
        </p>
      )}

      {!current ? (
        <Card>
          <EmptyState
            icon={<FileText size={26} />}
            title={t("reports.emptyTitle")}
            description={t("reports.emptyHint")}
            action={
              <Link to="/app/websites">
                <Button size="sm">{t("reports.openWebsites")}</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <Card className="p-6">
              <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">
                    {t("reports.monthlyReport")} {current.website_domain}
                  </p>
                  <h2 className="text-xl font-bold text-slate-900">
                    {monthLabel(current.period_start, locale)}
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    {t(
                      current.total_scans === 1
                        ? "reports.scanSummaryOne"
                        : "reports.scanSummaryMany",
                      {
                        count: current.total_scans,
                        date: formatDateTime(current.generated_at),
                      },
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <UpgradeBadge feature="reports.pdf" />
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!current.latest_scan_id || downloading === current.id}
                    onClick={() => void download(current)}
                  >
                    <Download size={14} />
                    {downloading === current.id ? "Preparing…" : "Download PDF"}
                  </Button>
                </div>
              </div>

              <div className="flex items-center gap-8 mb-6 pb-6 border-b border-slate-100">
                {current.current_score === null ? (
                  <div className="w-[100px] h-[100px] rounded-full border-8 border-slate-100 flex items-center justify-center text-slate-400 text-sm">
                    —
                  </div>
                ) : (
                  <ScoreRing score={current.current_score} size={100} />
                )}
                <div>
                  <p className="text-sm text-slate-500 mb-2">{t("reports.overallHealth")}</p>
                  {current.score_change === null ? (
                    <p className="text-sm text-slate-500">
                      {t("reports.noPreviousScore")}
                    </p>
                  ) : current.score_change > 0 ? (
                    <div className="flex items-center gap-2 mb-1">
                      <TrendingUp size={16} className="text-emerald-500" />
                      <span className="text-emerald-600 font-semibold">
                        {t("reports.pointsUp", { count: current.score_change })}
                      </span>
                    </div>
                  ) : current.score_change < 0 ? (
                    <div className="flex items-center gap-2 mb-1">
                      <TrendingDown size={16} className="text-red-500" />
                      <span className="text-red-600 font-semibold">
                        {t("reports.pointsDown", { count: current.score_change })}
                      </span>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-600 font-semibold">
                      {t("reports.stableScore")}
                    </p>
                  )}
                  <p className="text-sm text-slate-500">
                    {current.previous_score !== null &&
                      `${t("reports.firstScore", { score: current.previous_score })} `}
                    {current.period_start} → {current.period_end}
                  </p>
                </div>
              </div>

              <div className="space-y-4 mb-6">
                <h3 className="font-semibold text-slate-800">{t("reports.scoreBreakdown")}</h3>
                {rows.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    {t("reports.noCategoryScore")}
                  </p>
                ) : (
                  rows.map((row) => {
                    const score = row.avg_score ?? 0
                    const max = row.max_score ?? 0
                    return (
                      <div key={row.key} className="flex items-center gap-4">
                        <span className="text-sm text-slate-600 w-44 flex-shrink-0">
                          {checkCategoryLabel(row.key)}
                        </span>
                        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${breakdownColor(score, max)}`}
                            style={{ width: `${Math.min(100, (score / max) * 100)}%` }}
                          />
                        </div>
                        <span className="text-sm font-semibold text-slate-800 tabular-nums w-16 text-right">
                          {score.toFixed(1)}/{max}
                        </span>
                        <span className="text-xs text-slate-400 w-20 text-right">
                          {t("reports.criticalShort", { count: row.critical_count })}
                        </span>
                      </div>
                    )
                  })
                )}
              </div>

              <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
                <p className="text-sm font-semibold text-amber-800 mb-2">
                  {t("reports.recommendedActions")}
                </p>
                {current.recommendations.length === 0 ? (
                  <p className="text-sm text-amber-700">
                    {t("reports.noRecommendation")}
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {current.recommendations.map((recommendation, index) => (
                      <li
                        key={`${index}-${recommendation.slice(0, 24)}`}
                        className="text-sm text-amber-700"
                      >
                        • {recommendation}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          </div>

          <div className="flex flex-col gap-4">
            <Card className="p-5">
              <h3 className="font-semibold text-slate-900 mb-4">{t("reports.scoreHistory")}</h3>
              {history.length === 0 ? (
                <p className="text-sm text-slate-500">
                  {t("reports.noScoredScan")}
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart
                    data={history}
                    margin={{ top: 0, right: 0, bottom: 0, left: -20 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="#f1f5f9"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 10,
                        border: "1px solid #e2e8f0",
                        fontSize: 12,
                      }}
                      formatter={(value) => [
                        String(value ?? "—"),
                        t("reports.scoreChartLabel"),
                      ]}
                    />
                    <Bar dataKey="score" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card className="overflow-hidden">
              <div className="p-4 pb-0">
                <h3 className="font-semibold text-slate-900">{t("reports.history")}</h3>
              </div>
              <div className="divide-y divide-slate-100">
                {websiteReports.map((report) => (
                  <div
                    key={report.id}
                    className="flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors gap-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900">
                        {monthLabel(report.period_start, locale)}
                      </p>
                      <div className="flex items-center gap-1 mt-0.5">
                        {report.score_change !== null && report.score_change > 0 ? (
                          <TrendingUp size={10} className="text-emerald-500" />
                        ) : report.score_change !== null &&
                          report.score_change < 0 ? (
                          <TrendingDown size={10} className="text-red-500" />
                        ) : null}
                        <span className="text-xs text-slate-400">
                          {t(
                            report.total_scans === 1
                              ? "reports.scanCountOne"
                              : "reports.scanCountMany",
                            { count: report.total_scans },
                          )}
                          {report.score_change !== null && (
                            <>
                              {" "}
                              ·{" "}
                              {t("reports.pointsShort", {
                                count:
                                  report.score_change > 0
                                    ? `+${report.score_change}`
                                    : report.score_change,
                              })}
                            </>
                          )}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span
                        className={`text-lg font-black ${
                          report.current_score === null
                            ? "text-slate-300"
                            : report.current_score >= 80
                              ? "text-emerald-600"
                              : "text-amber-600"
                        }`}
                      >
                        {report.current_score ?? "—"}
                      </span>
                      <UpgradeBadge feature="reports.pdf" />
                      <button
                        onClick={() => void download(report)}
                        disabled={
                          !report.latest_scan_id || downloading === report.id
                        }
                        className="text-slate-400 hover:text-slate-600 disabled:opacity-40 disabled:cursor-not-allowed"
                        aria-label={t("reports.downloadFor", {
                          period: monthLabel(report.period_start, locale),
                        })}
                      >
                        <Download size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
