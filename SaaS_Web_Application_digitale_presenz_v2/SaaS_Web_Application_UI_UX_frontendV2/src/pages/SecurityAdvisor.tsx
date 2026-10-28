import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { ArrowLeft, ShieldCheck, X } from "lucide-react"

import { endpoints } from "../api/endpoints"
import { useApiList, useApiResource } from "../api/hooks/useApiResource"
import type { Organization, Website } from "../api/types"
import SecurityAdvisorChat from "../components/SecurityAdvisorChat"
import { Card, ErrorBlock, LoadingBlock } from "../components/ui"
import { useT } from "../i18n"

/**
 * `/app/advisor` — the organization-scoped entry point of the AI Security
 * Advisor.
 *
 * The organization id sent to the API is always one returned by
 * `/organizations/` for the signed-in user; the backend re-checks the role, so
 * hiding the composer for a viewer is a convenience, not the security boundary.
 */
export default function SecurityAdvisor() {
  const t = useT()
  const organizations = useApiList<Organization>(endpoints.organizations.list)
  const [selectedId, setSelectedId] = useState("")

  // Deep link from the asset page: `?org=<uuid>&asset=<id>`.  Both values are
  // hints only — the backend re-validates the membership and the tenant of the
  // asset on every request.
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedOrg = searchParams.get("org") ?? ""
  const rawAsset = Number(searchParams.get("asset"))
  const requestedAsset =
    Number.isFinite(rawAsset) && rawAsset > 0 ? rawAsset : null

  const selected =
    organizations.data.find((organization) => organization.id === requestedOrg) ??
    organizations.data.find((organization) => organization.id === selectedId) ??
    organizations.data[0] ??
    null

  // The asset is fetched through the website API, which is already scoped by
  // membership; it is only honoured when it belongs to the selected tenant.
  const asset = useApiResource<Website>(
    requestedAsset && selected ? endpoints.websites.detail(requestedAsset) : null,
    selected?.id ?? "",
  )
  const focusedAsset =
    asset.data && selected && asset.data.organization_id === selected.id
      ? asset.data
      : null

  const clearFocus = () => {
    if (!selected) return
    setSearchParams({ org: selected.id })
  }

  return (
    <div className="mx-auto max-w-3xl p-6 lg:p-8">
      <Link
        to="/app/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-indigo-600"
      >
        <ArrowLeft size={14} aria-hidden="true" />
        {t("advisorPage.backToOverview")}
      </Link>

      <div className="mb-6 mt-4">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("advisorPage.title")}
        </h1>
        <p className="mt-1 text-slate-500">{t("advisorPage.subtitle")}</p>
      </div>

      {organizations.loading ? (
        <Card className="p-6">
          <LoadingBlock label={t("advisorPage.loadingOrganizations")} />
        </Card>
      ) : organizations.error ? (
        <Card className="p-6">
          <ErrorBlock
            message={organizations.error}
            onRetry={organizations.refetch}
          />
        </Card>
      ) : !selected ? (
        <Card className="p-6">
          <p className="text-sm text-slate-600">
            {t("advisorPage.noOrganization")}
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {organizations.data.length > 1 && (
            <label className="flex flex-col gap-1.5 sm:max-w-sm">
              <span className="text-sm font-medium text-slate-700">
                {t("advisorPage.organization")}
              </span>
              <select
                value={selected.id}
                onChange={(event) => {
                  setSelectedId(event.target.value)
                  setSearchParams({ org: event.target.value })
                }}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {organizations.data.map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.name}
                    {organization.is_personal
                      ? t("advisorPage.personalSuffix")
                      : ""}
                  </option>
                ))}
              </select>
            </label>
          )}

          {focusedAsset && (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5">
              <p className="text-sm text-indigo-900">
                {t("advisorPage.focusedOn")}{" "}
                <span className="font-semibold">{focusedAsset.domain}</span>
                {t("advisorPage.focusedOnSuffix")}
              </p>
              <button
                type="button"
                onClick={clearFocus}
                className="inline-flex items-center gap-1 text-xs font-medium text-indigo-700 hover:text-indigo-900"
              >
                <X size={12} aria-hidden="true" />{" "}
                {t("advisorPage.wholeOrganization")}
              </button>
            </div>
          )}

          {/* `key` resets the local transcript when the tenant or the focused
              asset changes: two scopes must never share one conversation. */}
          <SecurityAdvisorChat
            key={`${selected.id}-${focusedAsset?.id ?? "org"}`}
            organizationId={selected.id}
            orgName={selected.name}
            role={selected.role}
            assetId={focusedAsset?.id ?? null}
            assetDomain={focusedAsset?.domain ?? null}
          />

          <Card className="p-5">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-emerald-50">
                <ShieldCheck
                  size={19}
                  className="text-emerald-600"
                  aria-hidden="true"
                />
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">
                  {t("advisorPage.privacyTitle")}
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {t("advisorPage.privacyBody")}
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
