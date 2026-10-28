import { readFileSync, readdirSync } from "node:fs"
import path from "node:path"
import { expect, test, type APIRequestContext } from "@playwright/test"
import {
  DIST,
  ROOT,
  canonicalOf,
  message,
  resolveNginx,
  startDistServer,
} from "./helpers/static-dist"

/**
 * The dedicated English URLs, against the *deployed artifact*.
 *
 * Lot 2 mounts the public site under `/en` and pre-renders one complete page per
 * URL. This spec proves the three things a URL migration can silently break:
 *
 *   1. an `/en` URL ships the real English page (pricing table, FAQ answers,
 *      legal draft notice), not a translated `<title>` over German markup,
 *   2. the sitemap lists every canonical URL in both languages — and neither
 *      the legacy `?lang=en` form nor the internal `_i18n/` folder,
 *   3. a browser opening `/en/...` hydrates that page, keeps the address and
 *      publishes the matching canonical.
 *
 * `pnpm build` must have run first (the suite fails with that instruction
 * instead of skipping).
 */

interface SeoRoute {
  path: string
  noindex?: boolean
}

const ROUTES: SeoRoute[] = JSON.parse(
  readFileSync(path.join(ROOT, "src", "seo", "routes.json"), "utf8"),
)
const PUBLIC_ROUTES = ROUTES.filter((route) => !route.noindex)

/** URL of one page in one language: German bare, English under `/en`. */
function localizedPath(routePath: string, locale: "de" | "en") {
  if (locale === "de") return routePath
  return routePath === "/" ? "/en" : `/en${routePath}`
}

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

async function fetchHtml(request: APIRequestContext, url: string) {
  const response = await request.get(`${origin}${url}`)
  return { status: response.status(), body: await response.text() }
}

test("the /en URLs ship the real English page, not a translated title", async ({
  request,
}) => {
  // Landing: the call-to-action copy, not only a `<h1>`.
  const home = await fetchHtml(request, "/en")
  expect(home.status, "/en is not served").toBe(200)
  expect(home.body).toContain('<html lang="en"')
  // React splits the headline around its highlighted span, so the two halves
  // are contiguous text nodes rather than one string in the raw HTML.
  expect(home.body).toContain("Your digital presence,")
  expect(home.body).toContain("always under control.")
  expect(home.body).toContain("No credit card required")
  expect(
    home.body,
    "/en still carries the German landing copy",
  ).not.toContain("Keine Kreditkarte erforderlich")

  // Pricing: every plan and its price from the component, not a placeholder.
  const pricing = await fetchHtml(request, "/en/pricing")
  expect(pricing.status, "/en/pricing is not served").toBe(200)
  expect(pricing.body).toContain(`<title data-prerender-head="true">Simple Website Monitoring Pricing | Presence</title>`)
  for (const plan of ["Free", "Pro", "Business", "Agency"]) {
    expect(pricing.body, `/en/pricing has no ${plan} plan`).toContain(plan)
  }
  for (const price of ["€9", "€29", "€79"]) {
    expect(pricing.body, `/en/pricing has no ${price} price`).toContain(price)
  }

  // FAQ: a real question *and* its answer are in the raw HTML.
  const faq = await fetchHtml(request, "/en/faq")
  expect(faq.status, "/en/faq is not served").toBe(200)
  const question = message("en", "faqPage.categories.general.i1.q")
  const answer = message("en", "faqPage.categories.general.i1.a")
  expect(faq.body, "/en/faq has no question").toContain(question)
  expect(faq.body, "/en/faq has no answer").toContain(answer.slice(0, 120))

  // Legal: the real content and the draft notice the German page carries.
  const imprint = await fetchHtml(request, "/en/impressum")
  expect(imprint.status, "/en/impressum is not served").toBe(200)
  expect(imprint.body).toContain("Imprint")
  expect(imprint.body).toMatch(
    /Arbeitsentwurf|Working draft|This page must be completed before launch/,
  )

  // Feature page: its sections, not the generic fallback shell.
  const feature = await fetchHtml(request, "/en/features/ssl-monitoring")
  expect(feature.status, "/en/features/ssl-monitoring is not served").toBe(200)
  expect((feature.body.match(/<h2/g) ?? []).length).toBeGreaterThanOrEqual(5)
  expect(feature.body).toContain("Frequently asked questions")
  expect(feature.body, "the English feature page leaked German sections").not.toContain(
    "Häufige Fragen",
  )
})

