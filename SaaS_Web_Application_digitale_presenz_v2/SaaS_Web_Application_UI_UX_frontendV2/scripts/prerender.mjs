#!/usr/bin/env node
/**
 * Pré-rendu statique des pages publiques.
 *
 * La SPA React reste inchangée, mais chaque route publique reçoit un fichier
 * HTML avec ses vraies balises <title>/<meta>/canonical et un contenu de repli
 * lisible sans JavaScript.  Les crawlers qui n'exécutent pas React (LinkedIn,
 * X, Slack, Bing preview…) voient donc la bonne page, et nginx peut renvoyer
 * un vrai 404 au lieu d'un "soft 404" en 200.
 *
 * Chaque route publique est écrite *pour chaque langue* : l'allemand (langue
 * par défaut) dans `<route>/index.html`, l'anglais dans `en/<route>/index.html`
 * (`/en/<route>`), servie directement par la règle `location /` puisque
 * `$uri/index.html` y résout.
 *
 * L'ancien alias `_i18n/<route>/index.html` n'est plus écrit pour les pages
 * publiques : `?lang=en` y répond désormais 301 vers `/en/<route>` (carte
 * générée depuis src/seo/publicPaths.ts), donc le fichier ne serait jamais
 * servi. `_i18n` ne subsiste que pour les cinq écrans noindex, qui n'ont pas
 * d'URL anglaise publique et doivent continuer à répondre 200 directement.
 * Le dossier reste `internal` dans nginx.conf et donc inadressable.
 *
 * Aucune dépendance : pas de Puppeteer, donc build léger et reproductible.
 *
 * Variables :
 *   VITE_BASE_URL      origine publique (ex. https://presence.app)
 *   VITE_WP_API_URL    CMS headless ; les slugs d'articles sont pré-rendus
 */

import dns from "node:dns/promises"
import fs from "node:fs"
import http from "node:http"
import https from "node:https"
import net from "node:net"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { loadEnv } from "vite"

const ROOT = path.resolve(import.meta.dirname, "..")
const DIST = path.join(ROOT, "dist")
/**
 * Build-time settings come from `.env` exactly like they do for `vite build`.
 * Reading only `process.env` silently dropped `VITE_WP_API_URL` when the build
 * ran through `pnpm run build`, so the blog articles were never pre-rendered
 * although the CMS was configured. Real environment variables still win.
 */
const ENV = {
  ...loadEnv("production", ROOT, ""),
  ...process.env,
}
const BASE_URL = (
  ENV.VITE_BASE_URL ||
  ENV.SITE_URL ||
  "http://localhost:8443"
).replace(/\/+$/, "")

if (/localhost|127\.0\.0\.1/.test(BASE_URL)) {
  console.warn(
    `[prerender] Public origin is ${BASE_URL} — canonical/sitemap remain local. ` +
      "Set VITE_BASE_URL before a public deployment.",
  )
}

const templatePath = path.join(DIST, "index.html")
if (!fs.existsSync(templatePath)) {
  console.error("[prerender] dist/index.html is missing — run vite build first.")
  process.exit(1)
}
const template = fs.readFileSync(templatePath, "utf8")
if (template.includes('data-ssg="true"')) {
  // `dist/index.html` is both the Vite template and the home page this script
  // writes. Re-running the script without a fresh client build would use the
  // rendered home page as the template for every route.
  console.error(
    "[prerender] dist/index.html is already a rendered page — run `vite build` before prerendering.",
  )
  process.exit(1)
}

/**
 * Server bundle produced by `vite build --ssr src/entry-server.tsx`.
 * The build must not silently fall back to a generic shell: a missing entry
 * means the production artifact would advertise content it does not contain.
 */
const SSR_ENTRY = path.join(ROOT, "dist-ssr", "entry-server.js")
if (!fs.existsSync(SSR_ENTRY)) {
  console.error(
    "[prerender] dist-ssr/entry-server.js is missing — run `pnpm run build:ssr` first.",
  )
  process.exit(1)
}
const { renderRoute } = await import(pathToFileURL(SSR_ENTRY).href)

const routes = JSON.parse(
  fs.readFileSync(path.join(ROOT, "src/seo/routes.json"), "utf8"),
)

function escapeHtml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
}

