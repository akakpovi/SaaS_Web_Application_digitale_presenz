#!/usr/bin/env node
/**
 * SEO gate for the built frontend.
 *
 * `scripts/prerender.mjs` writes one `index.html` per public route plus the
 * sitemap and robots.txt, and nginx then serves those files directly
 * (`try_files $uri/index.html $uri =404`). Two failure modes follow from that
 * layout, and both are invisible in the dev server, which falls back to the SPA
 * shell for every path:
 *
 *   1. a public route that is missing from `src/seo/routes.json` has no
 *      `dist/<route>/index.html`, so nginx answers a hard 404 in production,
 *   2. a route in the sitemap that was never pre-rendered advertises a URL that
 *      does not resolve — Google reports a "submitted URL blocked/404".
 *
 * This script validates the *generated files*, not the configuration: it reads
 * `dist/`, replays nginx' resolution, and re-derives the expected head tags and
 * sitemap entries from `routes.json`.
 *
 * It also covers the bilingual pages: every indexable route is written for
 * German (`<route>/index.html`, the bare historical URL) and for English
 * (`en/<route>/index.html`, its own canonical URL). The URL each pre-rendered
 * head advertises through `hreflang` must be the URL that really serves that
 * language, so the check resolves the advertised URL instead of trusting
 * routes.json. The historical `?lang=en` URL is now a 301: for the public
 * routes nginx redirects it to `/en/...` before try_files, so no `_i18n` copy
 * is written any more (and leaving a stale one would resurrect the duplicate
 * URL). The five noindex screens keep their `_i18n/<route>/index.html` shell:
 * they have no public English URL, so redirecting them would point at a 404.
 *
 * Usage:
 *   node scripts/check-seo-build.mjs [--base-url=https://presence.example]
 *                                    [--require-public-origin]
 *
 * Exit code 0 = every check passed, 1 = at least one check failed (the failing
 * lines are printed with the file and the value that was found).
 */
import fs from "node:fs"
import path from "node:path"

const ROOT = path.resolve(import.meta.dirname, "..")
const DIST = path.join(ROOT, "dist")
const argFlag = (name) => process.argv.includes(name)
const argValue = (name) => {
  const prefix = `${name}=`
  const hit = process.argv.find((value) => value.startsWith(prefix))
  return hit ? hit.slice(prefix.length) : undefined
}

/**
 * Origin the artifact was built for, read from the canonical URL it carries.
 * `pnpm check:seo` therefore inspects a public build without the CI variables
 * again — comparing its absolute URLs against `localhost` would report every
 * hreflang as broken instead of reporting the real state.
 */
function originFromArtifact() {
  const index = path.join(DIST, "index.html")
  if (!fs.existsSync(index)) return ""
  const canonical = fs
    .readFileSync(index, "utf8")
    .match(/<link rel="canonical" href="([^"]+)"/)
  return canonical ? canonical[1].replace(/\/+$/, "") : ""
}

// Same resolution order as scripts/prerender.mjs, so a build and its own gate
// always agree on the origin they were both produced with.
const BASE_URL = (
  argValue("--base-url") ||
  process.env.VITE_BASE_URL ||
  process.env.SITE_URL ||
  originFromArtifact() ||
  "http://localhost:8443"
).replace(/\/+$/, "")
const IS_LOCAL = /localhost|127\.0\.0\.1/.test(BASE_URL)
const DEFAULT_LOCALE = "de"
const LOCALES = ["de", "en"]
/** Prefix of the dedicated English site (mirrors src/i18n EN_PREFIX). */
const EN_PREFIX = "/en"
/** Folder of the private `?lang=en` shells; must stay non-addressable. */
const VARIANT_DIR = "_i18n"
const VARIANT_QUERY = "?lang=en"

/**
 * Repo catalogues.
 *
 * The SSG body is expected to contain the *real* answer texts, not only the
 * questions, so the gate reads the same JSON the page renders instead of a
 * duplicate expectation that would drift.
 */
const CATALOGS = Object.fromEntries(
  LOCALES.map((locale) => [
    locale,
    JSON.parse(
      fs.readFileSync(path.join(ROOT, `src/i18n/${locale}.json`), "utf8"),
    ),
  ]),
)

function copy(locale, key) {
  const value = key
    .split(".")
    .reduce((node, part) => node?.[part], CATALOGS[locale])
  return typeof value === "string" ? value : null
}

/** Title and description of one route in one language. */
function routeCopy(route, locale) {
  return locale === DEFAULT_LOCALE
    ? {
        title: route.titleDe || route.title,
        description: route.descriptionDe || route.description,
      }
    : { title: route.title, description: route.description }
}

/** URL of one page in one language: bare for German, `/en...` for English. */
function localizedPath(routePath, locale) {
  if (locale === DEFAULT_LOCALE) return routePath
  return routePath === "/" ? EN_PREFIX : `${EN_PREFIX}${routePath}`
}

/** Canonical file of one variant below `dist/` (also the URI nginx serves). */
function variantPath(routePath, locale) {
  const localized = localizedPath(routePath, locale)
  return localized === "/" ? "/index.html" : `${localized}/index.html`
}

/** Historical `?lang=en` alias of the English page, still written to `_i18n/`. */
function aliasPath(routePath) {
  const base = routePath === "/" ? "/index.html" : `${routePath}/index.html`
  return `/${VARIANT_DIR}${base}`
}

/** Canonical URL of one variant. */
function variantUrl(routePath, locale) {
  return absoluteUrl(localizedPath(routePath, locale))
}

const failures = []
const warnings = []
/** Pages that really carry a build-time React render (excludes shells). */
let ssgPages = 0
const check = (ok, message) => {
  if (!ok) failures.push(message)
  return ok
}
/** A known, documented limitation that does not invalidate the build. */
const warn = (message) => {
  warnings.push(message)
}

function read(file) {
  return fs.readFileSync(file, "utf8")
}

