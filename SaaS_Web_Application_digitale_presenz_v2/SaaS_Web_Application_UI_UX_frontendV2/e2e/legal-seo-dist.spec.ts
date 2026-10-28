import { readFileSync } from "node:fs"
import path from "node:path"
import { expect, test, type APIRequestContext, type Page } from "@playwright/test"
import {
  DIST,
  ROOT,
  canonicalOf,
  isFile,
  message,
  resolveNginx,
  startDistServer,
} from "./helpers/static-dist"

/**
 * SEO of the *deployed artifact*, not of the dev server.
 *
 * `pnpm build` pre-renders one `index.html` per public route, per language, and
 * nginx serves those files directly. The dev server used by the other specs
 * answers every path with the SPA shell, so a public route that was never
 * pre-rendered looks fine locally and returns a hard 404 in production. That is
 * exactly what happened to `/impressum` and `/cookies` before this spec existed.
 *
 * This spec serves `dist/` itself with the resolution rules of `nginx.conf`
 * (see `helpers/static-dist.ts`) and checks:
 *   1. every legal route returns 200 with its own pre-rendered head (title,
 *      description, canonical, hreflang de/en/x-default, robots, og:locale),
 *   2. the built bundle hydrates that shell and renders the German page, and
 *      `?lang=en` renders the English one,
 *   3. no asset of the page 404s,
 *   4. sitemap.xml lists the legal URLs and no private route, robots.txt keeps
 *      pointing at it,
 *   5. the client-rendered exceptions (`/app/…`) and the real 404 still behave.
 *
 * `pnpm build` must have run first: the spec fails with that instruction rather
 * than skipping, because a skip would report a green suite while verifying
 * nothing. `/api/…` answers 401 like Django does for an anonymous visitor, so
 * the checks do not depend on the Docker stack.
 */

interface SeoRoute {
  path: string
  title: string
  description: string
  titleDe: string
  descriptionDe: string
  noindex?: boolean
}

/** Marker on the pre-rendered head tags; see src/lib/prerenderedHead.ts. */
const HEAD_MARKER = 'data-prerender-head="true"'

const ROUTES: SeoRoute[] = JSON.parse(
  readFileSync(path.join(ROOT, "src", "seo", "routes.json"), "utf8"),
)

/** Legal pages that must be reachable as pre-rendered files. */
const LEGAL_ROUTES = [
  "/impressum",
  "/cookies",
  "/privacy",
  "/terms",
  "/widerruf",
] as const

let origin = ""
let stop: (() => Promise<void>) | undefined

test.beforeAll(async () => {
  const server = await startDistServer()
  origin = server.origin
  stop = server.close
})

test.afterAll(async () => {
  await stop?.()
})

async function html(request: APIRequestContext, routePath: string) {
  const response = await request.get(`${origin}${routePath}`)
  return { response, body: await response.text() }
}

/** Absolute canonical/alternate of the built shell, whatever origin it used. */
function originOf(body: string): string {
  const canonical = body.match(/<link rel="canonical" href="([^"]+)"/)?.[1]
  expect(canonical, "the shell has no canonical link").toBeTruthy()
  return new URL(canonical!).origin
}

/** One URL per language: German keeps the bare path, English lives under /en. */
function localizedPath(routePath: string, locale: "de" | "en") {
  if (locale === "de") return routePath
  return routePath === "/" ? "/en" : `/en${routePath}`
}

