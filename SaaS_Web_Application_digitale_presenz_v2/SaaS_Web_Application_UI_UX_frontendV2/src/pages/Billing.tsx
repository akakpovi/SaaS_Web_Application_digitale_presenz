import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  CreditCard,
  CheckCircle,
  ArrowRight,
  AlertTriangle,
  ExternalLink,
  Loader2,
} from "lucide-react"
import { Card, Button, Badge } from "../components/ui"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import type {
  ApiError,
  BillingCycle,
  CheckoutResponse,
  Plan,
  PortalResponse,
  SubscriptionMe,
} from "../api/types"
import {
  FALLBACK_PLANS,
  fromApiPlan,
  priceLabel,
  yearlyMonthlyEquivalent,
  type DisplayPlan,
} from "../lib/pricing"
import { useFormat, type Formatters } from "../lib/useFormat"
import type { MessageKey } from "../i18n"

/** Server message when there is one; a translated generic otherwise. */
function errorMessage(error: unknown, t: Formatters["t"]): string {
  const apiError = error as Partial<ApiError> | undefined
  if (apiError?.message) return apiError.message
  if (error instanceof Error && error.message) return error.message
  return t("errors.generic")
}

const STATUS_LABEL: Record<SubscriptionMe["status"], MessageKey> = {
  active: "billing.statusActive",
  trialing: "billing.statusTrialing",
  past_due: "billing.statusPastDue",
  cancelled: "billing.statusCancelled",
  expired: "billing.statusExpired",
}

