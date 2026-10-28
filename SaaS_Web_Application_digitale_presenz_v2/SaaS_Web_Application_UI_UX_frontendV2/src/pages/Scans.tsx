import React, { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  ScanSearch,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Zap,
  ArrowRight,
  ChevronDown,
} from "lucide-react"
import {
  Card,
  Button,
  Badge,
  ProgressBar,
  SeverityBadge,
  LoadingBlock,
  ErrorBlock,
  EmptyState,
} from "../components/ui"
import { endpoints } from "../api/endpoints"
import { useApiList, useApiResource } from "../api/hooks/useApiResource"
import type { CheckResult, Finding, Scan, ScannerRun } from "../api/types"
import { formatDuration, plainText } from "../lib/format"
import { useFormat, type Formatters } from "../lib/useFormat"

import type { MessageKey } from "../i18n"

type ScanFilter = "all" | "active" | "completed" | "partial" | "failed"

const FILTER_ENDPOINTS: Record<ScanFilter, string> = {
  all: endpoints.scans.list,
  active: `${endpoints.scans.list}?status=queued,running,pending`,
  completed: `${endpoints.scans.list}?status=completed`,
  partial: `${endpoints.scans.list}?status=partial`,
  failed: `${endpoints.scans.list}?status=failed,cancelled`,
}

const STATUS_STYLE: Record<
  Scan["status"],
  { Icon: React.FC<{ size?: number; className?: string }>; cls: string }
> = {
  pending: { Icon: Clock, cls: "text-slate-500" },
  queued: { Icon: Clock, cls: "text-slate-500" },
  running: { Icon: Clock, cls: "text-indigo-600" },
  completed: { Icon: CheckCircle, cls: "text-emerald-600" },
  partial: { Icon: AlertTriangle, cls: "text-amber-600" },
  failed: { Icon: XCircle, cls: "text-red-600" },
  cancelled: { Icon: XCircle, cls: "text-slate-500" },
}

/** Scanner run status → badge variant; the label comes from the catalogue. */
const SCANNER_STATUS_VARIANT: Record<
  ScannerRun["status"],
  "success" | "warning" | "critical" | "neutral" | "info"
> = {
  pending: "neutral",
  running: "info",
  completed: "success",
  partial: "warning",
  failed: "critical",
  timeout: "critical",
  cancelled: "neutral",
  unavailable: "neutral",
}

/** Scanner run status → catalogue key. */
const SCANNER_STATUS_KEY: Record<ScannerRun["status"], MessageKey> = {
  pending: "status.pending",
  running: "status.running",
  completed: "status.completed",
  partial: "status.partial",
  failed: "status.failed",
  timeout: "status.timeout",
  cancelled: "status.cancelled",
  unavailable: "status.unavailable",
}

/** Scan filter → catalogue key. */
const FILTER_LABELS: Record<ScanFilter, MessageKey> = {
  all: "scan.filterAll",
  active: "scan.filterActive",
  completed: "scan.filterCompleted",
  partial: "scan.filterPartial",
  failed: "scan.filterFailed",
}

type EvidenceLine = { label: string; value: string }

function evidenceText(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return plainText(value)
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return JSON.stringify(value)
}

/** Bounded, human-readable evidence for one finding (never raw HTML). */
function findingEvidence(finding: Finding, t: Formatters["t"]): EvidenceLine[] {
  const lines: EvidenceLine[] = []
  for (const [label, value] of [
    [t("scan.evidenceDetected"), finding.detected_value],
    [t("scan.evidenceExpected"), finding.expected_value],
  ] as const) {
    const text = evidenceText(value)
    if (text && text !== "{}" && text !== "[]") lines.push({ label, value: text })
  }

  const evidence = finding.evidence ?? {}
  const instances = Array.isArray(evidence.instances) ? evidence.instances : []
  const urls = instances
    .map((instance) =>
      instance && typeof instance === "object" && "uri" in instance
        ? String((instance as { uri?: unknown }).uri ?? "")
        : "",
    )
    .filter(Boolean)
  if (urls.length) {
    lines.push({
      label: t("scan.evidenceUrls", { count: urls.length }),
      value: urls.slice(0, 5).join("\n") + (urls.length > 5 ? "\n…" : ""),
    })
  }

  const addresses = Array.isArray(evidence.addresses)
    ? evidence.addresses.map((address) => String(address ?? "")).filter(Boolean)
    : []
  if (addresses.length) {
    lines.push({ label: t("scan.evidenceAddresses"), value: addresses.join(", ") })
  }

  return lines
}

