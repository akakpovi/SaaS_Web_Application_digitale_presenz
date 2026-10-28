import React, { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  Card,
  Button,
  Toggle,
  Tabs,
  Input,
  LoadingBlock,
} from "../components/ui"
import { useToast } from "../components/Toast"
import { useTheme } from "../components/AppShell"
import { UpgradeBadge, useUpgrade } from "../components/UpgradePrompt"
import { usePlan } from "../contexts/PlanContext"
import { useAuth } from "../api/hooks/useAuth"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import {
  apiErrorMessage,
  useApiList,
  useApiResource,
} from "../api/hooks/useApiResource"
import type {
  AccountDeletionResult,
  AccountExport,
  AlertPreferences,
  ApiKey,
  NotificationChannel,
  NotificationChannelType,
  UserProfile,
} from "../api/types"
import { useFormat } from "../lib/useFormat"
import { Copy, KeyRound, Moon, Plus, Sun, Trash2 } from "lucide-react"

/** The VAPID key is base64url; PushManager.subscribe expects raw bytes. */
function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/")
  const raw = window.atob(base64)
  // An explicit ArrayBuffer (not ArrayBufferLike) is what PushSubscriptionOptions
  // accepts as `applicationServerKey` in the DOM typings.
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index)
  }
  return bytes
}

const LANGUAGES: { code: UserProfile["language"]; label: string }[] = [
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
]

/** Sidebar entries. The identifiers stay stable; only the label is translated. */
const SECTION_KEYS = {
  Account: "settings.sectionAccount",
  Business: "settings.sectionBusiness",
  Websites: "settings.sectionWebsites",
  Notifications: "settings.sectionNotifications",
  Appearance: "settings.sectionAppearance",
  PWA: "settings.sectionPwa",
  Security: "settings.sectionSecurity",
  Subscription: "settings.sectionSubscription",
  "API access": "settings.sectionApi",
  Integrations: "settings.sectionIntegrations",
  Language: "settings.sectionLanguage",
  "Privacy & data": "settings.sectionPrivacy",
} as const

type SectionName = keyof typeof SECTION_KEYS

const INDUSTRIES: { value: UserProfile["business_industry"]; label: string }[] = [
  { value: "restaurant", label: "Restaurant / Café" },
  { value: "retail", label: "Retail" },
  { value: "hotel", label: "Hotel" },
  { value: "auto_repair", label: "Auto Repair" },
  { value: "beauty", label: "Beauty" },
  { value: "agency", label: "Agency" },
  { value: "other", label: "Other" },
]

const COUNTRIES: { value: UserProfile["business_country"]; label: string }[] = [
  { value: "DE", label: "Germany" },
  { value: "FR", label: "France" },
  { value: "AT", label: "Austria" },
  { value: "CH", label: "Switzerland" },
  { value: "OTHER", label: "Other" },
]

const TIMEZONES: UserProfile["timezone"][] = [
  "Europe/Berlin",
  "Europe/Paris",
  "Europe/Vienna",
  "UTC",
]

const sections = [
  "Account",
  "Business",
  "Websites",
  "Notifications",
  "Appearance",
  "PWA",
  "Security",
  "Subscription",
  "API access",
  "Integrations",
  "Language",
  "Privacy & data",
]

