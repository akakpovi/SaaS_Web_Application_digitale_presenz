import React from "react"
import { Link } from "react-router-dom"
import {
  Users,
  ScanSearch,
  TrendingUp,
  DollarSign,
  BarChart2,
  ArrowLeft,
  AlertTriangle,
  Globe,
  Eye,
} from "lucide-react"
import { Helmet } from "react-helmet-async"
import { endpoints } from "../api/endpoints"
import { useApiResource } from "../api/hooks/useApiResource"
import type { AdminAnalytics } from "../api/types"
import { useFormat } from "../lib/useFormat"

/**
 * Growth Center — staff only.
 *
 * Everything on this page comes from `GET /analytics/admin/overview/`
 * (Django + PostgreSQL aggregates). The endpoint is restricted with
 * `IsAdminUser`, so a signed-in non-staff visitor gets the 403 panel instead
 * of fabricated numbers. There is deliberately no Umami/Stripe placeholder
 * left: a metric either exists in the API or is not shown.
 */
export default function AdminDashboard() {
  // `formatEuro` places the currency the way the active language expects
  // ("1.234,00 €" in German, "€1,234.00" in English); the ARR sentence below
  // carries the symbol inside the translation instead.
  const { t, relativeTime, formatNumber, formatEuro } = useFormat()
  const { data, error, loading, refetch } =
    useApiResource<AdminAnalytics>(endpoints.analytics.adminOverview)

  const kpis = data
    ? [
        {
          label: t("admin.kpiMrr"),
          value: formatEuro(data.subscriptions?.mrr_eur ?? 0),
          sub: t("admin.kpiMrrSub", {
            paying: data.subscriptions?.paying_users ?? 0,
            trialing: data.subscriptions?.trialing_users ?? 0,
          }),
          icon: DollarSign,
          color: "text-emerald-400",
        },
        {
          label: t("admin.kpiAccounts"),
          value: formatNumber(data.overview.total_users),
          sub: t("admin.kpiAccountsSub"),
          icon: Users,
          color: "text-indigo-400",
        },
        {
          label: t("admin.kpiWebsites"),
          value: formatNumber(data.overview.total_websites),
          sub: t("admin.kpiWebsitesSub"),
          icon: Globe,
          color: "text-emerald-400",
        },
        {
          label: t("admin.kpiScans"),
          value: formatNumber(data.overview.total_scans),
          sub: t("admin.kpiScansSub"),
          icon: ScanSearch,
          color: "text-amber-400",
        },
        {
          label: t("admin.kpiVisitors"),
          value: formatNumber(data.overview.total_visitors),
          sub: t("admin.kpiVisitorsSub"),
          icon: Eye,
          color: "text-purple-400",
        },
      ]
    : []

  const maxViews = Math.max(1, ...(data?.traffic_14d ?? []).map((d) => d.views))

  return (
    <>
      <Helmet>
        <meta name="robots" content="noindex,nofollow" />
      </Helmet>

      <div className="min-h-screen bg-slate-950 text-slate-100">
        <header className="h-14 border-b border-slate-800 flex items-center px-6 gap-4">
          <Link
            to="/app/dashboard"
            className="flex items-center gap-2 text-slate-400 hover:text-slate-200 transition-colors text-sm"
          >
            <ArrowLeft size={14} /> {t("admin.backToApp")}
          </Link>
          <span className="text-slate-700">|</span>
          <div className="flex items-center gap-2">
            <BarChart2 size={16} className="text-indigo-400" />
            <span className="font-semibold text-sm text-slate-200">
              {t("admin.growthCenter")}
            </span>
            <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs font-semibold rounded border border-amber-500/30">
              {t("admin.staffBadge")}
            </span>
          </div>
        </header>

        <div className="p-6 lg:p-8 max-w-6xl mx-auto">
          <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
            <div>
              <h1 className="text-xl font-bold text-slate-100">
                {t("admin.platformOverview")}
              </h1>
              <p className="text-xs text-slate-500 mt-1">
                {t("admin.overviewSubtitle")}
              </p>
            </div>
            <button
              onClick={() => refetch()}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
            >
              {t("common.refresh")}
            </button>
          </div>

          {loading && !data ? (
            <div
              className="flex items-center justify-center gap-3 py-20 text-slate-500"
              role="status"
            >
              <span className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm">{t("admin.loading")}</span>
            </div>
          ) : error && !data ? (
            <div className="flex items-start gap-3 p-5 bg-amber-500/10 border border-amber-500/30 rounded-xl">
              <AlertTriangle
                size={18}
                className="text-amber-400 flex-shrink-0 mt-0.5"
              />
              <div>
                <p className="text-amber-300 font-semibold text-sm mb-1">
                  {error.includes("permission") || error.includes("403")
                    ? t("admin.staffAccessRequired")
                    : t("admin.overviewLoadFailed")}
                </p>
                <p className="text-amber-400/80 text-xs leading-relaxed">
                  {error}
                  {" · "}
                  {t("admin.staffRestricted")}
                </p>
              </div>
            </div>
          ) : data ? (
            <>
              <div className="grid grid-cols-2 xl:grid-cols-5 gap-4 mb-8">
                {kpis.map(({ label, value, sub, icon: Icon, color }) => (
                  <div
                    key={label}
                    className="bg-slate-900 border border-slate-800 rounded-2xl p-5"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-xs text-slate-500">{label}</p>
                      <Icon size={15} className={color} />
                    </div>
                    <p className="text-2xl font-black text-slate-100 tabular-nums mb-1">
                      {value}
                    </p>
                    <p className="text-xs text-slate-600">{sub}</p>
                  </div>
                ))}
              </div>

              <div className="grid lg:grid-cols-3 gap-6 mb-6">
                <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6">
                  <h2 className="font-bold text-slate-200 mb-1">
                    {t("admin.trafficTitle")}
                  </h2>
                  <p className="text-xs text-slate-600 mb-5">
                    {t("admin.trafficSubtitle")}
                  </p>
                  {data.traffic_14d.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      {t("admin.trafficEmpty")}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {data.traffic_14d.map((day) => (
                        <div
                          key={day.day}
                          className="flex items-center gap-3 text-xs"
                        >
                          <span className="w-20 flex-shrink-0 text-slate-500 font-mono">
                            {day.day}
                          </span>
                          <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-indigo-500"
                              style={{
                                width: `${Math.max(2, (day.views / maxViews) * 100)}%`,
                              }}
                            />
                          </div>
                          <span className="w-24 text-right text-slate-400 tabular-nums">
                            {t("admin.trafficRow", {
                              views: formatNumber(day.views),
                              unique: formatNumber(day.uniques),
                            })}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                  <h2 className="font-bold text-slate-200 mb-1 flex items-center gap-2">
                    <DollarSign size={15} className="text-emerald-400" />
                    {t("admin.revenue")}
                  </h2>
                  <p className="text-xs text-slate-600 mb-5">
                    {t("admin.revenueSubtitle")}
                  </p>
                  <p className="text-3xl font-black text-slate-100 tabular-nums mb-1">
                    {formatEuro(data.subscriptions?.mrr_eur ?? 0)}
                    <span className="text-sm font-semibold text-slate-500">
                      {" "}
                      {t("admin.perMonth")}
                    </span>
                  </p>
                  <p className="text-xs text-slate-500 mb-4">
                    {t("admin.revenueBreakdown", {
                      arr: formatNumber(data.subscriptions?.arr_eur ?? 0),
                      paying: data.subscriptions?.paying_users ?? 0,
                      trialing: data.subscriptions?.trialing_users ?? 0,
                    })}
                  </p>

                  {(data.subscriptions?.by_plan.length ?? 0) === 0 ? (
                    <p className="text-xs text-slate-600">
                      {t("admin.noPaidSubscription")}
                    </p>
                  ) : (
                    <div className="flex flex-col gap-2 text-sm">
                      {data.subscriptions.by_plan.map((plan) => (
                        <div
                          key={plan.tier}
                          className="flex items-center justify-between border-b border-slate-800 pb-2 last:border-0 last:pb-0"
                        >
                          <span className="text-slate-400">
                            {plan.name}{" "}
                            <span className="text-slate-600">
                              {t(
                                plan.count === 1
                                  ? "admin.planSubsOne"
                                  : "admin.planSubsMany",
                                { count: plan.count },
                              )}
                            </span>
                          </span>
                          <span className="text-slate-200 tabular-nums">
                            {t("admin.planMrr", {
                              mrr: formatNumber(plan.mrr_eur),
                            })}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="mt-5 pt-4 border-t border-slate-800">
                    <p className="text-xs text-slate-500 mb-2">
                      {t("admin.estimates", {
                        index: data.overview.monetization_index,
                      })}
                    </p>
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>{t("admin.ads")}</span>
                      <span className="tabular-nums">
                        {formatEuro(data.estimated_revenue.ads_eur)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-500 mt-1">
                      <span>{t("admin.affiliate")}</span>
                      <span className="tabular-nums">
                        {formatEuro(data.estimated_revenue.affiliate_eur)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid lg:grid-cols-2 gap-6">
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                  <h2 className="font-bold text-slate-200 mb-1 flex items-center gap-2">
                    <TrendingUp size={15} className="text-amber-400" />
                    {t("admin.acquisition")}
                  </h2>
                  <p className="text-xs text-slate-600 mb-5">
                    {t("admin.acquisitionSubtitle")}
                  </p>
                  <div className="space-y-4">
                    {[
                      [t("admin.funnelSignups"), data.funnel.signups],
                      [t("admin.funnelWebsites"), data.funnel.added_websites],
                      [t("admin.funnelScans"), data.funnel.scans_triggered],
                    ].map(([label, value]) => (
                      <div
                        key={label as string}
                        className="flex items-center justify-between"
                      >
                        <span className="text-sm text-slate-400">{label}</span>
                        <span className="text-lg font-bold text-slate-100 tabular-nums">
                          {value as number}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-6 pt-4 border-t border-slate-800 text-xs text-slate-500 flex items-center justify-between">
                    <span>{t("admin.cookieConsent")}</span>
                    <span className="tabular-nums">
                      {t("admin.cookieConsentBreakdown", {
                        all: formatNumber(data.cookies.accepted_all),
                        essential: formatNumber(data.cookies.essential_only),
                      })}
                    </span>
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                  <h2 className="font-bold text-slate-200 mb-1 flex items-center gap-2">
                    <Users size={15} className="text-indigo-400" />
                    {t("admin.latestAccounts")}
                  </h2>
                  <p className="text-xs text-slate-600 mb-4">
                    {t("admin.latestAccountsSubtitle")}
                  </p>
                  {data.latest_users.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      {t("admin.noAccount")}
                    </p>
                  ) : (
                    <ul className="divide-y divide-slate-800">
                      {data.latest_users.map((user) => (
                        <li
                          key={user.id}
                          className="flex items-center justify-between gap-3 py-2.5"
                        >
                          <span className="text-sm text-slate-300 truncate">
                            {user.email}
                          </span>
                          <span className="text-xs text-slate-500 flex-shrink-0">
                            {t("admin.siteCount", {
                              count: formatNumber(user.websites_count),
                            })}
                            {user.websites_count === 1 ? "" : "s"} ·{" "}
                            {relativeTime(user.created_at)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </>
          ) : null}

          <p className="text-xs text-slate-700 mt-8 text-center">
            {t("admin.footer")}
          </p>
        </div>
      </div>
    </>
  )
}
