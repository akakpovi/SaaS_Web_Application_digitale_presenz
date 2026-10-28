import { createServer, type Server, type ServerResponse } from "node:http"
import { existsSync, readFileSync, statSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect } from "@playwright/test"
import { PUBLIC_PATHS } from "../../src/seo/publicPaths"

/**
 * Serves the *built* frontend the way nginx does.
 *
 * The dev server answers every path with the SPA shell, so a route that was
 * never pre-rendered — or a language variant that was never written — looks
 * fine locally and fails in production. These helpers replay the rules of
 * `nginx.conf`:
 *
 *   if ($presence_locale_redirect != "") { return 301 $presence_locale_redirect; }
 *   location / { try_files $html_variant$uri/index.html $uri/index.html $uri =404; }
 *   location /_i18n/ { internal; }
 *
 * The 301 comes first: `?lang=` on a public route is no longer a URL (the map
 * is generated from src/seo/publicPaths.ts). `$html_variant` therefore only
 * applies to the five noindex screens, which have no public English URL and
 * keep their `_i18n` shell. `pnpm build` (vite + prerender +
 * scripts/check-seo-build.mjs) must have run, or the specs fail with that
 * instruction instead of skipping.
 */

export const ROOT = fileURLToPath(new URL("../..", import.meta.url))
export const DIST = path.join(ROOT, "dist")

/** Folder of the non-default shells; `internal` in nginx.conf. */
export const VARIANT_DIR = "_i18n"

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".xml": "application/xml; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".webmanifest": "application/manifest+json",
}

const NOT_FOUND = JSON.stringify({ detail: "Not Found" })

export function isFile(target: string) {
  return existsSync(target) && statSync(target).isFile()
}

function sendFile(response: ServerResponse, file: string, status = 200) {
  response.writeHead(status, {
    "Content-Type": MIME[path.extname(file)] ?? "application/octet-stream",
  })
  response.end(readFileSync(file))
}