export default function Billing() {
  const { t, formatDate } = useFormat()
  const [billing, setBilling] = useState<BillingCycle>("monthly")
  const [subscription, setSubscription] = useState<SubscriptionMe | null>(null)
  const [plans, setPlans] = useState<DisplayPlan[]>(FALLBACK_PLANS)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(
    null,
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [me, catalogue] = await Promise.all([
        api.get<SubscriptionMe>(endpoints.billing.me),
        api.get<Plan[]>(endpoints.billing.plans).catch(() => [] as Plan[]),
      ])
      setSubscription(me)
      if (catalogue.length > 0) setPlans(catalogue.map(fromApiPlan))
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error, t) })
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  async function startCheckout(tier: string) {
    setNotice(null)
    setBusy(tier)
    try {
      const checkout = await api.post<CheckoutResponse>(
        endpoints.billing.checkout,
        { plan_tier: tier, billing_cycle: billing },
      )
      window.location.assign(checkout.checkout_url)
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error, t) })
    } finally {
      setBusy(null)
    }
  }

  async function openPortal() {
    setNotice(null)
    setBusy("portal")
    try {
      const portal = await api.post<PortalResponse>(endpoints.billing.portal)
      window.location.assign(portal.portal_url)
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error, t) })
    } finally {
      setBusy(null)
    }
  }

  async function cancelPlan() {
    if (!window.confirm(t("billing.cancelConfirm"))) return
    setNotice(null)
    setBusy("cancel")
    try {
      await api.post(endpoints.billing.cancel)
      setNotice({
        tone: "success",
        text: t("billing.cancelScheduled"),
      })
      await load()
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error, t) })
    } finally {
      setBusy(null)
    }
  }

  if (loading && !subscription) {
    return (
      <div className="p-8 flex items-center gap-3 text-slate-500">
        <Loader2 size={18} className="animate-spin" /> {t("billing.loading")}
      </div>
    )
  }

  const billingEnabled = subscription?.billing.enabled ?? false
  const currentPlan = plans.find((p) => p.tier === subscription?.plan_tier)
  const periodEnd = subscription?.current_period_end
    ? formatDate(subscription.current_period_end)
    : null

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("billing.title")}
        </h1>
        <p className="text-slate-500 mt-1">{t("billing.subtitle")}</p>
      </div>

      {notice && (
        <div
          role="alert"
          className={`mb-6 flex items-start gap-2 rounded-xl border px-4 py-3 text-sm ${
            notice.tone === "error"
              ? "border-red-200 bg-red-50 text-red-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700"
          }`}
        >
          <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
          <span>{notice.text}</span>
        </div>
      )}

      {!billingEnabled && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {t("billing.disabledNotice")}
        </div>
      )}

      <Card className="p-6 mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <p className="font-bold text-slate-900 text-lg">
                {t("billing.planName", {
                  plan:
                    currentPlan?.name ??
                    subscription?.plan.name ??
                    t("billing.free"),
                })}
              </p>
              <Badge
                variant={
                  subscription?.status === "active" || subscription?.status === "trialing"
                    ? "success"
                    : "warning"
                }
              >
                {subscription
                  ? t(STATUS_LABEL[subscription.status])
                  : t("billing.statusUnknown")}
              </Badge>
            </div>
            <p className="text-sm text-slate-500">
              {subscription?.is_free
                ? t("billing.freeForever")
                : `${priceLabel(
                    billing === "yearly"
                      ? yearlyMonthlyEquivalent(currentPlan ?? FALLBACK_PLANS[0])
                      : (currentPlan?.monthly ?? 0),
                  )}${t("billing.perMonth")}${
                    periodEnd
                      ? ` · ${t("billing.renews", { date: periodEnd })}`
                      : ""
                  }`}
            </p>
            {subscription && (
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1 text-xs text-slate-600 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-full">
                  {subscription.usage.websites}/
                  {subscription.limits?.max_websites ?? "—"}{" "}
                  {t("billing.usageWebsites")}
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-slate-600 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-full">
                  {subscription.usage.scans_this_month}/
                  {subscription.limits?.max_scans_per_month ?? "—"}{" "}
                  {t("billing.usageScans")}
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-slate-600 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-full">
                  {subscription.usage.alert_channels}/
                  {subscription.limits?.max_alert_channels ?? "—"}{" "}
                  {t("billing.usageChannels")}
                </span>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2 sm:items-end">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <CreditCard size={14} aria-hidden="true" />
              {billingEnabled
                ? t("billing.processedByPaddle")
                : t("billing.paymentsDisabled")}
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={openPortal}
                disabled={!billingEnabled || busy === "portal"}
              >
                {busy === "portal" ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <ExternalLink size={13} />
                )}
                {t("billing.invoicesCard")}
              </Button>
              {!subscription?.is_free && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  onClick={cancelPlan}
                  disabled={busy === "cancel"}
                >
                  {t("billing.cancelPlan")}
                </Button>
              )}
            </div>
          </div>
        </div>
      </Card>

      <div className="mb-10">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h2 className="font-bold text-slate-900">
            {t("billing.availablePlans")}
          </h2>
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-xl">
            {(["monthly", "yearly"] as const).map((cycle) => (
              <button
                key={cycle}
                onClick={() => setBilling(cycle)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all ${
                  billing === cycle
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {cycle === "monthly"
                  ? t("billing.cycleMonthly")
                  : t("billing.cycleYearly")}
                {cycle === "yearly" && (
                  <span className="ml-1.5 text-[10px] text-emerald-600 font-semibold">
                    {t("billing.twoMonthsFree")}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.map((plan) => {
            const isCurrent = plan.tier === subscription?.plan_tier
            const price =
              billing === "yearly" && plan.monthly > 0
                ? yearlyMonthlyEquivalent(plan)
                : plan.monthly
            return (
              <div
                key={plan.tier}
                className={`relative flex flex-col rounded-2xl border p-5 ${
                  isCurrent
                    ? "border-indigo-400 shadow-md shadow-indigo-100"
                    : "border-slate-200 bg-white"
                }`}
              >
                {isCurrent && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-indigo-600 text-white text-xs font-bold rounded-full">
                    {t("billing.currentPlan")}
                  </span>
                )}
                <p className="font-bold text-slate-900 mb-3">{plan.name}</p>

                <div className="mb-4">
                  {plan.monthly === 0 ? (
                    <p className="text-2xl font-black text-slate-900">
                      {t("billing.free")}
                    </p>
                  ) : (
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-black text-slate-900 tabular-nums">
                        {priceLabel(price)}
                      </span>
                      <span className="text-xs text-slate-500">
                        {t("billing.perMonthShort")}
                      </span>
                    </div>
                  )}
                  {billing === "yearly" && plan.yearly > 0 && (
                    <p className="text-xs text-slate-400">
                      {t("billing.billedAnnually", {
                        price: priceLabel(plan.yearly),
                      })}
                    </p>
                  )}
                </div>

                <ul className="space-y-2 text-xs text-slate-600 flex-1 mb-5">
                  {plan.features.slice(0, 5).map((feature) => (
                    <li key={feature} className="flex items-center gap-1.5">
                      <CheckCircle
                        size={11}
                        className="text-emerald-500 flex-shrink-0"
                        aria-hidden="true"
                      />
                      {feature}
                    </li>
                  ))}
                </ul>

                {isCurrent ? (
                  <span className="w-full text-center text-xs font-medium text-slate-400 py-2 border border-slate-200 rounded-lg">
                    {t("billing.yourCurrentPlan")}
                  </span>
                ) : plan.tier === "free" ? (
                  <span className="w-full text-center text-xs font-medium text-slate-400 py-2 border border-slate-200 rounded-lg">
                    {t("billing.includedWithEveryAccount")}
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant={plan.tier === "pro" ? "primary" : "outline"}
                    className="w-full"
                    onClick={() => startCheckout(plan.tier)}
                    disabled={!billingEnabled || busy === plan.tier}
                  >
                    {busy === plan.tier ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <ArrowRight size={13} aria-hidden="true" />
                    )}
                    {plan.monthly > (currentPlan?.monthly ?? 0)
                      ? t("billing.upgrade")
                      : t("billing.switchPlan")}
                  </Button>
                )}
              </div>
            )
          })}
        </div>
      </div>

      <Card className="p-6">
        <h2 className="font-bold text-slate-900 mb-2">
          {t("billing.invoicesTitle")}
        </h2>
        <p className="text-sm text-slate-500 mb-4">
          {t("billing.invoicesBody")}
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={openPortal}
          disabled={!billingEnabled || busy === "portal"}
        >
          <ExternalLink size={13} /> {t("billing.openPortal")}
        </Button>
      </Card>

      <p className="text-xs text-slate-400 mt-6 text-center">
        {t("billing.footerBefore")}{" "}
        <Link to="/privacy" className="underline hover:text-slate-600">
          {t("footer.privacy")}
        </Link>
        {t("billing.footerAfter")}
      </p>
    </div>
  )
}