/**
 * Public bilingual paths, read from the same file the router, `LocaleLink`
 * and the nginx map generator use. A route added there must not be able to
 * keep answering the legacy `?lang=` URL just because this gate never saw it.
 */
const PUBLIC_PATHS = [
  ...read(path.join(ROOT, "src", "seo", "publicPaths.ts")).matchAll(
    /"(\/[^"]*)"/g,
  ),
].map((match) => match[1])
const PUBLIC_PATH_SET = new Set(PUBLIC_PATHS)

/**
 * Target of the 301 nginx answers for `?lang=` on a public path, or `null`
 * when the request is not redirected (private route, another language value).
 */
function localeRedirectTarget(uri, lang) {
  if (!PUBLIC_PATH_SET.has(uri)) return null
  // nginx `map` matches its string keys case-insensitively: `?lang=EN` already
  // redirects, so the model must lower-case too.
  const normalized = lang?.toLowerCase()
  if (normalized !== "en" && normalized !== "de") return null
  return localizedPath(uri, normalized)
}

/**
 * Same transformation as `map $args $presence_locale_query` in the generated
 * file: drop the `lang` token, keep every other parameter in its original
 * order, and add the `?` only when something remains. Mirrors the four regexes
 * (greedy, first match wins) so the gate cannot accept a rule nginx would not
 * apply.
 */
function localeRedirectQuery(args) {
  if (!args) return ""
  // `~*` in the generated map: same case handling as nginx.
  if (/^lang=(?:en|de)$/i.test(args)) return ""
  let match = args.match(/^lang=(?:en|de)&(.+)$/i)
  if (match) return `?${match[1]}`
  match = args.match(/^(.+)&lang=(?:en|de)&(.+)$/i)
  if (match) return `?${match[1]}&${match[2]}`
  match = args.match(/^(.+)&lang=(?:en|de)$/i)
  if (match) return `?${match[1]}`
  return ""
}

function decodeHtml(value) {
  return value
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
}

/** Value of the first match of `pattern`, or `null`. */
function first(html, pattern) {
  const match = html.match(pattern)
  return match ? decodeHtml(match[1]) : null
}

/** Capture groups of every match (the full match itself is dropped). */
function all(html, pattern) {
  return [...html.matchAll(pattern)].map((match) =>
    match.slice(1).map(decodeHtml),
  )
}

function absoluteUrl(routePath) {
  return routePath === "/" ? `${BASE_URL}/` : `${BASE_URL}${routePath}`
}

/* ── nginx: the rules that decide whether a URL resolves to a file ────────── */

/**
 * Replays `try_files` from nginx.conf, query string included. `public` is the
 * generic `location / { try_files $html_variant$uri/index.html
 * $uri/index.html $uri =404; }` rule; the other entries mirror the blocks that
 * deliberately keep client-rendered or private pages on the SPA shell.
 *
 * `/_i18n/**` is `internal` in nginx.conf, so an external request for it is a
 * 404 — the English shells must never become their own URLs.
 */
