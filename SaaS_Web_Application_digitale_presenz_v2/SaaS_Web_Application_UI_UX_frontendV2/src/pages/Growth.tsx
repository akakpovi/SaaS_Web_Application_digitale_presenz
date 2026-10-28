import React, { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import {
  ExternalLink,
  Globe,
  Megaphone,
  RefreshCw,
  ScanSearch,
  ShieldAlert,
  TrendingUp,
} from "lucide-react"
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBlock,
  LoadingBlock,
  ScoreRing,
  SeverityBadge,
  Tabs,
} from "../components/ui"
import { UpgradeBadge, useUpgrade } from "../components/UpgradePrompt"
import { useToast } from "../components/Toast"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { useApiList } from "../api/hooks/useApiResource"
import { apiErrorMessage } from "../api/errors"
import type {
  Backlink,
  Keyword,
  SEOAudit,
  SecurityIncident,
  SocialMention,
  SocialProfile,
  Website,
} from "../api/types"
import { useFormat } from "../lib/useFormat"
import { usePlan } from "../contexts/PlanContext"

const TABS = ["SEO", "Reputation", "Security"]
const QUERY_TO_TAB: Record<string, string> = {
  seo: "SEO",
  reputation: "Reputation",
  security: "Security",
}

function sentimentVariant(
  sentiment: SocialMention["sentiment"],
): "success" | "neutral" | "critical" {
  if (sentiment === "positive") return "success"
  if (sentiment === "negative") return "critical"
  return "neutral"
}

function providerLabel(provider: SocialProfile["provider"]): string {
  const labels: Record<SocialProfile["provider"], string> = {
    facebook: "Facebook",
    instagram: "Instagram",
    twitter: "Twitter/X",
    linkedin: "LinkedIn",
  }
  return labels[provider] ?? provider
}

