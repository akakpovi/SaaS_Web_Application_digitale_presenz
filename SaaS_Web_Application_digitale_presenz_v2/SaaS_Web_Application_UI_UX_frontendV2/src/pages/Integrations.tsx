import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  AlertTriangle,
  ArrowLeft,
  ExternalLink,
  Lock,
  RefreshCw,
  Share2,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react"

import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { apiErrorMessage } from "../api/errors"
import { useApiList } from "../api/hooks/useApiResource"
import type {
  OAuthAuthorizeResponse,
  OAuthConnection,
  Organization,
  OrganizationRole,
} from "../api/types"
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBlock,
  LoadingBlock,
  Tabs,
} from "../components/ui"
import SocialAuditLog from "../components/SocialAuditLog"
import { useToast } from "../components/Toast"
import { useFormat } from "../lib/useFormat"
import type { MessageKey } from "../i18n"

const WRITE_ROLES: OrganizationRole[] = ["owner", "admin", "analyst"]
const DELETE_ROLES: OrganizationRole[] = ["owner", "admin"]
// The audit trail is restricted to the roles the backend accepts on
// /social/audit/: owner and admin.
const AUDIT_ROLES: OrganizationRole[] = ["owner", "admin"]
const DISCONNECT_CONFIRMATION = "DISCONNECT"

const CONNECTIONS_TAB = "Connections"
const AUDIT_TAB = "Audit logs"

type TabValue = "connections" | "audit"

type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string

/** A missing expiry is a fact to state, not a date to invent. */
function formatExpiry(
  value: string | null,
  t: Translate,
  formatDateTime: (value: string | null | undefined) => string,
): string {
  if (!value) return t("integrations.noExpiry")
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return t("integrations.unknownExpiry")
  return formatDateTime(date.toISOString())
}

function connectionStatus(
  status: OAuthConnection["status"],
  t: Translate,
): {
  label: string
  variant: "success" | "warning" | "critical" | "neutral"
} {
  switch (status) {
    case "active":
      return { label: t("integrations.statusActive"), variant: "success" }
    case "expired":
      return { label: t("integrations.statusExpired"), variant: "warning" }
    case "error":
      return { label: t("integrations.statusError"), variant: "critical" }
    case "revoked":
      return { label: t("integrations.statusRevoked"), variant: "neutral" }
    default:
      return { label: t("socialAudit.unknown"), variant: "neutral" }
  }
}

/**
 * Settings → Integrations. The organization list and the connection metadata
 * both come from the API; the browser never guesses a tenant id and never sees
 * token ciphertext.
 */