function resolveUri(uriWithQuery) {
  const [rawUri, query = ""] = uriWithQuery.split("?")
  const uri = path.posix.normalize(rawUri)
  const lang = new URLSearchParams(query).get("lang")
  const exists = (fileUri) =>
    fs.existsSync(path.join(DIST, fileUri.replace(/^\//, "")))
  /** nginx concatenates `$html_variant$uri`, so `/` + home yields `//`; the
   * filesystem collapses it and so does the reported URI. */
  const served = (fileUri) => path.posix.normalize(fileUri)

  // `?lang=` on a public route never reaches try_files: the generated map
  // makes nginx answer a 301 first (`=301 <target>` mirrors that).
  const redirect = localeRedirectTarget(uri, lang)
  if (redirect !== null) return `=301 ${redirect}${localeRedirectQuery(query)}`

  if (uri.startsWith(`/${VARIANT_DIR}/`)) return "=404"
  if (uri === "/settings/integrations" || uri === "/verify-email" || uri === "/admin") {
    return exists("/index.html") ? "/index.html" : "=404"
  }
  if (uri.startsWith("/app/") || uri.startsWith("/report/") || uri.startsWith("/scan/")) {
    return exists(uri) ? uri : exists("/index.html") ? "/index.html" : "=404"
  }
  const variant = lang === "en" ? `/${VARIANT_DIR}` : ""
  // `location /blog/` has no language variant: an article is written in one
  // language and its translations live on their own slugs.
  if (uri.startsWith("/blog/")) {
    if (exists(`${uri}/index.html`)) return `${uri}/index.html`
    return exists("/index.html") ? "/index.html" : "=404"
  }
  // location /
  if (exists(`${variant}${uri}/index.html`)) return served(`${variant}${uri}/index.html`)
  if (exists(`${uri}/index.html`)) return served(`${uri}/index.html`)
  if (exists(uri)) return served(uri)
  return "=404"
}

/* ── Inputs ───────────────────────────────────────────────────────────────── */

if (!fs.existsSync(path.join(DIST, "index.html"))) {
  console.error("[check-seo] dist/index.html is missing — run `pnpm build` first.")
  process.exit(1)
}

const routes = JSON.parse(read(path.join(ROOT, "src", "seo", "routes.json")))
const appSource = read(path.join(ROOT, "src", "App.tsx"))
// Public paths live in `src/seo/publicPaths.ts` (mounted twice: bare and
// `/en`), private ones as JSX (`path="/login"`) in App.tsx. Both are declared
// routes; nothing else in the router counts.
const publicPathsSource = read(
  path.join(ROOT, "src", "seo", "publicPaths.ts"),
)
const appStaticPaths = new Set([
  ...[...publicPathsSource.matchAll(/"(\/[^"]*)"/g)].map(
    (match) => match[1],
  ),
  ...[...appSource.matchAll(/path="([^"]+)"/g)]
    .map((match) => match[1])
    .filter((value) => value.startsWith("/") && !value.includes(":")),
])

/* ── 1. routes.json is complete and bilingual ─────────────────────────────── */

const seen = new Set()
for (const route of routes) {
  const { path: routePath } = route
  check(
    typeof routePath === "string" && routePath.startsWith("/") && !/[?:]/.test(routePath),
    `routes.json: "${routePath}" is not a static, parameter-free path`,
  )
  check(!seen.has(routePath), `routes.json: "${routePath}" is declared twice`)
  seen.add(routePath)

  for (const field of ["title", "description"]) {
    check(
      typeof route[field] === "string" && route[field].length > 10,
      `routes.json ${routePath}: English ${field} is missing or too short`,
    )
    check(
      typeof route[`${field}De`] === "string" && route[`${field}De`].length > 10,
      `routes.json ${routePath}: German ${field} is missing or too short`,
    )
  }
  // Metadata left in German for the English variant is invisible in a German
  // build (the shell only prints the German pair) but wrong the moment the
  // English pair is used.
  check(
    route.title !== route.titleDe,
    `routes.json ${routePath}: English and German titles are identical (untranslated?)`,
  )
  check(
    route.description !== route.descriptionDe,
    `routes.json ${routePath}: English and German descriptions are identical (untranslated?)`,
  )
}

/* ── 2. every advertised route exists in the React router ─────────────────── */

for (const routePath of seen) {
  check(
    appStaticPaths.has(routePath),
    `src/App.tsx declares no route for "${routePath}" advertised in routes.json`,
  )
}

/* ── 3. pre-rendered HTML per route and per language, with the expected head ─ */

const OG_LOCALES = { de: "de_DE", en: "en_GB" }
/** Marker on the injected tags; see src/lib/prerenderedHead.ts. */
const HEAD_MARKER = 'data-prerender-head="true"'

for (const route of routes) {
  const { path: routePath } = route

  for (const locale of LOCALES) {
    // A noindex screen has no `/en` copy: its English shell is the historical
    // `?lang=en` alias, validated below.
    if (route.noindex && locale !== DEFAULT_LOCALE) continue

    const distPath = variantPath(routePath, locale)
    const file = path.join(DIST, distPath.replace(/^\//, ""))

    if (!check(fs.existsSync(file), `dist${distPath}: file missing (nginx would answer 404)`)) {
      continue
    }
    const html = read(file)
    const where = `dist${distPath}`
    const expected = routeCopy(route, locale)

    check(
      first(html, /<html lang="([^"]*)"/) === locale,
      `${where}: <html lang> is not "${locale}"`,
    )
  check(
    all(html, /<title[^>]*>([\s\S]*?)<\/title>/g).length === 1,
    `${where}: expected exactly one <title>`,
  )
  check(
    first(html, /<title[^>]*>([\s\S]*?)<\/title>/) === expected.title,
    `${where}: <title> is not the ${locale} title of routes.json`,
  )
  // The application can only drop the tags it replaced when they are marked
  // (`src/lib/prerenderedHead.ts`); unmarked ones would survive as duplicates.
  check(
    new RegExp(`<title ${HEAD_MARKER}`).test(html) &&
      new RegExp(`<meta name="description"[^>]*${HEAD_MARKER}`).test(html),
    `${where}: injected tags do not carry ${HEAD_MARKER}, so the app cannot deduplicate them`,
  )
    check(
      first(html, /<meta name="description" content="([^"]*)"/) === expected.description,
      `${where}: description is not the ${locale} description of routes.json`,
    )
    check(
      first(html, /<meta name="robots" content="([^"]*)"/) ===
        (route.noindex ? "noindex,nofollow" : "index,follow"),
      `${where}: robots meta is wrong`,
    )
    check(
      first(html, /<meta property="og:locale" content="([^"]*)"/) === OG_LOCALES[locale],
      `${where}: og:locale is not ${OG_LOCALES[locale]}`,
    )
    // The other language is announced as an alternate, never as the locale.
    const alternateLocales = all(
      html,
      /<meta property="og:locale:alternate" content="([^"]*)"/g,
    ).map(([value]) => value)
    check(
      alternateLocales.length === 1 &&
        alternateLocales[0] === OG_LOCALES[locale === "de" ? "en" : "de"],
      `${where}: og:locale:alternate should be exactly the other language`,
    )

    const canonical = first(html, /<link rel="canonical" href="([^"]*)"/)
    const alternates = all(html, /<link rel="alternate" hreflang="([^"]+)" href="([^"]*)"/g)

    if (route.noindex) {
      check(canonical === null, `${where}: a noindex page must not publish a canonical`)
      check(alternates.length === 0, `${where}: a noindex page must not publish hreflang alternates`)
      continue
    }

    // Each variant canonicalises to itself: `?lang=en` that pointed at the
    // German URL could never be indexed, which is what its own hreflang entry
    // promises. The default language owns the bare path.
    check(
      canonical === variantUrl(routePath, locale),
      `${where}: canonical is ${canonical}, expected ${variantUrl(routePath, locale)}`,
    )

    const expectedAlternates = [
      ...LOCALES.map((entry) => [entry, variantUrl(routePath, entry)]),
      ["x-default", absoluteUrl(routePath)],
    ]
    check(
      alternates.length === expectedAlternates.length,
      `${where}: expected ${expectedAlternates.length} hreflang links, found ${alternates.length}`,
    )
    for (const [hreflang, href] of expectedAlternates) {
      check(
        alternates.some(([foundLang, foundHref]) => foundLang === hreflang && foundHref === href),
        `${where}: hreflang ${hreflang} should point at ${href}`,
      )
    }
  }

  // A public route must NOT keep a `_i18n` copy any more: nginx answers
  // `?lang=en` with a 301 before try_files, so the file would never be served,
  // and a stale one would resurrect the duplicate URL the redirect removes.
  // The five noindex screens keep theirs (no `/en/login` page exists, so they
  // must still answer 200 directly).
  const alias = aliasPath(routePath)
  const aliasFile = path.join(DIST, alias.replace(/^\//, ""))
  if (!route.noindex) {
    check(
      !fs.existsSync(aliasFile),
      `dist${alias}: a public route must not carry a ?lang=en copy (nginx 301s it)`,
    )
  } else if (
    check(
      fs.existsSync(aliasFile),
      `dist${alias}: the private ?lang=en shell is missing (existing links would break)`,
    )
  ) {
    const html = read(aliasFile)
    const expected = routeCopy(route, "en")
    check(
      first(html, /<html lang="([^"]*)"/) === "en",
      `dist${alias}: the private shell is not English`,
    )
    check(
      first(html, /<title[^>]*>([\s\S]*?)<\/title>/) === expected.title,
      `dist${alias}: <title> is not the English title of routes.json`,
    )
    check(
      first(html, /<meta name="robots" content="([^"]*)"/) === "noindex,nofollow",
      `dist${alias}: robots meta is wrong`,
    )
    check(
      first(html, /<link rel="canonical" href="([^"]*)"/) === null,
      `dist${alias}: a noindex shell must not publish a canonical`,
    )
  }
}

