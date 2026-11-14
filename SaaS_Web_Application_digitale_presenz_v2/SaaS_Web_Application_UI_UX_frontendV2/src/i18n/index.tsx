/**
 * Minimal, dependency-free i18n layer for the public and in-app surfaces.
 *
 * Design choices:
 *  - German (`de`) is the default locale for the initial German launch; the
 *    browser language only *suggests* a locale and the visitor can always
 *    switch, which is what § 8.2 of the launch checklist requires.
 *  - The catalogues are plain JSON so the same files can be checked by a
 *    script (`scripts/check-i18n.mjs`) and translated by non-developers.
 *  - `t()` only accepts keys that exist in `en.json`; the German file is typed
 *    against the English shape, so a missing or misspelled key is a build
 *    error rather than a raw `billing.checkout.error` shown to a user.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import de from "./de.json"
import en from "./en.json"
import fr from "./fr.json"

export type Locale = "de" | "en" | "fr"

export const DEFAULT_LOCALE: Locale = "de"
export const LOCALES: readonly Locale[] = ["de", "en", "fr"] as const

/**
 * BCP-47 tags for `Intl`.
 *
 * Dates, times, numbers and currency must follow the active interface
 * language, not the browser default: a German UI showing `10/27/2026` reads
 * like a US site and `€1,234.50` as `1.234,50 €` is what German users expect.
 */
export const LOCALE_TAGS: Record<Locale, string> = {
  de: "de-DE",
  en: "en-GB",
  fr: "fr-FR",
}

/** Locale of the reference catalogue: every other catalogue mirrors its shape. */
export type Catalog = typeof en

/** Typed against the English shape: a missing German key fails `tsc`. */
const deCatalog: Catalog = de
const frCatalog: Catalog = fr
export const catalogs: Record<Locale, Catalog> = {
  de: deCatalog,
  en,
  fr: frCatalog,
}

const STORAGE_KEY = "presence-locale"

/* ── Key typing ──────────────────────────────────────────────────────────── */

type Join<P extends string, K extends string> = P extends "" ? K : `${P}.${K}`

export type MessageKey = {
  [K in keyof Catalog & string]: Catalog[K] extends string
    ? K
    : Catalog[K] extends readonly string[]
      ? never
      : FlattenStrings<Catalog[K], K>
}[keyof Catalog & string]

export type ListKey = {
  [K in keyof Catalog & string]: Catalog[K] extends readonly string[]
    ? K
    : Catalog[K] extends string
      ? never
      : FlattenLists<Catalog[K], K>
}[keyof Catalog & string]

type FlattenStrings<T, P extends string> = {
  [K in keyof T & string]: T[K] extends string
    ? Join<P, K>
    : T[K] extends readonly string[]
      ? never
      : FlattenStrings<T[K], Join<P, K>>
}[keyof T & string]

type FlattenLists<T, P extends string> = {
  [K in keyof T & string]: T[K] extends readonly string[]
    ? Join<P, K>
    : T[K] extends string
      ? never
      : FlattenLists<T[K], Join<P, K>>
}[keyof T & string]

/* ── Runtime lookup ──────────────────────────────────────────────────────── */

function lookup(catalog: Catalog, key: string): unknown {
  return key.split(".").reduce<unknown>((node, part) => {
    if (typeof node !== "object" || node === null) return undefined
    return (node as Record<string, unknown>)[part]
  }, catalog)
}

function interpolate(template: string, vars?: Record<string, string | number>) {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  )
}

/** Never show a raw key to a user; log it in development instead. */
function reportMissing(locale: Locale, key: string) {
  if (import.meta.env.DEV) {
    console.warn(`[i18n] missing ${locale} message for "${key}"`)
  }
}

/* ── Locale resolution ───────────────────────────────────────────────────── */

export function isLocale(value: unknown): value is Locale {
  return value === "de" || value === "en" || value === "fr"
}

/**
 * Legacy query parameter that selects a variant (`?lang=en`).
 *
 * The English site now lives under `/en` (see `EN_PREFIX`); the parameter stays
 * supported because it is the URL every older link, bookmark, hreflang entry
 * and search result may still carry. Both forms serve the same English page and
 * canonicalise to the `/en` URL.
 */
