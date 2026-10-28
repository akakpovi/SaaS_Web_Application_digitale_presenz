import { useState } from "react"
import {
  ArrowLeft,
  ArrowRight,
  CalendarClock,
  RefreshCw,
  ScrollText,
  ShieldAlert,
} from "lucide-react"

import { endpoints } from "../api/endpoints"
import { useApiResource } from "../api/hooks/useApiResource"
import type {
  OrganizationRole,
  Paginated,
  SocialAuditAction,
  SocialAuditEvent,
} from "../api/types"
import { Badge, Button, Card, EmptyState, ErrorBlock, LoadingBlock } from "./ui"
import { useFormat } from "../lib/useFormat"
import type { MessageKey } from "../i18n"

/**
 * Only owners and administrators may read the audit trail. The tab itself is
 * hidden for other roles by `Integrations`; this guard keeps the component
 * inert if it is ever mounted elsewhere.
 */
const AUDIT_ROLES: OrganizationRole[] = ["owner", "admin"]

// Mirrors the backend `TextChoices`: the API rejects anything else with a 400,
// so the selects must only ever submit declared values.
const PROVIDER_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  google: "Google",
  facebook: "Facebook",
  instagram: "Instagram",
  twitter: "Twitter / X",
}
const PROVIDERS = Object.keys(PROVIDER_LABELS)
const ACTIONS: SocialAuditAction[] = ["connected", "disconnected"]

const ALL = "all"

type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string

/** Provider names are proper nouns; an unknown value keeps its raw form. */
function providerLabel(provider: string, t: Translate): string {
  if (!provider) return t("socialAudit.unknown")
  return (
    PROVIDER_LABELS[provider] ??
    provider.charAt(0).toUpperCase() + provider.slice(1)
  )
}

function actionBadge(action: string, t: Translate) {
  if (action === "connected")
    return { label: t("socialAudit.connected"), variant: "success" as const }
  if (action === "disconnected")
    return { label: t("socialAudit.disconnected"), variant: "neutral" as const }
  return { label: action || t("socialAudit.unknown"), variant: "neutral" as const }
}

/**
 * Read a page number out of a DRF `next`/`previous` link.
 *
 * The link is parsed, never fetched: it is an absolute URL built by the API
 * host, and following it directly would drop the Authorization header and
 * could be pointed at another origin. Only the `page` value is reused against
 * our own client, which also keeps the request authenticated.
 *
 * DRF drops `page=1` from the link (the first page is the implicit default), so
 * a link without a `page` parameter means page 1 — not "no previous page".
 */
function pageFromLink(link: string | null | undefined): number | null {
  if (!link) return null
  try {
    const raw = new URL(link, window.location.origin).searchParams.get("page")
    if (raw === null) return 1
    const page = Number(raw)
    return Number.isInteger(page) && page > 0 ? page : null
  } catch {
    return null
  }
}