export default function Settings() {
  const { t, relativeTime } = useFormat()
  const [section, setSection] = useState("Account")
  const { theme, setTheme } = useTheme()
  const { logout, user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()

  // GDPR — Art. 15/20 export and Art. 17 erasure
  const [exporting, setExporting] = useState(false)
  const [deletePassword, setDeletePassword] = useState("")
  const [deleteConfirm, setDeleteConfirm] = useState("")
  const [deleting, setDeleting] = useState(false)

  // API access — the backend already answers 403 for Free, so the list is only
  // fetched when the plan actually allows it and the UI can sell the upgrade.
  const plan = usePlan()
  const { guard } = useUpgrade()
  const canUseApi = !plan.loading && Boolean(plan.limits?.can_use_api)
  const apiKeys = useApiList<ApiKey>(
    canUseApi ? endpoints.apiKeys.list : null,
  )
  const [keyName, setKeyName] = useState("")
  const [creatingKey, setCreatingKey] = useState(false)
  const [freshKey, setFreshKey] = useState<string | null>(null)
  const [revokingKey, setRevokingKey] = useState<string | null>(null)

  // Real delivery channels (the backend had CRUD but no UI).  A Free account
  // already owns its automatic e-mail channel, so adding a second one is the
  // quota boundary the upgrade modal explains.
  const alertChannels = useApiList<NotificationChannel>(
    endpoints.notifications.channels,
  )
  const [channelType, setChannelType] =
    useState<NotificationChannelType>("slack")
  const [channelName, setChannelName] = useState("")
  const [channelUrl, setChannelUrl] = useState("")
  const [savingChannel, setSavingChannel] = useState(false)
  const needsWebhook = channelType !== "email"

  const handleCreateChannel = async () => {
    if (!guard("alerts.channels")) return
    if (needsWebhook && !channelUrl.trim()) {
      showToast(t("settings.webhookRequired"), "error")
      return
    }
    setSavingChannel(true)
    try {
      await api.post(endpoints.notifications.channels, {
        channel_type: channelType,
        name:
          channelName.trim() ||
          channelType.charAt(0).toUpperCase() + channelType.slice(1),
        enabled: true,
        config: needsWebhook ? { webhook_url: channelUrl.trim() } : {},
      })
      setChannelName("")
      setChannelUrl("")
      alertChannels.refetch()
      plan.refresh()
      showToast(t("settings.toast.channelAdded"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setSavingChannel(false)
    }
  }

  const handleDeleteChannel = async (channel: NotificationChannel) => {
    if (!window.confirm(t("settings.toast.confirmDeleteChannel", { name: channel.name }))) return
    try {
      await api.delete(endpoints.notifications.channel(channel.id))
      alertChannels.refetch()
      plan.refresh()
      showToast(t("settings.toast.channelDeleted"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    }
  }

  const handleCreateKey = async () => {
    if (!guard("api.keys")) return
    setCreatingKey(true)
    try {
      const created = await api.post<ApiKey>(endpoints.apiKeys.list, {
        name: keyName.trim() || "Default key",
      })
      setFreshKey(created.api_key ?? null)
      setKeyName("")
      apiKeys.refetch()
      showToast(t("settings.toast.keyCreated"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setCreatingKey(false)
    }
  }

  const handleRevokeKey = async (key: ApiKey) => {
    if (
      !window.confirm(
        t("settings.toast.confirmRevokeKey", { name: key.name }),
      )
    ) {
      return
    }
    setRevokingKey(key.id)
    try {
      await api.delete(endpoints.apiKeys.revoke(key.id))
      apiKeys.refetch()
      showToast(t("settings.toast.keyRevoked"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setRevokingKey(null)
    }
  }

  const copyKey = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      showToast(t("settings.toast.keyCopied"), "success")
    } catch {
      showToast(t("settings.toast.keyCopyFailed"), "error")
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const data = await api.get<AccountExport>(endpoints.auth.exportData)
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `presence-export-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      showToast(t("settings.toast.exportDownloaded"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (deleteConfirm !== "DELETE") {
      showToast(t("settings.toast.typeDelete"), "error")
      return
    }
    if (!deletePassword) {
      showToast(t("settings.toast.passwordRequired"), "error")
      return
    }

    setDeleting(true)
    try {
      const result = await api.delete<AccountDeletionResult>(
        endpoints.auth.deleteAccount,
        { body: JSON.stringify({ password: deletePassword }) },
      )
      showToast(
        t("settings.toast.accountDeleted", { count: result.deleted.account ?? 0 }),
        "success",
      )
      setDeletePassword("")
      setDeleteConfirm("")
      await logout()
      navigate("/login", { replace: true })
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setDeleting(false)
    }
  }
  // Real alert preferences — these toggles were local state that vanished on
  // reload. They now persist through PATCH /alerts/preferences/.
  const prefs = useApiResource<AlertPreferences>(endpoints.alerts.preferences)
  const [savingPref, setSavingPref] = useState<string | null>(null)
  const [pushBusy, setPushBusy] = useState<"link" | "test" | null>(null)
  const [testingChannel, setTestingChannel] = useState<number | null>(null)

  const updatePref = async (
    field: keyof AlertPreferences,
    value: boolean | string,
  ) => {
    setSavingPref(field)
    try {
      await api.patch(endpoints.alerts.preferences, { [field]: value })
      prefs.refetch()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setSavingPref(null)
    }
  }

  /** Links the current browser to Web Push when a subscription exists. */
  const linkPush = async () => {
    setPushBusy("link")
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        showToast(t("settings.toast.pushUnsupported"), "error")
        return
      }
      const registration =
        (await navigator.serviceWorker.getRegistration()) ??
        (await navigator.serviceWorker.register("/sw.js"))

      const permission = await Notification.requestPermission()
      setPwa((previous) => ({ ...previous, push: permission }))
      if (permission !== "granted") {
        showToast(t("settings.toast.pushBlocked"), "error")
        return
      }

      const { public_key: publicKey } = await api.get<{ public_key: string }>(
        endpoints.notifications.pushPublicKey,
      )
      if (!publicKey) {
        showToast(
          t("settings.toast.pushNotConfigured"),
          "error",
        )
        return
      }

      let subscription = await registration.pushManager.getSubscription()
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        })
      }
      const json = subscription.toJSON()
      await api.post(endpoints.notifications.pushSubscribe, {
        endpoint: json.endpoint,
        keys: json.keys,
      })
      showToast(t("settings.toast.pushSubscribed"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setPushBusy(null)
    }
  }

  const sendTestPush = async () => {
    setPushBusy("test")
    try {
      const result = await api.post<{ message?: string }>(
        endpoints.notifications.pushTest,
        { scenario: "down" },
      )
      showToast(result.message ?? t("settings.toast.testPushSent"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setPushBusy(null)
    }
  }

  const testChannel = async (channel: NotificationChannel) => {
    setTestingChannel(channel.id)
    try {
      const result = await api.post<{ message?: string }>(
        endpoints.notifications.testChannel(channel.id),
      )
      showToast(
        result.message ?? t("settings.toast.testChannelSent", { name: channel.name }),
        "success",
      )
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setTestingChannel(null)
    }
  }
  // Real PWA state: the previous panel claimed "installed · last synchronized
  // today at 10:42" unconditionally. Both facts are now read from the browser.
  const [pwa, setPwa] = useState<{
    installed: boolean
    push: NotificationPermission | "unsupported"
  }>({ installed: false, push: "unsupported" })
  useEffect(() => {
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      (window.navigator as Navigator & { standalone?: boolean }).standalone ===
        true
    setPwa({
      installed: standalone,
      push: "Notification" in window ? Notification.permission : "unsupported",
    })
  }, [])
  // Profile preferences were previously hard-coded ("Schmidt's Bakery") or
  // kept in local state only. They now round-trip through the real API.
  const profile = useApiResource<UserProfile>(endpoints.profile)
  const [business, setBusiness] = useState({
    business_name: "",
    business_industry: "" as UserProfile["business_industry"],
    business_country: "" as UserProfile["business_country"],
    timezone: "Europe/Berlin" as UserProfile["timezone"],
  })
  const [language, setLanguage] = useState<UserProfile["language"]>("en")
  const [savingBusiness, setSavingBusiness] = useState(false)
  const [savingLanguage, setSavingLanguage] = useState(false)

  useEffect(() => {
    if (!profile.data) return
    setBusiness({
      business_name: profile.data.business_name,
      business_industry: profile.data.business_industry,
      business_country: profile.data.business_country,
      timezone: profile.data.timezone,
    })
    setLanguage(profile.data.language)
    document.documentElement.lang = profile.data.language
  }, [profile.data])

  const saveBusiness = async () => {
    setSavingBusiness(true)
    try {
      await api.patch(endpoints.profile, {
        business_name: business.business_name.trim(),
        business_industry: business.business_industry,
        business_country: business.business_country,
        timezone: business.timezone,
      })
      profile.refetch()
      showToast(t("settings.toast.businessSaved"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setSavingBusiness(false)
    }
  }

  const saveLanguage = async () => {
    setSavingLanguage(true)
    try {
      await api.patch(endpoints.profile, { language })
      document.documentElement.lang = language
      profile.refetch()
      showToast(t("settings.toast.languageSaved"), "success")
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setSavingLanguage(false)
    }
  }

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("settings.title")}
        </h1>
        <p className="text-slate-500 mt-1">{t("settings.subtitle")}</p>
      </div>

      <div className="grid lg:grid-cols-4 gap-6">
        {/* Sidebar nav */}
        <nav className="lg:col-span-1">
          <Card className="overflow-hidden">
            {sections.map((s) => (
              <button
                key={s}
                onClick={() => setSection(s)}
                className={`w-full text-left px-4 py-3 text-sm border-b border-slate-100 last:border-0 transition-colors ${
                  section === s
                    ? "bg-indigo-50 text-indigo-700 font-medium"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {t(SECTION_KEYS[s as SectionName])}
              </button>
            ))}
          </Card>
        </nav>

        {/* Content */}
        <div className="lg:col-span-3">
          {section === "Account" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-6">
                {t("settings.accountDetails")}
              </h2>
              {!user ? (
                <LoadingBlock label={t("settings.loadingAccount")} />
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-xl">
                    <div className="w-14 h-14 bg-indigo-100 rounded-full flex items-center justify-center text-xl font-bold text-indigo-600">
                      {(user.full_name || user.email).charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-semibold text-slate-900">
                        {user.full_name || "Name not set"}
                      </p>
                      <p className="text-sm text-slate-500">{user.email}</p>
                    </div>
                    <span
                      className={`ml-auto flex-shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                        user.is_email_verified
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}
                    >
                      {user.is_email_verified
                        ? "Email verified"
                        : "Email not verified"}
                    </span>
                  </div>
                  <div className="grid gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-sm font-medium text-slate-700">
                        {t("settings.account.fullName")}
                      </label>
                      <input
                        value={user.full_name || "—"}
                        readOnly
                        className="px-3 py-2 text-sm border border-slate-200 bg-slate-50 rounded-lg text-slate-600"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-sm font-medium text-slate-700">
                        {t("settings.account.email")}
                      </label>
                      <input
                        value={user.email}
                        readOnly
                        type="email"
                        className="px-3 py-2 text-sm border border-slate-200 bg-slate-50 rounded-lg text-slate-600"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-slate-400">
                    {t("settings.account.readOnly")}
                  </p>
                </div>
              )}
            </Card>
          )}

          {section === "Business" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-6">
                {t("settings.business.title")}
              </h2>
              {profile.loading ? (
                <LoadingBlock label={t("settings.account.loadingProfile")} />
              ) : profile.error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  {profile.error}{" "}
                  <button
                    type="button"
                    className="underline font-medium"
                    onClick={() => profile.refetch()}
                  >
                    {t("settings.retry")}
                  </button>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="business-name"
                      className="text-sm font-medium text-slate-700"
                    >
                      {t("settings.business.name")}
                    </label>
                    <input
                      id="business-name"
                      value={business.business_name}
                      onChange={(event) =>
                        setBusiness((current) => ({
                          ...current,
                          business_name: event.target.value,
                        }))
                      }
                      placeholder={t("settings.business.namePlaceholder")}
                      className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="business-industry"
                      className="text-sm font-medium text-slate-700"
                    >
                      {t("settings.business.industry")}
                    </label>
                    <select
                      id="business-industry"
                      value={business.business_industry}
                      onChange={(event) =>
                        setBusiness((current) => ({
                          ...current,
                          business_industry: event.target
                            .value as UserProfile["business_industry"],
                        }))
                      }
                      className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                    >
                      <option value="">{t("settings.business.notSet")}</option>
                      {INDUSTRIES.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="business-country"
                      className="text-sm font-medium text-slate-700"
                    >
                      {t("settings.business.country")}
                    </label>
                    <select
                      id="business-country"
                      value={business.business_country}
                      onChange={(event) =>
                        setBusiness((current) => ({
                          ...current,
                          business_country: event.target
                            .value as UserProfile["business_country"],
                        }))
                      }
                      className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                    >
                      <option value="">{t("settings.business.notSet")}</option>
                      {COUNTRIES.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="business-timezone"
                      className="text-sm font-medium text-slate-700"
                    >
                      {t("settings.business.timezone")}
                    </label>
                    <select
                      id="business-timezone"
                      value={business.timezone}
                      onChange={(event) =>
                        setBusiness((current) => ({
                          ...current,
                          timezone: event.target
                            .value as UserProfile["timezone"],
                        }))
                      }
                      className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                    >
                      {TIMEZONES.map((zone) => (
                        <option key={zone} value={zone}>
                          {zone}
                        </option>
                      ))}
                    </select>
                  </div>

                  <Button
                    className="self-start"
                    onClick={() => void saveBusiness()}
                    disabled={savingBusiness}
                  >
                    {savingBusiness ? t("settings.saving") : t("settings.business.save")}
                  </Button>
                </div>
              )}
            </Card>
          )}

          {section === "Notifications" && (
            <div className="flex flex-col gap-4">
              <Card className="p-6">
                <h2 className="font-bold text-slate-900 mb-4">{t("settings.notifications.alertTypes")}</h2>
                <div className="flex flex-col gap-4">
                  {(
                    [
                      {
                        key: "website_offline_enabled",
                        label: "Website unavailable",
                        desc: "Notify when your website goes offline",
                      },
                      {
                        key: "ssl_expiring_enabled",
                        label: "SSL certificate expiry",
                        desc: "Notify before the certificate expires",
                      },
                      {
                        key: "ssl_invalid_enabled",
                        label: "Invalid SSL certificate",
                        desc: "Notify when the certificate stops validating",
                      },
                      {
                        key: "dns_problem_enabled",
                        label: "DNS configuration problems",
                        desc: "Notify when DNS records break",
                      },
                      {
                        key: "email_security_enabled",
                        label: "Email security issues",
                        desc: "SPF, DKIM and DMARC problems",
                      },
                      {
                        key: "security_headers_enabled",
                        label: "Security headers",
                        desc: "Missing or weakened HTTP security headers",
                      },
                      {
                        key: "performance_enabled",
                        label: "Performance",
                        desc: "Slow response time or heavy pages",
                      },
                      {
                        key: "score_drop_enabled",
                        label: "Score drop",
                        desc: "Health score falls below its threshold",
                      },
                      {
                        key: "scan_failed_enabled",
                        label: "Scan failed",
                        desc: "A scheduled scan could not complete",
                      },
                    ] as const
                  ).map(({ key, label, desc }) => {
                    const checked = Boolean(
                      prefs.data?.[key as keyof AlertPreferences],
                    )
                    return (
                      <div
                        key={key}
                        className="flex items-center justify-between gap-4"
                      >
                        <div>
                          <p className="text-sm font-medium text-slate-800">
                            {label}
                          </p>
                          <p className="text-xs text-slate-500">{desc}</p>
                        </div>
                        <Toggle
                          checked={checked}
                          onChange={(v) =>
                            void updatePref(
                              key as keyof AlertPreferences,
                              v,
                            )
                          }
                        />
                      </div>
                    )
                  })}

                  <div className="flex items-center justify-between gap-4 pt-4 border-t border-slate-100">
                    <div>
                      <p className="text-sm font-medium text-slate-800">
                        {t("settings.notifications.digestFrequency")}
                      </p>
                      <p className="text-xs text-slate-500">
                        {t("settings.notifications.digestHint")}
                      </p>
                    </div>
                    <select
                      aria-label={t("settings.notifications.digestFrequency")}
                      value={prefs.data?.digest_frequency ?? "immediate"}
                      disabled={!prefs.data || savingPref === "digest_frequency"}
                      onChange={(event) =>
                        void updatePref("digest_frequency", event.target.value)
                      }
                      className="px-2 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                    >
                      <option value="immediate">{t("settings.notifications.digestImmediate")}</option>
                      <option value="hourly">{t("settings.notifications.digestHourly")}</option>
                      <option value="daily">{t("settings.notifications.digestDaily")}</option>
                    </select>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-bold text-slate-900 flex items-center gap-2">
                      {t("settings.notifications.channels")} <UpgradeBadge feature="alerts.channels" />
                    </h2>
                    <p className="text-sm text-slate-500 mt-1">
                      {t("settings.notifications.channelsHint")}
                      {plan.limits && plan.usage
                        ? ` ${plan.usage.alert_channels} of ${plan.limits.max_alert_channels} used.`
                        : ""}
                    </p>
                  </div>
                </div>

                {alertChannels.loading ? (
                  <LoadingBlock label={t("settings.notifications.loadingChannels")} />
                ) : (
                  <>
                    <ul className="mt-4 divide-y divide-slate-100">
                      {alertChannels.data.length === 0 && (
                        <li className="py-3 text-sm text-slate-500">
                          {t("settings.notifications.noChannel")}
                        </li>
                      )}
                      {alertChannels.data.map((channel) => (
                        <li
                          key={channel.id}
                          className="flex items-center gap-3 py-3"
                        >
                          <span className="flex-shrink-0 rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                            {channel.channel_type}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-800 truncate">
                              {channel.name}
                            </p>
                            <p className="text-xs text-slate-400 truncate">
                              {typeof channel.config.webhook_url === "string"
                                ? channel.config.webhook_url
                                : channel.channel_type === "email"
                                  ? "Account e-mail address"
                                  : "—"}
                            </p>
                          </div>
                          <span
                            className={`flex-shrink-0 text-xs ${
                              channel.enabled
                                ? "text-emerald-600"
                                : "text-slate-400"
                            }`}
                          >
                            {channel.enabled ? t("settings.notifications.enabled") : t("settings.notifications.disabled")}
                          </span>
                          <button
                            type="button"
                            onClick={() => void testChannel(channel)}
                            disabled={testingChannel === channel.id}
                            className="flex-shrink-0 rounded-lg border border-slate-300 px-2 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
                            aria-label={`Send a test notification via ${channel.name}`}
                          >
                            {testingChannel === channel.id
                              ? "Sending…"
                              : "Test"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleDeleteChannel(channel)}
                            className="flex-shrink-0 text-slate-400 transition-colors hover:text-red-600"
                            aria-label={`Delete ${channel.name}`}
                          >
                            <Trash2 size={15} />
                          </button>
                        </li>
                      ))}
                    </ul>

                    <div className="mt-5 grid sm:grid-cols-2 gap-3 sm:items-end">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-sm font-medium text-slate-700">
                          {t("settings.notifications.channelType")}
                        </label>
                        <select
                          value={channelType}
                          onChange={(event) =>
                            setChannelType(
                              event.target.value as NotificationChannelType,
                            )
                          }
                          className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        >
                          <option value="email">{t("settings.notifications.channelEmail")}</option>
                          <option value="slack">{t("settings.notifications.channelSlack")}</option>
                          <option value="discord">{t("settings.notifications.channelDiscord")}</option>
                          <option value="webhook">{t("settings.notifications.channelWebhook")}</option>
                        </select>
                      </div>
                      <Input
                        label={t("settings.notifications.channelName")}
                        placeholder={t("settings.notifications.channelNamePlaceholder")}
                        value={channelName}
                        onChange={setChannelName}
                      />
                      {needsWebhook && (
                        <div className="sm:col-span-2">
                          <Input
                            label={t("settings.notifications.channelUrl")}
                            placeholder={t("settings.notifications.channelUrlPlaceholder")}
                            value={channelUrl}
                            onChange={setChannelUrl}
                            helper="Incoming webhook used to deliver the alert."
                          />
                        </div>
                      )}
                      <div className="sm:col-span-2">
                        <Button
                          onClick={() => void handleCreateChannel()}
                          disabled={savingChannel}
                        >
                          <Plus size={14} />
                          {savingChannel ? t("settings.notifications.adding") : t("settings.notifications.add")}
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </Card>
            </div>
          )}

          {section === "Appearance" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-2">{t("settings.appearance.title")}</h2>
              <p className="text-sm text-slate-500 mb-6">
                {t("settings.appearance.hint")}
              </p>
              <div className="grid grid-cols-3 gap-3">
                {([
                  { value: "light", label: "Light", icon: Sun },
                  { value: "dark", label: "Dark", icon: Moon },
                ] as const).map(({ value, label, icon: Icon }) => (
                  <button
                    key={value}
                    onClick={() => setTheme(value)}
                    className={`flex flex-col items-center gap-2 p-4 rounded-xl border text-sm font-medium transition-all ${
                      theme === value
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    <Icon size={20} />
                    {label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-slate-400 mt-4">
                {t("settings.appearance.saved")}
              </p>
            </Card>
          )}

          {section === "PWA" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-2">
                {t("settings.pwa.title")}
              </h2>
              <p className="text-sm text-slate-500 mb-6">
                {t("settings.pwa.hint")}
              </p>

              <div
                className={`p-4 rounded-xl flex items-center gap-3 mb-6 border ${
                  pwa.installed
                    ? "bg-emerald-50 border-emerald-200"
                    : "bg-slate-50 border-slate-200"
                }`}
              >
                <span className="text-xl">{pwa.installed ? "✅" : "📱"}</span>
                <div>
                  <p
                    className={`text-sm font-semibold ${
                      pwa.installed ? "text-emerald-800" : "text-slate-800"
                    }`}
                  >
                    {pwa.installed
                      ? "Running as an installed app"
                      : "Running in the browser"}
                  </p>
                  <p
                    className={`text-xs ${
                      pwa.installed ? "text-emerald-600" : "text-slate-500"
                    }`}
                  >
                    {pwa.installed
                      ? "This window was launched from the installed app."
                      : "Use your browser's Install / Add to home screen action to install Presence."}
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      {t("settings.pwa.webPush")}
                    </p>
                    <p className="text-xs text-slate-500">
                      {t("settings.pwa.webPushHint")}
                    </p>
                    <p className="text-xs text-slate-400">
                      {t("settings.pwa.permission")}{" "}
                      <span className="font-medium text-slate-600">
                        {pwa.push === "unsupported"
                          ? "not supported by this browser"
                          : pwa.push}
                      </span>
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={pushBusy !== null}
                      onClick={() => void linkPush()}
                    >
                      {pushBusy === "link" ? t("settings.pwa.linking") : t("settings.pwa.enable")}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={pushBusy !== null}
                      onClick={() => void sendTestPush()}
                    >
                      {pushBusy === "test" ? t("settings.pwa.sending") : t("settings.pwa.sendTest")}
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {section === "Language" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-6">
                {t("settings.languageRegion.title")}
              </h2>
              {profile.loading ? (
                <LoadingBlock label={t("settings.languageRegion.loading")} />
              ) : profile.error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  {profile.error}{" "}
                  <button
                    type="button"
                    className="underline font-medium"
                    onClick={() => profile.refetch()}
                  >
                    {t("settings.retry")}
                  </button>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700 mb-2">
                      {t("settings.languageRegion.preferred")}
                    </p>
                    <div className="grid grid-cols-3 gap-2">
                      {LANGUAGES.map((item) => (
                        <button
                          key={item.code}
                          type="button"
                          onClick={() => setLanguage(item.code)}
                          aria-pressed={language === item.code}
                          className={`py-2.5 px-4 rounded-xl border text-sm font-medium transition-all ${
                            language === item.code
                              ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                              : "border-slate-200 text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-slate-400 mt-2">
                      {t("settings.languageRegion.hint")}
                    </p>
                  </div>
                  <Button
                    className="self-start"
                    onClick={() => void saveLanguage()}
                    disabled={savingLanguage}
                  >
                    {savingLanguage ? t("settings.saving") : t("settings.languageRegion.save")}
                  </Button>
                </div>
              )}
            </Card>
          )}

          {section === "API access" && (
            <Card className="p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-bold text-slate-900 flex items-center gap-2">
                    {t("settings.sectionApi")} <UpgradeBadge feature="api.keys" />
                  </h2>
                  <p className="text-sm text-slate-500 mt-1">
                    {t("settings.api.hint")}
                  </p>
                </div>
                <span
                  className={`flex-shrink-0 rounded-full px-3 py-1 text-xs font-bold ${
                    canUseApi
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-50 text-amber-700 border border-amber-200"
                  }`}
                >
                  {canUseApi ? t("settings.api.included") : t("settings.api.pro")}
                </span>
              </div>

              {plan.loading ? (
                <LoadingBlock label={t("settings.api.checkingPlan")} />
              ) : !canUseApi ? (
                <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
                  <p className="text-sm font-semibold text-amber-900">
                    {t("settings.api.proOnly")}
                  </p>
                  <p className="text-xs text-amber-700 mt-1">
                    {t("settings.api.upsell")}
                  </p>
                  <Button
                    className="mt-3"
                    size="sm"
                    onClick={() => guard("api.keys")}
                  >
                    {t("settings.api.unlock")}
                  </Button>
                </div>
              ) : (
                <>
                  <div className="mt-6 flex flex-col sm:flex-row sm:items-end gap-2">
                    <div className="flex-1">
                      <Input
                        label={t("settings.api.keyName")}
                        placeholder={t("settings.api.keyNamePlaceholder")}
                        value={keyName}
                        onChange={setKeyName}
                        helper="A label to recognise the integration later."
                      />
                    </div>
                    <Button
                      onClick={() => void handleCreateKey()}
                      disabled={creatingKey}
                    >
                      <Plus size={14} />
                      {creatingKey ? t("settings.api.creating") : t("settings.api.create")}
                    </Button>
                  </div>

                  {freshKey && (
                    <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
                        {t("settings.api.copyNow")}
                      </p>
                      <div className="mt-2 flex items-center gap-2">
                        <code className="flex-1 min-w-0 break-all rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs text-slate-700">
                          {freshKey}
                        </code>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => void copyKey(freshKey)}
                        >
                          <Copy size={13} /> {t("settings.api.copy")}
                        </Button>
                      </div>
                      <p className="mt-2 text-xs text-emerald-700">
                        {t("settings.keyShownOnce")}
                      </p>
                    </div>
                  )}

                  <div className="mt-6">
                    <h3 className="text-sm font-semibold text-slate-900 mb-1">
                      {t("settings.yourKeys")}
                    </h3>
                    {apiKeys.loading ? (
                      <LoadingBlock label={t("settings.loadingKeys")} />
                    ) : apiKeys.error ? (
                      <p className="text-sm text-red-600" role="alert">
                        {apiKeys.error}
                      </p>
                    ) : apiKeys.data.length === 0 ? (
                      <p className="text-sm text-slate-500">
                        {t("settings.noKey")}
                      </p>
                    ) : (
                      <ul className="divide-y divide-slate-100">
                        {apiKeys.data.map((key) => (
                          <li
                            key={key.id}
                            className="flex items-center gap-3 py-3"
                          >
                            <KeyRound
                              size={15}
                              className="flex-shrink-0 text-slate-400"
                              aria-hidden="true"
                            />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-slate-800 truncate">
                                {key.name}
                              </p>
                              <p className="text-xs text-slate-400 font-mono truncate">
                                {t("settings.keyMeta", {
                                  prefix: key.prefix,
                                  created: relativeTime(key.created_at),
                                  used: key.last_used_at
                                    ? relativeTime(key.last_used_at)
                                    : t("time.never"),
                                })}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => void handleRevokeKey(key)}
                              disabled={revokingKey === key.id}
                              className="flex-shrink-0 text-slate-400 transition-colors hover:text-red-600 disabled:opacity-40"
                              aria-label={t("settings.revokeKey", {
                                name: key.name,
                              })}
                            >
                              <Trash2 size={15} />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </>
              )}
            </Card>
          )}

          {section === "Integrations" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-2">{t("settings.sectionIntegrations")}</h2>
              <p className="text-sm text-slate-500">
                {t("settings.integrations.hint")}
              </p>
              <Button
                className="mt-4"
                onClick={() => navigate("/app/settings/integrations")}
              >
                {t("settings.integrations.manage")}
              </Button>
            </Card>
          )}

          {section === "Subscription" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-2">
                {t("settings.subscription.current")}
              </h2>
              <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl mb-6 flex items-center justify-between">
                <div>
                  <p className="font-semibold text-indigo-900">{t("settings.subscription.planPro")}</p>
                  <p className="text-sm text-indigo-600">
                    {t("settings.subscription.planProDetails")}
                  </p>
                </div>
                <span className="px-3 py-1 bg-indigo-600 text-white text-xs font-bold rounded-full">
                  {t("settings.subscription.active")}
                </span>
              </div>
              <div className="space-y-2 mb-6">
                <p className="text-sm font-medium text-slate-700">
                  {t("settings.subscription.included")}
                </p>
                {[
                  "10 websites",
                  "Automatic hourly monitoring",
                  "Email & push alerts",
                  "PDF reports",
                  "Score history",
                  "Advanced checks",
                ].map((f) => (
                  <div
                    key={f}
                    className="flex items-center gap-2 text-sm text-slate-600"
                  >
                    <span className="text-emerald-500">✓</span> {f}
                  </div>
                ))}
              </div>
              <div className="flex gap-3 flex-wrap">
                <Button variant="outline" size="sm">
                  {t("settings.subscription.upgradeBusiness")}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  {t("settings.subscription.cancel")}
                </Button>
              </div>
            </Card>
          )}

          {section === "Privacy & data" && (
            <div className="flex flex-col gap-4">
              <Card className="p-6">
                <h2 className="font-bold text-slate-900 mb-1">
                  {t("settings.privacy.exportTitle")}
                </h2>
                <p className="text-sm text-slate-500 mb-5">
                  {t("settings.privacy.exportHint")}
                </p>
                <Button variant="outline" onClick={handleExport} disabled={exporting}>
                  {exporting ? t("settings.privacy.exportPreparing") : t("settings.privacy.exportDownload")}
                </Button>
              </Card>

              <Card className="p-6 border-red-200">
                <h2 className="font-bold text-red-700 mb-1">
                  {t("settings.privacy.deleteTitle")}
                </h2>
                <p className="text-sm text-slate-500 mb-5">
                  {t("settings.privacy.deleteHint")}
                </p>
                <div className="grid sm:grid-cols-2 gap-4 mb-5">
                  <Input
                    label={t("settings.privacy.confirmPassword")}
                    type="password"
                    placeholder="••••••••"
                    value={deletePassword}
                    onChange={setDeletePassword}
                  />
                  <Input
                    label={t("settings.privacy.typeDelete")}
                    placeholder="DELETE"
                    value={deleteConfirm}
                    onChange={setDeleteConfirm}
                  />
                </div>
                <Button
                  variant="danger"
                  onClick={handleDeleteAccount}
                  disabled={
                    deleting || deleteConfirm !== "DELETE" || !deletePassword
                  }
                >
                  {deleting ? t("settings.privacy.deleting") : t("settings.privacy.deleteButton")}
                </Button>
              </Card>
            </div>
          )}

          {![
            "Account",
            "Business",
            "Notifications",
            "Appearance",
            "PWA",
            "Language",
            "Subscription",
            "Privacy & data",
          ].includes(section) && (
            <Card className="p-12 text-center">
              <p className="text-4xl mb-3">🔧</p>
              <p className="font-semibold text-slate-900 mb-1">
                {t("settings.sectionUnavailableTitle", { section })}
              </p>
              <p className="text-sm text-slate-500">
                {t("settings.sectionUnavailableHint")}
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