export default function Growth() {
  const { t, relativeTime, formatNumber } = useFormat()
  const [params, setParams] = useSearchParams()
  const { guard } = useUpgrade()
  const { isPaid, tier } = usePlan()
  const { showToast } = useToast()

  const [selectedWebsite, setSelectedWebsite] = useState<number | null>(null)
  const [busy, setBusy] = useState<"seo" | "social" | "security" | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const activeTab = QUERY_TO_TAB[params.get("tab") ?? "seo"] ?? "SEO"

  const websites = useApiList<Website>(endpoints.websites.list)
  const requestedWebsite = Number(params.get("website") ?? "")
  const websiteId =
    selectedWebsite ??
    (websites.data.some((site) => site.id === requestedWebsite)
      ? requestedWebsite
      : null) ??
    websites.data[0]?.id ??
    null

  const audits = useApiList<SEOAudit>(
    websiteId ? endpoints.seo.audits(websiteId) : null,
    refreshKey,
  )
  const keywords = useApiList<Keyword>(
    websiteId ? endpoints.seo.keywords(websiteId) : null,
    refreshKey,
  )
  const backlinks = useApiList<Backlink>(
    websiteId ? endpoints.seo.backlinks(websiteId) : null,
    refreshKey,
  )
  const profiles = useApiList<SocialProfile>(
    websiteId ? endpoints.social.profiles(websiteId) : null,
    refreshKey,
  )
  const mentions = useApiList<SocialMention>(
    websiteId ? endpoints.social.mentions(websiteId) : null,
    refreshKey,
  )
  const incidents = useApiList<SecurityIncident>(
    websiteId ? endpoints.security.incidents(websiteId) : null,
    refreshKey,
  )

  const latestAudit = audits.data[0] ?? null
  const openIncidents = incidents.data.filter((incident) => !incident.is_resolved)

  const setTab = (tab: string) => {
    const next = new URLSearchParams(params)
    const key =
      Object.keys(QUERY_TO_TAB).find((value) => QUERY_TO_TAB[value] === tab) ??
      "seo"
    next.set("tab", key)
    if (websiteId) next.set("website", String(websiteId))
    setParams(next, { replace: true })
  }

  const changeWebsite = (id: number) => {
    setSelectedWebsite(id)
    const next = new URLSearchParams(params)
    next.set("website", String(id))
    setParams(next, { replace: true })
  }

  const refreshAll = () => setRefreshKey((key) => key + 1)

  const runSeoAudit = async () => {
    if (!websiteId || !guard("seo.audit")) return
    setBusy("seo")
    try {
      await api.post(endpoints.seo.runAudit(websiteId))
      showToast("SEO audit queued. Results appear in a minute.", "success")
      refreshAll()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setBusy(null)
    }
  }

  const syncSocial = async () => {
    if (!websiteId || !guard("social.sync")) return
    setBusy("social")
    try {
      await api.post(endpoints.social.sync(websiteId))
      showToast("Reputation sync queued.", "success")
      refreshAll()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setBusy(null)
    }
  }

  const runSecurityScan = async () => {
    if (!websiteId || !guard("security.scan")) return
    setBusy("security")
    try {
      await api.post(endpoints.security.scan(websiteId))
      showToast("Advanced security scan queued.", "success")
      refreshAll()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <div className="flex flex-col lg:flex-row lg:items-start gap-4 mb-6">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <TrendingUp size={22} className="text-indigo-600" aria-hidden="true" />
            {t("growth.title")}
          </h1>
          <p className="text-slate-500 mt-1">{t("growth.subtitle")}</p>
        </div>
        {websites.data.length > 0 && (
          <select
            aria-label={t("growth.selectWebsiteAria")}
            value={websiteId ?? ""}
            onChange={(event) => changeWebsite(Number(event.target.value))}
            className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {websites.data.map((site) => (
              <option key={site.id} value={site.id}>
                {site.domain}
              </option>
            ))}
          </select>
        )}
      </div>

      {!isPaid && (
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center gap-3 rounded-2xl border border-indigo-200 bg-indigo-50/70 px-4 py-3">
          <div className="flex-1 text-sm text-indigo-900">
            <span className="font-semibold">{t("growth.freePlan")}</span>{" "}
            {t("growth.freePlanHint")}
          </div>
          <Link
            to="/app/billing"
            className="text-sm font-semibold text-indigo-700 hover:text-indigo-800"
          >
            {t("growth.comparePlans")}
          </Link>
        </div>
      )}

      {websites.loading ? (
        <LoadingBlock label={t("growth.loadingWebsites")} />
      ) : websites.error ? (
        <ErrorBlock message={websites.error} onRetry={websites.refetch} />
      ) : websites.data.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Globe size={26} />}
            title={t("growth.addWebsiteTitle")}
            description={t("growth.addWebsiteHint")}
            action={
              <Link to="/app/websites">
                <Button>{t("growth.addWebsite")}</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          <div className="mb-6 max-w-md">
            <Tabs tabs={TABS} active={activeTab} onChange={setTab} />
          </div>

          {activeTab === "SEO" && (
            <div className="flex flex-col gap-6">
              <Card className="p-6">
                <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                  <div className="flex-1">
                    <h2 className="font-bold text-slate-900 flex items-center gap-2">
                      <ScanSearch size={16} className="text-indigo-600" />
                      {t("growth.seoAuditTitle")}
                      <UpgradeBadge feature="seo.audit" />
                    </h2>
                    <p className="text-sm text-slate-500 mt-1">
                      {t("growth.seoAuditHint")}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy === "seo"}
                    onClick={() => void runSeoAudit()}
                  >
                    <RefreshCw
                      size={13}
                      className={busy === "seo" ? "animate-spin" : ""}
                    />
                    {busy === "seo"
                      ? t("growth.queuing")
                      : t("growth.runSeoAudit")}
                  </Button>
                </div>

                {audits.loading ? (
                  <LoadingBlock label={t("growth.loadingAudits")} />
                ) : audits.error ? (
                  <ErrorBlock message={audits.error} onRetry={audits.refetch} />
                ) : latestAudit ? (
                  <div className="mt-6 flex flex-col lg:flex-row gap-6">
                    <div className="flex items-center gap-4">
                      <ScoreRing
                        score={latestAudit.overall_score}
                        size={92}
                        label={t("growth.seoScore")}
                      />
                      <div className="grid grid-cols-3 gap-3 text-center">
                        {[
                          [t("growth.seoTechnical"), latestAudit.technical_score],
                          [t("growth.seoContent"), latestAudit.content_score],
                          [t("growth.seoMobile"), latestAudit.mobile_score],
                        ].map(([label, score]) => (
                          <div key={label as string}>
                            <p className="text-lg font-bold text-slate-900 tabular-nums">
                              {score}
                            </p>
                            <p className="text-[11px] text-slate-500">{label}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs text-slate-400 mb-2">
                        {t("growth.auditedAt", {
                          time: relativeTime(latestAudit.created_at),
                          robots: latestAudit.robots_txt,
                          sitemap: latestAudit.sitemap,
                        })}
                      </p>
                      {latestAudit.issues.length === 0 ? (
                        <p className="text-sm text-emerald-600">
                          {t("growth.noBlockingIssue")}
                        </p>
                      ) : (
                        <ul className="flex flex-col gap-1.5">
                          {latestAudit.issues.slice(0, 6).map((issue) => (
                            <li
                              key={issue}
                              className="text-sm text-slate-600 flex items-start gap-2"
                            >
                              <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                              {issue}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                ) : (
                  <EmptyState
                    icon={<ScanSearch size={24} />}
                    title={t("growth.noSeoAuditTitle")}
                    description={t("growth.noSeoAuditHint")}
                  />
                )}
              </Card>

              <div className="grid lg:grid-cols-2 gap-6">
                <Card className="p-6">
                  <h3 className="font-semibold text-slate-900 mb-3">
                    {t("growth.trackedKeywords")}
                  </h3>
                  {keywords.data.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      {t("growth.noKeyword")}
                    </p>
                  ) : (
                    <ul className="flex flex-col divide-y divide-slate-100">
                      {keywords.data.slice(0, 8).map((keyword) => (
                        <li
                          key={keyword.id}
                          className="flex items-center justify-between gap-3 py-2 text-sm"
                        >
                          <span className="text-slate-700 truncate">
                            {keyword.term}
                            <span className="text-slate-400">
                              {" "}
                              · {keyword.country}
                            </span>
                          </span>
                          <span className="text-slate-500 tabular-nums">
                            {keyword.current_rank
                              ? `#${keyword.current_rank}`
                              : "—"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>

                <Card className="p-6">
                  <h3 className="font-semibold text-slate-900 mb-3">
                    {t("growth.backlinks")}
                  </h3>
                  {backlinks.data.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      {t("growth.noBacklink")}
                    </p>
                  ) : (
                    <ul className="flex flex-col divide-y divide-slate-100">
                      {backlinks.data.slice(0, 8).map((link) => (
                        <li key={link.id} className="py-2 text-sm">
                          <p className="text-slate-700 truncate">
                            {link.source_url}
                          </p>
                          <p className="text-xs text-slate-400">
                            {t("growth.domainAuthority", {
                              value: link.domain_authority,
                            })}{" "}
                            · {link.is_dofollow ? "dofollow" : "nofollow"}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>
            </div>
          )}

          {activeTab === "Reputation" && (
            <div className="flex flex-col gap-6">
              <Card className="p-6">
                <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                  <div className="flex-1">
                    <h2 className="font-bold text-slate-900 flex items-center gap-2">
                      <Megaphone size={16} className="text-indigo-600" />
                      {t("growth.reputationTitle")}
                      <UpgradeBadge feature="social.sync" />
                    </h2>
                    <p className="text-sm text-slate-500 mt-1">
                      {t("growth.reputationHint")}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy === "social"}
                    onClick={() => void syncSocial()}
                  >
                    <RefreshCw
                      size={13}
                      className={busy === "social" ? "animate-spin" : ""}
                    />
                    {busy === "social"
                      ? t("growth.syncing")
                      : t("growth.syncNow")}
                  </Button>
                </div>

                {profiles.loading ? (
                  <LoadingBlock label={t("growth.loadingProfiles")} />
                ) : profiles.data.length === 0 ? (
                  <EmptyState
                    icon={<Megaphone size={24} />}
                    title={t("growth.noProfileTitle")}
                    description={t("growth.noProfileHint")}
                  />
                ) : (
                  <div className="mt-5 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {profiles.data.map((profile) => (
                      <div
                        key={profile.id}
                        className="rounded-xl border border-slate-200 p-4"
                      >
                        <p className="text-xs font-semibold text-slate-400 uppercase">
                          {providerLabel(profile.provider)}
                        </p>
                        <p className="text-sm font-semibold text-slate-900 truncate">
                          {profile.handle}
                        </p>
                        <p className="text-xs text-slate-500 mt-1">
                          {t("growth.profileStats", {
                            followers: formatNumber(profile.followers),
                            rate: profile.engagement_rate.toFixed(1),
                          })}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              <Card className="p-6">
                <h3 className="font-semibold text-slate-900 mb-3">
                  {t("growth.recentMentions")}
                </h3>
                {mentions.data.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    {t("growth.noMention")}
                  </p>
                ) : (
                  <ul className="flex flex-col divide-y divide-slate-100">
                    {mentions.data.slice(0, 10).map((mention) => (
                      <li key={mention.id} className="py-3">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <Badge variant={sentimentVariant(mention.sentiment)}>
                            {mention.sentiment}
                          </Badge>
                          <span className="text-xs text-slate-400">
                            {mention.platform} · {mention.author} ·{" "}
                            {relativeTime(mention.mentioned_at)}
                          </span>
                          {mention.url && (
                            <a
                              href={mention.url}
                              target="_blank"
                              rel="noreferrer noopener"
                              className="text-indigo-600 hover:text-indigo-700"
                              aria-label={t("growth.openMentionAria")}
                            >
                              <ExternalLink size={12} />
                            </a>
                          )}
                        </div>
                        <p className="text-sm text-slate-600 line-clamp-2">
                          {mention.content}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          )}

          {activeTab === "Security" && (
            <Card className="p-6">
              <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                <div className="flex-1">
                  <h2 className="font-bold text-slate-900 flex items-center gap-2">
                    <ShieldAlert size={16} className="text-indigo-600" />
                    {t("growth.securityTitle")}
                    <UpgradeBadge feature="security.scan" />
                  </h2>
                  <p className="text-sm text-slate-500 mt-1">
                    {t("growth.securityHint")}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy === "security"}
                  onClick={() => void runSecurityScan()}
                >
                  <RefreshCw
                    size={13}
                    className={busy === "security" ? "animate-spin" : ""}
                  />
                  {busy === "security"
                    ? t("growth.scanning")
                    : t("growth.runSecurityScan")}
                </Button>
              </div>

              <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
                <span>
                  {t(
                    openIncidents.length === 1
                      ? "growth.openIncidentsOne"
                      : "growth.openIncidentsMany",
                    { count: openIncidents.length },
                  )}
                </span>
                <span>·</span>
                <span>
                  {t("growth.detectedTotal", {
                    count: incidents.data.length,
                  })}
                </span>
              </div>

              {incidents.loading ? (
                <LoadingBlock label={t("growth.loadingIncidents")} />
              ) : incidents.error ? (
                <ErrorBlock
                  message={incidents.error}
                  onRetry={incidents.refetch}
                />
              ) : incidents.data.length === 0 ? (
                <EmptyState
                  icon={<ShieldAlert size={24} />}
                  title={t("growth.noIncidentTitle")}
                  description={t("growth.noIncidentHint")}
                />
              ) : (
                <ul className="mt-4 flex flex-col divide-y divide-slate-100">
                  {incidents.data.slice(0, 20).map((incident) => (
                    <li key={incident.id} className="py-3">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <SeverityBadge severity={incident.severity} />
                        <span className="text-sm font-semibold text-slate-900">
                          {incident.title}
                        </span>
                        {incident.is_resolved && (
                          <Badge variant="success">{t("growth.resolved")}</Badge>
                        )}
                      </div>
                      <p className="text-sm text-slate-600">
                        {incident.description}
                      </p>
                      <p className="text-xs text-slate-400 mt-1">
                        {incident.incident_type.replace("_", " ")}
                        {t("growth.incidentDetected", {
                          time: relativeTime(incident.detected_at),
                        })}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          <p className="mt-6 text-xs text-slate-400">
            {t("growth.planFooter", { tier })}
          </p>
        </>
      )}
    </div>
  )
}
