import { useMemo } from "react"
import type { HealthStatus, Scan } from "../api/types"
import { useI18n, type Locale, type MessageKey } from "../i18n"
import {
  checkCategoryLabel,
  formatDate,
  formatDateTime,
  formatEuro,
  formatNumber,
  healthStatusLabel,
  relativeTime,
  scannerRunReasonLabel,
  scanStatusLabel,
  scanTriggerLabel,
  scanTypeLabel,
} from "./format"

export interface Formatters {
  locale: Locale
  t: (key: MessageKey, vars?: Record<string, string | number>) => string
  relativeTime: (value: string | null | undefined) => string
  formatDateTime: (value: string | null | undefined) => string
  formatDate: (value: string | null | undefined) => string
  formatNumber: (value: number | null | undefined) => string
  formatEuro: (value: number | null | undefined) => string
  healthStatusLabel: (status: HealthStatus | null | undefined) => string
  scanStatusLabel: (status: Scan["status"]) => string
  scanTypeLabel: (type: Scan["scan_type"]) => string
  scanTriggerLabel: (trigger: Scan["trigger"]) => string
  checkCategoryLabel: (category: string | null | undefined) => string
  scannerRunReasonLabel: (
    reason: string | null | undefined,
    exitCode: number | null | undefined,
  ) => string | null
}

/**
 * Locale-bound formatting helpers for components.
 *
 * `t` is returned alongside the helpers so a page can translate its own
 * strings and format its dates from the same hook, and so a language switch
 * re-renders the component instead of leaving stale English dates behind.
 */
export function useFormat(): Formatters {
  const { locale, t } = useI18n()

  return useMemo<Formatters>(
    () => ({
      locale,
      t,
      relativeTime: (value) => relativeTime(value, t),
      formatDateTime: (value) => formatDateTime(value, locale),
      formatDate: (value) => formatDate(value, locale),
      formatNumber: (value) => formatNumber(value, locale),
      formatEuro: (value) => formatEuro(value, locale),
      healthStatusLabel: (status) => healthStatusLabel(status, t),
      scanStatusLabel: (status) => scanStatusLabel(status, t),
      scanTypeLabel: (type) => scanTypeLabel(type, t),
      scanTriggerLabel: (trigger) => scanTriggerLabel(trigger, t),
      checkCategoryLabel: (category) => checkCategoryLabel(category, t),
      scannerRunReasonLabel: (reason, exitCode) =>
        scannerRunReasonLabel(reason, exitCode, t),
    }),
    [locale, t],
  )
}