/* ── 3a. the SSG body really contains each page, not a generic shell ─────── */

const SSG_H1 = {
  "/": {
    de: "Ihre digitale Präsenz, jederzeit unter Kontrolle.",
    en: "Your digital presence, always under control.",
  },
  "/pricing": { de: "Einfache, transparente Preise", en: "Simple, transparent pricing" },
  "/faq": { de: "Häufig gestellte Fragen", en: "Frequently asked questions" },
  "/blog": {
    de: "Leitfäden zur digitalen Präsenz für kleine Unternehmen",
    en: "Digital presence guides for small businesses",
  },
  "/about": {
    de: "Digitale Gesundheitsinfrastruktur für das moderne Web.",
    en: "Digital health infrastructure for the modern web.",
  },
  "/contact": { de: "Kontakt aufnehmen", en: "Get in touch" },
  "/privacy": { de: "Datenschutzerklärung", en: "Privacy policy" },
  "/terms": { de: "Allgemeine Geschäftsbedingungen", en: "Terms of service" },
  "/impressum": { de: "Impressum", en: "Imprint" },
  "/cookies": { de: "Cookies und Speicherung", en: "Cookies and storage" },
  "/widerruf": { de: "Widerrufsrecht", en: "Right of withdrawal" },
  "/solutions/small-business": {
    de: "Website-Monitoring für kleine Unternehmen",
    en: "Website monitoring built for small businesses",
  },
  "/solutions/freelancers": {
    de: "Website-Monitoring für Selbstständige und Beratungen",
    en: "Website monitoring for freelancers and consultants",
  },
  "/solutions/agencies": {
    de: "Website-Monitoring für Digitalagenturen",
    en: "Website monitoring for digital agencies",
  },
  "/solutions/restaurants": {
    de: "Website-Monitoring für Restaurants und Cafés",
    en: "Website monitoring for restaurants and cafés",
  },
  "/solutions/ecommerce": {
    de: "Website-Monitoring für E-Commerce-Unternehmen",
    en: "Website monitoring for e-commerce businesses",
  },
  "/solutions/local-business": {
    de: "Website-Monitoring für lokale Unternehmen",
    en: "Website monitoring for local businesses",
  },
  "/features/website-monitoring": {
    de: "Website-Überwachung für kleine Unternehmen",
    en: "Website Monitoring for Small Businesses",
  },
  "/features/ssl-monitoring": {
    de: "SSL-Zertifikatsüberwachung",
    en: "SSL Certificate Monitoring",
  },
  "/features/dns-monitoring": {
    de: "DNS-Überwachung und Domain-Prüfung",
    en: "DNS Monitoring & Domain Health Checks",
  },
  "/features/email-security": {
    de: "E-Mail-Sicherheit überwachen – SPF, DKIM und DMARC",
    en: "Email Security Monitoring — SPF, DKIM & DMARC",
  },
  "/features/uptime-monitoring": {
    de: "Uptime-Überwachung für Ihre Website",
    en: "Website Uptime Monitoring",
  },
  "/features/website-performance": {
    de: "Performance-Überwachung für Ihre Website",
    en: "Website Performance Monitoring",
  },
  "/features/security-headers": {
    de: "HTTP-Sicherheitsheader überwachen",
    en: "Website Security Headers Monitoring",
  },
  "/features/review-monitoring": {
    de: "Online-Bewertungen für kleine Unternehmen überwachen",
    en: "Online Review Monitoring for Small Businesses",
  },
  "/tools/website-checker": {
    de: "Kostenloser Website-Gesundheitscheck",
    en: "Free Website Health Checker",
  },
  "/tools/ssl-checker": {
    de: "Kostenloser SSL-Zertifikat-Check",
    en: "Free SSL Certificate Checker",
  },
  "/tools/dns-checker": {
    de: "Kostenloser DNS-Check",
    en: "Free DNS Checker",
  },
  "/tools/email-security-checker": {
    de: "Kostenloser E-Mail-Sicherheitscheck",
    en: "Free Email Security Checker",
  },
}

function h1Text(html) {
  const headings = all(html, /<h1[^>]*>([\s\S]*?)<\/h1>/g)
  if (headings.length === 0) return null
  return headings[0][0].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
}

function rootHtml(html) {
  const start = html.indexOf('<div id="root"')
  const bodyEnd = html.indexOf("</body>", start)
  if (start < 0 || bodyEnd < 0) return null
  // The root's closing </div> is the last one before </body>; nested page
  // markup and the blog JSON script never contain a later </div>.
  const end = html.lastIndexOf("</div>", bodyEnd)
  return end > start ? html.slice(start, end) : null
}

