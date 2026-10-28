import type { HealthStatus, Scan } from "../api/types"
import type { Locale, MessageKey } from "../i18n"
import { LOCALE_TAGS } from "../i18n"

/**
 * Every user-visible string in this module goes through `t`, and every
 * locale-dependent format through `Intl` with the active interface locale.
 *
 * The functions stay pure (the locale and the translator are arguments) so
 * they can be called outside React — but pages should use `useFormat()`,
 * which binds both to the current language and re-renders on a switch.
 */
type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string

/** "just now", "3 min ago", "2 days ago" — for timestamps coming from the API. */
export function relativeTime(
  value: string | null | undefined,
  t: Translate,
): string {
  if (!value) return t("time.never")
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return t("time.never")

  const seconds = Math.round((Date.now() - timestamp) / 1000)
  if (seconds < 45) return t("time.justNow")
  if (seconds < 90) return t("time.oneMinuteAgo")

  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return t("time.minutesAgo", { count: minutes })

  const hours = Math.round(minutes / 60)
  if (hours < 24) return t("time.hoursAgo", { count: hours })

  const days = Math.round(hours / 24)
  if (days < 30) {
    return days === 1 ? t("time.oneDayAgo") : t("time.daysAgo", { count: days })
  }

  const months = Math.round(days / 30)
  if (months < 12) {
    return months === 1
      ? t("time.oneMonthAgo")
      : t("time.monthsAgo", { count: months })
  }

  const years = Math.round(months / 12)
  return years === 1 ? t("time.oneYearAgo") : t("time.yearsAgo", { count: years })
}