export default function SocialAuditLog({
  organizationId,
  organizationName,
  role,
}: {
  organizationId: string
  organizationName: string
  role: OrganizationRole | null
}) {
  const { t, formatDateTime } = useFormat()
  const [page, setPage] = useState(1)
  const [provider, setProvider] = useState<string>(ALL)
  const [action, setAction] = useState<SocialAuditAction | typeof ALL>(ALL)

  const { data, error, loading, refetch } =
    useApiResource<Paginated<SocialAuditEvent>>(
      endpoints.social.audit(organizationId, {
        page,
        provider: provider === ALL ? undefined : provider,
        action: action === ALL ? undefined : action,
      }),
    )

  if (!role || !AUDIT_ROLES.includes(role)) return null

  const events = data?.results ?? []
  const total = data?.count ?? 0
  const nextPage = pageFromLink(data?.next)
  const previousPage = pageFromLink(data?.previous)
  const filtersActive = provider !== ALL || action !== ALL

  const changeProvider = (value: string) => {
    setProvider(value)
    // Narrowing the result set can make the current page out of range, and
    // DRF answers an out-of-range page with a 404.
    setPage(1)
  }

  const changeAction = (value: string) => {
    setAction(value as SocialAuditAction | typeof ALL)
    setPage(1)
  }

  const clearFilters = () => {
    setProvider(ALL)
    setAction(ALL)
    setPage(1)
  }

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-bold text-slate-900">{t("socialAudit.title")}</h2>
          <p className="text-sm text-slate-500 mt-1">
            {t("socialAudit.subtitle", { organization: organizationName })}
          </p>
        </div>
        <Badge variant="neutral">
          {t(
            total === 1
              ? "socialAudit.eventCountOne"
              : "socialAudit.eventCountMany",
            { count: total },
          )}
        </Badge>
      </div>

      <div className="mt-5 flex flex-col sm:flex-row sm:items-end gap-3">
        <label className="flex flex-col gap-1.5 flex-1 min-w-0">
          <span className="text-sm font-medium text-slate-700">{t("socialAudit.provider")}</span>
          <select
            value={provider}
            onChange={(event) => changeProvider(event.target.value)}
            className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value={ALL}>{t("socialAudit.allProviders")}</option>
            {PROVIDERS.map((value) => (
              <option key={value} value={value}>
                {providerLabel(value, t)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5 flex-1 min-w-0">
          <span className="text-sm font-medium text-slate-700">{t("socialAudit.action")}</span>
          <select
            value={action}
            onChange={(event) => changeAction(event.target.value)}
            className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value={ALL}>{t("socialAudit.allActions")}</option>
            {ACTIONS.map((value) => (
              <option key={value} value={value}>
                {t(
                  value === "connected"
                    ? "socialAudit.connected"
                    : "socialAudit.disconnected",
                )}
              </option>
            ))}
          </select>
        </label>

        <Button
          variant="outline"
          size="sm"
          onClick={() => void refetch()}
          disabled={loading}
          className="sm:mb-0.5"
        >
          <RefreshCw
            size={14}
            className={loading ? "animate-spin" : undefined}
            aria-hidden="true"
          />
          {t("common.refresh")}
        </Button>
      </div>

      <div className="mt-5">
        {loading && !data ? (
          <LoadingBlock label={t("socialAudit.loading")} />
        ) : error ? (
          <ErrorBlock message={error} onRetry={() => void refetch()} />
        ) : events.length === 0 ? (
          filtersActive ? (
            <EmptyState
              icon={<ScrollText size={24} aria-hidden="true" />}
              title={t("socialAudit.emptyFilteredTitle")}
              description={t("socialAudit.emptyFilteredHint")}
              action={
                <Button size="sm" variant="outline" onClick={clearFilters}>
                  {t("socialAudit.clearFilters")}
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={<CalendarClock size={24} aria-hidden="true" />}
              title={t("socialAudit.emptyTitle")}
              description={t("socialAudit.emptyHint")}
            />
          )
        ) : (
          <>
            <div className="overflow-x-auto -mx-6 px-6">
              <table className="min-w-full text-sm">
                <caption className="sr-only">
                  {t("socialAudit.caption", { organization: organizationName })}
                </caption>
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th scope="col" className="py-2 pr-4 font-semibold">
                      {t("socialAudit.timestamp")}
                    </th>
                    <th scope="col" className="py-2 pr-4 font-semibold">
                      {t("socialAudit.actor")}
                    </th>
                    <th scope="col" className="py-2 pr-4 font-semibold">
                      {t("socialAudit.action")}
                    </th>
                    <th scope="col" className="py-2 pr-4 font-semibold">
                      {t("socialAudit.provider")}
                    </th>
                    <th scope="col" className="py-2 pr-4 font-semibold">
                      {t("socialAudit.accountId")}
                    </th>
                    <th scope="col" className="py-2 font-semibold">
                      {t("socialAudit.ip")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => {
                    const status = actionBadge(event.action, t)
                    return (
                      <tr
                        key={event.id}
                        className="border-b border-slate-100 last:border-0 align-top"
                      >
                        <td className="py-3 pr-4 whitespace-nowrap text-slate-600">
                          <time dateTime={event.created_at}>
                            {formatDateTime(event.created_at)}
                          </time>
                        </td>
                        <td
                          className="py-3 pr-4 break-all text-slate-700"
                          title={event.actor_email || undefined}
                        >
                          {event.actor_email || "—"}
                        </td>
                        <td className="py-3 pr-4">
                          <Badge variant={status.variant}>{status.label}</Badge>
                        </td>
                        <td className="py-3 pr-4 whitespace-nowrap text-slate-700">
                          {providerLabel(event.provider, t)}
                        </td>
                        <td
                          className="py-3 pr-4 font-mono text-xs break-all text-slate-600"
                          title={event.external_account_id}
                        >
                          {event.external_account_id || "—"}
                        </td>
                        <td className="py-3 font-mono text-xs whitespace-nowrap text-slate-600">
                          {event.ip_address || "—"}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <p
                className="text-xs text-slate-500"
                role="status"
                aria-live="polite"
              >
                {t(
                  total === 1
                    ? "socialAudit.pageOne"
                    : "socialAudit.pageMany",
                  { page, shown: events.length, total },
                )}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!previousPage || loading}
                  onClick={() => {
                    if (previousPage) setPage(previousPage)
                  }}
                >
                  <ArrowLeft size={14} aria-hidden="true" />
                  {t("socialAudit.previous")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!nextPage || loading}
                  onClick={() => {
                    if (nextPage) setPage(nextPage)
                  }}
                >
                  {t("socialAudit.next")}
                  <ArrowRight size={14} aria-hidden="true" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>

      <p className="mt-4 inline-flex items-center gap-1.5 text-xs text-slate-400">
        <ShieldAlert size={12} aria-hidden="true" />
        {t("socialAudit.footer")}
      </p>
    </Card>
  )
}
