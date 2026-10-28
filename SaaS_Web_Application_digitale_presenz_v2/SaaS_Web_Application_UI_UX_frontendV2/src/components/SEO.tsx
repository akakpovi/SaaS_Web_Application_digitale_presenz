import { useEffect, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useLocation } from "react-router-dom"
import {
  alternateLinks,
  canonicalPath,
  localeFromPath,
  localeFromSearch,
  useI18n,
} from "../i18n"
import type { Locale } from "../i18n"
import { dropPreRenderedDuplicates } from "../lib/prerenderedHead"

// Set VITE_BASE_URL in your .env to your production domain (e.g. https://yourdomain.com).
// When unset, fall back to the browser origin so canonical/OG URLs stay
// absolute instead of emitting invalid relative canonicals.
const CONFIGURED_BASE_URL = (
  import.meta.env.VITE_BASE_URL as string | undefined
)?.replace(/\/$/, "")
const BASE_URL =
  CONFIGURED_BASE_URL ||
  (typeof window !== "undefined" ? window.location.origin : "")
const SITE_NAME = "Presence"
const DEFAULT_OG_IMAGE = `${BASE_URL}/og-image.png`

interface SEOProps {
  title: string
  description: string
  path?: string
  noIndex?: boolean
  ogType?: "website" | "article"
  ogImage?: string
  /** Overrides the active UI locale for `<html lang>`; rarely needed. */
  lang?: "en" | "fr" | "de"
  /**
   * Replaces the `?lang=` alternates. Needed whenever the translations of a
   * page live on *different* paths (bilingual CMS articles), where pointing
   * hreflang at the same slug with a parameter would declare a wrong URL.
   */
  alternates?: { lang: string; path: string }[]
  /**
   * `false` for a page that exists in one language only under this URL — a CMS
   * article, whose translation lives on its own slug. Such a page keeps the
   * language of its content, never advertises a `?lang=` variant of itself and
   * always canonicalises to its own path.
   */
  bilingual?: boolean
  structuredData?: Record<string, unknown> | Record<string, unknown>[]
}

export default function SEO({
  title,
  description,
  path = "/",
  noIndex = false,
  ogType = "website",
  ogImage = DEFAULT_OG_IMAGE,
  lang,
  alternates: alternateOverrides,
  bilingual = true,
  structuredData,
}: SEOProps) {
  const { locale } = useI18n()
  const { pathname, search } = useLocation()
  // The static HTML is written by `scripts/prerender.mjs`; rendering the
  // Helmet tags during SSG would put React 19's native `<title>`/`<meta>`
  // elements inside `<div id="root">` (React only hoists them for a full
  // document). Rendering them after hydration keeps the first client tree
  // identical to the server tree, then replaces the pre-rendered head in one
  // step through `dropPreRenderedDuplicates()`.
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])
  const htmlLang = lang ?? locale
  // One URL per language: the default locale keeps the bare path and English
  // lives under `/en`. The legacy `?lang=en` parameter still names the same
  // English page, so it resolves to the same canonical. `bilingual={false}`
  // pages (translated CMS articles) have one URL and one language, so they own
  // their path and never advertise a variant of it.
  const urlLocale: Locale | null = bilingual
    ? (localeFromPath(pathname) ?? localeFromSearch(search))
    : null
  // The variant this URL denotes. A page that is not bilingual publishes the
  // single language it is written in, whatever the visitor's preference is.
  const variant: Locale = bilingual
    ? (urlLocale ?? "de")
    : htmlLang === "de"
      ? "de"
      : "en"
  const alternates = alternateOverrides
    ? alternateOverrides.map(({ lang: code, path: alternatePath }) => ({
        hreflang: code,
        href: BASE_URL ? `${BASE_URL}${alternatePath}` : alternatePath,
      }))
    : bilingual
      ? alternateLinks(path)
      : []
  const canonicalUrl = BASE_URL
    ? `${BASE_URL}${canonicalPath(path, urlLocale)}`
    : canonicalPath(path, urlLocale)
  const fullTitle = title.includes(SITE_NAME)
    ? title
    : `${title} | ${SITE_NAME}`

  const schemas = structuredData
    ? Array.isArray(structuredData)
      ? structuredData
      : [structuredData]
    : []

  // The page arrived pre-rendered with a head of its own (same tags, for
  // clients without JavaScript). React only *adds* the tags rendered here, so
  // this component — the one that owns them — drops the pre-rendered copies it
  // replaced. In an effect, so the tags rendered above are already in <head>;
  // without a dependency array, because the props change when the data loads.
  useEffect(() => {
    dropPreRenderedDuplicates()
  })

  if (!mounted) return null

  return (
    <Helmet>
      <html lang={htmlLang} />
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <meta
        name="robots"
        content={noIndex ? "noindex,nofollow" : "index,follow"}
      />
      {/* A noindex page publishes neither a canonical nor alternates; the
          pre-rendered file for such a route omits them too. */}
      {!noIndex && canonicalUrl && (
        <link rel="canonical" href={canonicalUrl} />
      )}
      {!noIndex &&
        alternates.map(({ hreflang, href }) => (
          <link key={hreflang} rel="alternate" hrefLang={hreflang} href={href} />
        ))}
      {/* `og:locale` describes the variant this URL denotes (not the language
          the visitor picked in the switcher), and `en_GB` mirrors
          `LOCALE_TAGS` — exactly like the pre-rendered shell, so the static
          and the hydrated head agree. On `/en/...` the path is what denotes
          the variant; on a legacy `?lang=en` URL it is the parameter. */}
      <meta property="og:locale" content={variant === "de" ? "de_DE" : "en_GB"} />
      {bilingual && (
        <meta
          property="og:locale:alternate"
          content={variant === "de" ? "en_GB" : "de_DE"}
        />
      )}

      {/* Open Graph */}
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:type" content={ogType} />
      {canonicalUrl && <meta property="og:url" content={canonicalUrl} />}
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:site_name" content={SITE_NAME} />

      {/* Twitter/X Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />

      {/* Structured data */}
      {schemas.map((schema, i) => (
        <script key={i} type="application/ld+json">
          {JSON.stringify(schema)}
        </script>
      ))}
    </Helmet>
  )
}