function escapeXml(value = "") {
  return escapeHtml(value).replace(/'/g, "&apos;")
}

/** JSON safe inside a <script> element: `</script>` must not close it. */
function embedJson(value) {
  return JSON.stringify(value).replace(/</g, "\\u003c")
}

function stripHtml(value = "") {
  return String(value)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#8217;|&#039;|&#39;/g, "'")
    .replace(/&#8211;|&ndash;/g, "–")
    .replace(/&#8212;|&mdash;/g, "—")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function absoluteUrl(routePath) {
  return routePath === "/" ? `${BASE_URL}/` : `${BASE_URL}${routePath}`
}

function cleanHead(html) {
  return html
    .replace(/<title>[\s\S]*?<\/title>\s*/i, "")
    .replace(
      /<meta\s+(?:name|property)=["'](?:description|robots|og:[^"']+|twitter:[^"']+)["'][^>]*>\s*/gi,
      "",
    )
    .replace(/<link\s+rel=["']canonical["'][^>]*>\s*/gi, "")
    // The hreflang alternates are re-rendered per route. Without this the
    // template (dist/index.html) carries the home page's alternates into every
    // subsequent run, which duplicates them on the public pages and leaks them
    // onto the noindex ones.
    .replace(/<link\s+rel=["']alternate["'][^>]*>\s*/gi, "")
}

/**
 * hreflang alternates, mirroring `alternateLinks()` in src/i18n/index.tsx: the
 * language lives in a query parameter here too, so the static head and the
 * hydrated one describe exactly the same set of URLs. The default locale owns
 * the bare path (and `x-default`), every other locale its own parameter.
 */
const DEFAULT_LOCALE = "de"
const LOCALES = ["de", "en"]
/** Folder of the legacy English shells: served via ?lang=en, never addressable. */
const VARIANT_DIR = "_i18n"
/** Prefix of the dedicated English site, mirroring EN_PREFIX in src/i18n. */
const EN_PREFIX = "/en"

/** URL of one page in one language: bare for German, `/en...` for English. */
function localizedPath(routePath, locale) {
  if (locale === DEFAULT_LOCALE) return routePath
  return routePath === "/" ? EN_PREFIX : `${EN_PREFIX}${routePath}`
}

/** Canonical URL of one variant: bare path by default, `/en...` for English. */
function canonicalUrl(routePath, locale) {
  return absoluteUrl(localizedPath(routePath, locale))
}

/**
 * File that serves one route.
 *
 * `inVariantFolder` is set for the non-default language of a *bilingual* route
 * (`?lang=en`). A CMS article is never stored there, whatever its language:
 * its translations live on their own slugs, so it keeps its own URL and the
 * `?lang=` variant rule does not apply to it.
 */
function variantFile(routePath, inVariantFolder) {
  return path.join(
    DIST,
    ...(inVariantFolder ? [VARIANT_DIR] : []),
    ...(routePath === "/" ? [] : routePath.replace(/^\//, "").split("/")),
    "index.html",
  )
}

function renderAlternates(routePath) {
  return [
    ...LOCALES.map(
      (locale) =>
        `<link rel="alternate" hreflang="${locale}" href="${escapeHtml(
          canonicalUrl(routePath, locale),
        )}" />`,
    ),
    `<link rel="alternate" hreflang="x-default" href="${escapeHtml(
      absoluteUrl(routePath),
    )}" />`,
  ].join("\n    ")
}

/**
 * Repo catalogues, so the fallback chrome (the links a crawler reads without
 * JavaScript) uses the same words as the application instead of a second copy.
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
  return typeof value === "string" ? value : key
}

/**
 * Marker carried by every tag this script injects, so the application can drop
 * the ones it replaces (the constant is duplicated in
 * `src/lib/prerenderedHead.ts`; the checker asserts it is present).
 */
const HEAD_MARKER = 'data-prerender-head="true"'

function renderHead({
  title,
  description,
  routePath,
  noindex = false,
  type = "website",
  image,
  jsonLd,
  /** Variant this file serves; drives `<html lang>`, canonical and og:locale. */
  locale = DEFAULT_LOCALE,
  /** Overrides the canonical URL (a CMS article owns its own path). */
  canonical = canonicalUrl(routePath, locale),
  /** Explicit alternates; defaults to the `?lang=` set of this app. */
  alternates,
  /** Locales the page is also published in (og:locale:alternate). */
  alternateLocales = LOCALES.filter((entry) => entry !== locale),
}) {
  const ogImage = image?.startsWith("http")
    ? image
    : `${BASE_URL}${image || "/og-image.png"}`
  const ogLocale = locale === "de" ? "de_DE" : "en_GB"
  const tags = [
    `<title ${HEAD_MARKER}>${escapeHtml(title)}</title>`,
    `<meta name="description" content="${escapeHtml(description)}" />`,
    `<meta name="robots" content="${noindex ? "noindex,nofollow" : "index,follow"}" />`,
    noindex ? "" : `<link rel="canonical" href="${escapeHtml(canonical)}" />`,
    noindex
      ? ""
      : alternates
        ? alternates
            .map(
              (entry) =>
                `<link rel="alternate" hreflang="${escapeHtml(
                  entry.hreflang,
                )}" href="${escapeHtml(entry.href)}" />`,
            )
            .join("\n    ")
        : renderAlternates(routePath),
    `<meta property="og:locale" content="${ogLocale}" />`,
    alternateLocales
      .map(
        (entry) =>
          `<meta property="og:locale:alternate" content="${
            entry === "de" ? "de_DE" : "en_GB"
          }" />`,
      )
      .join("\n    "),
    `<meta property="og:type" content="${type}" />`,
    `<meta property="og:site_name" content="Presence" />`,
    `<meta property="og:title" content="${escapeHtml(title)}" />`,
    `<meta property="og:description" content="${escapeHtml(description)}" />`,
    `<meta property="og:url" content="${escapeHtml(canonical)}" />`,
    `<meta property="og:image" content="${ogImage}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${escapeHtml(title)}" />`,
    `<meta name="twitter:description" content="${escapeHtml(description)}" />`,
    `<meta name="twitter:image" content="${ogImage}" />`,
    jsonLd
      ? `<script type="application/ld+json" ${HEAD_MARKER}>${JSON.stringify(
          jsonLd,
        ).replace(/<\//g, "<\\/")}</script>`
      : "",
  ]
  return tags.filter(Boolean).join("\n    ")
}

function renderFallback({
  title,
  description,
  routePath,
  locale = DEFAULT_LOCALE,
  extra = "",
  /** Machine-readable explanation of why this page is not pre-rendered. */
  marker = "",
}) {
  return `${marker ? `<!-- ${marker} -->` : ""}<main data-prerender="true" style="max-width:720px;margin:0 auto;padding:64px 24px;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#0f172a">
      <p style="font-weight:700;color:#4f46e5;margin:0 0 8px">Presence</p>
      <h1 style="font-size:32px;line-height:1.2;margin:0 0 16px">${escapeHtml(title)}</h1>
      <p style="font-size:17px;line-height:1.6;color:#475569;margin:0 0 24px">${escapeHtml(description)}</p>
      ${extra}
      <p style="font-size:14px;color:#64748b">
        <a href="${escapeHtml(localizedPath("/", locale))}" style="color:#4f46e5">${escapeHtml(copy(locale, "common.home"))}</a> ·
        <a href="${escapeHtml(localizedPath("/pricing", locale))}" style="color:#4f46e5">${escapeHtml(copy(locale, "nav.pricing"))}</a> ·
        <a href="${escapeHtml(localizedPath("/blog", locale))}" style="color:#4f46e5">${escapeHtml(copy(locale, "nav.blog"))}</a>
      </p>
      <p style="font-size:12px;color:#94a3b8">Path: ${escapeHtml(routePath)}</p>
    </main>`
}

/**
 * Marks the injected tags so the application can drop the ones it replaces.
 *
 * These tags are for clients that never run JavaScript. React 19 hoists the
 * head the app renders next to them instead of adopting them, so without this
 * attribute a hydrated page would publish two canonicals, two descriptions and
 * a title from the other language. `src/lib/prerenderedHead.ts` removes only
 * the pre-rendered tags that have an equivalent rendered by the app, and only
 * when the application says so (`data-prerender-head`, the same constant there).
 */
function markManaged(head) {
  return head.replace(
    /<(meta|link)\b([^>]*?)\s*\/>/g,
    `<$1$2 ${HEAD_MARKER} />`,
  )
}

function writePage(
  route,
  locale,
  headOptions,
  fallbackOptions,
  inVariantFolder = false,
  /** Complete HTML from the build-time React renderer, when available. */
  ssr = null,
) {
  let html = cleanHead(template)
  // The variant decides the document language, not the template default.
  html = html.replace(/<html lang="[^"]*"/, `<html lang="${locale}"`)
  html = html.replace(
    "</head>",
    `    ${markManaged(renderHead({ locale, ...headOptions }))}\n  </head>`,
  )

  const root = ssr
    ? `<div id="root" data-ssg="true">${ssr.html}</div>${
        ssr.blogData
          ? `<script type="application/json" id="__blog-data">${embedJson(
              ssr.blogData,
            )}</script>`
          : ""
      }`
    : `<div id="root">${renderFallback({ locale, ...fallbackOptions })}</div>`

  html = html.replace('<div id="root"></div>', root)

  const target = variantFile(route, inVariantFolder)
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, html)
}

// ---------------------------------------------------------------------------
// Blog articles: prerendered from the headless CMS when its URL is absolute
// and reachable at build time. There is no local fallback: if the CMS cannot
// be reached the blog pages are served by the SPA (see nginx /blog/ route).
// ---------------------------------------------------------------------------

/** `true` only for the two loopback addresses a local stack can publish. */
function isLoopbackAddress(address) {
  return address === "127.0.0.1" || address === "::1"
}

/**
 * Resolve the CMS host and return a loopback IP only when **every** address it
 * resolves to is loopback.
 *
 * Checking the URL string (`localhost`, `127.0.0.1`, `[::1]`) is not enough:
 * a hostname can resolve elsewhere through DNS or `/etc/hosts`, and the TLS
 * relaxation must never apply to a remote CMS. The caller connects to the
 * returned address (not to the hostname again), so the decision cannot change
 * between the check and the request.
 */
async function loopbackAddressFor(parsed) {
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "")
  if (net.isIP(hostname)) return isLoopbackAddress(hostname) ? hostname : null
  const addresses = await dns.lookup(hostname, {
    all: true,
    verbatim: true,
  })
  if (
    addresses.length === 0 ||
    !addresses.every(({ address }) => isLoopbackAddress(address))
  ) {
    return null
  }
  // Prefer IPv4: the local stack publishes its port on 127.0.0.1, while a
  // `localhost` entry may list `::1` first. Both are loopback and verified.
  const preferred = addresses.find(({ family }) => family === 4)
  return (preferred ?? addresses[0]).address
}

/**
 * Fetch JSON for the build.
 *
 * The local docker stack serves its CMS behind a self-signed certificate on
 * loopback; `fetch` refuses that certificate, so a developer build silently
 * lost every article. Verification is relaxed **only** when every resolved
 * address is loopback (where there is no remote peer to impersonate), and the
 * relaxation is logged so it can never pass unnoticed in CI. Any real CMS URL
 * keeps Node's default certificate verification.
 */
async function getJson(url, { timeoutMs = 10_000 } = {}) {
  const parsed = new URL(url)
  const loopback = await loopbackAddressFor(parsed)
  const client = parsed.protocol === "https:" ? https : http
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "")

  if (loopback) {
    console.warn(
      `[prerender] TLS verification disabled for loopback CMS ` +
        `${parsed.host} -> ${loopback} (self-signed local certificate).`,
    )
  }

  // Connect to the already-verified address; keep the original hostname for
  // SNI and the `Host` header. This prevents a second DNS answer from moving
  // the request to a non-loopback peer after the check.
  const options = loopback
    ? {
        host: loopback,
        port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
        path: `${parsed.pathname}${parsed.search}`,
        servername: hostname,
        headers: { Accept: "application/json", Host: parsed.host },
        rejectUnauthorized: false,
      }
    : parsed

  return new Promise((resolve, reject) => {
    const onResponse = (response) => {
      if (!response.statusCode || response.statusCode >= 400) {
        response.resume()
        reject(new Error(`HTTP ${response.statusCode}`))
        return
      }
      let body = ""
      response.setEncoding("utf8")
      response.on("data", (chunk) => {
        body += chunk
      })
      response.on("end", () => {
        try {
          resolve(JSON.parse(body))
        } catch (error) {
          reject(new Error(`invalid JSON (${error.message})`))
        }
      })
    }
    // `(url, options, callback)` for a normal remote CMS; a pre-connected
    // option object when the loopback address was already verified above.
    const request = loopback
      ? client.get(options, onResponse)
      : client.get(parsed, { headers: { Accept: "application/json" } }, onResponse)
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`timed out after ${timeoutMs}ms`))
    })
    request.on("error", reject)
  })
}

async function loadWpPosts() {
  // `PRERENDER_WP_API_URL` is a build-only override: Docker builds cannot
  // resolve the Compose `wordpress` service, so they point this at the
  // loopback-published CMS while the browser keeps the same-origin `/cms`.
  const wp = (ENV.PRERENDER_WP_API_URL || ENV.VITE_WP_API_URL)
    ?.trim()
    .replace(/\/+$/, "")
  if (!wp) {
    console.warn(
      "[prerender] VITE_WP_API_URL is empty — blog articles will be client-rendered.",
    )
    return { posts: [], ok: false }
  }
  /**
   * Same-origin CMS (`/cms`) on a loopback build: resolve it against the local
   * origin so a developer build still pre-renders the real articles. Any other
   * same-origin value cannot be fetched at build time without hitting a site
   * that is not deployed yet, so it keeps the documented client-rendered
   * fallback.
   */
  let apiBase = wp
  if (!/^https?:\/\//.test(wp)) {
    const local = /^(https?:\/\/)(localhost|127\.0\.0\.1)(:\d+)?$/.exec(BASE_URL)
    if (!local) {
      console.warn(
        `[prerender] VITE_WP_API_URL=${wp} is a same-origin path and cannot be fetched at build time — blog articles will be client-rendered.`,
      )
      return { posts: [], ok: false }
    }
    apiBase = `${BASE_URL}${wp.startsWith("/") ? "" : "/"}${wp}`
  }
  const api = apiBase.endsWith("/wp-json")
    ? `${apiBase}/wp/v2`
    : `${apiBase}/wp-json/wp/v2`
  try {
    const posts = await getJson(
      `${api}/posts?per_page=100&_embed=1&orderby=date&order=desc`,
    )
    if (!Array.isArray(posts)) throw new Error("unexpected payload")
    const mapped = posts.map((post) => {
      const terms = (post._embedded?.["wp:term"] || []).flat()
      const category =
        terms.find((term) => term.taxonomy === "category")?.name || "Blog"
      return {
        slug: post.slug,
        title: stripHtml(post.title?.rendered || post.slug),
        excerpt: stripHtml(post.excerpt?.rendered || ""),
        date: (post.date || "").slice(0, 10),
        category,
        contentHtml: post.content?.rendered || "",
        author: post._embedded?.author?.[0]?.name || "Presence Team",
        image: post._embedded?.["wp:featuredmedia"]?.[0]?.source_url,
        // Fields added by wordpress/mu-plugins/presence-i18n.php; the same
        // defaults as src/api/blog.ts, so the shell and the hydrated head
        // describe an article the same way.
        lang: post.presence_lang?.code === "de" ? "de" : "en",
        translations: (post.presence_translations ?? [])
          .filter((entry) => entry.slug && entry.lang)
          .map((entry) => ({ lang: String(entry.lang), slug: String(entry.slug) })),
        source: "wordpress",
        // Shape expected by src/api/blog.ts when the same objects are embedded
        // for the blog index. Computed here exactly like readingTime() there.
        readTime: `${Math.max(
          1,
          Math.ceil(
            stripHtml(post.content?.rendered || post.excerpt?.rendered || "")
              .split(/\s+/)
              .filter(Boolean).length / 200,
          ),
        )} min`,
        related: [],
      }
    })
    return { posts: mapped, ok: true }
  } catch (error) {
    console.warn(
      `[prerender] WordPress unreachable (${error.message}) — blog articles will be client-rendered.`,
    )
    return { posts: [], ok: false }
  }
}

const { posts, ok: postsLoaded } = await loadWpPosts()

// ---------------------------------------------------------------------------
// Public routes
// ---------------------------------------------------------------------------

/**
 * Title and description of one route in one language. English is the
 * reference pair in routes.json, the German fields are the `…De` siblings.
 */
function routeCopy(route, locale) {
  return locale === DEFAULT_LOCALE
    ? {
        title: route.titleDe || route.title,
        description: route.descriptionDe || route.description,
      }
    : { title: route.title, description: route.description }
}

let ssgPages = 0
/** `?lang=en` shells written to `_i18n/` — noindex routes only. */
let privateShells = 0
let blogSsgUnavailable = false

for (const route of routes) {
  // `noindex` routes keep the existing lightweight shell: they are forms and
  // private entry points, they never appear in search results, and the app
  // replaces the shell with `createRoot` exactly as before. The blog index is
  // rendered only when its data really exists; an empty list pretending to be
  // the blog would be worse than the documented SPA fallback.
  const canRenderSsr =
    !route.noindex && (route.path !== "/blog" || postsLoaded)
  if (!canRenderSsr && route.path === "/blog") blogSsgUnavailable = true

  for (const locale of LOCALES) {
    const { title, description } = routeCopy(route, locale)
    const jsonLd =
      route.path === "/"
        ? {
            "@context": "https://schema.org",
            "@type": "WebSite",
            name: "Presence",
            url: `${BASE_URL}/`,
            description,
          }
        : route.path === "/pricing"
          ? {
              "@context": "https://schema.org",
              "@type": "Product",
              name: "Presence Website Monitoring",
              offers: [0, 9, 29, 79].map((price, index) => ({
                "@type": "Offer",
                name: ["Free", "Pro", "Business", "Agency"][index],
                price: String(price),
                priceCurrency: "EUR",
              })),
            }
          : undefined

    const blogData =
      route.path === "/blog"
        ? {
            locale,
            posts: posts.filter((post) => post.lang === locale),
          }
        : null
    /** Canonical URL of this language: `/pricing` or `/en/pricing`. */
    const urlPath = localizedPath(route.path, locale)

    // `head` always receives the *bare* route: canonical and hreflang are
    // derived from it for the current locale, so the `/en` file and its
    // `?lang=en` alias publish the same canonical URL instead of a doubly
    // prefixed one.
    const head = () => ({
      title,
      description,
      routePath: route.path,
      noindex: Boolean(route.noindex),
      type: "website",
      jsonLd,
    })
    const fallback = (path) => ({
      title,
      description,
      routePath: path,
      // Only the blog index can be data-dependent. Say *why* it is a shell
      // instead of pretending a pre-rendered page exists; check-seo-build
      // accepts this marker and reports it as a warning.
      marker:
        route.path === "/blog" && !postsLoaded
          ? "ssg:blog-fallback cms-unavailable"
          : "",
    })

    /**
     * Render the file that serves `pathname`. The StaticRouter sees the exact
     * URL of the file — the canonical `/en/...` page or the historical
     * `?lang=en` alias — so anything reading `useLocation` matches the document
     * the browser will hydrate on that URL.
     */
    const render = async (pathname, search) => {
      if (!canRenderSsr) return null
      try {
        const html = await renderRoute(pathname, locale, {
          blogData,
          url: { pathname, search },
        })
        ssgPages += 1
        return { html, blogData }
      } catch (error) {
        console.error(
          `[prerender] SSG failed for ${pathname} (${locale}):`,
          error instanceof Error ? error.message : error,
        )
        process.exit(1)
      }
    }

    if (route.noindex) {
      // Noindex screens are language-agnostic entry points: German keeps the
      // bare path, English only the historical `?lang=en` shell in `_i18n/`
      // (no redirect for them: `/en/login` does not exist). Mounting a second
      // URL would add indexable surface nothing asks for.
      writePage(
        route.path,
        locale,
        head(),
        fallback(route.path),
        locale !== DEFAULT_LOCALE,
        null,
      )
      if (locale !== DEFAULT_LOCALE) privateShells += 1
      continue
    }

    // Canonical file: `<route>/index.html` (German) or `en/<route>/index.html`.
    // No `_i18n` copy: nginx answers `?lang=en` with a 301 before try_files,
    // so the file would only be dead weight in the image.
    const ssg = await render(urlPath, "")
    writePage(urlPath, locale, head(), fallback(urlPath), false, ssg)
  }
}

for (const post of posts) {
  const routePath = `/blog/${post.slug}`
  // An article exists in one language under this URL; its translations live on
  // their own slugs, exactly like `alternates` in src/pages/BlogArticle.tsx.
  // No `?lang=` variant is advertised for an article, and it is never written
  // into `_i18n`.
  const alternates = [
    { hreflang: post.lang, href: absoluteUrl(routePath) },
    ...post.translations.map((translation) => ({
      hreflang: translation.lang,
      href: absoluteUrl(`/blog/${translation.slug}`),
    })),
  ]
  writePage(
    routePath,
    post.lang,
    {
      title: `${post.title} | Presence Blog`,
      description: post.excerpt,
      routePath,
      type: "article",
      image: post.image,
      canonical: absoluteUrl(routePath),
      alternates,
      alternateLocales: post.translations.map((translation) => translation.lang),
      jsonLd: {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        headline: post.title,
        description: post.excerpt,
        datePublished: post.date,
        author: { "@type": "Organization", name: post.author || "Presence Team" },
        publisher: { "@type": "Organization", name: "Presence" },
        mainEntityOfPage: { "@type": "WebPage", "@id": absoluteUrl(routePath) },
      },
    },
    {
      title: post.title,
      description: post.excerpt,
      routePath,
      extra: `<p style="font-size:13px;color:#94a3b8;margin:0 0 16px">${escapeHtml(
        post.category,
      )} · ${escapeHtml(post.date)}</p><article>${post.contentHtml}</article>`,
    },
  )
}

// Real 404 page (served by nginx with an actual 404 status). It stays in the
// default language: the SPA replaces it with the localized NotFound page, and
// an error page has no language variant to advertise.
writePage(
  "/404",
  DEFAULT_LOCALE,
  {
    title: "Seite nicht gefunden | Presence",
    description: "Die aufgerufene Seite existiert nicht.",
    routePath: "/404",
    noindex: true,
  },
  {
    title: "Seite nicht gefunden",
    description: "Die aufgerufene Seite existiert nicht oder wurde verschoben.",
    routePath: "/404",
  },
)
fs.copyFileSync(
  path.join(DIST, "404", "index.html"),
  path.join(DIST, "404.html"),
)
// The /404 URL itself must not be a browseable 200 page.
fs.rmSync(path.join(DIST, "404"), { recursive: true, force: true })

// ---------------------------------------------------------------------------
// sitemap.xml / robots.txt
// ---------------------------------------------------------------------------

const today = new Date().toISOString().slice(0, 10)
/**
 * One entry per language: the German bare path, the English `/en` path, and
 * the CMS articles whose translations have their own slugs. The legacy
 * `?lang=en` aliases never appear here — a sitemap lists canonical URLs only.
 */
const sitemapRoutes = [
  ...routes
    .filter((route) => !route.noindex)
    .flatMap((route) =>
      LOCALES.map((locale) => ({
        ...route,
        path: localizedPath(route.path, locale),
      })),
    ),
  ...posts.map((post) => ({
    path: `/blog/${post.slug}`,
    title: post.title,
    date: post.date,
    priority: "0.6",
    changefreq: "monthly",
  })),
]

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemapRoutes
  .map(
    (route) => `  <url>
    <loc>${escapeXml(absoluteUrl(route.path))}</loc>
    <lastmod>${escapeXml(route.date || today)}</lastmod>
    <changefreq>${route.changefreq || "monthly"}</changefreq>
    <priority>${route.priority || "0.5"}</priority>
  </url>`,
  )
  .join("\n")}
</urlset>
`
fs.writeFileSync(path.join(DIST, "sitemap.xml"), sitemap)

const robots = `User-agent: *
Allow: /

# Private application routes
Disallow: /app/
Disallow: /settings/
Disallow: /login
Disallow: /register
Disallow: /forgot-password
Disallow: /reset-password
Disallow: /onboarding
Disallow: /admin
Disallow: /verify-email
Disallow: /report/

Sitemap: ${absoluteUrl("/sitemap.xml")}
`
fs.writeFileSync(path.join(DIST, "robots.txt"), robots)

console.log(
  `[prerender] ${routes.length} routes × ${LOCALES.length} languages ` +
    `(${ssgPages} SSG pages + ${privateShells} private ?lang=en shells) + ` +
    `${posts.length} articles, sitemap ${sitemapRoutes.length} URLs, base=${BASE_URL}` +
    (postsLoaded
      ? ""
      : " — CMS unreachable: blog articles are served by the SPA at build time.") +
    (!postsLoaded && blogSsgUnavailable
      ? " Blog index keeps its fallback shell."
      : ""),
)
