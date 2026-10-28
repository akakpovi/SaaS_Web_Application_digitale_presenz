import { readFileSync } from "node:fs"
import path from "node:path"
import { expect, test, type APIRequestContext, type Page } from "@playwright/test"
import {
  ROOT,
  alternatesOf,
  canonicalOf,
  message,
  startDistServer,
} from "./helpers/static-dist"
import { PRE_RENDERED_HEAD_ATTRIBUTE } from "../src/lib/prerenderedHead"

/**
 * The bilingual shell of the *deployed artifact*.
 *
 * The app advertises two URLs per public page through hreflang: the bare path
 * (German, the launch default) and `/en/...` (English). Both are indexable, so
 * both must serve usable HTML *without* JavaScript. `scripts/prerender.mjs`
 * writes a page per URL, which makes the advertised URL the URL that really
 * answers in that language — the point of this spec. The historical
 * `?lang=en` URL is no longer a URL of its own: it answers a 301 to the `/en`
 * page, which is what the redirect test below asserts (and follows).
 *
 * Everything here runs against `dist/` served with the nginx rules
 * (`helpers/static-dist.ts`), never against the dev server: the dev server
 * would hand out the SPA shell and hide a missing variant.
 *
 * `pnpm build` must have run first (the suite fails with that instruction
 * rather than skipping).
 */

interface SeoRoute {
  path: string
  title: string
  description: string
  titleDe: string
  descriptionDe: string
  noindex?: boolean
}

const ROUTES: SeoRoute[] = JSON.parse(
  readFileSync(path.join(ROOT, "src", "seo", "routes.json"), "utf8"),
)
const PUBLIC_ROUTES = ROUTES.filter((route) => !route.noindex)

const OG_LOCALE = { de: "de_DE", en: "en_GB" } as const

/** Marker on the pre-rendered head tags; see src/lib/prerenderedHead.ts. */
const HEAD_MARKER = 'data-prerender-head="true"'

/** URL of one variant: the default locale owns the bare path, English `/en`. */
function variantUrl(routePath: string, locale: "de" | "en") {
  if (locale === "de") return routePath
  return routePath === "/" ? "/en" : `/en${routePath}`
}

function expectedCopy(route: SeoRoute, locale: "de" | "en") {
  return locale === "de"
    ? { title: route.titleDe, description: route.descriptionDe }
    : { title: route.title, description: route.description }
}

/**
 * Pins the language the *interface* renders in, so an assertion about it is
 * deterministic.
 *
 * A fresh Chromium reports `en-US`, and the app lets the browser language
 * suggest a locale (src/i18n/index.tsx): on the bare URL that makes the
 * rendered page English even though the delivered shell is German. The URL
 * variant and the canonical stay German — that is what these tests are about —
 * but any check of the rendered language has to seed the stored preference.
 */