const distFile = (...segments: string[]) => path.join(DIST, ...segments)
const distPath = (value: string) => distFile(value.replace(/^\//, ""))

/**
 * Mirrors the `try_files` rules of nginx.conf. Returns the file nginx would
 * serve, or `null` for its `=404` branch. The query string matters: it selects
 * the language variant.
 */
/** What nginx answers for one request URI, exactly as the config does. */
export type NginxResolution =
  | { status: 200; file: string }
  | { status: 301; location: string }
  | { status: 404 }

/** English URL of a public route, mirroring `localizedPath()` in src/i18n. */
function englishUrl(routePath: string): string {
  return routePath === "/" ? "/en" : `/en${routePath}`
}

/**
 * Mirrors `map $args $presence_locale_query`: drop the `lang` token, keep every
 * other parameter in its original order, `?` only when something remains.
 */
function remainingQuery(args: string): string {
  if (!args) return ""
  // `~*` in the generated map: case-insensitive, like nginx.
  if (/^lang=(?:en|de)$/i.test(args)) return ""
  let match = args.match(/^lang=(?:en|de)&(.+)$/i)
  if (match) return `?${match[1]}`
  match = args.match(/^(.+)&lang=(?:en|de)&(.+)$/i)
  if (match) return `?${match[1]}&${match[2]}`
  match = args.match(/^(.+)&lang=(?:en|de)$/i)
  if (match) return `?${match[1]}`
  return ""
}

/** Exact keys of the generated map; `isPublicRoutePath()` normalises a
 * trailing slash, the map does not, so membership is tested verbatim. */
const PUBLIC_PATH_SET: ReadonlySet<string> = new Set(PUBLIC_PATHS)

/**
 * The generated map decides before any location: a public route answers 301
 * for `?lang=en` (to `/en/...`) and for `?lang=de` (to the bare path). The
 * five noindex screens are absent from the map and keep their 200 shell.
 */
export function nginxResolution(uriWithQuery: string): NginxResolution {
  const [rawUri, query = ""] = uriWithQuery.split("?")
  const uri = path.posix.normalize(rawUri)
  // `map` matches its keys case-insensitively (`?lang=EN` redirects).
  const lang = new URLSearchParams(query).get("lang")?.toLowerCase()
  if (PUBLIC_PATH_SET.has(uri) && (lang === "en" || lang === "de")) {
    return {
      status: 301,
      location: `${lang === "en" ? englishUrl(uri) : uri}${remainingQuery(query)}`,
    }
  }

  const variant = lang === "en" ? `/${VARIANT_DIR}` : ""

  // location /_i18n/ { internal; } — addressable internally, 404 externally.
  if (uri.startsWith(`/${VARIANT_DIR}/`)) return { status: 404 }
  if (
    uri === "/settings/integrations" ||
    uri === "/verify-email" ||
    uri === "/admin"
  ) {
    return isFile(distFile("index.html"))
      ? { status: 200, file: distFile("index.html") }
      : { status: 404 }
  }
  if (uri.startsWith("/app/") || uri.startsWith("/report/") || uri.startsWith("/scan/")) {
    return {
      status: 200,
      file: isFile(distPath(uri)) ? distPath(uri) : distFile("index.html"),
    }
  }
  // `location /blog/` keeps no language variant: an article is written in one
  // language and its translations live on their own slugs.
  if (uri.startsWith("/blog/")) {
    return {
      status: 200,
      file: isFile(distPath(`${uri}/index.html`))
        ? distPath(`${uri}/index.html`)
        : distFile("index.html"),
    }
  }
  // location /
  if (isFile(distPath(`${variant}${uri}/index.html`))) {
    return { status: 200, file: distPath(`${variant}${uri}/index.html`) }
  }
  if (isFile(distPath(`${uri}/index.html`))) {
    return { status: 200, file: distPath(`${uri}/index.html`) }
  }
  if (isFile(distPath(uri))) return { status: 200, file: distPath(uri) }
  return { status: 404 }
}

/**
 * File nginx would serve (200), or `null` for a redirect or a 404. Kept for
 * assertions about what a URL resolves to; use `nginxResolution()` when the
 * status itself matters.
 */
export function resolveNginx(uriWithQuery: string): string | null {
  const resolution = nginxResolution(uriWithQuery)
  return resolution.status === 200 ? resolution.file : null
}

export interface DistServer {
  origin: string
  close: () => Promise<void>
}

/**
 * Static server for `dist/`. `/api/…` answers 401 like Django does for an
 * anonymous visitor and `/cms/…` 404s, so the pages render without the Docker
 * stack.
 */
export async function startDistServer(): Promise<DistServer> {
  if (!isFile(distFile("index.html"))) {
    throw new Error(
      "dist/index.html is missing — run `pnpm build` before `pnpm test:e2e` " +
        "(the SEO checks verify the artifact that nginx serves).",
    )
  }

  const server: Server = createServer((request, response) => {
    const uri = new URL(request.url ?? "/", "http://localhost").pathname

    if (uri.startsWith("/api/")) {
      response.writeHead(401, { "Content-Type": MIME[".json"] })
      response.end(JSON.stringify({ detail: "Unauthorized" }))
      return
    }
    if (uri.startsWith("/cms")) {
      response.writeHead(404, { "Content-Type": MIME[".json"] })
      response.end(NOT_FOUND)
      return
    }

    const resolution = nginxResolution(request.url ?? "/")
    if (resolution.status === 301) {
      // nginx sends an absolute URL built from the requested host and port
      // (`$scheme://$http_host$uri`), so the browser keeps the port it used.
      response.writeHead(301, {
        Location: `http://${request.headers.host ?? "127.0.0.1"}${resolution.location}`,
      })
      response.end()
      return
    }
    const file = resolution.status === 200 ? resolution.file : null
    if (!file) {
      const notFoundPage = distFile("404.html")
      if (isFile(notFoundPage)) {
        sendFile(response, notFoundPage, 404)
      } else {
        response.writeHead(404, { "Content-Type": MIME[".json"] })
        response.end(NOT_FOUND)
      }
      return
    }
    sendFile(response, file)
  })

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve))
  const address = server.address()
  if (typeof address === "string" || address === null) {
    throw new Error("could not determine the static server port")
  }

  return {
    origin: `http://127.0.0.1:${address.port}`,
    close: () =>
      new Promise<void>((resolve) => server.close(() => resolve())),
  }
}

/* ── Catalogues: assertions read the app copy instead of hard-coding it ───── */

function loadCatalog(locale: "de" | "en") {
  return JSON.parse(
    readFileSync(path.join(ROOT, "src", "i18n", `${locale}.json`), "utf8"),
  ) as Record<string, unknown>
}

export function message(locale: "de" | "en", key: string): string {
  const value = key
    .split(".")
    .reduce<unknown>(
      (node, part) =>
        typeof node === "object" && node !== null
          ? (node as Record<string, unknown>)[part]
          : undefined,
      loadCatalog(locale),
    )
  expect(typeof value, `${locale}.json is missing ${key}`).toBe("string")
  return value as string
}

/* ── Raw HTML helpers (no browser involved) ──────────────────────────────── */

export function headOf(html: string, pattern: RegExp): string | null {
  const match = html.match(pattern)
  return match ? match[1] : null
}

export function allOf(html: string, pattern: RegExp): string[][] {
  return [...html.matchAll(pattern)].map((match) =>
    match.slice(1).map((value) =>
      value
        .replace(/&quot;/g, '"')
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&amp;/g, "&"),
    ),
  )
}

export function canonicalOf(html: string): string | null {
  return headOf(html, /<link rel="canonical" href="([^"]+)"/)
}

export function alternatesOf(html: string): { hreflang: string; href: string }[] {
  return allOf(html, /<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"/g).map(
    ([hreflang, href]) => ({ hreflang, href }),
  )
}