export const VARIANT_PARAM = "lang"

/**
 * URL prefix of the dedicated English site.
 *
 * German is the default locale and keeps the bare paths (`/pricing`), so every
 * existing deep link, canonical and bookmark is untouched. English gets an
 * explicit, indexable path (`/en/pricing`) instead of a query parameter that
 * crawlers have to trust.
 */
export const EN_PREFIX = "/en"
/** Prefix of the dedicated French site, mirroring FR_PREFIX in prerender.mjs. */
export const FR_PREFIX = "/fr"

/** Locale carried by a localized path, or `null` on the bare German paths. */
export function localeFromPath(pathname: string): Locale | null {
  if (pathname === EN_PREFIX || pathname.startsWith(`${EN_PREFIX}/`)) {
    return "en"
  }
  if (pathname === FR_PREFIX || pathname.startsWith(`${FR_PREFIX}/`)) {
    return "fr"
  }
  return null
}

/**
 * URL of one page in one language.
 *
 * The default locale owns the bare path, the English site is mounted under
 * `/en`. Every canonical, hreflang and sitemap entry derives from this single
 * function so the three can never disagree.
 */
export function localizedPath(path: string, locale: Locale): string {
  if (locale === DEFAULT_LOCALE) return path
  const prefix = locale === "en" ? EN_PREFIX : FR_PREFIX
  return path === "/" ? prefix : `${prefix}${path}`
}

function readStoredLocale(): Locale | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isLocale(stored) ? stored : null
  } catch {
    return null
  }
}

/**
 * Locale explicitly chosen by the visitor on this device.
 *
 * `detectLocale` uses it as a fallback, while `RouteLocaleSync` needs the raw
 * value to decide whether a bare public URL should be upgraded to its
 * localized canonical URL after hydration.
 */
export function getStoredLocale(): Locale | null {
  if (typeof window === "undefined") return null
  return readStoredLocale()
}

/**
 * Locale carried by `?lang=`, which is the URL form of the English variant
 * (`?lang=en`) advertised by the hreflang alternates and served by nginx as a
 * distinct pre-rendered file. Without this the English URL would show the
 * visitor's stored/browser language instead of the advertised one. The
 * parameter wins over the stored preference — otherwise the alternate would be
 * dead for every returning visitor — and the provider persists it, so
 * following a shared link changes the language once and keeps it.
 */
export function localeFromSearch(search: string): Locale | null {
  try {
    const value = new URLSearchParams(search).get(VARIANT_PARAM)
    return isLocale(value) ? value : null
  } catch {
    return null
  }
}

/**
 * Language of the requested URL. The path wins over the legacy parameter: a
 * `/en/...` page must never render German because an old link also carries
 * `?lang=de`, and vice versa. Outside `/en` the parameter still applies, so
 * `?lang=en` keeps working exactly as before.
 */
function readUrlLocale(): Locale | null {
  if (typeof window === "undefined") return null
  return (
    localeFromPath(window.location.pathname) ??
    localeFromSearch(window.location.search)
  )
}

/** Browser language suggests a locale; anything non-German falls back to `de`. */
function detectLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE

  const fromUrl = readUrlLocale()
  if (fromUrl) return fromUrl

  const stored = readStoredLocale()
  if (stored) return stored

  const candidates = [
    ...(typeof navigator === "undefined" ? [] : (navigator.languages ?? [])),
    typeof navigator === "undefined" ? "" : (navigator.language ?? ""),
  ].map((value) => value.toLowerCase())

  for (const value of candidates) {
    if (value.startsWith("fr")) return "fr"
    if (value.startsWith("en")) return "en"
  }
  return DEFAULT_LOCALE
}

export function applyDocumentLanguage(locale: Locale) {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("lang", locale)
  }
}

/* ── Context ─────────────────────────────────────────────────────────────── */

interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: MessageKey, vars?: Record<string, string | number>) => string
  tList: (key: ListKey) => string[]
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({
  children,
  /**
   * Locale of the pre-rendered document. The static HTML for a URL has one
   * language, so hydration must start in that language: a stored preference
   * or a browser language may not produce a different tree than the one the
   * server wrote. Outside SSG pages the prop is omitted and detection runs as
   * before.
   */
  initialLocale,
}: {
  children: React.ReactNode
  initialLocale?: Locale
}) {
  const [locale, setLocaleState] = useState<Locale>(
    () => initialLocale ?? detectLocale(),
  )
  const mounted = useRef(false)

  useEffect(() => {
    applyDocumentLanguage(locale)

    // A pre-rendered German page hydrates with `initialLocale="de"` even when
    // the visitor previously chose French. Do not overwrite that preference
    // before RouteLocaleSync has had a chance to redirect the bare URL to
    // `/fr/...`; after the first effect, every switch is persisted normally.
    if (!mounted.current) {
      mounted.current = true
      const stored = readStoredLocale()
      if (initialLocale && stored && stored !== initialLocale) return
    }

    try {
      window.localStorage.setItem(STORAGE_KEY, locale)
    } catch {
      // Storage can be blocked; the in-memory locale still applies.
    }
  }, [initialLocale, locale])

  const setLocale = useCallback((next: Locale) => {
    if (!isLocale(next)) return
    setLocaleState(next)
  }, [])

  const value = useMemo<I18nContextValue>(() => {
    const catalog = catalogs[locale]

    const t: I18nContextValue["t"] = (key, vars) => {
      const value = lookup(catalog, key)
      if (typeof value === "string") return interpolate(value, vars)
      // Fall back to English rather than showing a key.
      const fallback = lookup(en, key)
      if (typeof fallback === "string") return interpolate(fallback, vars)
      reportMissing(locale, key)
      return key
    }

    const tList: I18nContextValue["tList"] = (key) => {
      const value = lookup(catalog, key)
      if (Array.isArray(value)) return value.map(String)
      const fallback = lookup(en, key)
      if (Array.isArray(fallback)) return fallback.map(String)
      reportMissing(locale, key)
      return []
    }

    return { locale, setLocale, t, tList }
  }, [locale, setLocale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error("useI18n must be used inside <I18nProvider>")
  }
  return context
}

export function useT() {
  return useI18n().t
}

/* ── SEO helpers ─────────────────────────────────────────────────────────── */

/**
 * Canonical URL of one page.
 *
 * The default locale owns the bare path and the English site its `/en` URL, so
 * every page has exactly one canonical address and the sitemap lists each of
 * them once. `?lang=de` is an alias of the bare path and `?lang=en` an alias of
 * the `/en` URL: neither gets a canonical of its own, otherwise the same English
 * page would be indexable under two addresses.
 *
 * The canonical comes from the *requested* URL, never from the active interface
 * language: switching the language in the app leaves the address bar untouched,
 * and the canonical must keep describing the URL that was requested.
 */
export function canonicalPath(path: string, urlLocale: Locale | null): string {
  return localizedPath(path, urlLocale ?? DEFAULT_LOCALE)
}

/**
 * hreflang alternates for one path.
 *
 * One URL per language: the bare path for German (also `x-default`, the
 * sensible entry point for a language the site does not offer) and `/en...`
 * for English. Each advertised URL must serve the language it declares without
 * JavaScript; `scripts/prerender.mjs` writes a complete page per URL and the
 * hydrated head renders exactly this set, so the static and the client-rendered
 * document describe the same URLs.
 */
export function alternateLinks(
  path: string,
): { hreflang: string; href: string }[] {
  const base =
    (import.meta.env.VITE_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
    (typeof window !== "undefined" ? window.location.origin : "")

  return [
    // Adding a locale to LOCALES is enough: the default keeps the bare path
    // and every other locale is mounted under its prefix.
    ...LOCALES.map((locale) => ({
      hreflang: locale as string,
      href: `${base}${localizedPath(path, locale)}`,
    })),
    { hreflang: "x-default", href: `${base}${path}` },
  ]
}

