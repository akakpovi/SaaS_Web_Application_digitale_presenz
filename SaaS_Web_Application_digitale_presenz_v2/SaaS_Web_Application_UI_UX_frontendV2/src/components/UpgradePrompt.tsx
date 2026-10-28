import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react"
import { Link } from "react-router-dom"
import { Check, Crown, Lock, Sparkles, X } from "lucide-react"
import { endpoints } from "../api/endpoints"
import { useApiList } from "../api/hooks/useApiResource"
import type { Plan } from "../api/types"
import { usePlan } from "../contexts/PlanContext"
import { useI18n, type MessageKey } from "../i18n"
import {
  FEATURES,
  isLocked,
  planLabel,
  type FeatureKey,
} from "../lib/entitlements"

// ─── Modal ────────────────────────────────────────────────────────────────────

/** Only used when the plans endpoint cannot be reached: keeps the copy translated. */
const FALLBACK_BENEFIT_KEYS: MessageKey[] = [
  "upgrade.fallback.websites",
  "upgrade.fallback.monitoring",
  "upgrade.fallback.pdf",
  "upgrade.fallback.api",
  "upgrade.fallback.alerts",
]

function benefitsFor(
  plans: Plan[],
  targetTier: string,
  t: (key: MessageKey) => string,
): string[] {
  const match = plans.find((plan) => plan.tier === targetTier)
  if (match?.features?.length) return match.features.slice(0, 6)
  return FALLBACK_BENEFIT_KEYS.map((key) => t(key))
}

/**
 * Sales panel shown when a free (or lower-tier) account clicks a premium
 * action. It is purely presentational: the caller decides when to open it.
 */
export function UpgradePromptModal({
  feature,
  onClose,
}: {
  feature: FeatureKey | null
  onClose: () => void
}) {
  const { tier } = usePlan()
  const { t } = useI18n()
  const plans = useApiList<Plan>(endpoints.billing.plans)
  const open = feature !== null

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!feature) return null

  const definition = FEATURES[feature]
  const target = definition.plan
  const benefits = benefitsFor(plans.data, target, t)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upgrade-title"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="bg-gradient-to-br from-indigo-600 to-violet-600 px-6 py-5 text-white">
          <button
            type="button"
            onClick={onClose}
            aria-label={t("upgrade.close")}
            className="absolute right-4 top-4 rounded-lg p-1 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
          >
            <X size={16} />
          </button>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-indigo-100">
            <Sparkles size={13} aria-hidden="true" />{" "}
            {t("upgrade.feature", { plan: planLabel(target) })}
          </div>
          <h2 id="upgrade-title" className="text-xl font-bold">
            {t(definition.labelKey)}
          </h2>
        </div>

        <div className="p-6">
          <p className="text-sm text-slate-600">
            {t(definition.descriptionKey)}
          </p>

          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              {t("upgrade.includedFrom", { plan: planLabel(target) })}
            </p>
            <ul className="flex flex-col gap-1.5">
              {benefits.map((benefit) => (
                <li
                  key={benefit}
                  className="flex items-start gap-2 text-sm text-slate-700"
                >
                  <Check
                    size={14}
                    className="mt-0.5 flex-shrink-0 text-emerald-600"
                    aria-hidden="true"
                  />
                  {benefit}
                </li>
              ))}
            </ul>
          </div>

          <p className="mt-3 text-xs text-slate-400">
            {t("upgrade.currentPlan", { plan: planLabel(tier) })}
          </p>

          <div className="mt-5 flex items-center gap-2">
            <Link
              to="/app/billing"
              onClick={onClose}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
            >
              <Crown size={15} aria-hidden="true" /> {t("upgrade.seePlans")}
            </Link>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
            >
              {t("upgrade.notNow")}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Provider ─────────────────────────────────────────────────────────────────

interface UpgradeContextValue {
  /** Opens the modal without checking anything (badges, "Pro" links). */
  open: (feature: FeatureKey) => void
  /**
   * Interception used by every premium click handler: closes over the plan
   * snapshot, returns false and shows the modal when the action is locked.
   *
   *   if (!guard("seo.audit")) return
   *   await api.post(...)   // never reached for a free account
   */
  guard: (feature: FeatureKey) => boolean
  activeFeature: FeatureKey | null
  close: () => void
}

const UpgradeCtx = createContext<UpgradeContextValue>({
  open: () => {},
  guard: () => true,
  activeFeature: null,
  close: () => {},
})

export function UpgradeProvider({ children }: { children: React.ReactNode }) {
  const plan = usePlan()
  const [activeFeature, setActiveFeature] = useState<FeatureKey | null>(null)

  const open = useCallback((feature: FeatureKey) => {
    setActiveFeature(feature)
  }, [])

  const close = useCallback(() => setActiveFeature(null), [])

  const guard = useCallback(
    (feature: FeatureKey) => {
      const locked = isLocked(feature, {
        tier: plan.tier,
        limits: plan.limits,
        usage: plan.usage,
        loading: plan.loading,
      })
      if (locked) setActiveFeature(feature)
      return !locked
    },
    [plan.tier, plan.limits, plan.usage, plan.loading],
  )

  return (
    <UpgradeCtx.Provider
      value={{ open, guard, activeFeature, close }}
    >
      {children}
      <UpgradePromptModal feature={activeFeature} onClose={close} />
    </UpgradeCtx.Provider>
  )
}

export function useUpgrade(): UpgradeContextValue {
  return useContext(UpgradeCtx)
}

// ─── Badge ────────────────────────────────────────────────────────────────────

/**
 * Discreet "Pro" pill shown next to a locked action. It never hides the
 * control — the whole point is that the feature stays visible and clickable.
 */
export function UpgradeBadge({
  feature,
  className = "",
}: {
  feature: FeatureKey
  className?: string
}) {
  const plan = usePlan()
  const { t } = useI18n()
  const { open } = useUpgrade()
  const locked = isLocked(feature, {
    tier: plan.tier,
    limits: plan.limits,
    usage: plan.usage,
    loading: plan.loading,
  })

  if (!locked) return null

  return (
    <button
      type="button"
      onClick={(event) => {
        event.preventDefault()
        event.stopPropagation()
        open(feature)
      }}
      className={`inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 transition-colors hover:bg-amber-100 ${className}`}
      aria-label={t("upgrade.lockedAria", { feature: t(FEATURES[feature].labelKey) })}
      title={t("upgrade.lockedTitle", {
        feature: t(FEATURES[feature].labelKey),
        plan: planLabel(FEATURES[feature].plan),
      })}
    >
      <Crown size={10} aria-hidden="true" /> {t("upgrade.badgePro")}
    </button>
  )
}

/** Lock icon + Pro pill, for compact icon-only controls. */
export function LockedHint({ feature }: { feature: FeatureKey }) {
  const { t } = useI18n()
  const { open } = useUpgrade()
  return (
    <button
      type="button"
      onClick={(event) => {
        event.preventDefault()
        event.stopPropagation()
        open(feature)
      }}
      className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-600 hover:text-amber-700"
      aria-label={t("upgrade.lockedAria", { feature: t(FEATURES[feature].labelKey) })}
    >
      <Lock size={10} aria-hidden="true" /> {t("upgrade.badgePro")}
    </button>
  )
}