export function formatDateTime(
  value: string | null | undefined,
  locale: Locale,
): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleString(LOCALE_TAGS[locale], {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export function formatDate(
  value: string | null | undefined,
  locale: Locale,
): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleDateString(LOCALE_TAGS[locale], { dateStyle: "medium" })
}

/** Grouped digits: `1.234` in German, `1,234` in English. */
export function formatNumber(value: number | null | undefined, locale: Locale): string {
  if (value === null || value === undefined) return "—"
  return new Intl.NumberFormat(LOCALE_TAGS[locale]).format(value)
}

/** Euro amount. `value` is in euros, not cents, and is never re-derived. */
export function formatEuro(
  value: number | null | undefined,
  locale: Locale,
): string {
  if (value === null || value === undefined) return "—"
  return new Intl.NumberFormat(LOCALE_TAGS[locale], {
    style: "currency",
    currency: "EUR",
  }).format(value)
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—"
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes}m ${rest}s` : `${minutes}m`
}

/** Tailwind text colour for a 0-100 health score. */
export function scoreTextClass(score: number | null | undefined): string {
  if (score === null || score === undefined) return "text-slate-400"
  if (score >= 80) return "text-emerald-600"
  if (score >= 60) return "text-amber-600"
  return "text-red-600"
}

/** Tone of a 0-100 health score, for a badge or a label. */
export function scoreTone(
  score: number | null | undefined,
): "healthy" | "warning" | "critical" | "neutral" {
  if (score === null || score === undefined) return "neutral"
  if (score >= 80) return "healthy"
  if (score >= 60) return "warning"
  return "critical"
}

/** Tone for a 0-100 health score's textual verdict. */
export function scoreLabelKey(
  score: number | null | undefined,
): MessageKey {
  if (score === null || score === undefined) return "status.neverScanned"
  if (score >= 80) return "status.good"
  if (score >= 60) return "status.needsAttention"
  return "status.critical"
}

/** Human label for the API's health status. */
export function healthStatusLabel(
  status: HealthStatus | null | undefined,
  t: Translate,
): string {
  switch (status) {
    case "healthy":
      return t("status.online")
    case "warning":
      return t("status.needsAttention")
    case "critical":
      return t("status.critical")
    default:
      return t("status.neverScanned")
  }
}

export function healthStatusTone(
  status: HealthStatus | null | undefined,
): "healthy" | "warning" | "critical" | "neutral" {
  switch (status) {
    case "healthy":
    case "warning":
    case "critical":
      return status
    default:
      return "neutral"
  }
}

/** Human label for a scan lifecycle/outcome status. */
export function scanStatusLabel(status: Scan["status"], t: Translate): string {
  switch (status) {
    case "pending":
      return t("status.pending")
    case "queued":
      return t("status.queued")
    case "running":
      return t("status.running")
    case "completed":
      return t("status.completed")
    case "partial":
      return t("status.partial")
    case "failed":
      return t("status.failed")
    case "cancelled":
      return t("status.cancelled")
    default:
      // Unknown status from a newer backend: show it rather than guessing.
      return status
  }
}

/** Colour tone for a scan status; partial is explicitly a warning, not success. */
export function scanStatusTone(
  status: Scan["status"],
): "healthy" | "warning" | "critical" | "neutral" {
  switch (status) {
    case "completed":
      return "healthy"
    case "partial":
    case "running":
      return "warning"
    case "failed":
      return "critical"
    default:
      return "neutral"
  }
}

/** Scan profile → catalogue key (the backend enum is never shown raw). */
export function scanTypeLabel(type: Scan["scan_type"], t: Translate): string {
  switch (type) {
    case "health":
      return t("scan.typeHealth")
    case "security":
      return t("scan.typeSecurity")
    case "full":
      return t("scan.typeFull")
    default:
      return type
  }
}

/** Who started the scan → catalogue key. */
export function scanTriggerLabel(trigger: Scan["trigger"], t: Translate): string {
  switch (trigger) {
    case "manual":
      return t("scan.triggerManual")
    case "onboarding":
      return t("scan.triggerOnboarding")
    case "monitoring":
      return t("scan.triggerMonitoring")
    case "public":
      return t("scan.triggerPublic")
    default:
      return trigger
  }
}

/** Health-check category → catalogue key. */
const CHECK_CATEGORY_KEYS: Record<string, MessageKey> = {
  website: "checks.website",
  ssl: "checks.ssl",
  ssl_certificate: "checks.ssl",
  dns: "checks.dns",
  email: "checks.email",
  email_security: "checks.email",
  headers: "checks.headers",
  security_headers: "checks.headers",
  performance: "checks.performance",
  uptime: "checks.uptime",
}

/**
 * Label for a check category (SSL, DNS, …).
 *
 * A category the catalogue does not know yet is shown de-underscored rather
 * than hidden: a new backend check must stay visible before it is translated.
 */
export function checkCategoryLabel(
  category: string | null | undefined,
  t: Translate,
): string {
  if (!category) return ""
  const key = CHECK_CATEGORY_KEYS[category]
  return key ? t(key) : category.replace(/_/g, " ")
}

/**
 * Plain text for scanner output.
 *
 * ZAP descriptions/recommendations are HTML fragments; the finding cards render
 * text, never markup, so tags and entities are stripped. ``DOMParser`` builds
 * an inert document: nothing is executed or fetched.
 */
export function plainText(value: string | null | undefined): string {
  if (!value) return ""
  if (!/[<&]/.test(value)) return value.trim()
  // Adjacent block elements carry no whitespace of their own; without a
  // separator their text would run together ("site/app.If you expect…").
  const separated = value
    .replace(/<\s*br\s*\/?>/gi, " ")
    .replace(/<\/\s*(p|div|li|tr|td|th|h[1-6])\s*>/gi, " ")
  const doc = new DOMParser().parseFromString(separated, "text/html")
  return (doc.body.textContent ?? "").replace(/\s+/g, " ").trim()
}

/** Human label for a scanner run's machine-readable partial reason. */
export function scannerRunReasonLabel(
  reason: string | null | undefined,
  exitCode: number | null | undefined,
  t: Translate,
): string | null {
  if (!reason) {
    return typeof exitCode === "number" && exitCode !== 0
      ? t("scan.reason.exitCode", { code: exitCode })
      : null
  }
  if (reason === "timeout") return t("scan.reason.timeout")
  if (reason === "unavailable") return t("scan.reason.unavailable")

  const exit = /^exit_code_(-?\d+)$/.exec(reason)
  if (exit) return t("scan.reason.exitCode", { code: exit[1] })

  const labels: Record<string, MessageKey> = {
    empty_report: "scan.reason.emptyReport",
    no_raw_report: "scan.reason.noRawReport",
    unparsable_report: "scan.reason.unparsableReport",
    output_truncated: "scan.reason.outputTruncated",
    host_unresponsive: "scan.reason.hostUnresponsive",
    target_validation: "scan.reason.targetValidation",
    memory_exceeded: "scan.reason.memoryExceeded",
  }
  const key = labels[reason]
  // An unmapped machine reason stays readable instead of disappearing.
  return key ? t(key) : reason.replace(/_/g, " ")
}

/** Average of the numeric scores, or null when nothing has been scored yet. */
export function averageScore(scores: (number | null | undefined)[]): number | null {
  const values = scores.filter((score): score is number => typeof score === "number")
  if (!values.length) return null
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
}
