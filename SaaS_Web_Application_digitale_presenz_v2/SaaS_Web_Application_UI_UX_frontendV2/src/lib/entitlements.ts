import type { PlanLimits, PlanTier, PlanUsage } from "../api/types"
import type { MessageKey } from "../i18n"

/**
 * One feature key per premium action in the dashboard.
 *
 * Locking is derived from the plan snapshot the API already returns in
 * `GET /subscriptions/me/` (`limits` + `usage`), so the UI never hardcodes a
 * price list: the backend stays the source of truth, and the 403 it returns
 * remains the real enforcement when someone calls the API directly.
 */
export type FeatureKey =
  | "reports.pdf"
  | "api.keys"
  | "seo.audit"
  | "social.sync"
  | "security.scan"
  | "websites.extra"
  | "scans.extra"
  | "alerts.channels"

export interface FeatureDefinition {
  /** Short label reused by badges and the modal title. */
  labelKey: MessageKey
  /** One sentence of sales copy, shown in the upgrade modal. */
  descriptionKey: MessageKey
  /** Lowest tier that unlocks it — used to pick the benefits list. */
  plan: PlanTier
}

export const FEATURES: Record<FeatureKey, FeatureDefinition> = {
  "reports.pdf": {
    labelKey: "upgrade.features.pdf.label",
    descriptionKey: "upgrade.features.pdf.description",
    plan: "pro",
  },
  "api.keys": {
    labelKey: "upgrade.features.api.label",
    descriptionKey: "upgrade.features.api.description",
    plan: "pro",
  },
  "seo.audit": {
    labelKey: "upgrade.features.seo.label",
    descriptionKey: "upgrade.features.seo.description",
    plan: "pro",
  },
  "social.sync": {
    labelKey: "upgrade.features.reputation.label",
    descriptionKey: "upgrade.features.reputation.description",
    plan: "pro",
  },
  "security.scan": {
    labelKey: "upgrade.features.advancedSecurity.label",
    descriptionKey: "upgrade.features.advancedSecurity.description",
    plan: "pro",
  },
  "websites.extra": {
    labelKey: "upgrade.features.moreWebsites.label",
    descriptionKey: "upgrade.features.moreWebsites.description",
    plan: "pro",
  },
  "scans.extra": {
    labelKey: "upgrade.features.moreScans.label",
    descriptionKey: "upgrade.features.moreScans.description",
    plan: "pro",
  },
  "alerts.channels": {
    labelKey: "upgrade.features.moreChannels.label",
    descriptionKey: "upgrade.features.moreChannels.description",
    plan: "pro",
  },
}

export interface EntitlementsSnapshot {
  tier: PlanTier
  limits: PlanLimits | null
  usage: PlanUsage | null
  /** While the subscription is still loading, never block: the API decides. */
  loading: boolean
}

export const PLAN_ORDER: PlanTier[] = ["free", "pro", "business", "agency"]

export function planRank(tier: PlanTier): number {
  return PLAN_ORDER.indexOf(tier)
}

export function isLocked(
  feature: FeatureKey,
  { tier, limits, usage, loading }: EntitlementsSnapshot,
): boolean {
  if (loading) return false

  switch (feature) {
    // Boolean capabilities of the current plan.
    case "reports.pdf":
      return Boolean(limits) && !limits!.can_export_reports
    case "api.keys":
      return Boolean(limits) && !limits!.can_use_api

    // Advanced suites are part of every paid tier.
    case "seo.audit":
    case "social.sync":
    case "security.scan":
      return tier === "free"

    // Numeric quotas: locked only once the allowance is actually consumed.
    case "websites.extra":
      return Boolean(limits && usage) && usage!.websites >= limits!.max_websites
    case "scans.extra":
      return (
        Boolean(limits && usage) &&
        usage!.scans_this_month >= limits!.max_scans_per_month
      )
    case "alerts.channels":
      return (
        Boolean(limits && usage) &&
        usage!.alert_channels >= limits!.max_alert_channels
      )
  }
}

export function planLabel(tier: PlanTier): string {
  return tier.charAt(0).toUpperCase() + tier.slice(1)
}