export default function Integrations() {
  const { t, formatDateTime } = useFormat()
  const { showToast } = useToast()
  // Tab labels are translated per render; the tab *identity* stays the constant.
  const connectionsTab = t("integrations.tabConnections")
  const auditTab = t("socialAudit.title")
  const organizations = useApiList<Organization>(endpoints.organizations.list)
  const [selectedId, setSelectedId] = useState("")
  const [connecting, setConnecting] = useState(false)
  const [disconnectTarget, setDisconnectTarget] =
    useState<OAuthConnection | null>(null)
  const [disconnectConfirm, setDisconnectConfirm] = useState("")
  const [disconnecting, setDisconnecting] = useState(false)
  const [requestedTab, setRequestedTab] = useState<TabValue>("connections")

  const selected =
    organizations.data.find((organization) => organization.id === selectedId) ??
    organizations.data[0] ??
    null
  const canWrite = selected?.role ? WRITE_ROLES.includes(selected.role) : false
  const canDelete = selected?.role
    ? DELETE_ROLES.includes(selected.role)
    : false
  const canAudit = selected?.role ? AUDIT_ROLES.includes(selected.role) : false
  // Derived, not stored: a role change (or an organization switch) can revoke
  // access while the audit tab is open, and the tab must disappear with it.
  const tab: TabValue = canAudit ? requestedTab : "connections"

  const connections = useApiList<OAuthConnection>(
    selected ? endpoints.social.connections(selected.id) : null,
  )

  const closeDisconnectDialog = () => {
    if (disconnecting) return
    setDisconnectTarget(null)
    setDisconnectConfirm("")
  }

  useEffect(() => {
    if (!disconnectTarget) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !disconnecting) {
        setDisconnectTarget(null)
        setDisconnectConfirm("")
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [disconnectTarget, disconnecting])

  const connectLinkedIn = async () => {
    if (!selected) {
      showToast("No organization is available for this action.", "error")
      return
    }
    if (!canWrite) {
      showToast(
        "Your organization role does not allow connecting social accounts.",
        "error",
      )
      return
    }

    setConnecting(true)
    try {
      const authorization = await api.get<OAuthAuthorizeResponse>(
        endpoints.social.authorize(selected.id, "linkedin"),
      )

      // The backend returns the exact LinkedIn authorization URL. Reject a
      // non-HTTPS value so a compromised response cannot become a script or
      // insecure redirect.
      const target = new URL(authorization.authorization_url)
      if (target.protocol !== "https:") {
        throw new Error("The authorization URL must use HTTPS.")
      }

      window.location.assign(target.toString())
    } catch (error) {
      showToast(apiErrorMessage(error), "error")
      setConnecting(false)
    }
  }

  const openDisconnectDialog = (connection: OAuthConnection) => {
    if (!canDelete) {
      showToast(
        "Only owners and administrators can disconnect social accounts.",
        "error",
      )
      return
    }
    setDisconnectTarget(connection)
    setDisconnectConfirm("")
  }

  const disconnectConnection = async () => {
    if (!disconnectTarget || !canDelete) return
    if (disconnectConfirm !== DISCONNECT_CONFIRMATION) return

    setDisconnecting(true)
    try {
      await api.delete<void>(
        endpoints.social.connection(
          disconnectTarget.organization,
          disconnectTarget.id,
        ),
      )
      showToast("LinkedIn account disconnected.", "success")
      setDisconnectTarget(null)
      setDisconnectConfirm("")
      await connections.refetch()
    } catch (error) {
      // A provider revocation failure keeps the connection server-side; the
      // dialog stays open so the user can retry or cancel.
      showToast(apiErrorMessage(error), "error")
    } finally {
      setDisconnecting(false)
    }
  }

  const hasConnections = connections.data.length > 0

  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto">
      <Link
        to="/app/settings"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-indigo-600"
      >
        <ArrowLeft size={14} />
        {t("integrations.backToSettings")}
      </Link>

      <div className="mt-4 mb-8">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("integrations.title")}
        </h1>
        <p className="text-slate-500 mt-1">{t("integrations.subtitle")}</p>
      </div>

      {!organizations.loading && !organizations.error && selected && (
        <div className="mb-6 flex flex-col gap-3">
          {organizations.data.length > 1 ? (
            <label className="flex flex-col gap-1.5 sm:max-w-sm">
              <span className="text-sm font-medium text-slate-700">
                {t("integrations.organization")}
              </span>
              <select
                value={selected.id}
                onChange={(event) => setSelectedId(event.target.value)}
                className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
          ) : (
            <p className="text-sm text-slate-600">
              {t("integrations.organizationWithColon")}{" "}
              <span className="font-medium text-slate-900">
                {selected.name}
              </span>
            </p>
          )}

          {canAudit && (
            <Tabs
              tabs={[connectionsTab, auditTab]}
              active={tab === "audit" ? auditTab : connectionsTab}
              onChange={(label) =>
                setRequestedTab(label === auditTab ? "audit" : "connections")
              }
            />
          )}
        </div>
      )}

      {tab === "audit" && selected ? (
        <SocialAuditLog
          organizationId={selected.id}
          organizationName={selected.name}
          role={selected.role}
        />
      ) : (
        <div className="flex flex-col gap-4">
          <Card className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-start gap-4">
              <div className="w-11 h-11 rounded-xl bg-[#0a66c2] flex items-center justify-center flex-shrink-0">
                <Share2 size={20} className="text-white" aria-hidden="true" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-bold text-slate-900">LinkedIn</h2>
                  <Badge variant="info">OAuth 2.0 · PKCE</Badge>
                </div>
                <p className="text-sm text-slate-500 mt-1">
                  {t("integrations.linkedinHint")}
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
              {organizations.loading ? (
                <LoadingBlock label={t("advisorPage.loadingOrganizations")} />
              ) : organizations.error ? (
                <ErrorBlock
                  message={organizations.error}
                  onRetry={organizations.refetch}
                />
              ) : organizations.data.length === 0 ? (
                <p className="text-sm text-slate-600">
                  {t("integrations.noOrganization")}
                </p>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      onClick={() => void connectLinkedIn()}
                      disabled={connecting || !selected || !canWrite}
                    >
                      {connecting ? (
                        <RefreshCw size={15} className="animate-spin" />
                      ) : (
                        <ExternalLink size={15} />
                      )}
                      {connecting
                        ? t("integrations.redirecting")
                        : t("integrations.connectLinkedIn")}
                    </Button>
                    <span className="text-xs text-slate-500">
                      {canWrite
                        ? t("integrations.willReturn")
                        : t("integrations.viewOnly")}
                    </span>
                  </div>

                  {!canWrite && (
                    <p className="text-xs text-slate-500">
                      {t("integrations.askToConnect")}
                    </p>
                  )}
                </div>
              )}
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-bold text-slate-900">
                  {t("integrations.connectedAccounts")}
                </h2>
                <p className="text-sm text-slate-500 mt-1">
                  {t("integrations.manageLinkedIn", {
                    organization:
                      selected?.name ?? t("integrations.defaultOrganization"),
                  })}
                </p>
              </div>
              {selected && (
                <Badge variant="neutral">
                  {t(
                    connections.count === 1
                      ? "integrations.connectionCountOne"
                      : "integrations.connectionCountMany",
                    { count: connections.count },
                  )}
                </Badge>
              )}
            </div>

            <div className="mt-5">
              {organizations.loading ? (
                <LoadingBlock label={t("advisorPage.loadingOrganizations")} />
              ) : organizations.error ? (
                <ErrorBlock
                  message={organizations.error}
                  onRetry={organizations.refetch}
                />
              ) : !selected ? (
                <p className="text-sm text-slate-600">
                  {t("integrations.selectOrganization")}
                </p>
              ) : connections.loading ? (
                <LoadingBlock label={t("integrations.loadingConnections")} />
              ) : connections.error ? (
                <ErrorBlock
                  message={connections.error}
                  onRetry={connections.refetch}
                />
              ) : !hasConnections ? (
                <EmptyState
                  icon={<Share2 size={24} aria-hidden="true" />}
                  title={t("integrations.noLinkedInTitle")}
                  description={t("integrations.noLinkedInHint")}
                />
              ) : (
                <div className="flex flex-col gap-3">
                  {connections.data.map((connection) => {
                    const status = connectionStatus(connection.status, t)
                    return (
                      <div
                        key={connection.id}
                        className="flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border border-slate-200 p-4"
                      >
                        <div className="w-10 h-10 rounded-xl bg-[#0a66c2] flex items-center justify-center flex-shrink-0">
                          <Share2
                            size={17}
                            className="text-white"
                            aria-hidden="true"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-semibold text-slate-900">
                              LinkedIn
                            </p>
                            <Badge variant={status.variant}>
                              {status.label}
                            </Badge>
                          </div>
                          <p
                            className="mt-1 text-sm text-slate-500 break-all"
                            title={connection.external_account_id}
                          >
                            {t("integrations.accountLabel", {
                              id: connection.external_account_id,
                            })}
                          </p>
                          <p className="mt-1 text-xs text-slate-400">
                            {t("integrations.expires", {
                              date: formatExpiry(
                                connection.expires_at,
                                t,
                                formatDateTime,
                              ),
                            })}
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openDisconnectDialog(connection)}
                          disabled={!canDelete}
                        >
                          <Trash2 size={14} aria-hidden="true" />
                          {t("integrations.disconnect")}
                        </Button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {selected && hasConnections && !canDelete && (
              <p className="mt-4 text-xs text-slate-500">
                {t("integrations.onlyOwners")}
              </p>
            )}
          </Card>

          <Card className="p-6">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center flex-shrink-0">
                <ShieldCheck
                  size={19}
                  className="text-emerald-600"
                  aria-hidden="true"
                />
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">
                  {t("integrations.credentialsTitle")}
                </h2>
                <p className="text-sm text-slate-500 mt-1">
                  {t("integrations.credentialsBody")}
                </p>
                <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-slate-400">
                  <Lock size={12} aria-hidden="true" />
                  {t("integrations.noPassword")}
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {disconnectTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="disconnect-title"
          onClick={closeDisconnectDialog}
        >
          <div
            className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center flex-shrink-0">
                  <AlertTriangle
                    size={19}
                    className="text-red-600"
                    aria-hidden="true"
                  />
                </div>
                <div>
                  <h2
                    id="disconnect-title"
                    className="font-bold text-slate-900"
                  >
                    {t("integrations.disconnectTitle")}
                  </h2>
                  <p className="text-sm text-slate-500 mt-1">
                    {t("integrations.disconnectHint")}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={closeDisconnectDialog}
                disabled={disconnecting}
                className="text-slate-400 hover:text-slate-600 disabled:opacity-50"
                aria-label={t("integrations.closeDisconnectAria")}
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              <span className="font-medium text-slate-800">
                {t("integrations.accountColon")}
              </span>{" "}
              <span className="break-all">
                {disconnectTarget.external_account_id}
              </span>
            </div>

            <label className="mt-4 flex flex-col gap-1.5">
              <span className="text-sm font-medium text-slate-700">
                {t("integrations.typeWordPrefix")}{" "}
                <strong>{DISCONNECT_CONFIRMATION}</strong>{" "}
                {t("integrations.typeWordSuffix")}
              </span>
              <input
                autoFocus
                value={disconnectConfirm}
                onChange={(event) => setDisconnectConfirm(event.target.value)}
                disabled={disconnecting}
                placeholder="DISCONNECT"
                aria-label={t("integrations.typeToConfirmAria", {
                  word: DISCONNECT_CONFIRMATION,
                })}
                autoComplete="off"
                spellCheck={false}
                className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent disabled:opacity-50"
              />
            </label>

            <div className="mt-5 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={closeDisconnectDialog}
                disabled={disconnecting}
              >
                {t("common.cancel")}
              </Button>
              <Button
                variant="danger"
                onClick={() => void disconnectConnection()}
                disabled={
                  disconnecting || disconnectConfirm !== DISCONNECT_CONFIRMATION
                }
              >
                {disconnecting ? (
                  <RefreshCw size={15} className="animate-spin" />
                ) : (
                  <Trash2 size={15} />
                )}
                {disconnecting
                  ? t("integrations.disconnecting")
                  : t("integrations.disconnectAccount")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