test("the sitemap lists both languages and no alias", async ({ request }) => {
  const response = await request.get(`${origin}/sitemap.xml`)
  expect(response.status()).toBe(200)
  const xml = await response.text()
  const locs = [...xml.matchAll(/<loc>([^<]*)<\/loc>/g)].map(
    (match) => match[1],
  )
  const paths = locs.map((loc) => new URL(loc).pathname)

  const blogSlugs = readdirSync(path.join(DIST, "blog"), {
    withFileTypes: true,
  })
    .filter(
      (entry) =>
        entry.isDirectory() &&
        resolveNginx(`/blog/${entry.name}`) !== null,
    )
    .map((entry) => entry.name)

  // 29 indexable routes × 2 languages + 8 CMS articles = 66 canonical URLs.
  const expected = new Set([
    ...PUBLIC_ROUTES.flatMap((route) => [
      localizedPath(route.path, "de"),
      localizedPath(route.path, "en"),
    ]),
    ...blogSlugs.map((slug) => `/blog/${slug}`),
  ])
  expect(new Set(paths).size, "duplicate URLs in the sitemap").toBe(paths.length)
  expect(paths.length, "unexpected sitemap size").toBe(expected.size)
  for (const expectedPath of expected) {
    expect(paths, `sitemap is missing ${expectedPath}`).toContain(expectedPath)
  }
  expect(paths, "the home page has no English entry").toContain("/en")
  expect(paths, "an article was duplicated under /en").not.toContain(
    "/en/blog/",
  )
  for (const path of paths) {
    expect(path, `internal variant folder in the sitemap: ${path}`).not.toContain(
      "/_i18n",
    )
  }
  for (const loc of locs) {
    expect(loc, `query string in the sitemap: ${loc}`).not.toContain("?")
  }

  // Every advertised URL resolves through the nginx rules and declares the
  // language its path promises (articles keep their own content language).
  for (const loc of locs) {
    const pathname = new URL(loc).pathname
    expect(resolveNginx(pathname), `${loc} does not resolve`).not.toBeNull()
    const page = await request.get(`${origin}${pathname}`)
    expect(page.status(), `${loc} is advertised but not served`).toBe(200)
    if (pathname.startsWith("/blog/")) continue
    const locale = pathname.startsWith("/en") ? "en" : "de"
    expect(await page.text(), `${loc} does not declare ${locale}`).toContain(
      `<html lang="${locale}"`,
    )
  }
})

test("a browser opening /en/... keeps the English URL and hydrates it", async ({
  page,
}) => {
  test.setTimeout(180_000)
  const pageErrors: string[] = []
  const onPageError = (error: Error) => pageErrors.push(error.message)
  page.on("pageerror", onPageError)

  const navigation = await page.goto(`${origin}/en/pricing`)
  expect(navigation?.status(), "/en/pricing is not served").toBe(200)
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    message("en", "pricing.title"),
  )
  await expect(page.locator('[data-prerender="true"]')).toHaveCount(0)
  expect(page.url(), "the address bar was rewritten").toMatch(/\/en\/pricing$/)

  const canonical = await page.evaluate(() =>
    document.querySelector('link[rel="canonical"]')?.getAttribute("href"),
  )
  expect(canonical, "/en/pricing: no hydrated canonical").toBeTruthy()
  const parsed = new URL(canonical!)
  expect(parsed.pathname).toBe("/en/pricing")
  expect(parsed.search).toBe("")
  expect(
    await page.locator('link[rel="canonical"]').count(),
    "/en/pricing: duplicate canonical",
  ).toBe(1)

  // A second real navigation (new document, not a client-side click) shows the
  // English home page and its own canonical.
  const home = await page.goto(`${origin}/en`)
  expect(home?.status(), "/en is not served").toBe(200)
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Your digital presence, always under control.",
  )
  const homeCanonical = await page.evaluate(() =>
    document.querySelector('link[rel="canonical"]')?.getAttribute("href"),
  )
  expect(new URL(homeCanonical!).pathname).toBe("/en")

  page.off("pageerror", onPageError)
  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
})