for (const route of routes) {
  const { path: routePath } = route
  for (const locale of LOCALES) {
    // Noindex screens are never mounted under `/en`; their English shell is
    // the legacy alias checked in section 3.
    if (route.noindex && locale !== DEFAULT_LOCALE) continue
    const distPath = variantPath(routePath, locale)
    const html = read(path.join(DIST, distPath.replace(/^\//, "")))
    const where = `dist${distPath}`

    if (route.noindex) {
      check(
        html.includes('data-prerender="true"') && !html.includes('data-ssg="true"'),
        `${where}: a noindex route must keep the lightweight shell, not an SSG page`,
      )
      continue
    }

    // The blog index needs CMS data. When the CMS is unreachable *at build
    // time*, prerender writes an explicitly marked fallback instead of a page
    // pretending to be complete; the SPA fetches the posts on load exactly as
    // it did before. That is a reported limitation, not a silent success.
    if (routePath === "/blog" && html.includes("ssg:blog-fallback cms-unavailable")) {
      warn(
        `${where}: CMS unreachable at build time — blog index is a client-rendered fallback (not pre-rendered)`,
      )
      continue
    }
    check(
      !html.includes("ssg:blog-fallback"),
      `${where}: unexpected CMS fallback marker on a page that should be pre-rendered`,
    )

    check(
      html.includes('<div id="root" data-ssg="true">'),
      `${where}: no SSG root marker (the page is still a fallback shell)`,
    )
    ssgPages += 1
    check(
      !html.includes('data-prerender="true"'),
      `${where}: the generic fallback shell is still present in an SSG page`,
    )

    const expectedH1 = SSG_H1[routePath]?.[locale]
    check(
      Boolean(expectedH1),
      `${where}: no expected H1 is declared for this route in check-seo-build.mjs`,
    )
    check(
      h1Text(html) === expectedH1,
      `${where}: H1 is "${h1Text(html)}", expected "${expectedH1}"`,
    )

    const body = rootHtml(html)
    check(
      body !== null && body.length > 3000,
      `${where}: the rendered body is only ${body ? body.length : 0} bytes — not a complete page`,
    )

    if (routePath === "/pricing") {
      // Every tier and its real price, not just one card: a partial SSG that
      // dropped the table would still contain a single plan name.
      for (const name of ["Free", "Pro", "Business", "Agency"]) {
        check(html.includes(name), `${where}: pricing page has no ${name} plan`)
      }
      for (const price of ["9", "29", "79"]) {
        check(html.includes(price), `${where}: pricing page has no ${price} price`)
      }
    }
    if (routePath === "/faq") {
      const question = copy(locale, "faqPage.categories.general.i1.q")
      const answer = copy(locale, "faqPage.categories.general.i1.a")
      check(
        Boolean(question) && html.includes(question),
        `${where}: FAQ page has no real question`,
      )
      // The accordion keeps the answer in the HTML and collapses it with
      // `hidden`; a conditional render would silently drop every answer again.
      check(
        Boolean(answer) && html.includes(answer.slice(0, 120)),
        `${where}: FAQ answers are missing from the pre-rendered HTML`,
      )
      const answerCount = (html.match(/<div hidden="" class="px-5 pb-4 text-sm text-slate-600/g) || []).length
      check(
        answerCount >= 10,
        `${where}: only ${answerCount} collapsed FAQ answers are rendered`,
      )
    }
    if (routePath.startsWith("/features/")) {
      const subsections = (html.match(/<h2/g) || []).length
      check(
        subsections >= 5,
        `${where}: feature page has only ${subsections} <h2> sections — looks like a shell`,
      )
      check(
        html.includes(locale === "de" ? "Häufige Fragen" : "Frequently asked questions"),
        `${where}: feature page has no FAQ section`,
      )
    }
    if (routePath === "/privacy") {
      check(
        html.includes(locale === "de" ? "Verantwortlicher" : "Controller"),
        `${where}: privacy page has no controller section`,
      )
      check(
        html.includes(locale === "de" ? "Rechtsgrundlagen" : "Legal bases"),
        `${where}: privacy page has no legal-bases section`,
      )
    }
    if (routePath === "/terms") {
      check(
        html.includes(locale === "de" ? "Kündigung" : "cancellation"),
        `${where}: terms page has no termination section`,
      )
      check(html.includes("Paddle"), `${where}: terms page does not mention the payment provider`)
    }
    if (routePath === "/privacy" || routePath === "/terms" || routePath === "/impressum") {
      check(
        /Arbeitsentwurf|Working draft|Diese Seite muss vor dem Livegang|This page must be completed/.test(html),
        `${where}: legal page has no visible draft notice`,
      )
    }
    if (routePath === "/") {
      check(
        html.includes(locale === "de" ? "Keine Kreditkarte erforderlich" : "No credit card required"),
        `${where}: landing page is missing its call-to-action copy`,
      )
    }

    const blogData = html.match(
      /<script type="application\/json" id="__blog-data">([\s\S]*?)<\/script>/,
    )
    if (routePath === "/blog") {
      check(Boolean(blogData), `${where}: blog index has no build-time posts`)
      if (blogData) {
        try {
          const data = JSON.parse(blogData[1])
          check(data.locale === locale, `${where}: blog data is for ${data.locale}`)
          check(Array.isArray(data.posts), `${where}: blog data is not a list`)
          check(
            data.posts.every((post) => post.lang === locale),
            `${where}: blog data mixes languages`,
          )
          const slugs = data.posts.map((post) => post.slug)
          if (locale === "de") {
            check(slugs.includes("de-was-ist-website-monitoring"), `${where}: German blog misses its German article`)
          } else {
            check(slugs.includes("what-is-dmarc"), `${where}: English blog misses its English article`)
            check(!slugs.some((slug) => slug.startsWith("de-")), `${where}: English blog lists a German slug`)
          }
        } catch (error) {
          check(false, `${where}: blog data is not valid JSON (${error.message})`)
        }
      }
    } else {
      check(!blogData, `${where}: blog data leaked onto a non-blog page`)
    }
  }
}

/* ── 3b. every advertised hreflang URL really serves that language ─────────── */

const nginxConfig = read(path.join(ROOT, "nginx.conf"))
check(
  /map\s+\$arg_lang\s+\$html_variant/.test(nginxConfig),
  "nginx.conf: no `map $arg_lang $html_variant`, so ?lang=en cannot select the English shell",
)
check(
  new RegExp(`location\\s+/${VARIANT_DIR}/\\s*\\{[^}]*internal`).test(nginxConfig),
  `nginx.conf: /${VARIANT_DIR}/ is not marked internal — the English shells would be addressable URLs of their own`,
)
check(
  /location\s+\/\s*\{[^}]*try_files\s+\$html_variant\$uri\/index\.html/.test(nginxConfig),
  "nginx.conf: `location /` does not try $html_variant$uri/index.html, so the private ?lang=en shells could not be served",
)

// `?lang=` on a public route is a 301 decided by a map generated from
// publicPaths.ts, before any location is selected.
check(
  /include\s+\/etc\/nginx\/conf\.d\/presence-locale-map\.conf;/.test(nginxConfig),
  "nginx.conf: the generated locale map is not included, so ?lang= would not redirect",
)
check(
  /if\s*\(\$presence_locale_redirect\s*!=\s*""\)\s*\{\s*return\s+301\s+\$scheme:\/\/\$http_host\$presence_locale_redirect\$presence_locale_query;/.test(
    nginxConfig,
  ),
  "nginx.conf: no `if ($presence_locale_redirect != \"\") { return 301 $scheme://$http_host$presence_locale_redirect$presence_locale_query; }`, so ?lang= is not redirected with its other parameters",
)

const localeMapFile = path.join(ROOT, "nginx.locale-map.conf")
if (
  check(
    fs.existsSync(localeMapFile),
    "nginx.locale-map.conf is missing — run `node scripts/generate-nginx-locale-map.mjs`",
  )
) {
  const localeMap = read(localeMapFile)
  check(
    /map\s+"\$uri\|\$arg_lang"\s+\$presence_locale_redirect/.test(localeMap),
    "nginx.locale-map.conf: the map key is not `$uri|$arg_lang`",
  )
  check(
    /map\s+\$args\s+\$presence_locale_query/.test(localeMap),
    "nginx.locale-map.conf: no `map $args $presence_locale_query`, so utm_* would be lost on redirect",
  )
  for (const publicPath of PUBLIC_PATHS) {
    for (const locale of LOCALES) {
      const target = localizedPath(publicPath, locale)
      check(
        localeMap.includes(`"${publicPath}|${locale}" "${target}";`),
        `nginx.locale-map.conf: ${publicPath}?lang=${locale} should 301 to ${target}`,
      )
    }
  }
  for (const route of routes) {
    if (!route.noindex) continue
    check(
      !localeMap.includes(`"${route.path}|`),
      `nginx.locale-map.conf: the noindex route ${route.path} must not be redirected`,
    )
  }
  const ruleCount = (localeMap.match(/^    "\/[^"]*\|/gm) || []).length
  check(
    ruleCount === PUBLIC_PATHS.length * LOCALES.length,
    `nginx.locale-map.conf: ${ruleCount} rules for ${PUBLIC_PATHS.length} public routes × ${LOCALES.length} languages`,
  )
}

for (const route of routes) {
  if (route.noindex) continue
  for (const locale of LOCALES) {
    const advertised = new URL(variantUrl(route.path, locale)).pathname + new URL(variantUrl(route.path, locale)).search
    const resolved = resolveUri(advertised)
    check(
      resolved === variantPath(route.path, locale),
      `hreflang ${locale} on ${route.path} advertises ${advertised}, which nginx resolves to "${resolved}"`,
    )
    const body = resolved === "=404" ? "" : read(path.join(DIST, resolved.replace(/^\//, "")))
    check(
      first(body, /<html lang="([^"]*)"/) === locale,
      `${advertised} advertises language ${locale} but serves <html lang="${first(body, /<html lang="([^"]*)"/)}">`,
    )
  }
}

// `?lang=` is no longer a URL. A public route answers 301 to its canonical
// page and nothing else; the five noindex screens still answer 200 directly,
// because they have no public English URL to redirect to.
for (const route of routes) {
  const where = `${route.path}${VARIANT_QUERY}`
  const resolvedEn = resolveUri(`${route.path}?lang=en`)
  const resolvedDe = resolveUri(`${route.path}?lang=de`)

  if (route.noindex) {
    check(
      resolvedEn === aliasPath(route.path),
      `${where} on a noindex route must serve the private shell, resolved "${resolvedEn}"`,
    )
    const body =
      resolvedEn === "=404"
        ? ""
        : read(path.join(DIST, resolvedEn.replace(/^\//, "")))
    check(
      first(body, /<html lang="([^"]*)"/) === "en",
      `${where} does not serve English (<html lang="${first(body, /<html lang="([^"]*)"/)}">)`,
    )
    check(
      resolvedDe === variantPath(route.path, "de"),
      `${route.path}?lang=de on a noindex route must serve the German shell, resolved "${resolvedDe}"`,
    )
    continue
  }

  check(
    resolvedEn === `=301 ${localizedPath(route.path, "en")}`,
    `${where} resolves to "${resolvedEn}", expected "=301 ${localizedPath(route.path, "en")}"`,
  )
  check(
    resolvedDe === `=301 ${localizedPath(route.path, "de")}`,
    `${route.path}?lang=de resolves to "${resolvedDe}", expected "=301 ${localizedPath(route.path, "de")}"`,
  )
}

// Other query parameters survive the redirect, in their original order: a
// campaign URL keeps its attribution across the migration.
for (const [url, expected] of [
  [
    "/pricing?lang=en&utm_source=newsletter&utm_medium=email&utm_campaign=launch",
    "=301 /en/pricing?utm_source=newsletter&utm_medium=email&utm_campaign=launch",
  ],
  [
    "/pricing?utm_source=newsletter&lang=en&utm_medium=email",
    "=301 /en/pricing?utm_source=newsletter&utm_medium=email",
  ],
  [
    "/pricing?utm_source=newsletter&lang=en",
    "=301 /en/pricing?utm_source=newsletter",
  ],
  ["/pricing?lang=en", "=301 /en/pricing"],
  ["/pricing?lang=de&a=1&b=2", "=301 /pricing?a=1&b=2"],
  ["/?lang=en&utm_source=x", "=301 /en?utm_source=x"],
  // `map` is case-insensitive, the regex is `~*`: no attribution lost here.
  ["/pricing?lang=EN", "=301 /en/pricing"],
  ["/pricing?lang=EN&utm_source=x", "=301 /en/pricing?utm_source=x"],
]) {
  const resolved = resolveUri(url)
  check(
    resolved === expected,
    `?lang= redirect of ${url} resolves to "${resolved}", expected "${expected}"`,
  )
}

// The variant folder must not be reachable as a URL of its own.
for (const route of routes) {
  const internal = `/${VARIANT_DIR}${route.path === "/" ? "/index.html" : `${route.path}/index.html`}`
  check(
    resolveUri(internal) === "=404",
    `${internal} is served although the variant folder must stay internal`,
  )
}

/* ── 3c. CMS articles never advertise a ?lang= variant of their own URL ───── */

const blogDir = path.join(DIST, "blog")
if (fs.existsSync(blogDir)) {
  for (const entry of fs.readdirSync(blogDir, { withFileTypes: true })) {
    const file = path.join(blogDir, entry.name, "index.html")
    if (!entry.isDirectory() || !fs.existsSync(file)) continue
    const html = read(file)
    const where = `dist/blog/${entry.name}/index.html`
    const queryAlternates = all(
      html,
      /<link rel="alternate" hreflang="([^"]+)" href="([^"]*\?lang=[^"]*)"/g,
    )
    check(
      queryAlternates.length === 0,
      `${where}: an article translation lives on its own slug, not on ?lang= (${queryAlternates[0]?.[1]})`,
    )
    check(
      !(first(html, /<link rel="canonical" href="([^"]*)"/) || "").includes("?lang="),
      `${where}: canonical must not carry a ?lang= parameter`,
    )
    // The raw HTML has to carry the article itself, not a teaser: without JS a
    // crawler must still read the real body the CMS returned at build time.
    const article = html.match(/<article>([\s\S]*?)<\/article>/)
    const articleText = article
      ? article[1].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
      : ""
    check(
      articleText.length > 500,
      `${where}: the pre-rendered article body is only ${articleText.length} chars`,
    )
    // Like the hydrated head, an article declares its own language first.
    const declaredLocales = all(
      html,
      /<link rel="alternate" hreflang="([^"]+)" href="([^"]*)"/g,
    ).map(([lang]) => lang)
    check(
      declaredLocales.length === 0 ||
        declaredLocales.includes(first(html, /<html lang="([^"]*)"/)),
      `${where}: the article's own language is missing from its hreflang set (${declaredLocales.join(", ")})`,
    )
    for (const [href] of all(html, /<link rel="alternate" hreflang="[^"]+" href="([^"]*)"/g)) {
      check(
        href.startsWith(`${BASE_URL}/blog/`),
        `${where}: an article translation must be a real slug, found ${href}`,
      )
    }
    // Same acceptance criterion as 3b, for articles: an advertised translation
    // must resolve through the real nginx rules to a shell declaring that
    // language. A translation left unpublished would otherwise advertise a URL
    // that serves the German shell.
    for (const [hreflang, href] of all(
      html,
      /<link rel="alternate" hreflang="([^"]+)" href="([^"]*)"/g,
    )) {
      if (hreflang === "x-default") continue
      // A mismatch here means one build was checked with another origin; report
      // it once instead of resolving every advertised path to a 404.
      if (
        !check(
          href.startsWith(`${BASE_URL}/`),
          `${where}: hreflang ${hreflang} advertises ${href}, outside the build origin ${BASE_URL} — pass --base-url=<origin of the build>`,
        )
      ) {
        continue
      }
      const advertised = href.slice(BASE_URL.length)
      const resolved = resolveUri(advertised)
      const body =
        resolved === "=404" ? "" : read(path.join(DIST, resolved.replace(/^\//, "")))
      check(
        first(body, /<html lang="([^"]*)"/) === hreflang,
        `${where}: hreflang ${hreflang} advertises ${advertised}, served by ${resolved} with <html lang="${first(body, /<html lang="([^"]*)"/)}">`,
      )
    }
  }
}

/* ── 4. the legal pages resolve to their own file, not to the SPA shell ───── */

const LEGAL_ROUTES = ["/impressum", "/cookies", "/privacy", "/terms", "/widerruf"]
for (const routePath of LEGAL_ROUTES) {
  const resolved = resolveUri(routePath)
  check(
    resolved === `${routePath}/index.html`,
    `${routePath}: nginx resolves to "${resolved}" instead of "${routePath}/index.html"`,
  )
  const english = `${EN_PREFIX}${routePath}`
  const resolvedEn = resolveUri(english)
  check(
    resolvedEn === `${english}/index.html`,
    `${english}: nginx resolves to "${resolvedEn}" instead of "${english}/index.html"`,
  )
}

/* ── 5. no unresolved operator placeholder in the generated HTML ──────────── */

const LEGAL_PAGE = /\/(impressum|privacy|terms|cookies|widerruf)\/index\.html$/
const DRAFT_NOTICE =
  /Arbeitsentwurf|Working draft|Diese Seite muss vor dem Livegang vervollständigt werden|This page must be completed before launch/i
for (const entry of fs.readdirSync(DIST, { recursive: true })) {
  const file = path.join(DIST, String(entry))
  if (!file.endsWith(".html") || !fs.statSync(file).isFile()) continue
  const relative = path.relative(DIST, file).split(path.sep).join("/")
  const html = read(file)
  const leak = html.match(/\[[^\]]*(?:eintragen|enter the)[^\]]*\]/i)
  if (!leak) continue
  // Legal pages deliberately show unresolved operator fields as placeholders
  // next to a visible draft notice; inventing values there would be worse. The
  // dedicated `check-operator-identity.mjs` owns their completeness. A
  // placeholder anywhere else is still a leak.
  check(
    LEGAL_PAGE.test(`/${relative}`),
    `dist/${relative}: unresolved placeholder rendered outside a legal page (${leak[0]})`,
  )
  check(
    DRAFT_NOTICE.test(html),
    `dist/${relative}: unresolved placeholder without a visible draft notice (${leak[0]})`,
  )
}

/* ── 6. sitemap ───────────────────────────────────────────────────────────── */

const sitemapPath = path.join(DIST, "sitemap.xml")
const sitemapLocs = fs.existsSync(sitemapPath)
  ? all(read(sitemapPath), /<loc>([^<]*)<\/loc>/g).map(([loc]) => loc)
  : []
check(fs.existsSync(sitemapPath), "dist/sitemap.xml was not generated")

const blogPosts = fs.existsSync(path.join(DIST, "blog"))
  ? fs
      .readdirSync(path.join(DIST, "blog"), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && fs.existsSync(path.join(DIST, "blog", entry.name, "index.html")))
      .map((entry) => `/blog/${entry.name}`)
  : []

const expectedLocs = [
  ...routes
    .filter((route) => !route.noindex)
    .flatMap((route) =>
      LOCALES.map((locale) => absoluteUrl(localizedPath(route.path, locale))),
    ),
  ...blogPosts.map((post) => absoluteUrl(post)),
]
check(
  new Set(sitemapLocs).size === sitemapLocs.length,
  "dist/sitemap.xml contains duplicate <loc> entries",
)
for (const loc of expectedLocs) {
  check(sitemapLocs.includes(loc), `dist/sitemap.xml is missing ${loc}`)
}
for (const loc of sitemapLocs) {
  check(expectedLocs.includes(loc), `dist/sitemap.xml advertises an unexpected URL: ${loc}`)
  check(loc.startsWith(`${BASE_URL}/`), `dist/sitemap.xml entry is outside ${BASE_URL}: ${loc}`)
  check(!loc.includes("?") && !loc.includes("lang="), `dist/sitemap.xml entry carries a query string: ${loc}`)
  check(
    !new URL(loc).pathname.startsWith(`/${VARIANT_DIR}/`),
    `dist/sitemap.xml advertises the internal variant folder: ${loc}`,
  )
}

const PRIVATE_PATHS = ["/login", "/register", "/forgot-password", "/reset-password", "/onboarding", "/verify-email", "/admin", "/app/", "/scan/", "/report/", "/settings", "/404"]
for (const prefix of PRIVATE_PATHS) {
  check(
    !routes.filter((route) => route.noindex).some((route) => route.path === prefix && sitemapLocs.includes(absoluteUrl(route.path))),
    `dist/sitemap.xml lists the non-indexable route ${prefix}`,
  )
}

/* ── 7. robots.txt ────────────────────────────────────────────────────────── */

const robotsFile = path.join(DIST, "robots.txt")
check(fs.existsSync(robotsFile), "dist/robots.txt was not generated")
if (fs.existsSync(robotsFile)) {
  const robots = read(robotsFile)
  check(
    robots.includes(`Sitemap: ${BASE_URL}/sitemap.xml`),
    `dist/robots.txt does not point at ${BASE_URL}/sitemap.xml`,
  )
  for (const prefix of ["/app/", "/login", "/register", "/forgot-password", "/reset-password", "/onboarding", "/admin", "/verify-email"]) {
    check(robots.includes(`Disallow: ${prefix}`), `dist/robots.txt does not disallow ${prefix}`)
    check(
      !sitemapLocs.some((loc) => new URL(loc).pathname === prefix),
      `dist/robots.txt disallows ${prefix} but the sitemap advertises it`,
    )
  }
}

/* ── 8. every advertised URL is actually served ───────────────────────────── */

for (const loc of sitemapLocs) {
  const uri = new URL(loc).pathname
  const resolved = resolveUri(uri === "/" ? "/" : uri.replace(/\/$/, ""))
  check(resolved !== "=404", `sitemap URL ${loc} resolves to nginx 404 (no pre-rendered file)`)
}

/* ── 9. a public origin must not leak into local URLs ─────────────────────── */

if (!IS_LOCAL) {
  for (const entry of fs.readdirSync(DIST, { recursive: true })) {
    const file = path.join(DIST, String(entry))
    if (!/\.(html|xml|txt)$/.test(file) || !fs.statSync(file).isFile()) continue
    const leak = read(file).match(/https?:\/\/(?:localhost|127\.0\.0\.1)[^"'\s<]*/)
    check(!leak, `${path.relative(ROOT, file)}: local URL in a public build (${leak?.[0]})`)
  }
} else if (argFlag("--require-public-origin")) {
  failures.push(`--require-public-origin: ${BASE_URL} is a local origin`)
}

/* ── Report ───────────────────────────────────────────────────────────────── */

console.log(`[check-seo] origin=${BASE_URL}${IS_LOCAL ? " (local preview — canonical/sitemap stay local)" : ""}`)
console.log(`[check-seo] routes=${routes.length} (${routes.filter((r) => r.noindex).length} noindex) · pre-rendered=${ssgPages} · articles=${blogPosts.length} · sitemap=${sitemapLocs.length}`)
for (const warning of warnings) console.warn(`⚠️  ${warning}`)
if (failures.length === 0) {
  console.log("✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.")
  process.exit(0)
}
console.error(`❌ ${failures.length} SEO problem(s):`)
for (const failure of failures) console.error(`   - ${failure}`)
process.exit(1)
