import { useState } from "react"
import { useNavigate } from "react-router-dom"
import Link from "../components/LocaleLink"
import { CheckCircle, ArrowLeft } from "lucide-react"
import SEO from "../components/SEO"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n } from "../i18n"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { authStorage } from "../api/authStorage"
import type { CheckoutResponse } from "../api/types"
import { FALLBACK_PLANS, priceLabel, yearlyMonthlyEquivalent } from "../lib/pricing"
import {
  usePlanCopy,
  usePricingPlans,
  type LocalizedPlan,
} from "../lib/usePricingPlans"

export default function Pricing() {
  const navigate = useNavigate()
  const { t } = useI18n()
  const [yearly, setYearly] = useState(false)
  const plans = usePricingPlans().map(usePlanCopy())
  const [busyTier, setBusyTier] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function choosePlan(plan: LocalizedPlan) {
    setNotice(null)
    const cycle = yearly ? "yearly" : "monthly"

    if (plan.tier === "free") {
      navigate("/register")
      return
    }
    if (!authStorage.getAccessToken()) {
      navigate(`/register?plan=${plan.tier}&cycle=${cycle}`)
      return
    }

    setBusyTier(plan.tier)
    try {
      const checkout = await api.post<CheckoutResponse>(
        endpoints.billing.checkout,
        { plan_tier: plan.tier, billing_cycle: cycle },
      )
      window.location.assign(checkout.checkout_url)
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : t("pricing.checkoutUnavailable")
      setNotice(`${message} ${t("pricing.freeMeanwhile")}`)
    } finally {
      setBusyTier(null)
    }
  }

  return (
    <div className="min-h-full bg-white">
      <SEO
        title={t("meta.pricing.title")}
        description={t("meta.pricing.description")}
        path="/pricing"
        structuredData={{
          "@context": "https://schema.org",
          "@type": "Product",
          name: "Presence Website Monitoring",
          description:
            "Website monitoring for small businesses. Monitor uptime, SSL, DNS, email security and reviews.",
          offers: FALLBACK_PLANS.map((plan) => ({
            "@type": "Offer",
            name: plan.name,
            price: String(plan.monthly),
            priceCurrency: "EUR",
            availability: "https://schema.org/InStock",
          })),
        }}
      />
      <div className="max-w-6xl mx-auto px-4 py-16">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 mb-12"
        >
          <ArrowLeft size={14} /> {t("pricing.backToSite")}
        </Link>

        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-slate-900 mb-4">
            {t("pricing.title")}
          </h1>
          <p className="text-lg text-slate-500 mb-8">
            {t("pricing.subtitle")}
          </p>

          <LanguageSwitcher className="mx-auto mb-6 w-fit" />

          <div className="inline-flex items-center gap-3 p-1.5 bg-slate-100 rounded-xl">
            <button
              onClick={() => setYearly(false)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                !yearly ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"
              }`}
            >
              {t("pricing.monthly")}
            </button>
            <button
              onClick={() => setYearly(true)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                yearly ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"
              }`}
            >
              {t("pricing.yearly")}
              <span className="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded-full font-semibold">
                {t("pricing.twoMonthsFree")}
              </span>
            </button>
          </div>
        </div>

        {notice && (
          <div
            role="alert"
            className="max-w-2xl mx-auto mb-8 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
          >
            {notice}
          </div>
        )}

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
          {plans.map((plan) => {
            const highlight = plan.tier === "pro"
            const monthlyEquivalent = yearly
              ? yearlyMonthlyEquivalent(plan)
              : plan.monthly
            return (
              <div
                key={plan.tier}
                className={`relative rounded-2xl p-7 border flex flex-col ${
                  highlight
                    ? "border-indigo-500 shadow-2xl shadow-indigo-100/60 bg-indigo-600"
                    : "border-slate-200 bg-white"
                } ${highlight ? "lg:scale-105" : ""}`}
              >
                {highlight && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                    <span className="bg-amber-400 text-amber-900 text-xs font-bold px-4 py-1.5 rounded-full shadow">
                      {t("landing.mostPopular")}
                    </span>
                  </div>
                )}

                <div
                  className={`mb-5 ${highlight ? "text-white" : "text-slate-900"}`}
                >
                  <p
                    className={`text-sm font-semibold mb-2 ${
                      highlight ? "text-indigo-200" : "text-slate-500"
                    }`}
                  >
                    {plan.name}
                  </p>
                  <div className="flex items-baseline gap-1 mb-1">
                    <span className="text-4xl font-black tabular-nums">
                      {priceLabel(monthlyEquivalent)}
                    </span>
                    <span
                      className={`text-sm ${
                        highlight ? "text-indigo-300" : "text-slate-400"
                      }`}
                    >
                      {t("pricing.perMonth")}
                    </span>
                  </div>
                  {yearly && plan.monthly > 0 && (
                    <p
                      className={`text-xs ${
                        highlight ? "text-indigo-300" : "text-slate-400"
                      }`}
                    >
                      {priceLabel(plan.yearly)} {t("pricing.billedAnnually")}
                    </p>
                  )}
                  <p
                    className={`text-sm mt-2 ${
                      highlight ? "text-indigo-200" : "text-slate-500"
                    }`}
                  >
                    {plan.description}
                  </p>
                </div>

                <ul className="space-y-2.5 mb-7 flex-1">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2.5">
                      <CheckCircle
                        size={15}
                        className={
                          highlight ? "text-emerald-400" : "text-emerald-500"
                        }
                      />
                      <span
                        className={`text-sm ${
                          highlight ? "text-indigo-100" : "text-slate-700"
                        }`}
                      >
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => choosePlan(plan)}
                  disabled={busyTier === plan.tier}
                  className={`w-full py-3 rounded-xl font-semibold text-sm transition-all disabled:opacity-60 ${
                    highlight
                      ? "bg-white text-indigo-700 hover:bg-indigo-50"
                      : "bg-indigo-600 text-white hover:bg-indigo-700"
                  }`}
                >
                  {busyTier === plan.tier ? t("pricing.redirecting") : plan.cta}
                </button>
              </div>
            )
          })}
        </div>

        <div className="text-center text-sm text-slate-500 space-y-1">
          <p>{t("pricing.merchantNotice")}</p>
          <p>{t("pricing.cancelNotice")}</p>
        </div>

        <div className="mt-16 border-t border-slate-100 pt-12">
          <h2 className="text-2xl font-bold text-slate-900 text-center mb-8">
            {t("pricing.faqTitle")}
          </h2>
          <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
            {([
              {
                q: t("pricing.faq.change.q"),
                a: t("pricing.faq.change.a"),
              },
              {
                q: t("pricing.faq.afterCancel.q"),
                a: t("pricing.faq.afterCancel.a"),
              },
              {
                q: t("pricing.faq.annual.q"),
                a: t("pricing.faq.annual.a"),
              },
              {
                q: t("pricing.faq.payment.q"),
                a: t("pricing.faq.payment.a"),
              },
            ] as const).map(({ q, a }) => (
              <div key={q} className="p-5 bg-slate-50 rounded-xl">
                <p className="font-semibold text-slate-900 mb-2">{q}</p>
                <p className="text-sm text-slate-500">{a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
