import { useState } from "react"
import { Link } from "react-router-dom"
import {
  AlertTriangle,
  Bot,
  Loader2,
  RefreshCw,
  ScanLine,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react"

import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { apiErrorMessage, useApiList, useApiResource } from "../api/hooks/useApiResource"
import type {
  AdvisorRecommendationsResponse,
  AssetSecurityFinding,
  MonitoringPolicy,
  Organization,
  OrganizationRole,
  Scan,
} from "../api/types"
import { useFormat } from "../lib/useFormat"
import type { MessageKey } from "../i18n"
import { useToast } from "./Toast"
import {
  Badge,
  Button,
  Card,
  ErrorBlock,
  LoadingBlock,
  SeverityBadge,
} from "./ui"

/** Roles the backend lets launch a scan or change the scan policy. */
const SCAN_ROLES: OrganizationRole[] = ["owner", "admin", "analyst"]

/** Scheduled scan profile → catalogue key. */
const POLICY_KEYS: Record<MonitoringPolicy["scan_type"], MessageKey> = {
  health: "assetSecurity.policyHealth",
  security: "assetSecurity.policySecurity",
  full: "assetSecurity.policyFull",
}

function PriorityRow({ finding }: { finding: AssetSecurityFinding }) {
  const { t, relativeTime } = useFormat()
  return (
    <li className="flex items-start gap-3 border-t border-slate-50 px-5 py-3 first:border-t-0">
      <SeverityBadge severity={finding.severity} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800">
          {finding.vulnerability_name}
        </p>
        <p className="text-xs text-slate-500">
          {finding.scanner_source}
          {t("assetSecurity.detected", {
            time: relativeTime(finding.detected_at),
          })}
          {finding.status === "resolved"
            ? t("assetSecurity.resolved", {
                time: relativeTime(finding.resolved_at),
              })
            : ""}
        </p>
      </div>
      <Badge variant={finding.status === "open" ? "warning" : "success"}>
        {finding.status === "open"
          ? t("assetSecurity.statusOpen")
          : t("assetSecurity.statusResolved")}
      </Badge>
    </li>
  )
}

/**
 * Automated security block of one asset.
 *
 * It reflects what the backend actually stored: the latest scan, the scan
 * policy, the ZAP/Nuclei findings of this asset and the advisor's persisted
 * recommendations.  Nothing here simulates progress or fabricates a result —
 * every state comes from an API response, and empty/failed states say so.
 *
 * It is rendered on the website detail page, which is where the automated
 * loop becomes visible: scan → findings → AI recommendations → discuss.
 */
export default function AssetSecurityPanel({
  websiteId,
  organizationId,
  latestScan,
  activeScan,
  scans,
  refreshKey,
  onScanStarted,
}: {
  websiteId: number
  organizationId: string | null
  latestScan: Scan | null
  activeScan: Scan | null
  /** Recent scans, newest first; used to find the last analysed one. */
  scans: Scan[]
  refreshKey: number
  onScanStarted: () => void
}) {
  const { showToast } = useToast()
  const { t, relativeTime, formatDateTime, scanTypeLabel } = useFormat()
  const [showResolved, setShowResolved] = useState(false)
  const [starting, setStarting] = useState(false)
  const [savingPolicy, setSavingPolicy] = useState(false)

  const organizations = useApiList<Organization>(endpoints.organizations.list)
  const role =
    organizations.data.find((org) => org.id === organizationId)?.role ?? null
  const canScan = role ? SCAN_ROLES.includes(role) : false

  const findings = useApiList<AssetSecurityFinding>(
    organizationId
      ? endpoints.advisory.assetFindings(organizationId, websiteId, {
          status: showResolved ? "all" : "open",
        })
      : null,
    `${refreshKey}-${showResolved ? "all" : "open"}`,
  )

  const policy = useApiResource<MonitoringPolicy>(
    endpoints.monitoring.detail(websiteId),
    refreshKey,
  )

  // The advisor analyses completed scans.  A security/full scan is preferred
  // over a health scan because its findings are what the recommendations are
  // about; the newest completed scan is the fallback.
  const completed = scans.filter((scan) => scan.status === "completed")
  const completedScan =
    completed.find((scan) => scan.scan_type !== "health") ?? completed[0] ?? null
  const recommendations = useApiResource<AdvisorRecommendationsResponse>(
    completedScan ? endpoints.advisory.recommendations(completedScan.id) : null,
    refreshKey,
  )

  const updatePolicy = async (scanType: MonitoringPolicy["scan_type"]) => {
    setSavingPolicy(true)
    try {
      await api.patch(endpoints.monitoring.detail(websiteId), {
        scan_type: scanType,
      })
      showToast(
        t("assetSecurity.policySaved", { policy: t(POLICY_KEYS[scanType]) }),
        "success",
      )
      policy.refetch()
    } catch (error) {
      showToast(apiErrorMessage(error), "error")
    } finally {
      setSavingPolicy(false)
    }
  }

  const runFullScan = async () => {
    if (!canScan) return
    setStarting(true)
    try {
      await api.post(endpoints.websites.scan(websiteId), { scan_type: "full" })
      showToast("Full scan queued. Findings update when it completes.", "success")
      onScanStarted()
    } catch (error) {
      showToast(apiErrorMessage(error), "error")
    } finally {
      setStarting(false)
    }
  }

  const openCount = showResolved
    ? findings.data.filter((row) => row.status === "open").length
    : findings.count
  const advisorHref = organizationId
    ? `/app/advisor?org=${organizationId}&asset=${websiteId}`
    : "/app/advisor"

  return (
    <div className="mt-6 flex flex-col gap-4">
      {/* Automated loop header: last scan, policy, actions */}
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-50">
              <ScanLine size={18} className="text-indigo-600" aria-hidden="true" />
            </div>
            <div>
              <h2 className="font-bold text-slate-900">
                {t("assetSecurity.title")}
              </h2>
              <p className="mt-0.5 text-sm text-slate-500">
                {latestScan
                  ? t("assetSecurity.latestScan", {
                      type: scanTypeLabel(latestScan.scan_type),
                      id: latestScan.id,
                      time: formatDateTime(
                        latestScan.completed_at ?? latestScan.created_at,
                      ),
                    })
                  : t("assetSecurity.noScan")}
              </p>
              {policy.data ? (
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                  <span>
                    {t("assetSecurity.every", { interval: policy.data.interval })}
                    {policy.data.enabled
                      ? ` · ${t("assetSecurity.nextCheck", {
                          time: relativeTime(policy.data.next_scan_at),
                        })}`
                      : ` · ${t("assetSecurity.monitoringPaused")}`}
                  </span>
                  <span aria-hidden="true">·</span>
                  {canScan ? (
                    <label className="inline-flex items-center gap-1.5">
                      <span className="sr-only">
                        {t("assetSecurity.policyLabel")}
                      </span>
                      <select
                        value={policy.data.scan_type}
                        disabled={savingPolicy}
                        onChange={(event) =>
                          void updatePolicy(
                            event.target.value as MonitoringPolicy["scan_type"],
                          )
                        }
                        className="rounded-md border border-slate-300 bg-white px-1.5 py-0.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                      >
                        <option value="health">
                          {t("assetSecurity.policyHealth")}
                        </option>
                        <option value="security">
                          {t("assetSecurity.policySecurity")}
                        </option>
                        <option value="full">
                          {t("assetSecurity.policyFull")}
                        </option>
                      </select>
                    </label>
                  ) : (
                    <span>{t(POLICY_KEYS[policy.data.scan_type])}</span>
                  )}
                </div>
              ) : policy.loading ? (
                <p className="mt-1 text-xs text-slate-400">
                  {t("assetSecurity.loadingPolicy")}
                </p>
              ) : null}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              to={advisorHref}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:border-indigo-300 hover:text-indigo-700"
            >
              <Bot size={14} aria-hidden="true" />
              {t("assetSecurity.discuss")}
            </Link>
            <Button
              size="sm"
              variant="outline"
              onClick={runFullScan}
              disabled={!canScan || starting || Boolean(activeScan)}
            >
              {starting ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              {activeScan
                ? t("assetSecurity.scanning")
                : t("assetSecurity.runFullScan")}
            </Button>
          </div>
        </div>

        {latestScan?.status === "failed" && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" aria-hidden="true" />
            <p>
              {t("assetSecurity.lastScanFailed", {
                reason: latestScan.failure_message
                  ? `: ${latestScan.failure_message}`
                  : ".",
              })}
            </p>
          </div>
        )}

        {latestScan?.status === "partial" && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" aria-hidden="true" />
            <p>
              {t("assetSecurity.lastScanPartial", {
                reason: latestScan.failure_message
                  ? `: ${latestScan.failure_message}`
                  : ".",
              })}
            </p>
          </div>
        )}

        {policy.data && policy.data.consecutive_failures > 0 && (
          <p className="mt-3 text-xs text-amber-700">
            {t("assetSecurity.monitoringFailures", {
              count: policy.data.consecutive_failures,
            })}
          </p>
        )}
      </Card>

      {/* Findings */}
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 p-5 pb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert size={16} className="text-slate-400" aria-hidden="true" />
            <h2 className="font-bold text-slate-900">
              {t("assetSecurity.findingsTitle")}
            </h2>
            <Badge variant={openCount > 0 ? "warning" : "success"}>
              {t("assetSecurity.openCount", { count: openCount })}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={showResolved ? "secondary" : "ghost"}
              onClick={() => setShowResolved((value) => !value)}
            >
              {showResolved
                ? t("assetSecurity.openOnly")
                : t("assetSecurity.includeResolved")}
            </Button>
            <Link
              to={advisorHref}
              className="text-sm text-indigo-600 hover:text-indigo-700"
            >
              {t("assetSecurity.askAdvisor")}
            </Link>
          </div>
        </div>

        {findings.loading && findings.data.length === 0 ? (
          <LoadingBlock label={t("assetSecurity.loadingFindings")} />
        ) : findings.error ? (
          <div className="p-5">
            <ErrorBlock message={findings.error} onRetry={findings.refetch} />
          </div>
        ) : findings.data.length === 0 ? (
          <div className="px-5 pb-5">
            <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <ShieldCheck
                size={18}
                className="mt-0.5 flex-shrink-0 text-emerald-600"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-emerald-900">
                  {t("assetSecurity.noFindings")}
                </p>
                <p className="mt-1 text-xs text-emerald-800">
                  {t("assetSecurity.noFindingsHint")}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <ul>
            {findings.data.map((finding) => (
              <PriorityRow key={finding.id} finding={finding} />
            ))}
          </ul>
        )}
      </Card>

      {/* AI recommendations of the latest completed scan */}
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between p-5 pb-3">
          <div className="flex items-center gap-2">
            <Bot size={16} className="text-slate-400" aria-hidden="true" />
            <h2 className="font-bold text-slate-900">
              {t("assetSecurity.recommendationsTitle")}
            </h2>
          </div>
          {completedScan && (
            <Link
              to={`/app/scans`}
              className="text-sm text-indigo-600 hover:text-indigo-700"
            >
              {t("assetSecurity.scanRef", { id: completedScan.id })}
            </Link>
          )}
        </div>

        {!completedScan ? (
          <p className="px-5 pb-5 text-sm text-slate-500">
            {t("assetSecurity.noCompletedScan")}
          </p>
        ) : recommendations.loading && !recommendations.data ? (
          <LoadingBlock label={t("assetSecurity.loadingRecommendations")} />
        ) : recommendations.error ? (
          <div className="p-5">
            <ErrorBlock
              message={recommendations.error}
              onRetry={recommendations.refetch}
            />
          </div>
        ) : !recommendations.data ||
          recommendations.data.recommendations.length === 0 ? (
          <div className="px-5 pb-5 text-sm text-slate-500">
            <p>{t("assetSecurity.noRecommendation")}</p>
            {recommendations.data?.run?.status === "failed" && (
              <p className="mt-2 text-xs text-amber-700">
                {t("assetSecurity.aiFailed", {
                  id: completedScan.id,
                  code: recommendations.data.run.error_code
                    ? ` (${recommendations.data.run.error_code})`
                    : "",
                })}
              </p>
            )}
          </div>
        ) : (
          <>
            <ul>
              {recommendations.data.recommendations.slice(0, 3).map((rec) => (
                <li
                  key={rec.id}
                  className="border-t border-slate-50 px-5 py-3 first:border-t-0"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium text-slate-800">{rec.title}</p>
                    <Badge
                      variant={
                        rec.priority === "critical"
                          ? "critical"
                          : rec.priority === "high"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {rec.priority}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{rec.summary}</p>
                  {rec.action && (
                    <p className="mt-1 text-xs text-slate-500">{rec.action}</p>
                  )}
                </li>
              ))}
            </ul>
            <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-500">
              {recommendations.data.source === "ai"
                ? recommendations.data.run?.model_used
                  ? t("assetSecurity.generatedByModel", {
                      model: recommendations.data.run.model_used,
                    })
                  : t("assetSecurity.generatedByAdvisor")
                : t("assetSecurity.aiFallback")}
            </div>
          </>
        )}
      </Card>

      <p className="px-1 text-xs text-slate-400">
        {t("assetSecurity.scannersFooter")}
      </p>
    </div>
  )
}