/* ── Structured data builders ── */

export function organizationSchema() {
  const url = BASE_URL || "https://yourdomain.com"
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Presence",
    url,
    logo: `${url}/icons/icon-512.png`,
    description: "Digital presence monitoring for small businesses.",
  }
}

export function websiteSchema() {
  const url = BASE_URL || "https://yourdomain.com"
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Presence",
    url,
    potentialAction: {
      "@type": "SearchAction",
      target: `${url}/tools/website-checker?q={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  }
}

export function softwareAppSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Presence",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web, iOS, Android",
    offers: [
      { "@type": "Offer", price: "0", priceCurrency: "EUR", name: "Free" },
      { "@type": "Offer", price: "9", priceCurrency: "EUR", name: "Pro" },
      { "@type": "Offer", price: "29", priceCurrency: "EUR", name: "Business" },
      { "@type": "Offer", price: "79", priceCurrency: "EUR", name: "Agency" },
    ],
    description:
      "Monitor your website, SSL, DNS, email security, uptime and online reputation from one simple dashboard.",
    url: BASE_URL || "https://yourdomain.com",
  }
}

export function faqSchema(items: { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map(({ q, a }) => ({
      "@type": "Question",
      name: q,
      acceptedAnswer: { "@type": "Answer", text: a },
    })),
  }
}

export function articleSchema(article: {
  title: string
  description: string
  slug: string
  date: string
  author: string
}) {
  const url = BASE_URL ? `${BASE_URL}/blog/${article.slug}` : `/blog/${article.slug}`
  const published = new Date(article.date)
  return {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: article.title,
    description: article.description,
    ...(Number.isNaN(published.getTime())
      ? {}
      : { datePublished: published.toISOString() }),
    author: { "@type": "Organization", name: article.author },
    publisher: { "@type": "Organization", name: SITE_NAME },
    mainEntityOfPage: { "@type": "WebPage", "@id": url },
  }
}

export function breadcrumbSchema(items: { name: string; url: string }[]) {
  const base = BASE_URL || ""
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map(({ name, url }, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name,
      item: base ? `${base}${url}` : url,
    })),
  }
}
