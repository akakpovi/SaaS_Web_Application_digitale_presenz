import Link from "../components/LocaleLink"
import { ArrowLeft, Cookie } from "lucide-react"
import SEO from "../components/SEO"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n } from "../i18n"

/**
 * Storage transparency page.
 *
 * Presence sets no advertising or analytics cookie in the browser: the only
 * client-side storage is the authentication token (localStorage, see
 * src/api/authStorage.ts) plus the theme and language preference. That is why
 * there is no consent banner — a banner is only required for non-essential
 * cookies, and this page documents exactly what is stored instead of claiming
 * a consent screen that does not exist.
 */
export default function CookiesPage() {
  const { t } = useI18n()

  // Exact keys written by the app (see src/api/authStorage.ts, src/i18n and
  // src/components/AppShell.tsx): a transparency page that lists keys the app
  // never writes is worse than no page at all.
  const stored: { key: string; purpose: string; retention: string }[] = [
    {
      key: "presence_access",
      purpose: "Signed-in session — short-lived access token",
      retention: "Until you sign out, or the token expires",
    },
    {
      key: "presence_refresh",
      purpose: "Signed-in session — refresh token",
      retention: "Until you sign out, or the session expires",
    },
    {
      key: "presence-locale",
      purpose: "Remembers your language choice (DE/EN)",
      retention: "Until you clear your browser storage",
    },
    {
      key: "presence-theme",
      purpose: "Remembers light or dark mode",
      retention: "Until you clear your browser storage",
    },
    {
      key: "presence:debug-api",
      purpose: "Only set manually by a developer to trace API calls",
      retention: "Until you clear your browser storage",
    },
  ]

  return (
    <div className="min-h-screen bg-white">
      <SEO
        title={`${t("legal.cookiesTitle")} | Presence`}
        description={t("legal.cookiesBody")}
        path="/cookies"
      />

      <header className="border-b border-slate-200">
        <div className="max-w-3xl mx-auto px-4 h-16 flex items-center gap-4">
          <Link
            to="/"
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800"
          >
            <ArrowLeft size={14} /> Presence
          </Link>
          <div className="ml-auto">
            <LanguageSwitcher />
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12">
        <h1 className="text-3xl font-bold text-slate-900 mb-3 flex items-center gap-3">
          <Cookie size={24} className="text-indigo-600" />
          {t("legal.cookiesTitle")}
        </h1>
        <p className="text-slate-600 leading-relaxed mb-8">
          {t("legal.cookiesBody")}
        </p>

        <div className="border border-slate-200 rounded-xl overflow-hidden mb-8">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">
                  {t("legal.cookieKey")}
                </th>
                <th className="px-4 py-2 font-medium">
                  {t("legal.cookiePurpose")}
                </th>
                <th className="px-4 py-2 font-medium">
                  {t("legal.cookieRetention")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {stored.map((entry) => (
                <tr key={entry.key}>
                  <td className="px-4 py-3 font-mono text-xs text-slate-700">
                    {entry.key}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{entry.purpose}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {entry.retention}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="text-sm text-slate-500">
          {t("legal.withdrawalNotice")}
        </p>
      </main>
    </div>
  )
}
