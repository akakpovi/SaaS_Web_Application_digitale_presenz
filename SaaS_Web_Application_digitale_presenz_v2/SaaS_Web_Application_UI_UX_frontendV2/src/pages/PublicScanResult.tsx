import React, { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Check,
  ChevronDown,
  Clock,
  Globe,
  Loader2,
  Lock,
  Mail,
  MinusCircle,
  RefreshCw,
  Share2,
  XCircle,
} from "lucide-react"
import SEO from "../components/SEO"
import { ScoreRing } from "../components/ui"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { apiErrorMessage } from "../api/errors"
import { useApiResource } from "../api/hooks/useApiResource"
import { useAuth } from "../api/hooks/useAuth"
import { useI18n, type MessageKey } from "../i18n"
import { useFormat } from "../lib/useFormat"
import type { PublicScanCheck, PublicScanReport } from "../api/types"

/**
 * Public scan result page (`/scan/:scanId`).
 *
 * The backend runs the health scan asynchronously: create with
 * `POST /public/scan/`, then poll `GET /public/scan/:id/status/` until the
 * status settles. The page is the lead-gen surface: score and per-category
 * findings are visible, the account-only extras are behind the CTA.
 */

const CATEGORY_ORDER = [
  "website",
  "ssl",
  "dns",
  "email_security",
  "security_headers",
  "performance",
  "uptime",
]

/** Category → catalogue key. A category the catalogue does not know yet is
 * shown de-underscored rather than hidden. */
const CATEGORY_KEYS: Record<string, MessageKey> = {
  website: "publicScan.categories.website",
  ssl: "publicScan.categories.ssl",
  dns: "publicScan.categories.dns",
  email_security: "publicScan.categories.emailSecurity",
  security_headers: "publicScan.categories.securityHeaders",
  performance: "publicScan.categories.performance",
  uptime: "publicScan.categories.uptime",
}

const ACTIVE_STATUSES = new Set(["pending", "queued", "running"])

function CheckIcon({ status }: { status: string }) {
  if (status === "healthy" || status === "passed" || status === "good") {
    return <CheckCircle size={17} className="text-emerald-600" aria-hidden="true" />
  }
  if (status === "critical" || status === "failed") {
    return <XCircle size={17} className="text-red-600" aria-hidden="true" />
  }
  if (status === "warning") {
    return <AlertTriangle size={17} className="text-amber-500" aria-hidden="true" />
  }
  return <MinusCircle size={17} className="text-slate-400" aria-hidden="true" />
}

function borderFor(status: string): string {
  if (status === "healthy" || status === "passed" || status === "good")
    return "border-emerald-200 bg-emerald-50/60"
  if (status === "critical" || status === "failed")
    return "border-red-200 bg-red-50/60"
  if (status === "warning") return "border-amber-200 bg-amber-50/60"
  return "border-slate-200 bg-white"
}

function StepRow({ step }: { step: PublicScanReport["steps"][number] }) {
  const { t } = useI18n()
  const done = step.status === "completed"
  const failed = ["failed", "timeout", "unavailable"].includes(step.status)
  const running = step.status === "running"

  return (
    <div className="flex items-center gap-3 text-sm">
      {done ? (
        <CheckCircle size={15} className="text-emerald-500 flex-shrink-0" />
      ) : failed ? (
        <XCircle size={15} className="text-slate-400 flex-shrink-0" />
      ) : running ? (
        <Loader2 size={15} className="text-indigo-600 animate-spin flex-shrink-0" />
      ) : (
        <Clock size={15} className="text-slate-300 flex-shrink-0" />
      )}
      <span
        className={
          done
            ? "text-slate-700"
            : running
              ? "text-indigo-700 font-medium"
              : "text-slate-400"
        }
      >
        {step.label}
      </span>
      {failed && (
        <span className="text-xs text-slate-400 ml-auto">
          {t("publicScan.stepUnavailable")}
        </span>
      )}
    </div>
  )
}