async function assertPrerenderedLegalRoute(
  request: APIRequestContext,
  routePath: string,
) {
  const route = ROUTES.find((entry) => entry.path === routePath)
  expect(route, `routes.json has no entry for ${routePath}`).toBeTruthy()

  // The bare path is the German page, `/en…` the English one. The historical
  // `?lang=en` URL now answers a 301, checked at the end.
  const german = await html(request, routePath)
  const english = await html(request, localizedPath(routePath, "en"))
  const englishPath = localizedPath(routePath, "en")

  expect(german.response.status(), `${routePath} is not served by nginx`).toBe(200)
  expect(english.response.status(), `${englishPath} is not served`).toBe(200)
  expect(german.response.headers()["content-type"]).toContain("text/html")
  expect(english.response.headers()["content-type"]).toContain("text/html")

  for (const [locale, body] of [
    ["de", german.body],
    ["en", english.body],
  ] as const) {
    const where = localizedPath(routePath, locale)
    // Exactly one title, in the language of the variant.
    expect(
      [...body.matchAll(/<title[^>]*>([\s\S]*?)<\/title>/g)],
      `${where}: expected exactly one <title>`,
    ).toHaveLength(1)
    expect(body).toContain(
      `<title ${HEAD_MARKER}>${locale === "de" ? route!.titleDe : route!.title}</title>`,
    )
    expect(body).toContain('<meta name="robots" content="index,follow"')
    expect(body).toContain(`<html lang="${locale}"`)
    expect(body).toContain(
      `<meta property="og:locale" content="${locale === "de" ? "de_DE" : "en_GB"}"`,
    )

    // `data-prerender-head` marks the tag as coming from the shell, so the app
    // drops it once it rendered its own (checked in
    // bilingual-shell-dist.spec.ts).
    const pageOrigin = originOf(body)
    expect(body).toContain(
      `<link rel="canonical" href="${pageOrigin}${localizedPath(routePath, locale)}" ${HEAD_MARKER} />`,
    )
    for (const [lang, expected] of [
      ["de", routePath],
      ["en", englishPath],
      ["x-default", routePath],
    ] as const) {
      expect(
        body,
        `${where} does not advertise hreflang ${lang}`,
      ).toContain(
        `<link rel="alternate" hreflang="${lang}" href="${pageOrigin}${expected}" ${HEAD_MARKER} />`,
      )
    }
  }

  // `?lang=en` is no longer a URL: nginx answers 301 to the canonical `/en`
  // page. The assertion checks the exact status and Location, then follows the
  // redirect to prove the destination serves the English document.
  const redirect = await request.get(`${origin}${routePath}?lang=en`, {
    maxRedirects: 0,
  })
  expect(
    redirect.status(),
    `${routePath}?lang=en is not a 301`,
  ).toBe(301)
  expect(redirect.headers()["location"], `${routePath}?lang=en: Location`).toBe(
    `${origin}${englishPath}`,
  )
  const alias = await html(request, `${routePath}?lang=en`)
  expect(
    new URL(alias.response.url()).pathname,
    `${routePath}?lang=en did not land on ${englishPath}`,
  ).toBe(englishPath)
  expect(alias.response.status(), `${routePath}?lang=en is not served`).toBe(200)
  expect(alias.body).toContain('<html lang="en"')
  expect(canonicalOf(alias.body)).toBe(
    `${originOf(alias.body)}${englishPath}`,
  )
}

async function assertHydratesInLanguage(
  page: Page,
  routePath: string,
  locale: "de" | "en",
) {
  const failedAssets: string[] = []
  const pageErrors: string[] = []
  const onResponse = (response: import("@playwright/test").Response) => {
    if (
      response.status() >= 400 &&
      new URL(response.url()).pathname.startsWith("/assets/")
    ) {
      failedAssets.push(`${response.status()} ${response.url()}`)
    }
  }
  const onPageError = (error: Error) => pageErrors.push(error.message)
  page.on("response", onResponse)
  page.on("pageerror", onPageError)

  // Each language has its own URL, and that URL decides the language, so both
  // runs stay deterministic whatever an earlier navigation left in storage.
  const url = localizedPath(routePath, locale)
  const navigation = await page.goto(`${origin}${url}`)
  // Without this the SPA would happily render the page from its 404 shell and
  // hide the fact that nginx answered 404 to crawlers.
  expect(
    navigation?.status(),
    `${routePath} is not served by nginx`,
  ).toBe(200)
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    message(locale, routeH1Key(routePath)),
  )
  await expect(page.locator("html")).toHaveAttribute("lang", locale)
  // The static fallback is replaced by the rendered application.
  await expect(page.locator('[data-prerender="true"]')).toHaveCount(0)

  page.off("response", onResponse)
  page.off("pageerror", onPageError)
  expect(failedAssets, `assets that failed to load: ${failedAssets.join(", ")}`).toEqual([])
  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
}

