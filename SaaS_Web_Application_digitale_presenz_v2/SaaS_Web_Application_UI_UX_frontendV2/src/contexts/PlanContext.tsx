import React, { createContext, useCallback, useContext } from "react"
import { endpoints } from "../api/endpoints"
import { useApiResource } from "../api/hooks/useApiResource"
import type {
  PlanLimits,
  PlanTier,
  PlanUsage,
  SubscriptionMe,
} from "../api/types"

interface PlanContextValue {
  subscription: SubscriptionMe | null
  tier: PlanTier
  limits: PlanLimits | null
  usage: PlanUsage | null
  loading: boolean
  isPaid: boolean
  refresh: () => void
}

const FALLBACK: PlanContextValue = {
  subscription: null,
  tier: "free",
  limits: null,
  usage: null,
  loading: true,
  isPaid: false,
  refresh: () => {},
}

const PlanCtx = createContext<PlanContextValue>(FALLBACK)

/**
 * Fetches `/subscriptions/me/` once for the whole authenticated app.
 *
 * Every premium button reads the same snapshot, so the dashboard cannot show
 * two different answers for the same plan, and the upgrade modal does not
 * trigger a second request.
 */
export function PlanProvider({ children }: { children: React.ReactNode }) {
  const { data, loading, refetch } = useApiResource<SubscriptionMe>(
    endpoints.billing.me,
  )

  const refresh = useCallback(() => {
    void refetch()
  }, [refetch])

  const tier: PlanTier = data?.plan_tier ?? "free"
  const value: PlanContextValue = {
    subscription: data,
    tier,
    limits: data?.limits ?? null,
    usage: data?.usage ?? null,
    loading,
    isPaid: tier !== "free",
    refresh,
  }

  return <PlanCtx.Provider value={value}>{children}</PlanCtx.Provider>
}

export function usePlan(): PlanContextValue {
  return useContext(PlanCtx)
}