function CheckCard({ category, check }: { category: string; check: PublicScanCheck }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const remediation = check.remediation ?? {}
  const snippet =
    remediation.nginx || remediation.apache || remediation.htaccess || remediation.code
  const hasDetails = Boolean(snippet) || Boolean(check.days_until_expiry)

  return (
    <div className={`rounded-xl border p-4 ${borderFor(check.status)}`}>
      <div className="flex items-start gap-3">
        <CheckIcon status={check.status} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-slate-900">
              {CATEGORY_KEYS[category]
                ? t(CATEGORY_KEYS[category])
                : category.replace(/_/g, " ")}
            </p>
            {typeof check.score === "number" && (
              <span className="text-xs font-bold tabular-nums text-slate-500 flex-shrink-0">
                {check.score}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">
            {check.message || t("publicScan.noDetail")}
          </p>
          {typeof check.days_until_expiry === "number" && (
            <p className="text-xs text-slate-500 mt-1">
              {check.days_until_expiry === 1
                ? t("publicScan.certExpiresOne", {
                    days: check.days_until_expiry,
                  })
                : t("publicScan.certExpiresMany", {
                    days: check.days_until_expiry,
                  })}
            </p>
          )}
          {hasDetails && snippet && (
            <>
              <button
                type="button"
                onClick={() => setOpen((value) => !value)}
                aria-expanded={open}
                className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-indigo-700 hover:text-indigo-800"
              >
                <ChevronDown
                  size={12}
                  className={`transition-transform ${open ? "rotate-180" : ""}`}
                />
                {open ? t("publicScan.hideFix") : t("publicScan.showFix")}
              </button>
              {open && (
                <pre className="mt-2 p-3 bg-slate-900 text-slate-100 text-xs rounded-lg overflow-x-auto whitespace-pre-wrap">
                  {snippet}
                </pre>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function PublicScanResult() {
  const { t, tList } = useI18n()
  const { formatDateTime } = useFormat()
  const ctaFeatures = tList("publicScan.ctaFeatures")
  const { scanId } = useParams<{ scanId: string }>()
  const { user } = useAuth()
  const [polling, setPolling] = useState(true)

  const report = useApiResource<PublicScanReport>(
    scanId ? endpoints.publicScan.status(scanId) : null,
    scanId ?? "",
    polling ? 2000 : 0,
  )

  const [email, setEmail] = useState("")
  const [emailStatus, setEmailStatus] = useState<"idle" | "sending" | "sent">(
    "idle",
  )
  const [emailError, setEmailError] = useState("")
  const [notice, setNotice] = useState("")
  const [linkCopied, setLinkCopied] = useState(false)

  const status = report.data?.status
  const isActive = status ? ACTIVE_STATUSES.has(status) : true
  // A partial report is terminal but incomplete: results exist for the checks
  // that ran, so they are shown with an explicit warning; they are never
  // labelled as a complete report.
  const hasReport = status === "completed" || status === "partial"

  useEffect(() => {
    if (status && !ACTIVE_STATUSES.has(status)) setPolling(false)
  }, [status])

  const shareReport = async () => {
    const url = window.location.href
    if (navigator.share) {
      try {
        await navigator.share({
          title: t("publicScan.shareTitle", {
            domain: report.data?.domain ?? "Presence",
          }),
          url,
        })
        return
      } catch {
        // The user dismissed the native sheet: fall back to copying.
      }
    }
    try {
      await navigator.clipboard.writeText(url)
      setLinkCopied(true)
      window.setTimeout(() => setLinkCopied(false), 2000)
    } catch {
      // Clipboard access can be denied; the URL stays visible in the address bar.
    }
  }

  const sendReport = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!email.trim() || !scanId) return
    setEmailStatus("sending")
    setEmailError("")
    try {
      await api.post<{ message?: string }>(endpoints.publicScan.email(scanId), {
        email: email.trim(),
      })
      setEmailStatus("sent")
      // The confirmation comes from the catalogue so it follows the interface
      // language; the provider message is English-only and is not surfaced.
      setNotice(t("publicScan.emailSent", { email: email.trim() }))
    } catch (error) {
      setEmailStatus("idle")
      setEmailError(apiErrorMessage(error, t("publicScan.emailFailed")))
    }
  }

  const checks = report.data
    ? CATEGORY_ORDER.filter((key) => report.data?.checks[key]).map((key) => ({
        key,
        check: report.data!.checks[key],
      }))
    : []

  const registerUrl =
    report.data?.cta?.register_url ??
    (report.data
      ? `/register?scan_id=${report.data.scan_id}&url=${encodeURIComponent(report.data.url)}`
      : "/register")

  return (
    <div className="min-h-full bg-slate-50">
      <SEO
        title={
          report.data
            ? t("publicScan.metaReportTitle", { domain: report.data.domain })
            : t("publicScan.metaTitle")
        }
        description={t("publicScan.metaDescription")}
        noIndex
        path={scanId ? `/scan/${scanId}` : "/tools/website-checker"}
      />

      <header className="bg-white border-b border-slate-200">
        <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 flex-shrink-0">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <div className="flex items-center gap-3 text-sm">
            {user ? (
              <Link
                to="/app/dashboard"
                className="font-medium text-indigo-600 hover:text-indigo-700"
              >
                {t("publicScan.navDashboard")}
              </Link>
            ) : (
              <>
                <Link to="/login" className="text-slate-600 hover:text-slate-900">
                  {t("common.login")}
                </Link>
                <Link
                  to={registerUrl}
                  className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700"
                >
                  {t("publicScan.createAccount")}
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-10">
        {report.error && !report.data ? (
          <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center">
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle size={22} className="text-red-600" />
            </div>
            <p className="font-bold text-slate-900 mb-2">
              {t("publicScan.reportUnavailable")}
            </p>
            <p className="text-sm text-slate-500 mb-6">{report.error}</p>
            <p className="text-xs text-slate-400 mb-6">
              {t("publicScan.reportRetention")}
            </p>
            <Link
              to="/tools/website-checker"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700"
            >
              <RefreshCw size={14} /> {t("publicScan.runNewCheck")}
            </Link>
          </div>
        ) : (
          <>
            {/* Domain + score header */}
            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm mb-6">
              <div className="flex flex-col sm:flex-row sm:items-center gap-6">
                {report.data && hasReport ? (
                  <ScoreRing score={report.data.score} size={104} />
                ) : (
                  <div className="w-[104px] h-[104px] rounded-full bg-indigo-50 flex items-center justify-center flex-shrink-0">
                    {status === "failed" || status === "cancelled" ? (
                      <XCircle size={30} className="text-red-500" />
                    ) : status === "partial" ? (
                      <AlertTriangle size={30} className="text-amber-500" />
                    ) : (
                      <Loader2 size={28} className="text-indigo-600 animate-spin" />
                    )}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <Globe size={15} className="text-slate-400" />
                    <a
                      href={`https://${report.data?.domain ?? ""}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xl font-bold text-slate-900 font-mono hover:text-indigo-600"
                    >
                      {report.data?.domain ?? t("publicScan.runningChecks")}
                    </a>
                    {isActive && (
                      <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-full border border-indigo-200">
                        {t("publicScan.statusScanning")}
                      </span>
                    )}
                    {status === "completed" && (
                      <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full border border-emerald-200">
                        {t("publicScan.statusReady")}
                      </span>
                    )}
                    {status === "partial" && (
                      <span className="px-2 py-0.5 bg-amber-50 text-amber-700 text-xs font-medium rounded-full border border-amber-200">
                        {t("publicScan.statusPartial")}
                      </span>
                    )}
                    {report.data?.is_guest && (
                      <button
                        type="button"
                        onClick={() => void shareReport()}
                        className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50"
                      >
                        {linkCopied ? (
                          <Check size={12} className="text-emerald-600" />
                        ) : (
                          <Share2 size={12} />
                        )}
                        {linkCopied
                          ? t("publicScan.linkCopied")
                          : t("publicScan.share")}
                      </button>
                    )}
                  </div>
                  <p className="text-sm text-slate-500">
                    {report.data && hasReport
                      ? t("publicScan.scannedAt", {
                          date: formatDateTime(report.data.scanned_at),
                        })
                      : t("publicScan.usuallyTakes")}
                  </p>
                  {report.data && hasReport && (
                    <div className="flex gap-5 text-sm mt-3 flex-wrap">
                      <div>
                        <p className="text-xs text-slate-400">
                          {t("publicScan.issues")}
                        </p>
                        <p className="font-bold text-slate-900 tabular-nums">
                          {report.data.summary.critical + report.data.summary.warnings}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">
                          {t("publicScan.passed")}
                        </p>
                        <p className="font-bold text-emerald-600 tabular-nums">
                          {report.data.summary.passed}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">
                          {t("publicScan.critical")}
                        </p>
                        <p className="font-bold text-red-600 tabular-nums">
                          {report.data.summary.critical}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {isActive && report.data && (
                <div className="mt-6 pt-5 border-t border-slate-100">
                  <div className="flex items-center justify-between text-xs text-slate-600 mb-2">
                    <span>
                      {report.data.current_step || t("publicScan.queued")}
                    </span>
                    <span className="font-semibold tabular-nums">
                      {report.data.progress}%
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mb-4">
                    <div
                      className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                      style={{ width: `${Math.max(4, report.data.progress)}%` }}
                    />
                  </div>
                  <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
                    {report.data.steps?.map((step) => (
                      <StepRow key={step.key} step={step} />
                    ))}
                  </div>
                </div>
              )}

              {status === "partial" && (
                <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
                  <p className="font-semibold mb-1">
                    {t("publicScan.partialTitle")}
                  </p>
                  <p>{t("publicScan.partialBody")}</p>
                </div>
              )}

              {(status === "failed" || status === "cancelled") && (
                <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
                  <p className="font-semibold mb-1">
                    {t("publicScan.failedTitle")}
                  </p>
                  <p>
                    {t("publicScan.failedBody")}{" "}
                    <Link
                      to="/tools/website-checker"
                      className="underline font-medium"
                    >
                      {t("publicScan.tryAnotherDomain")}
                    </Link>
                    .
                  </p>
                </div>
              )}
            </div>

            {/* Results */}
            {hasReport && report.data && (
              <>
                <h2 className="font-bold text-slate-900 mb-3">
                  {t("publicScan.healthChecks")}
                </h2>
                <div className="grid sm:grid-cols-2 gap-3 mb-8">
                  {checks.map(({ key, check }) => (
                    <CheckCard key={key} category={key} check={check} />
                  ))}
                </div>

                {/* Email capture */}
                <div className="bg-white border border-slate-200 rounded-2xl p-6 mb-6">
                  <div className="flex items-center gap-2 mb-2">
                    <Mail size={16} className="text-indigo-600" />
                    <p className="font-semibold text-slate-900 text-sm">
                      {t("publicScan.emailTitle")}
                    </p>
                  </div>
                  <p className="text-xs text-slate-500 mb-4">
                    {t("publicScan.emailBody")}
                  </p>
                  {emailStatus === "sent" ? (
                    <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 flex items-center gap-2">
                      <CheckCircle size={14} /> {notice}
                    </p>
                  ) : (
                    <form onSubmit={sendReport} className="flex flex-col sm:flex-row gap-2">
                      <input
                        type="email"
                        required
                        aria-label={t("publicScan.emailAria")}
                        placeholder="you@example.com"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        className="flex-1 px-3 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <button
                        type="submit"
                        disabled={emailStatus === "sending"}
                        className="px-4 py-2.5 bg-slate-900 text-white text-sm font-semibold rounded-lg hover:bg-slate-800 disabled:opacity-60"
                      >
                        {emailStatus === "sending"
                          ? t("publicScan.sending")
                          : t("publicScan.sendReport")}
                      </button>
                    </form>
                  )}
                  {emailError && (
                    <p className="text-xs text-red-600 mt-2" role="alert">
                      {emailError}
                    </p>
                  )}
                </div>

                {/* CTA */}
                <div className="bg-indigo-600 rounded-2xl p-6 text-white">
                  <div className="flex items-start gap-3 mb-4">
                    <Lock size={18} className="mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-bold text-lg">
                        {t("publicScan.ctaTitle")}
                      </p>
                      <p className="text-indigo-200 text-sm mt-1">
                        {t("publicScan.ctaBody")}
                      </p>
                    </div>
                  </div>
                  <ul className="grid sm:grid-cols-2 gap-2 text-sm text-indigo-100 mb-5">
                    {ctaFeatures.map((item) => (
                      <li key={item} className="flex items-center gap-2">
                        <CheckCircle size={13} className="text-indigo-300 flex-shrink-0" />
                        {item}
                      </li>
                    ))}
                  </ul>
                  {report.data.preview_limitations?.length > 0 && (
                    <p className="text-xs text-indigo-300 mb-5">
                      {report.data.preview_limitations.join(" · ")}
                    </p>
                  )}
                  <div className="flex flex-col sm:flex-row gap-3">
                    <Link
                      to={user ? "/app/dashboard" : registerUrl}
                      className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-white text-indigo-700 font-semibold rounded-xl hover:bg-indigo-50 text-sm"
                    >
                      {user
                        ? t("publicScan.openDashboard")
                        : t("publicScan.createAccount")}
                      <ArrowRight size={14} />
                    </Link>
                    <Link
                      to="/tools/website-checker"
                      className="inline-flex items-center justify-center gap-2 px-5 py-2.5 border border-indigo-400 text-white font-semibold rounded-xl hover:bg-indigo-700 text-sm"
                    >
                      {t("publicScan.checkAnother")}
                    </Link>
                  </div>
                </div>
              </>
            )}

            {isActive && (
              <p className="text-xs text-slate-400 text-center mt-6">
                {t("publicScan.autoRefresh")}
              </p>
            )}
          </>
        )}
      </main>
    </div>
  )
}