function routeH1Key(routePath: string) {
  switch (routePath) {
    case "/impressum":
      return "legal.impressumTitle"
    case "/cookies":
      return "legal.cookiesTitle"
    case "/privacy":
      return "legal.privacyTitle"
    case "/terms":
      return "legal.termsTitle"
    default:
      return "legal.withdrawalTitle"
  }
}

test("nginx-served legal pages carry their own pre-rendered head in both languages", async ({
  request,
}) => {
  for (const routePath of LEGAL_ROUTES) {
    await assertPrerenderedLegalRoute(request, routePath)
  }
})

test("the pre-rendered legal pages hydrate in German and in English", async ({
  page,
}) => {
  test.setTimeout(240_000)
  for (const routePath of LEGAL_ROUTES) {
    await assertHydratesInLanguage(page, routePath, "de")
    await assertHydratesInLanguage(page, routePath, "en")
  }
})

test("sitemap.xml advertises the legal pages and no private route", async ({
  request,
}) => {
  const response = await request.get(`${origin}/sitemap.xml`)
  expect(response.status()).toBe(200)
  const xml = await response.text()
  const locs = [...xml.matchAll(/<loc>([^<]*)<\/loc>/g)].map(
    (match) => match[1],
  )
  const paths = locs.map((loc) => new URL(loc).pathname)

  for (const routePath of LEGAL_ROUTES) {
    expect(paths, `sitemap is missing ${routePath}`).toContain(routePath)
    expect(
      paths,
      `sitemap is missing the English ${routePath}`,
    ).toContain(localizedPath(routePath, "en"))
  }
  for (const path of paths) {
    expect(
      path,
      `internal variant folder advertised in the sitemap: ${path}`,
    ).not.toContain("/_i18n/")
  }
  for (const privatePath of [
    "/login",
    "/register",
    "/onboarding",
    "/admin",
    "/verify-email",
  ]) {
    expect(
      paths,
      `sitemap advertises the private route ${privatePath}`,
    ).not.toContain(privatePath)
  }
  for (const loc of locs) {
    expect(loc, `query string in the sitemap: ${loc}`).not.toContain("?")
  }

  // Every advertised URL must be served, otherwise the sitemap reports a 404.
  for (const loc of locs) {
    const routePath = new URL(loc).pathname
    const page = await request.get(`${origin}${routePath}`)
    expect(page.status(), `${loc} is advertised but not served`).toBe(200)
  }
})

test("robots.txt protects the private routes and points at the sitemap", async ({
  request,
}) => {
  const response = await request.get(`${origin}/robots.txt`)
  expect(response.status()).toBe(200)
  const robots = await response.text()
  expect(robots).toContain("Disallow: /app/")
  expect(robots).toContain("Disallow: /login")
  expect(robots).toMatch(/Sitemap: https?:\/\/\S+\/sitemap\.xml/)
})

test("client-rendered exceptions and the real 404 still behave", async ({
  request,
}) => {
  // Private application route: the SPA shell, not a 404.
  const app = await request.get(`${origin}/app/dashboard`)
  expect(app.status()).toBe(200)

  // Public route that was never pre-rendered: nginx must answer a real 404
  // instead of a soft-404 shell.
  const unknown = await request.get(`${origin}/definitely-not-a-page`)
  expect(unknown.status()).toBe(404)
})

test("the language variant folder is not a URL of its own", async ({
  request,
}) => {
  // The English shells live outside the public URL space; only the `?lang=en`
  // resolution of the public routes reaches them (mirrors `internal`).
  expect(resolveNginx("/_i18n/pricing/index.html")).toBeNull()
  expect(isFile(path.join(DIST, "index.html"))).toBe(true)

  for (const routePath of ["/_i18n/pricing/index.html", "/_i18n/index.html"]) {
    const response = await request.get(`${origin}${routePath}`)
    expect(
      response.status(),
      `${routePath} must not be a browseable page`,
    ).toBe(404)
  }
})