async function seedLocale(page: Page, locale: "de" | "en") {
  await page.addInitScript(
    (value) => window.localStorage.setItem("presence-locale", value),
    locale,
  )
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

/** Raw HTML, exactly what a crawler without JavaScript receives. */
async function fetchHtml(request: APIRequestContext, url: string) {
  const response = await request.get(`${origin}${url}`)
  return { status: response.status(), body: await response.text() }
}

test("every public URL answers in the language its hreflang entry declares", async ({
  request,
}) => {
  for (const route of PUBLIC_ROUTES) {
    for (const locale of ["de", "en"] as const) {
      const url = variantUrl(route.path, locale)
      const { status, body } = await fetchHtml(request, url)
      expect(status, `${url} is not served`).toBe(200)

      const copy = expectedCopy(route, locale)
      expect(
        [...body.matchAll(/<title[^>]*>([\s\S]*?)<\/title>/g)],
        `${url}: expected exactly one <title>`,
      ).toHaveLength(1)
      expect(body, `${url}: wrong <html lang>`).toContain(
        `<html lang="${locale}"`,
      )
      expect(body, `${url}: wrong title`).toContain(
        `<title ${HEAD_MARKER}>${copy.title}</title>`,
      )
      expect(body, `${url}: wrong description`).toContain(
        `<meta name="description" content="${copy.description.replace(/"/g, "&quot;")}"`,
      )
      expect(body, `${url}: wrong robots`).toContain(
        '<meta name="robots" content="index,follow"',
      )
      expect(body, `${url}: wrong og:locale`).toContain(
        `<meta property="og:locale" content="${OG_LOCALE[locale]}"`,
      )

      // Canonical: self-referential per URL, no query string on either side.
      const canonical = canonicalOf(body)
      expect(canonical, `${url}: no canonical`).toBeTruthy()
      const parsed = new URL(canonical!)
      expect(parsed.pathname, `${url}: canonical points elsewhere`).toBe(
        variantUrl(route.path, locale),
      )
      expect(parsed.search, `${url}: canonical carries a query string`).toBe("")

      const alternates = alternatesOf(body)
      expect(alternates.map((entry) => entry.hreflang).sort()).toEqual([
        "de",
        "en",
        "x-default",
      ])
      for (const entry of alternates) {
        const href = new URL(entry.href)
        expect(href.origin, `${url}: alternate on a foreign origin`).toBe(
          parsed.origin,
        )
        const expectedPath =
          entry.hreflang === "en" ? variantUrl(route.path, "en") : route.path
        expect(href.pathname, `${url}: alternate on another page`).toBe(
          expectedPath,
        )
        expect(href.search, `${url}: alternate carries a query string`).toBe("")
      }

      // The *content*, not only the head: an English URL that still carries
      // the German markup would be a fake English shell. Every public page
      // renders the language switcher, whose `aria-label` comes from the
      // catalogue, so it is a reliable per-language marker even on pages with
      // a minimal header (pricing, legal, tools).
      expect(body, `${url}: the page is not in ${locale}`).toContain(
        `aria-label="${message(locale, "nav.languageLabel")}"`,
      )
      const other = locale === "de" ? "en" : "de"
      expect(
        body,
        `${url}: the ${other} navigation leaked into the ${locale} page`,
      ).not.toContain(`aria-label="${message(other, "nav.languageLabel")}"`)
    }
  }
})

test("each advertised hreflang URL opens the advertised language", async ({
  request,
}) => {
  // Follow the alternates the page itself publishes instead of rebuilding the
  // URLs: a link nobody can follow is the defect this guards against.
  for (const route of PUBLIC_ROUTES) {
    const { body } = await fetchHtml(request, route.path)
    for (const entry of alternatesOf(body)) {
      if (entry.hreflang === "x-default") continue
      const advertised = new URL(entry.href)
      const { status, body: target } = await fetchHtml(
        request,
        `${advertised.pathname}${advertised.search}`,
      )
      expect(status, `${entry.href} is advertised but not served`).toBe(200)
      expect(target, `${entry.href} does not serve ${entry.hreflang}`).toContain(
        `<html lang="${entry.hreflang}"`,
      )
      expect(target, `${entry.href} is a duplicate of the German shell`).toContain(
        `<title ${HEAD_MARKER}>${expectedCopy(route, entry.hreflang as "de" | "en").title}</title>`,
      )
    }
  }
})

test("the historical ?lang= URL is a 301 to the canonical URL", async ({
  request,
}) => {
  // The migration adds `/en`; it does not break the URL every existing link,
  // bookmark and search result may still carry. That URL is now a permanent
  // redirect: the destination must serve the same English page, and the
  // German variant must collapse back to the bare path.
  for (const routePath of ["/", "/pricing", "/impressum", "/features/ssl-monitoring"]) {
    const route = PUBLIC_ROUTES.find((entry) => entry.path === routePath)!
    const target = variantUrl(routePath, "en")

    const redirect = await request.get(`${origin}${routePath}?lang=en`, {
      maxRedirects: 0,
    })
    expect(redirect.status(), `${routePath}?lang=en is not a 301`).toBe(301)
    expect(redirect.headers()["location"], `${routePath}?lang=en: Location`).toBe(
      `${origin}${target}`,
    )

    const germanRedirect = await request.get(
      `${origin}${routePath}?lang=de`,
      { maxRedirects: 0 },
    )
    expect(germanRedirect.status(), `${routePath}?lang=de is not a 301`).toBe(301)
    expect(
      germanRedirect.headers()["location"],
      `${routePath}?lang=de: Location`,
    ).toBe(`${origin}${routePath}`)

    // Following the redirect yields the English page and its own canonical.
    const followed = await request.get(`${origin}${routePath}?lang=en`)
    expect(followed.status(), `${routePath}?lang=en does not land on a page`).toBe(
      200,
    )
    expect(new URL(followed.url()).pathname).toBe(target)
    const body = await followed.text()
    expect(body, `${routePath}?lang=en is not English`).toContain(
      '<html lang="en"',
    )
    expect(body).toContain(
      `<title ${HEAD_MARKER}>${expectedCopy(route, "en").title}</title>`,
    )

    const canonical = canonicalOf(body)
    expect(canonical, `${routePath}?lang=en: no canonical`).toBeTruthy()
    const parsed = new URL(canonical!)
    expect(parsed.pathname, `${routePath}?lang=en: canonical path`).toBe(target)
    expect(parsed.search, `${routePath}?lang=en: canonical query`).toBe("")
    expect(
      alternatesOf(body).map((entry) => entry.hreflang).sort(),
      `${routePath}?lang=en: alternates`,
    ).toEqual(["de", "en", "x-default"])
  }
})

/**
 * Head of the *hydrated* document: exactly one canonical, three alternates, one
 * description and one title. A pre-rendered tag the app does not drop would
 * survive next to the one it renders, which is how a bilingual page ends up
 * advertising two different canonicals at once.
 */
async function hydratedHead(page: Page) {
  return page.evaluate((marker: string) => {
    const canonicals = Array.from(
      document.querySelectorAll('link[rel="canonical"]'),
    ).map((link) => link.getAttribute("href"))
    const alternates = Array.from(
      document.querySelectorAll('link[rel="alternate"]'),
    ).map((link) => ({
      hreflang: link.getAttribute("hreflang"),
      href: link.getAttribute("href"),
    }))
    const descriptions = Array.from(
      document.querySelectorAll('meta[name="description"]'),
    ).map((meta) => meta.getAttribute("content"))
    const locales = Array.from(
      document.querySelectorAll('meta[property="og:locale"]'),
    ).map((meta) => meta.getAttribute("content"))
    const titles = Array.from(document.querySelectorAll("head title")).map(
      (title) => title.textContent,
    )
    const preRenderedLeft = Array.from(
      document.querySelectorAll(`head [${marker}]`),
    ).map((node) => node.outerHTML.slice(0, 80))
    return { canonicals, alternates, descriptions, locales, titles, preRenderedLeft }
  }, PRE_RENDERED_HEAD_ATTRIBUTE)
}

test("the hydrated head describes the requested variant, without duplicates", async ({
  page,
}) => {
  test.setTimeout(180_000)

  for (const [locale, url, canonicalPath] of [
    ["de", "/pricing", "/pricing"],
    ["en", "/en/pricing", "/en/pricing"],
  ] as const) {
    const pageErrors: string[] = []
    const onPageError = (error: Error) => pageErrors.push(error.message)
    page.on("pageerror", onPageError)
    await seedLocale(page, locale)

    const navigation = await page.goto(`${origin}${url}`)
    expect(navigation?.status(), `${url} is not served`).toBe(200)
    await expect(page.locator("html")).toHaveAttribute("lang", locale)
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      message(locale, "pricing.title"),
    )
    await expect(page.locator('[data-prerender="true"]')).toHaveCount(0)

    // The pre-rendered tags must be dropped once the app rendered its own: two
    // canonicals, two descriptions or a title in the other language would mean
    // the served variant leaks into the hydrated document.
    const head = await hydratedHead(page)
    expect(head.canonicals, `${url}: canonical count`).toHaveLength(1)
    const canonical = new URL(head.canonicals[0]!)
    expect(canonical.pathname, `${url}: canonical path`).toBe(canonicalPath)
    expect(canonical.search, `${url}: canonical query`).toBe("")
    expect(head.alternates, `${url}: alternate count`).toHaveLength(3)
    expect(head.descriptions, `${url}: description count`).toHaveLength(1)
    expect(head.locales, `${url}: og:locale count`).toHaveLength(1)
    expect(head.locales[0]).toBe(OG_LOCALE[locale])
    expect(head.titles, `${url}: title count`).toHaveLength(1)
    expect(head.titles[0]).toContain(message(locale, "meta.pricing.title"))
    // Nothing is left of the shell version of these tags. The structured-data
    // script is the one tag the app does not re-render on this page, so the
    // pre-rendered copy is kept on purpose (crawlers need exactly one).
    expect(
      head.preRenderedLeft.filter(
        (tag) => !tag.startsWith('<script type="application/ld+json"'),
      ),
      `${url}: the app replaced these tags but left the pre-rendered copies`,
    ).toEqual([])

    page.off("pageerror", onPageError)
    expect(pageErrors, `${url}: page errors`).toEqual([])
  }
})

