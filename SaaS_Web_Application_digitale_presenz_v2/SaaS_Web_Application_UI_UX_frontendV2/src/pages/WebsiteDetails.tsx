import React, { useEffect, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, RefreshCw, ChevronDown, Clock, ShieldCheck } from "lucide-react"
import {
  Card,
  StatusBadge,
  ScoreRing,
  Button,
  ProgressBar,
  LoadingBlock,
  ErrorBlock,
} from "../components/ui"
import AssetSecurityPanel from "../components/AssetSecurityPanel"
import { useToast } from "../components/Toast"
import { useUpgrade } from "../components/UpgradePrompt"
import { usePlan } from "../contexts/PlanContext"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { useApiList, useApiResource, apiErrorMessage } from "../api/hooks/useApiResource"
import type { CheckResult, MonitoringConfig, Scan, Website } from "../api/types"
import { formatDuration, healthStatusTone, scanStatusTone } from "../lib/format"
import { useFormat } from "../lib/useFormat"

function SectionCard({ section }: { section: CheckResult }) {
  const { t, healthStatusLabel, checkCategoryLabel } = useFormat()
  const [open, setOpen] = useState(false)
  const [techOpen, setTechOpen] = useState(false)
  const details = Object.entries(section.technical_details ?? {})

  return (
    <Card>
      <button
        className="w-full flex items-center gap-4 p-5 text-left"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="font-semibold text-slate-900">
              {checkCategoryLabel(section.category)}
            </h3>
            <StatusBadge
              status={healthStatusTone(section.status)}
              label={healthStatusLabel(section.status)}
            />
          </div>
          {!open && (
            <p className="text-sm text-slate-500 mt-1 truncate">
              {section.summary || t("websiteDetails.noSummary")}
            </p>
          )}
        </div>
        {section.score !== null && (
          <div className="flex-shrink-0 text-right">
            <span
              className={`text-lg font-black ${
                section.score === section.max_score
                  ? "text-emerald-600"
                  : section.score >= section.max_score * 0.7
                    ? "text-amber-600"
                    : "text-red-600"
              }`}
            >
              {section.score}
            </span>
            <span className="text-xs text-slate-400">/{section.max_score}</span>
          </div>
        )}
        <ChevronDown
          size={18}
          className={`text-slate-400 flex-shrink-0 transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-slate-100 pt-4">
          <p className="text-sm text-slate-700 mb-3">
            {section.summary || t("websiteDetails.noSummary")}
          </p>
          {section.recommendation && (
            <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl mb-4">
              <span className="text-amber-600 text-sm flex-shrink-0 mt-0.5">
                💡
              </span>
              <p className="text-sm text-amber-800">{section.recommendation}</p>
            </div>
          )}
          {details.length > 0 && (
            <>
              <button
                onClick={() => setTechOpen(!techOpen)}
                className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-600 transition-colors"
              >
                <ChevronDown
                  size={12}
                  className={`transition-transform ${techOpen ? "rotate-180" : ""}`}
                />
                {t("websiteDetails.technicalDetails")}
              </button>
              {techOpen && (
                <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200 overflow-x-auto">
                  <pre className="text-xs font-mono text-slate-600 leading-relaxed whitespace-pre-wrap">
                    {JSON.stringify(section.technical_details, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Card>
  )
}

export default function WebsiteDetails() {
  const {
    t,
    relativeTime,
    formatDateTime,
    healthStatusLabel,
    scanStatusLabel,
    scanTypeLabel,
    scanTriggerLabel,
    scannerRunReasonLabel,
    checkCategoryLabel,
  } = useFormat()
  const { id } = useParams()
  const websiteId = Number(id)
  const { showToast } = useToast()
  const [refreshKey, setRefreshKey] = useState(0)
  const [starting, setStarting] = useState(false)
  const [activatingMonitoring, setActivatingMonitoring] = useState(false)

  const monitoring = useApiResource<MonitoringConfig>(
    Number.isFinite(websiteId) ? endpoints.monitoring.detail(websiteId) : null,
    refreshKey,
  )

  const website = useApiResource<Website>(
    Number.isFinite(websiteId) ? endpoints.websites.detail(websiteId) : null,
    refreshKey,
  )
  const scans = useApiList<Scan>(
    Number.isFinite(websiteId) ? endpoints.scans.byWebsite(websiteId) : null,
    refreshKey,
    // Refresh while a scan is running so progress is live.
    starting ? 5000 : 0,
  )

  const latestScan = scans.data[0] ?? null
  const activeScan = scans.data.find((scan) => scan.is_active) ?? null

  useEffect(() => {
    if (starting && !activeScan && scans.data.length > 0) {
      setStarting(false)
    }
  }, [starting, activeScan, scans.data.length])

  const { guard } = useUpgrade()
  const { refresh: refreshPlan } = usePlan()

  const activateMonitoring = async () => {
    setActivatingMonitoring(true)
    try {
      await api.patch(endpoints.monitoring.detail(websiteId), { enabled: true })
      showToast(t("websiteDetails.monitoringActivated"), "success")
      monitoring.refetch()
      // The security panel keeps its own copy of the monitoring policy; without
      // this it kept displaying "monitoring paused" right after activation.
      setRefreshKey((key) => key + 1)
      refreshPlan()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setActivatingMonitoring(false)
    }
  }

  const runCheck = async () => {
    if (!guard("scans.extra")) return
    setStarting(true)
    try {
      const scan = await api.post<Scan>(endpoints.websites.scan(websiteId))
      showToast(t("websiteDetails.scanQueued", { id: scan.id }), "success")
      setRefreshKey((key) => key + 1)
      refreshPlan()
    } catch (err) {
      setStarting(false)
      showToast(apiErrorMessage(err), "error")
    }
  }

  if (!Number.isFinite(websiteId)) {
    return (
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <ErrorBlock message={t("websiteDetails.invalidId")} />
      </div>
    )
  }

  if (website.loading && !website.data) {
    return (
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <LoadingBlock label={t("websiteDetails.loading")} />
      </div>
    )
  }

  if (website.error || !website.data) {
    return (
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <Link
          to="/app/websites"
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6"
        >
          <ArrowLeft size={14} /> {t("websiteDetails.allWebsites")}
        </Link>
        <ErrorBlock
          message={website.error ?? t("websiteDetails.websiteNotFound")}
          onRetry={website.refetch}
        />
      </div>
    )
  }

  const site = website.data
  const checks = site.checks ?? []
  const score = site.health_score

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <Link
        to="/app/websites"
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6"
      >
        <ArrowLeft size={14} /> {t("websiteDetails.allWebsites")}
      </Link>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-8">
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-slate-900 font-mono">
              {site.domain}
            </h1>
            <StatusBadge
              status={healthStatusTone(site.health_status)}
              label={healthStatusLabel(site.health_status)}
            />
          </div>
          <p className="text-sm text-slate-500 mt-1">
            {t("websiteDetails.lastChecked", {
              time: relativeTime(site.last_scan_at),
            })}{" "}
            ·{" "}
            {monitoring.data?.enabled
              ? t("websiteDetails.monitoringActive")
              : t("websiteDetails.monitoringPaused")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={runCheck}
            disabled={starting || Boolean(activeScan)}
          >
            <RefreshCw
              size={14}
              className={starting || activeScan ? "animate-spin" : ""}
            />
            {starting || activeScan
              ? t("websiteDetails.scanning")
              : t("websiteDetails.runCheck")}
          </Button>
        </div>
      </div>

      {/* Opt-in continuous monitoring, offered once a real scan exists. */}
      {monitoring.data &&
        !monitoring.data.enabled &&
        latestScan?.status === "completed" && (
          <Card className="p-5 mb-6 border-indigo-100 bg-indigo-50/40">
            <div className="flex flex-col sm:flex-row sm:items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center flex-shrink-0">
                <ShieldCheck size={18} className="text-indigo-600" />
              </div>
              <div className="flex-1">
                <h2 className="font-bold text-slate-900">
                  {t("websiteDetails.keepWatching", { domain: site.domain })}
                </h2>
                <p className="text-sm text-slate-600 mt-1">
                  {t("websiteDetails.keepWatchingBody")}
                </p>
                <p className="text-xs text-slate-500 mt-2">
                  {t("websiteDetails.keepWatchingHint")}
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => void activateMonitoring()}
                disabled={activatingMonitoring}
              >
                {activatingMonitoring
                  ? t("websiteDetails.activating")
                  : t("monitoring.activateMonitoring")}
              </Button>
            </div>
          </Card>
        )}

      {/* Live progress */}
      {activeScan && (
        <Card className="p-4 mb-6">
          <div className="flex items-center justify-between text-xs text-slate-600 mb-2">
            <span className="flex items-center gap-2">
              <Clock size={13} className="text-indigo-500" aria-hidden="true" />
              {t("scan.ref", { id: activeScan.id })} ·{" "}
              {activeScan.current_step || scanStatusLabel(activeScan.status)}
            </span>
            <span className="font-semibold tabular-nums">
              {activeScan.progress}%
            </span>
          </div>
          <ProgressBar value={activeScan.progress} max={100} />
        </Card>
      )}

      {/* Automated loop: scan state, ZAP/Nuclei findings, AI recommendations. */}
      <AssetSecurityPanel
        websiteId={websiteId}
        organizationId={site.organization_id}
        latestScan={latestScan}
        activeScan={activeScan}
        scans={scans.data}
        refreshKey={refreshKey}
        onScanStarted={() => {
          setStarting(true)
          setRefreshKey((key) => key + 1)
        }}
      />

      <div className="mt-6 grid lg:grid-cols-4 gap-6">
        {/* Score sidebar */}
        <div className="lg:col-span-1">
          <Card className="p-5 sticky top-6">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">
              {t("websiteDetails.healthScore")}
            </p>
            <div className="flex justify-center mb-4">
              {score === null ? (
                <div className="w-[100px] h-[100px] rounded-full border-8 border-slate-100 flex items-center justify-center">
                  <span className="text-xl font-bold text-slate-300">—</span>
                </div>
              ) : (
                <ScoreRing score={score} size={100} />
              )}
            </div>
            {checks.length > 0 ? (
              <div className="space-y-2 mt-2">
                {checks
                  .filter((check) => check.score !== null)
                  .map((check) => (
                    <div key={check.id}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-slate-500">
                          {checkCategoryLabel(check.category)}
                        </span>
                        <span className="font-semibold text-slate-700">
                          {check.score}/{check.max_score}
                        </span>
                      </div>
                      <ProgressBar
                        value={check.score ?? 0}
                        max={check.max_score || 20}
                      />
                    </div>
                  ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 text-center">
                {t("websiteDetails.noResultYet")}
              </p>
            )}
          </Card>
        </div>

        {/* Sections */}
        <div className="lg:col-span-3 flex flex-col gap-3">
          {checks.length === 0 ? (
            <Card className="p-8 text-center">
              <p className="font-semibold text-slate-900 mb-1">
                {t("websiteDetails.noScanResult")}
              </p>
              <p className="text-sm text-slate-500 mb-4">
                {t("websiteDetails.noScanResultHint")}
              </p>
              <Button size="sm" onClick={runCheck} disabled={starting}>
                <RefreshCw size={13} /> {t("websiteDetails.runCheck")}
              </Button>
            </Card>
          ) : (
            checks.map((section) => (
              <SectionCard key={section.id} section={section} />
            ))
          )}
        </div>
      </div>

      {/* Scan history */}
      <Card className="mt-6 overflow-hidden">
        <div className="flex items-center justify-between p-5 pb-3">
          <h2 className="font-bold text-slate-900">
            {t("websiteDetails.scanHistory")}
          </h2>
          <Link
            to="/app/scans"
            className="text-sm text-indigo-600 hover:text-indigo-700"
          >
            {t("websiteDetails.allScans")}
          </Link>
        </div>
        {scans.loading && !scans.data.length ? (
          <LoadingBlock label={t("scan.loadingHistory")} />
        ) : scans.data.length === 0 ? (
          <p className="px-5 pb-5 text-sm text-slate-500">
            {t("websiteDetails.noScan")}
          </p>
        ) : (
          scans.data.slice(0, 10).map((scan) => (
            <div
              key={scan.id}
              className="flex items-center justify-between px-5 py-3 border-t border-slate-50 text-sm"
            >
              <div>
                <p className="text-slate-700">{formatDateTime(scan.created_at)}</p>
                <p className="text-xs text-slate-400 capitalize">
                  {scanTypeLabel(scan.scan_type)} ·{" "}
                  {scanTriggerLabel(scan.trigger)}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <span
                  className={`font-bold tabular-nums ${
                    scan.health_score === null
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
                <StatusBadge
                  status={scanStatusTone(scan.status)}
                  label={scanStatusLabel(scan.status)}
                />
                <span className="text-xs text-slate-400 font-mono w-12 text-right">
                  {formatDuration(scan.duration_seconds)}
                </span>
              </div>
            </div>
          ))
        )}
      </Card>
    </div>
  )
}
