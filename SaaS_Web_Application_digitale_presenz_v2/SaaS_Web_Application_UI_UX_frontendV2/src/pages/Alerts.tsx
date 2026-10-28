import React, { useState } from "react"
import { Link } from "react-router-dom"
import { BellOff, CalendarOff, Mail, SlidersHorizontal, Trash2 } from "lucide-react"
import {
  Card,
  Button,
  Tabs,
  Badge,
  SeverityBadge,
  LoadingBlock,
  ErrorBlock,
} from "../components/ui"
import { useToast } from "../components/Toast"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { useApiList, apiErrorMessage } from "../api/hooks/useApiResource"
import type { Alert, AlertRule, MuteWindow } from "../api/types"
import { useFormat } from "../lib/useFormat"
import type { MessageKey } from "../i18n"

const FILTERS = {
  All: endpoints.alerts.list,
  Critical: `${endpoints.alerts.list}?severity=critical&status=firing`,
  Warning: `${endpoints.alerts.list}?severity=warning&status=firing`,
  Resolved: `${endpoints.alerts.list}?status=resolved`,
} as const

type FilterName = keyof typeof FILTERS

const FILTER_LABELS: Record<FilterName, MessageKey> = {
  All: "alerts.filterAll",
  Critical: "alerts.filterCritical",
  Warning: "alerts.filterWarning",
  Resolved: "alerts.filterResolved",
}

const SEVERITY_ICON: Record<Alert["severity"], string> = {
  critical: "🔴",
  warning: "🟠",
  info: "🔵",
}

const METRIC_LABELS: Record<AlertRule["metric"], MessageKey> = {
  health_score: "alerts.metrics.healthScore",
  ssl_days_remaining: "alerts.metrics.sslDaysRemaining",
  load_time_ms: "alerts.metrics.loadTimeMs",
  page_size_kb: "alerts.metrics.pageSizeKb",
}

const OPERATOR_LABELS: Record<AlertRule["operator"], MessageKey> = {
  lt: "alerts.operators.lt",
  lte: "alerts.operators.lte",
  gt: "alerts.operators.gt",
  gte: "alerts.operators.gte",
  eq: "alerts.operators.eq",
}

/** Rule severity → reuses the shared severity labels. */
const RULE_SEVERITY_LABELS: Record<AlertRule["severity"], MessageKey> = {
  warning: "severity.warning",
  critical: "severity.critical",
}

const MUTE_REASON_LABELS: Record<MuteWindow["reason"], MessageKey> = {
  maintenance: "alerts.reasons.maintenance",
  deployment: "alerts.reasons.deployment",
  migration: "alerts.reasons.migration",
  other: "alerts.reasons.other",
}

