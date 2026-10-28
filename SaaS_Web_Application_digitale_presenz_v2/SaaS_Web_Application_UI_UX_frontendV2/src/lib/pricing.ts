import fallback from "../data/plans.json"
import type { Plan, PlanTier } from "../api/types"

export interface DisplayPlan {
  tier: PlanTier
  name: string
  description: string
  monthly: number
  yearly: number
  maxWebsites: number
  maxScans: number
  maxAlertChannels: number
  canExport: boolean
  canUseApi: boolean
  features: string[]
}

export const FALLBACK_PLANS: DisplayPlan[] = fallback.plans.map((plan) => ({
  tier: plan.tier as PlanTier,
  name: plan.name,
  description: plan.description,
  monthly: plan.price_monthly,
  yearly: plan.price_yearly,
  maxWebsites: plan.max_websites,
  maxScans: plan.max_scans_per_month,
  maxAlertChannels: plan.max_alert_channels,
  canExport: plan.can_export_reports,
  canUseApi: plan.can_use_api,
  features: plan.features,
}))

export function fromApiPlan(plan: Plan): DisplayPlan {
  return {
    tier: plan.tier,
    name: plan.name,
    description: plan.description,
    monthly: Number(plan.price_monthly),
    yearly: Number(plan.price_yearly),
    maxWebsites: plan.max_websites,
    maxScans: plan.max_scans_per_month,
    maxAlertChannels: plan.max_alert_channels,
    canExport: plan.can_export_reports,
    canUseApi: plan.can_use_api,
    features: plan.features,
  }
}

export const PAID_TIERS: PlanTier[] = ["pro", "business", "agency"]

export function priceLabel(amount: number): string {
  return Number.isInteger(amount) ? `€${amount}` : `€${amount.toFixed(2)}`
}

/** Monthly equivalent of the annual price, rounded to the cent. */
export function yearlyMonthlyEquivalent(plan: DisplayPlan): number {
  return Math.round((plan.yearly / 12) * 100) / 100
}
