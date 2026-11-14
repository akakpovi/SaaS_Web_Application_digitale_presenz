import { useLocation, useNavigate } from "react-router-dom"
import {
  localizedPath,
  useI18n,
  type Locale,
} from "../i18n"
import { isPublicRoutePath } from "../seo/publicPaths"
import { useAuth } from "../api/hooks/useAuth"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import type { User } from "../api/types"

/**
 * Visible DE/EN/FR switcher.
 *
 * The choice is stored on the device and, for a signed-in visitor, mirrored to
 * `/users/profile/` so transactional email and the in-app default follow the
 * same preference. A failed profile write never blocks the UI: the local
 * choice already applies.
 */
export default function LanguageSwitcher({
  tone = "light",
  className = "",
}: {
  tone?: "light" | "dark"
  className?: string
}) {
  const { locale, setLocale, t } = useI18n()
  const { user } = useAuth()
  const navigate = useNavigate()
  const { pathname, search, hash } = useLocation()

  /** Remove `/fr` or `/en` so the next locale can be applied to the same page. */
  const barePath = (value: string): string => {
    if (value === "/fr" || value.startsWith("/fr/")) {
      return value.slice(3) || "/"
    }
    if (value === "/en" || value.startsWith("/en/")) {
      return value.slice(3) || "/"
    }
    return value
  }

  const select = async (next: Locale) => {
    const base = barePath(pathname)
    const params = new URLSearchParams(search)
    // `lang` is a legacy alias, not part of the canonical localized URL.
    params.delete("lang")
    const query = params.toString()
    const localized = localizedPath(base, next)
    // Public pages use directory URLs (`/fr/pricing/`); private app routes
    // keep their extension-less path (`/fr/app/dashboard`).
    const targetPath =
      isPublicRoutePath(base) && localized !== "/"
        ? `${localized.replace(/\/+$/, "")}/`
        : localized
    const target = `${targetPath}${query ? `?${query}` : ""}${hash}`
    const current = `${pathname}${search}${hash}`

    setLocale(next)
    if (target !== current) navigate(target, { replace: true })

    if (!user) return
    try {
      await api.patch<User>(endpoints.profile, { language: next })
    } catch {
      // Preference stays local; the next successful save will retry.
    }
  }

  const options: { value: Locale; label: string }[] = [
    { value: "de", label: "DE" },
    { value: "en", label: "EN" },
    { value: "fr", label: "FR" },
  ]

  const base =
    tone === "dark"
      ? "border-white/15 text-slate-300"
      : "border-slate-200 text-slate-600"

  return (
    <div
      className={`flex items-center rounded-lg border overflow-hidden ${base} ${className}`}
      role="group"
      aria-label={t("nav.languageLabel")}
    >
      {options.map(({ value, label }) => {
        const active = value === locale
        return (
          <button
            key={value}
            type="button"
            onClick={() => void select(value)}
            aria-pressed={active}
            aria-label={
              value === "de"
                ? t("nav.german")
                : value === "en"
                  ? t("nav.english")
                  : t("nav.french")
            }
            className={`px-2.5 py-1 text-xs font-semibold transition-colors ${
              active
                ? tone === "dark"
                  ? "bg-white text-slate-900"
                  : "bg-indigo-600 text-white"
                : tone === "dark"
                  ? "hover:bg-white/10"
                  : "hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