export default function Alerts() {
  const { t, relativeTime, formatDateTime } = useFormat()
  const { showToast } = useToast()
  const [filter, setFilter] = useState<FilterName>("All")
  const [refreshKey, setRefreshKey] = useState(0)
  const [busyId, setBusyId] = useState<string | null>(null)

  const { data: alerts, error, loading, refetch } = useApiList<Alert>(
    FILTERS[filter],
    `${filter}:${refreshKey}`,
  )

  // Automation: threshold rules and maintenance windows. Both route families
  // existed in the API but had no surface anywhere in the dashboard.
  const rules = useApiList<AlertRule>(endpoints.alerts.rules, refreshKey)
  const mutes = useApiList<MuteWindow>(
    endpoints.alerts.muteWindows,
    refreshKey,
  )
  const [ruleName, setRuleName] = useState("")
  const [ruleMetric, setRuleMetric] = useState<AlertRule["metric"]>(
    "health_score",
  )
  const [ruleOperator, setRuleOperator] = useState<AlertRule["operator"]>("lt")
  const [ruleThreshold, setRuleThreshold] = useState("70")
  const [ruleSeverity, setRuleSeverity] = useState<AlertRule["severity"]>(
    "warning",
  )
  const [muteStart, setMuteStart] = useState("")
  const [muteEnd, setMuteEnd] = useState("")
  const [muteReason, setMuteReason] = useState<MuteWindow["reason"]>(
    "maintenance",
  )
  const [saving, setSaving] = useState(false)

  const addRule = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      await api.post(endpoints.alerts.rules, {
        name:
          ruleName.trim() ||
          `${ruleMetric.replace(/_/g, " ")} ${ruleOperator} ${ruleThreshold}`,
        metric: ruleMetric,
        operator: ruleOperator,
        threshold: Number(ruleThreshold),
        severity: ruleSeverity,
        enabled: true,
      })
      setRuleName("")
      rules.refetch()
      showToast(t("alerts.toastRuleCreated"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setSaving(false)
    }
  }

  const addMuteWindow = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!muteStart || !muteEnd) {
      showToast(t("alerts.needDates"), "error")
      return
    }
    setSaving(true)
    try {
      await api.post(endpoints.alerts.muteWindows, {
        start_at: new Date(muteStart).toISOString(),
        end_at: new Date(muteEnd).toISOString(),
        reason: muteReason,
        note: "",
      })
      setMuteStart("")
      setMuteEnd("")
      mutes.refetch()
      showToast(t("alerts.toastMuteCreated"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setSaving(false)
    }
  }

  const removeRule = async (rule: AlertRule) => {
    if (!window.confirm(t("alerts.confirmDeleteRule", { name: rule.name }))) return
    try {
      await api.delete(endpoints.alerts.ruleDetail(rule.id))
      rules.refetch()
      showToast(t("alerts.toastRuleDeleted"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    }
  }

  const removeMute = async (window_: MuteWindow) => {
    if (!window.confirm(t("alerts.confirmDeleteMute"))) return
    try {
      await api.delete(endpoints.alerts.muteWindowDetail(window_.id))
      mutes.refetch()
      showToast(t("alerts.toastMuteDeleted"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    }
  }

  const act = async (alert: Alert, action: "acknowledge" | "resolve") => {
    setBusyId(alert.id)
    try {
      const endpoint =
        action === "acknowledge"
          ? endpoints.alerts.acknowledge(alert.id)
          : endpoints.alerts.resolve(alert.id)
      await api.post(endpoint)
      showToast(
        action === "acknowledge"
          ? t("alerts.toastAcknowledged", { title: alert.title })
          : t("alerts.toastResolved", { title: alert.title }),
        "success",
      )
      setRefreshKey((key) => key + 1)
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("alerts.title")}
        </h1>
        <p className="text-slate-500 mt-1">{t("alerts.subtitle")}</p>
      </div>

      <div className="mb-6">
        <Tabs
          tabs={(Object.keys(FILTERS) as FilterName[]).map((name) =>
            t(FILTER_LABELS[name]),
          )}
          active={t(FILTER_LABELS[filter])}
          onChange={(label) => {
            const next = (Object.keys(FILTERS) as FilterName[]).find(
              (name) => t(FILTER_LABELS[name]) === label,
            )
            if (next) setFilter(next)
          }}
        />
      </div>

      {loading && !alerts.length ? (
        <LoadingBlock label={t("alerts.loading")} />
      ) : error && !alerts.length ? (
        <ErrorBlock message={error} onRetry={refetch} />
      ) : alerts.length === 0 ? (
        <Card className="p-12 text-center">
          <BellOff size={32} className="text-slate-300 mx-auto mb-4" />
          <p className="font-semibold text-slate-900 mb-1">
            {t("alerts.emptyTitle")}
          </p>
          <p className="text-sm text-slate-500">{t("alerts.emptyBody")}</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {alerts.map((alert) => {
            const isResolved = alert.status === "resolved"
            return (
              <Card key={alert.id} className="p-5">
                <div className="flex items-start gap-4">
                  <span className="text-2xl flex-shrink-0 mt-0.5">
                    {isResolved ? "✅" : SEVERITY_ICON[alert.severity]}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <SeverityBadge severity={alert.severity} />
                          <p className="font-semibold text-slate-900">
                            {alert.title}
                          </p>
                        </div>
                        <Link
                          to={`/app/websites/${alert.website_id}`}
                          className="text-sm text-indigo-600 hover:text-indigo-700 font-mono mt-0.5 inline-block"
                        >
                          {alert.website_domain}
                        </Link>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="text-xs text-slate-400 flex-shrink-0">
                          {relativeTime(alert.created_at)}
                        </span>
                        {/* Channel names are backend identifiers (email, slack). */}
                        {alert.notification_channels_sent.length > 0 && (
                          <Badge variant="info">
                            <Mail size={10} aria-hidden="true" />
                            {alert.notification_channels_sent.join(", ")}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-slate-600 mt-2">{alert.message}</p>

                    {alert.status === "firing" && (
                      <div className="flex items-center gap-2 mt-4">
                        <Link to={`/app/websites/${alert.website_id}`}>
                          <Button size="sm">{t("alerts.viewDetails")}</Button>
                        </Link>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busyId === alert.id}
                          onClick={() => act(alert, "acknowledge")}
                        >
                          {t("alerts.acknowledge")}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={busyId === alert.id}
                          onClick={() => act(alert, "resolve")}
                        >
                          {t("alerts.resolve")}
                        </Button>
                      </div>
                    )}
                    {alert.status === "acknowledged" && (
                      <div className="flex items-center gap-3 mt-3">
                        <Badge variant="neutral">
                          {t("alerts.acknowledged")}
                        </Badge>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={busyId === alert.id}
                          onClick={() => act(alert, "resolve")}
                        >
                          {t("alerts.resolve")}
                        </Button>
                      </div>
                    )}
                    {isResolved && (
                      <span className="inline-flex items-center gap-1.5 mt-3 px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full border border-emerald-200">
                        ✅ {t("alerts.resolved")}
                      </span>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Automation — threshold rules and mute windows */}
      <section className="mt-10">
        <h2 className="font-bold text-slate-900 flex items-center gap-2">
          <SlidersHorizontal size={16} className="text-indigo-600" />
          {t("alerts.automation")}
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          {t("alerts.automationSubtitle")}
        </p>

        <div className="grid lg:grid-cols-2 gap-6 mt-4">
          <Card className="p-5">
            <h3 className="font-semibold text-slate-900 mb-1">
              {t("alerts.rulesTitle")}
            </h3>
            <p className="text-xs text-slate-500 mb-3">
              {t("alerts.rulesSubtitle")}
            </p>

            {rules.data.length === 0 ? (
              <p className="text-sm text-slate-500">{t("alerts.noRules")}</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {rules.data.map((rule) => (
                  <li
                    key={rule.id}
                    className="flex items-center gap-3 py-2.5 text-sm"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-800 truncate">
                        {rule.name}
                      </p>
                      <p className="text-xs text-slate-400">
                        {t(METRIC_LABELS[rule.metric])}{" "}
                        {t(OPERATOR_LABELS[rule.operator])} {rule.threshold} ·{" "}
                        {t(RULE_SEVERITY_LABELS[rule.severity])}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void removeRule(rule)}
                      className="text-slate-400 hover:text-red-600"
                      aria-label={t("alerts.deleteRuleLabel", {
                        name: rule.name,
                      })}
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <form onSubmit={addRule} className="mt-4 flex flex-col gap-2">
              <input
                value={ruleName}
                onChange={(event) => setRuleName(event.target.value)}
                placeholder={t("alerts.ruleNamePlaceholder")}
                className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <div className="grid grid-cols-2 gap-2">
                <select
                  aria-label={t("alerts.metricLabel")}
                  value={ruleMetric}
                  onChange={(event) =>
                    setRuleMetric(event.target.value as AlertRule["metric"])
                  }
                  className="px-2 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                >
                  <option value="health_score">
                    {t("alerts.metrics.healthScore")}
                  </option>
                  <option value="ssl_days_remaining">
                    {t("alerts.metrics.sslDaysRemaining")}
                  </option>
                  <option value="load_time_ms">
                    {t("alerts.metrics.loadTimeMs")}
                  </option>
                  <option value="page_size_kb">
                    {t("alerts.metrics.pageSizeKb")}
                  </option>
                </select>
                <select
                  aria-label={t("alerts.operatorLabel")}
                  value={ruleOperator}
                  onChange={(event) =>
                    setRuleOperator(
                      event.target.value as AlertRule["operator"],
                    )
                  }
                  className="px-2 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                >
                  <option value="lt">{t("alerts.operators.lt")}</option>
                  <option value="lte">{t("alerts.operators.lte")}</option>
                  <option value="gt">{t("alerts.operators.gt")}</option>
                  <option value="gte">{t("alerts.operators.gte")}</option>
                  <option value="eq">{t("alerts.operators.eq")}</option>
                </select>
                <input
                  aria-label={t("alerts.thresholdLabel")}
                  type="number"
                  value={ruleThreshold}
                  onChange={(event) => setRuleThreshold(event.target.value)}
                  className="px-2 py-2 text-sm border border-slate-300 rounded-lg"
                />
                <select
                  aria-label={t("alerts.severityLabel")}
                  value={ruleSeverity}
                  onChange={(event) =>
                    setRuleSeverity(
                      event.target.value as AlertRule["severity"],
                    )
                  }
                  className="px-2 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                >
                  <option value="warning">{t("severity.warning")}</option>
                  <option value="critical">{t("severity.critical")}</option>
                </select>
              </div>
              <Button type="submit" size="sm" disabled={saving}>
                {t("alerts.addRule")}
              </Button>
            </form>
          </Card>

          <Card className="p-5">
            <h3 className="font-semibold text-slate-900 mb-1 flex items-center gap-2">
              <CalendarOff size={14} className="text-indigo-600" />
              {t("alerts.mutesTitle")}
            </h3>
            <p className="text-xs text-slate-500 mb-3">
              {t("alerts.mutesSubtitle")}
            </p>

            {mutes.data.length === 0 ? (
              <p className="text-sm text-slate-500">{t("alerts.noMutes")}</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {mutes.data.map((window_) => (
                  <li
                    key={window_.id}
                    className="flex items-center gap-3 py-2.5 text-sm"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-800">
                        {t(MUTE_REASON_LABELS[window_.reason])}
                        {window_.is_active && (
                          <span className="ml-2 text-[10px] font-semibold uppercase text-emerald-600">
                            {t("alerts.active")}
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-slate-400">
                        {formatDateTime(window_.start_at)} →{" "}
                        {formatDateTime(window_.end_at)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void removeMute(window_)}
                      className="text-slate-400 hover:text-red-600"
                      aria-label={t("alerts.deleteMuteLabel")}
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <form onSubmit={addMuteWindow} className="mt-4 flex flex-col gap-2">
              <div className="grid grid-cols-2 gap-2">
                <label className="text-xs text-slate-500">
                  {t("alerts.start")}
                  <input
                    type="datetime-local"
                    value={muteStart}
                    onChange={(event) => setMuteStart(event.target.value)}
                    className="mt-1 w-full px-2 py-2 text-sm border border-slate-300 rounded-lg"
                  />
                </label>
                <label className="text-xs text-slate-500">
                  {t("alerts.end")}
                  <input
                    type="datetime-local"
                    value={muteEnd}
                    onChange={(event) => setMuteEnd(event.target.value)}
                    className="mt-1 w-full px-2 py-2 text-sm border border-slate-300 rounded-lg"
                  />
                </label>
              </div>
              <select
                aria-label={t("alerts.muteReasonLabel")}
                value={muteReason}
                onChange={(event) =>
                  setMuteReason(event.target.value as MuteWindow["reason"])
                }
                className="px-2 py-2 text-sm border border-slate-300 rounded-lg bg-white"
              >
                <option value="maintenance">
                  {t("alerts.reasons.maintenance")}
                </option>
                <option value="deployment">
                  {t("alerts.reasons.deployment")}
                </option>
                <option value="migration">
                  {t("alerts.reasons.migration")}
                </option>
                <option value="other">{t("alerts.reasons.other")}</option>
              </select>
              <Button type="submit" size="sm" disabled={saving}>
                {t("alerts.addMute")}
              </Button>
            </form>
          </Card>
        </div>
      </section>
    </div>
  )
}