test("a noindex route publishes no canonical and no alternates in either variant", async ({
  page,
  request,
}) => {
  await seedLocale(page, "de")
  // No redirect on a noindex screen: `/en/login` does not exist, so a 301
  // would send the visitor to a 404. The shell must keep answering 200.
  for (const url of ["/login", "/login?lang=en"]) {
    const direct = await request.get(`${origin}${url}`, { maxRedirects: 0 })
    expect(direct.status(), `${url} must not redirect`).toBe(200)
    expect(direct.headers()["location"], `${url}: unexpected Location`).toBeUndefined()
    const { status, body } = await fetchHtml(request, url)
    expect(status, `${url} is not served`).toBe(200)
    expect(body, `${url}: robots`).toContain(
      '<meta name="robots" content="noindex,nofollow"',
    )
    expect(canonicalOf(body), `${url}: static canonical`).toBeNull()
    expect(alternatesOf(body), `${url}: static alternates`).toEqual([])

    const navigation = await page.goto(`${origin}${url}`)
    expect(navigation?.status(), `${url} is not served`).toBe(200)
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    const head = await hydratedHead(page)
    expect(head.canonicals, `${url}: hydrated canonical`).toEqual([])
    expect(head.alternates, `${url}: hydrated alternates`).toEqual([])
  }
})

test("switching the language keeps the canonical on the requested URL", async ({
  page,
}) => {
  await seedLocale(page, "de")
  await page.goto(`${origin}/pricing`)
  await expect(page.locator("html")).toHaveAttribute("lang", "de")

  // The switcher changes the interface, not the address bar: the canonical
  // must keep describing the URL that was requested (the German variant).
  await page.getByRole("button", { name: message("en", "nav.english") }).click()
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
  expect(page.url(), "the switcher must not rewrite the URL").not.toContain("lang=")

  const head = await hydratedHead(page)
  expect(head.canonicals).toHaveLength(1)
  expect(new URL(head.canonicals[0]!).search).toBe("")
})
