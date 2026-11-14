import { useEffect, useState } from "react"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import type { Plan } from "../api/types"
import { useI18n } from "../i18n"
import { FALLBACK_PLANS, fromApiPlan, type DisplayPlan } from "./pricing"

/**
 * Single source of plan data for every public page.
 *
 * The landing page used to hard-code its own prices (€5.99 / €14.99) while the
 * catalogue, the API and the pricing page said €9 / €29 / €79. Two pages
 * advertising different prices is a commercial defect, so both now read the
 * same hook: the API is authoritative and `data/plans.json` (mirrored from
 * `subscriptions/pricing.py`, checked by scripts/check_pricing_sync.py) is the
 * offline fallback.
 */
const PUBLIC_TIERS = new Set(["free", "pro", "business", "agency"])

/**
 * The public catalogue deliberately excludes internal QA plans. The only
 * exception is an authenticated QA account viewing the pricing page: it must
 * still see which plan it currently uses.
 */
export function usePricingPlans(includeInternal = false): DisplayPlan[] {
  const [plans, setPlans] = useState<DisplayPlan[]>(FALLBACK_PLANS)

  useEffect(() => {
    let cancelled = false
    api
      .get<Plan[]>(endpoints.billing.plans)
      .then((data) => {
        if (cancelled) return
        const mapped = data
          .map(fromApiPlan)
          .filter(
            (plan) =>
              includeInternal || PUBLIC_TIERS.has(String(plan.tier)),
          )
        if (mapped.length > 0) setPlans(mapped)
      })
      .catch(() => {
        // Keep the mirrored fallback: pricing must never disappear.
      })
    return () => {
      cancelled = true
    }
  }, [includeInternal])

  return plans
}

const LOCALIZED_TIERS = ["free", "pro", "business", "agency"] as const

export interface LocalizedPlan extends DisplayPlan {
  /** Localized call to action ("Pro wählen" / "Choose Pro"). */
  cta: string
}

/**
 * Overlay German/English copy on a plan from the API.
 *
 * Only the wording is translated — every number (price, limits) still comes
 * from the plan row, so a catalogue change can never be masked by a stale
 * translation. A tier that exists in the database but not in the catalogue
 * keeps its API copy instead of rendering an empty card.
 */
export function usePlanCopy(): (plan: DisplayPlan) => LocalizedPlan {
  const { t, tList } = useI18n()

  return (plan: DisplayPlan): LocalizedPlan => {
    const tier = plan.tier as string
    if (!(LOCALIZED_TIERS as readonly string[]).includes(tier)) {
      return { ...plan, cta: plan.name }
    }
    const key = tier as (typeof LOCALIZED_TIERS)[number]
    return {
      ...plan,
      name: t(`pricing.tiers.${key}.name`),
      description: t(`pricing.tiers.${key}.description`),
      features: tList(`pricing.tiers.${key}.features`),
      cta: t(`pricing.tiers.${key}.cta`),
    }
  }
}