function ScanDetails({ scanId }: { scanId: number }) {
  const { t, checkCategoryLabel, scannerRunReasonLabel } = useFormat()
  const detail = useApiResource<Scan>(endpoints.scans.detail(scanId))
  const scannerRuns = useApiResource<ScannerRun[]>(
    endpoints.scans.scannerRuns(scanId),
  )
  const findings = useApiList<Finding>(endpoints.scans.findings(scanId))
  // Aggregate endpoint: one request returns every category result for the
  // scan, which is what the consolidated diagnosis below is computed from.
  const checkResults = useApiList<CheckResult>(endpoints.scans.results(scanId))

  if (detail.loading) return <LoadingBlock label={t("scan.loadingResults")} />
  if (detail.error) return <ErrorBlock message={detail.error} onRetry={detail.refetch} />
  if (!detail.data) return null

  const scan = detail.data
  const checks =
    checkResults.data.length > 0
      ? checkResults.data
      : (scan.check_results ?? [])

  const scored = checks.filter((check) => typeof check.score === "number")
  const earned = scored.reduce((sum, check) => sum + (check.score ?? 0), 0)
  const possible = scored.reduce((sum, check) => sum + check.max_score, 0)
  const overall =
    possible > 0 ? Math.round((earned / possible) * 100) : scan.health_score
  const criticalCount = checks.filter((c) => c.status === "critical").length
  const warningCount = checks.filter((c) => c.status === "warning").length
  const healthyCount = checks.filter((c) => c.status === "healthy").length
  const topFixes = checks
    .filter((c) => c.status !== "healthy" && c.recommendation)
    .slice(0, 3)

  return (
    <div className="px-5 pb-5 pt-4 border-t border-slate-100 bg-slate-50/60">
      {scan.status === "partial" && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800">
          <span className="font-semibold">{t("scan.partialBanner")}</span>{" "}
          {scan.failure_message || t("scan.partialBannerBody")}
        </div>
      )}

      {scan.status === "failed" && scan.failure_message && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">
          <span className="font-semibold">{t("scan.failedBanner")}</span>{" "}
          {scan.failure_message}
        </div>
      )}

      {/* Live progress for queued / running scans */}
      {scan.is_active && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-slate-600 mb-1">
            <span>{scan.current_step || t("scan.waitingWorker")}</span>
            <span className="font-semibold tabular-nums">{scan.progress}%</span>
          </div>
          <ProgressBar value={scan.progress} max={100} />
        </div>
      )}

      {/* Per-scanner outcome: a scan-level status alone hides which tool
          timed out or failed. */}
      {(scannerRuns.loading || scannerRuns.data?.length || scannerRuns.error) && (
        <div className="mb-4 rounded-xl border border-slate-200 bg-white p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {t("scan.scannerRuns")}
            </p>
            {scan.status === "partial" && (
              <Badge variant="warning">{t("scan.incompleteCoverage")}</Badge>
            )}
          </div>
          {scannerRuns.loading && !scannerRuns.data ? (
            <p className="text-xs text-slate-400">
              {t("scan.loadingScannerRuns")}
            </p>
          ) : scannerRuns.error ? (
            <p className="text-xs text-amber-700">
              {t("scan.scannerRunsError", { error: scannerRuns.error })}
            </p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {(scannerRuns.data ?? []).map((run) => {
                const variant = SCANNER_STATUS_VARIANT[run.status] ?? "neutral"
                const statusLabel = SCANNER_STATUS_KEY[run.status]
                  ? t(SCANNER_STATUS_KEY[run.status])
                  : run.status
                const partialReason =
                  run.status === "completed"
                    ? null
                    : scannerRunReasonLabel(
                        typeof run.metadata?.partial_reason === "string"
                          ? run.metadata.partial_reason
                          : "",
                        run.exit_code,
                      )
                const reasonTone =
                  run.status === "failed" || run.status === "timeout"
                    ? "text-red-600"
                    : "text-amber-700"
                return (
                  <div
                    key={run.id}
                    className="flex flex-wrap items-center gap-2 border-t border-slate-50 py-1.5 first:border-t-0 first:pt-0"
                  >
                    <span className="min-w-24 text-xs font-semibold text-slate-700">
                      {run.scanner}
                    </span>
                    <Badge variant={variant}>{statusLabel}</Badge>
                    <span className="text-xs font-mono text-slate-400">
                      {run.duration_ms !== null
                        ? formatDuration(Math.round(run.duration_ms / 1000))
                        : "—"}
                    </span>
                    {partialReason ? (
                      <span className={`text-xs font-medium ${reasonTone}`}>
                        {t("scan.incomplete", { reason: partialReason })}
                      </span>
                    ) : (
                      run.exit_code !== null && (
                        <span className="text-xs font-mono text-slate-400">
                          {t("scan.exitCode", { code: run.exit_code })}
                        </span>
                      )
                    )}
                    {run.error_message && (
                      <span className="min-w-0 flex-1 truncate text-xs text-slate-500" title={run.error_message}>
                        {run.error_message}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Consolidated diagnosis — computed from /scans/{id}/results/ */}
      {checks.length > 0 && (
        <div className="mb-4 p-4 bg-white border border-slate-200 rounded-xl">
          <div className="flex items-center justify-between gap-3 mb-2">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                {t("scan.diagnosis")}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                {checks.length === 1
                  ? t("scan.diagnosisAggregatedOne")
                  : t("scan.diagnosisAggregatedMany", { count: checks.length })}
              </p>
              {scan.status === "partial" && (
                <p className="mt-1 text-xs font-medium text-amber-700">
                  {t("scan.diagnosisPartialNote")}
                </p>
              )}
            </div>
            <span
              className={`text-2xl font-black tabular-nums ${
                overall === null
                  ? "text-slate-400"
                  : overall >= 80
                    ? "text-emerald-600"
                    : overall >= 60
                      ? "text-amber-600"
                      : "text-red-600"
              }`}
            >
              {overall ?? "—"}
              <span className="text-xs font-medium text-slate-400">/100</span>
            </span>
          </div>
          {overall !== null && (
            <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  overall >= 80
                    ? "bg-emerald-500"
                    : overall >= 60
                      ? "bg-amber-500"
                      : "bg-red-500"
                }`}
                style={{ width: `${overall}%` }}
              />
            </div>
          )}
          <div className="grid grid-cols-3 gap-2 mt-3 text-center">
            <div className="rounded-lg bg-emerald-50 border border-emerald-100 py-1.5">
              <p className="text-sm font-bold text-emerald-700 tabular-nums">
                {healthyCount}
              </p>
              <p className="text-[11px] text-emerald-700">
                {t("scan.healthy")}
              </p>
            </div>
            <div className="rounded-lg bg-amber-50 border border-amber-100 py-1.5">
              <p className="text-sm font-bold text-amber-700 tabular-nums">
                {warningCount}
              </p>
              <p className="text-[11px] text-amber-700">{t("scan.warnings")}</p>
            </div>
            <div className="rounded-lg bg-red-50 border border-red-100 py-1.5">
              <p className="text-sm font-bold text-red-700 tabular-nums">
                {criticalCount}
              </p>
              <p className="text-[11px] text-red-700">{t("scan.critical")}</p>
            </div>
          </div>
          {topFixes.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-slate-500 mb-1">
                {t("scan.fixFirst")}
              </p>
              <ul className="text-xs text-slate-600 space-y-1 list-disc pl-4">
                {topFixes.map((check) => (
                  <li key={check.id}>
                    <span className="font-medium capitalize">
                      {checkCategoryLabel(check.category)}:
                    </span>{" "}
                    {check.recommendation}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Per-category results */}
      {checkResults.error && !checkResults.data.length && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
          {t("scan.resultsError", { error: checkResults.error })}
        </p>
      )}
      {checks.length > 0 ? (
        <div className="grid sm:grid-cols-2 gap-3 mb-4">
          {checks.map((check) => (
            <div
              key={check.id}
              className="p-3 bg-white border border-slate-200 rounded-xl"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-700 capitalize">
                  {checkCategoryLabel(check.category)}
                </span>
                <Badge
                  variant={
                    check.status === "healthy"
                      ? "success"
                      : check.status === "warning"
                        ? "warning"
                        : check.status === "critical"
                          ? "critical"
                          : "neutral"
                  }
                >
                  {check.score ?? "—"}/{check.max_score}
                </Badge>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                {check.summary || t("scan.noSummary")}
              </p>
              {check.recommendation && (
                <p className="text-xs text-indigo-700 mt-1.5 border-l-2 border-indigo-200 pl-2">
                  {check.recommendation}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500 mb-4">
          {t("scan.noCategoryResult")}
        </p>
      )}

      {/* Findings */}
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
        {t("scan.findings")} {findings.count > 0 && `(${findings.count})`}
      </p>

      {findings.loading ? (
        <p className="text-xs text-slate-400">{t("scan.loadingFindings")}</p>
      ) : findings.data.length === 0 ? (
        <p className="text-xs text-slate-500">{t("scan.noFindings")}</p>
      ) : (
        <div className="flex flex-col gap-2 max-h-72 overflow-y-auto">
          {findings.data.map((finding) => {
            const description = plainText(finding.description)
            const recommendation = plainText(finding.recommendation)
            const evidence = findingEvidence(finding, t)
            return (
              <div
                key={finding.id}
                className="p-3 bg-white border border-slate-200 rounded-xl"
              >
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <SeverityBadge severity={finding.severity} />
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    {finding.scanner}
                  </span>
                  {/* Scanner names and check codes stay as the backend sends
                      them: they are technical identifiers, not prose. */}
                  <span className="text-xs font-semibold text-slate-900">
                    {plainText(finding.title)}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    {finding.check_code}
                  </span>
                </div>
                {description && (
                  <p className="text-xs text-slate-600">{description}</p>
                )}
                {recommendation && (
                  <p className="text-xs text-indigo-700 mt-1">
                    {recommendation}
                  </p>
                )}
                {evidence.length > 0 && (
                  <details className="mt-2 group">
                    <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-700">
                      {t("scan.evidence")}
                    </summary>
                    <dl className="mt-1 space-y-1">
                      {evidence.map((line) => (
                        <div key={line.label} className="text-xs">
                          <dt className="font-medium text-slate-500">
                            {line.label}
                          </dt>
                          <dd className="font-mono text-slate-600 whitespace-pre-wrap break-all">
                            {line.value}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function Scans() {
  const { t, relativeTime, formatDateTime, scanStatusLabel, scanTypeLabel, scanTriggerLabel } =
    useFormat()
  const [filter, setFilter] = useState<ScanFilter>("all")
  const [refreshKey, setRefreshKey] = useState(0)
  const [expanded, setExpanded] = useState<number | null>(null)

  // Read from the previous response so the polling interval can be derived in
  // the same render pass (see the `pollsActiveScans` usage below).
  const [pollsActiveScans, setPollsActiveScans] = useState(false)

  const {
    data: rows,
    count,
    error,
    loading,
    refetch,
  } = useApiList<Scan>(
    FILTER_ENDPOINTS[filter],
    `${filter}:${refreshKey}`,
    // Only poll while a scan is actually queued or running: the interval is
    // re-evaluated on every render, so it starts as soon as one appears and
    // stops as soon as the last one finishes.
    pollsActiveScans ? 5000 : 0,
  )

  const hasActive = rows.some((scan) => scan.is_active)

  useEffect(() => {
    setPollsActiveScans(hasActive)
  }, [hasActive])

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-8">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">{t("scan.title")}</h1>
          <p className="text-slate-500 mt-1">
            {t("scan.subtitle")}
            {count > 0 &&
              (count > 1
                ? t("scan.recordMany", { count })
                : t("scan.recordOne"))}
            .
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            {t("scan.refresh")}
          </Button>
          <Link to="/app/websites">
            <Button className="gap-2">
              <Zap size={14} /> {t("scan.runNew")}
            </Button>
          </Link>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {(["all", "active", "completed", "partial", "failed"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 text-sm rounded-lg border font-medium transition-colors capitalize ${
              filter === f
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
            }`}
          >
            {t(FILTER_LABELS[f])}
          </button>
        ))}
      </div>

      {loading && !rows.length ? (
        <LoadingBlock label={t("scan.loadingHistory")} />
      ) : error && !rows.length ? (
        <ErrorBlock message={error} onRetry={refetch} />
      ) : (
        <Card className="overflow-hidden">
          {/* Table header */}
          <div className="hidden md:grid grid-cols-6 gap-4 px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide border-b border-slate-100 bg-slate-50">
            <span className="col-span-2">{t("scan.tableWebsite")}</span>
            <span>{t("scan.tableScore")}</span>
            <span>{t("scan.tableType")}</span>
            <span>{t("scan.tableStatus")}</span>
            <span>{t("scan.tableDuration")}</span>
          </div>

          {rows.length === 0 ? (
            <EmptyState
              icon={<ScanSearch size={26} />}
              title={t("scan.emptyTitle")}
              description={t("scan.emptyBody")}
              action={
                <Link to="/app/websites">
                  <Button size="sm" className="gap-1.5">
                    <Zap size={13} /> {t("scan.runScan")}
                  </Button>
                </Link>
              }
            />
          ) : (
            rows.map((scan) => {
              const { Icon, cls } = STATUS_STYLE[scan.status]
              const label = scanStatusLabel(scan.status)
              const isOpen = expanded === scan.id
              return (
                <div key={scan.id} className="border-b border-slate-50 last:border-0">
                  <button
                    type="button"
                    onClick={() => setExpanded(isOpen ? null : scan.id)}
                    aria-expanded={isOpen}
                    className="w-full grid md:grid-cols-6 gap-4 px-5 py-4 hover:bg-slate-50 transition-colors items-center text-left"
                  >
                    {/* Website */}
                    <div className="md:col-span-2 flex items-center gap-2">
                      <ChevronDown
                        size={14}
                        className={`text-slate-400 transition-transform ${
                          isOpen ? "rotate-180" : ""
                        }`}
                        aria-hidden="true"
                      />
                      <div>
                        <span className="text-sm font-semibold text-slate-900 font-mono">
                          {scan.domain}
                        </span>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {formatDateTime(scan.created_at)}
                        </p>
                      </div>
                    </div>

                    {/* Score */}
                    <div className="hidden md:block">
                      <span
                        className={`text-sm font-black tabular-nums ${
                          scan.status === "partial"
                            ? "text-amber-600"
                            : scan.health_score === null
                              ? "text-slate-400"
                              : scan.health_score >= 80
                                ? "text-emerald-600"
                                : scan.health_score >= 60
                                  ? "text-amber-600"
                                  : "text-red-600"
                        }`}
                      >
                        {scan.health_score ?? "—"}
                      </span>
                    </div>

                    {/* Type */}
                    <div className="hidden md:block">
                      <span className="text-xs font-semibold px-2 py-0.5 bg-slate-100 text-slate-600 rounded uppercase">
                        {scanTypeLabel(scan.scan_type)}
                      </span>
                    </div>

                    {/* Status */}
                    <div className="hidden md:flex items-center gap-1.5">
                      <Icon
                        size={13}
                        className={`${cls} ${
                          scan.status === "running" ? "animate-spin" : ""
                        }`}
                        aria-hidden="true"
                      />
                      <span className={`text-xs font-medium ${cls}`}>{label}</span>
                    </div>

                    {/* Duration */}
                    <div className="hidden md:block text-sm text-slate-500 font-mono">
                      {formatDuration(scan.duration_seconds)}
                    </div>

                    {/* Mobile fallback */}
                    <div className="md:hidden flex items-center justify-between">
                      <span className="text-sm font-bold text-slate-700 tabular-nums">
                        {scan.health_score ?? "—"}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <Icon size={13} className={cls} aria-hidden="true" />
                        <span className={`text-xs font-medium ${cls}`}>
                          {label}
                        </span>
                      </div>
                    </div>
                  </button>

                  {isOpen && (
                    <>
                      <ScanDetails scanId={scan.id} />
                      <div className="px-5 pb-4 flex items-center gap-3 text-xs">
                        <Link
                          to={`/app/websites/${scan.website_id}`}
                          className="text-indigo-600 hover:text-indigo-700 font-medium inline-flex items-center gap-1"
                        >
                          {t("scan.openWebsite")} <ArrowRight size={11} />
                        </Link>
                        <span className="text-slate-400">
                          {t("scan.triggered", {
                            trigger: scanTriggerLabel(scan.trigger),
                            time: relativeTime(scan.created_at),
                          })}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              )
            })
          )}
        </Card>
      )}

      {hasActive && (
        <p className="flex items-center gap-2 text-xs text-slate-500 mt-4">
          <AlertTriangle size={12} className="text-amber-500" aria-hidden="true" />
          {t("scan.pollingNote")}
        </p>
      )}
    </div>
  )
}
