import { readFileSync } from "node:fs"
import { expect, test, type Page } from "@playwright/test"

/**
 * Language coverage of the secondary public pages.
 *
 * Companion to `authenticated-i18n.spec.ts` (product shell) and
 * `launch-readiness.spec.ts` (public journey, legal pages, blog). Here the
 * pages that carry the marketing and tool funnel are checked in both
 * languages:
 *
 *  1. the page renders its `h1` and the copy from its own catalogue,
 *  2. `<html lang>`, `<title>` and the description follow the language,
 *  3. no raw catalogue key leaks into the visible text,
 *  4. nothing overflows a 390 px viewport,
 *  5. the tool → scan funnel still ends on a German report.
 *
 * Expected strings are read from the catalogues so a deliberate copy change
 * does not fail the suite, while an untranslated page still does.
 */

type Catalog = Record<string, unknown>

function flatten(catalog: Catalog, prefix = "", into: Record<string, string> = {}) {
  for (const [key, value] of Object.entries(catalog)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof value === "string") {
      into[path] = value
    } else if (value && typeof value === "object" && !Array.isArray(value)) {
      flatten(value as Catalog, path, into)
    }
  }
  return into
}

function loadCatalog(file: "de.json" | "en.json") {
  const url = new URL(`../src/i18n/${file}`, import.meta.url)
  return flatten(JSON.parse(readFileSync(url, "utf8")) as Catalog)
}

const DE = loadCatalog("de.json")
const EN = loadCatalog("en.json")
const ALL_KEYS = [...new Set([...Object.keys(DE), ...Object.keys(EN)])]

/** A catalogue value that is safe to assert verbatim (no interpolation). */
function copy(locale: "de" | "en", key: string): string {
  const value = (locale === "de" ? DE : EN)[key]
  expect(value, `catalogue ${locale}.json is missing ${key}`).toBeTruthy()
  expect(value).not.toContain("{")
  return value
}

/** Each page with the `h1` key and the SEO title key it must render. */
const PAGES: { path: string; h1: string; title: string }[] = [
  { path: "/about", h1: "about.h1", title: "about.metaTitle" },
  { path: "/contact", h1: "contact.h1", title: "contact.metaTitle" },
  {
    path: "/tools/website-checker",
    h1: "tools.websiteChecker.h1",
    title: "tools.websiteChecker.metaTitle",
  },
  {
    path: "/tools/ssl-checker",
    h1: "tools.sslChecker.h1",
    title: "tools.sslChecker.metaTitle",
  },
  {
    path: "/tools/dns-checker",
    h1: "tools.dnsChecker.h1",
    title: "tools.dnsChecker.metaTitle",
  },
  {
    path: "/tools/email-security-checker",
    h1: "tools.emailSecurityChecker.h1",
    title: "tools.emailSecurityChecker.metaTitle",
  },
  {
    path: "/features/website-monitoring",
    h1: "features.websiteMonitoring.h1",
    title: "features.websiteMonitoring.metaTitle",
  },
  {
    path: "/features/ssl-monitoring",
    h1: "features.sslMonitoring.h1",
    title: "features.sslMonitoring.metaTitle",
  },
  {
    path: "/features/dns-monitoring",
    h1: "features.dnsMonitoring.h1",
    title: "features.dnsMonitoring.metaTitle",
  },
  {
    path: "/features/email-security",
    h1: "features.emailSecurity.h1",
    title: "features.emailSecurity.metaTitle",
  },
  {
    path: "/features/uptime-monitoring",
    h1: "features.uptimeMonitoring.h1",
    title: "features.uptimeMonitoring.metaTitle",
  },
  {
    path: "/features/website-performance",
    h1: "features.websitePerformance.h1",
    title: "features.websitePerformance.metaTitle",
  },
  {
    path: "/features/security-headers",
    h1: "features.securityHeaders.h1",
    title: "features.securityHeaders.metaTitle",
  },
  {
    path: "/features/review-monitoring",
    h1: "features.reviewMonitoring.h1",
    title: "features.reviewMonitoring.metaTitle",
  },
  {
    path: "/solutions/small-business",
    h1: "solutions.smallBusiness.h1",
    title: "solutions.smallBusiness.metaTitle",
  },
  {
    path: "/solutions/freelancers",
    h1: "solutions.freelancers.h1",
    title: "solutions.freelancers.metaTitle",
  },
  {
    path: "/solutions/agencies",
    h1: "solutions.agencies.h1",
    title: "solutions.agencies.metaTitle",
  },
  {
    path: "/solutions/restaurants",
    h1: "solutions.restaurants.h1",
    title: "solutions.restaurants.metaTitle",
  },
  {
    path: "/solutions/ecommerce",
    h1: "solutions.ecommerce.h1",
    title: "solutions.ecommerce.metaTitle",
  },
  {
    path: "/solutions/local-business",
    h1: "solutions.localBusiness.h1",
    title: "solutions.localBusiness.metaTitle",
  },
]

/** Seeds the locale before the first paint (only for the very first load). */
async function seedLocale(page: Page, locale: "de" | "en") {
  await page.addInitScript((value: string) => {
    if (!window.localStorage.getItem("presence-locale")) {
      window.localStorage.setItem("presence-locale", value)
    }
  }, locale)
}

/**
 * Opens a route and waits until the client app rendered. Bounded retry: the
 * Vite dev server can still be compiling on the first request of a run.
 */
async function openApp(page: Page, path: string) {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    await page.goto(path)
    try {
      await expect(page.locator("#root")).not.toBeEmpty({ timeout: 30_000 })
      return
    } catch (error) {
      if (attempt === 3) throw error
      await page.waitForTimeout(2_000)
    }
  }
}

/** Clicks the visible DE/EN switcher and waits for `<html lang>` to follow. */
async function switchLanguage(page: Page, locale: "de" | "en") {
  await page
    .getByRole("button", { name: locale === "de" ? "Deutsch" : "English" })
    .first()
    .click()
  await expect(page.locator("html")).toHaveAttribute("lang", locale)
}

async function assertNoRawKeys(page: Page) {
  const leaked = await page.evaluate((keys) => {
    const text = document.body.innerText
    if (!text) return []
    const normalised = text.replace(/\s+/g, " ")
    return keys.filter((key) => normalised.includes(key))
  }, ALL_KEYS)
  expect(leaked, `raw i18n keys visible: ${leaked.join(", ")}`).toEqual([])
}

async function expectPage(
  page: Page,
  locale: "de" | "en",
  entry: (typeof PAGES)[number],
) {
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    copy(locale, entry.h1),
  )
  await expect(page.locator("html")).toHaveAttribute("lang", locale)
  // The SEO title is a user-visible contract too: it must not stay English.
  await expect(page).toHaveTitle(copy(locale, entry.title))
  await assertNoRawKeys(page)
}

test("secondary public pages render in German and switch to English", async ({
  page,
}) => {
  test.setTimeout(240_000)
  const pageErrors: string[] = []
  page.on("pageerror", (error) => pageErrors.push(error.message))

  // Deterministic first paint, then the real switcher does the rest.
  await seedLocale(page, "en")
  await openApp(page, "/about")
  await switchLanguage(page, "de")

  for (const entry of PAGES) {
    await openApp(page, entry.path)
    await expectPage(page, "de", entry)
  }

  // The choice survives a reload instead of snapping back to the browser one.
  await openApp(page, "/contact")
  await page.reload()
  await expect(page.locator("html")).toHaveAttribute("lang", "de")

  await switchLanguage(page, "en")
  for (const entry of PAGES) {
    await openApp(page, entry.path)
    await expectPage(page, "en", entry)
  }

  await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
})

test("secondary public pages fit a mobile viewport in both languages", async ({
  page,
}) => {
  test.setTimeout(240_000)
  await seedLocale(page, "en")
  await openApp(page, "/about")
  await page.setViewportSize({ width: 390, height: 844 })

  for (const locale of ["de", "en"] as const) {
    await switchLanguage(page, locale)
    for (const entry of PAGES) {
      await openApp(page, entry.path)
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      )
      expect(
        overflow,
        `horizontal overflow on ${entry.path} (${locale}): ${overflow}px`,
      ).toBeLessThanOrEqual(1)
    }
  }
})

test("?lang= links open the advertised language and the hreflang alternates agree", async ({
  page,
}) => {
  test.setTimeout(120_000)

  // `?lang=` is the URL form the hreflang alternates point at: it must win
  // over a stored preference, otherwise those alternates are dead links.
  await seedLocale(page, "en")
  await openApp(page, "/pricing?lang=de")
  await expect(page.locator("html")).toHaveAttribute("lang", "de")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    copy("de", "pricing.title"),
  )

  await openApp(page, "/pricing?lang=en")
  await expect(page.locator("html")).toHaveAttribute("lang", "en")

  // The advertised alternates must be self-consistent: one URL per language
  // (German keeps the bare path, English is mounted under /en), plus an
  // x-default on the default. Each of those URLs is served with that language's
  // HTML — e2e/bilingual-shell-dist.spec.ts proves it against the built
  // artifact.
  await openApp(page, "/features/ssl-monitoring")
  const alternates = await page.evaluate(() =>
    Array.from(document.querySelectorAll('link[rel="alternate"]')).map(
      (link) => ({
        hreflang: link.getAttribute("hreflang"),
        href: link.getAttribute("href"),
      }),
    ),
  )
  const byLang = Object.fromEntries(
    alternates.map((entry) => [entry.hreflang, entry.href]),
  )
  expect(Object.keys(byLang).sort()).toEqual(["de", "en", "x-default"])
  expect(byLang.de).toMatch(/\/features\/ssl-monitoring$/)
  expect(byLang["x-default"]).toBe(byLang.de)
  expect(byLang.en).toMatch(/\/en\/features\/ssl-monitoring$/)

  // The requested URL stays canonical, and the English variant canonicalises
  // to itself: a variant that pointed at the German URL could never be
  // indexed, which is what its own hreflang entry promises.
  const canonical = await page.evaluate(
    () => document.querySelector('link[rel="canonical"]')?.getAttribute("href"),
  )
  expect(canonical).toMatch(/\/features\/ssl-monitoring$/)
  expect(canonical).not.toContain("lang=")

  // The legacy parameter still opens the English page, but no longer owns a
  // canonical of its own: it points at the dedicated URL.
  await openApp(page, "/features/ssl-monitoring?lang=en")
  const aliasCanonical = await page.evaluate(
    () => document.querySelector('link[rel="canonical"]')?.getAttribute("href"),
  )
  expect(aliasCanonical).toMatch(/\/en\/features\/ssl-monitoring$/)

  // The dedicated URL is a real page of the app, not only a pre-rendered file:
  // it hydrates, keeps its own address and canonicalises to itself.
  await openApp(page, "/en/features/ssl-monitoring")
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    copy("en", "features.sslMonitoring.h1"),
  )
  expect(page.url()).toMatch(/\/en\/features\/ssl-monitoring$/)
  const prefixedCanonical = await page.evaluate(
    () => document.querySelector('link[rel="canonical"]')?.getAttribute("href"),
  )
  expect(prefixedCanonical).toMatch(/\/en\/features\/ssl-monitoring$/)
})

test("the tool funnel ends on a German report", async ({ page }) => {
  test.setTimeout(180_000)
  await seedLocale(page, "en")
  await openApp(page, "/tools/website-checker")
  await switchLanguage(page, "de")

  await page.getByLabel(copy("de", "tools.websiteChecker.inputLabel")).fill(
    "example.com",
  )
  await page
    .getByRole("button", { name: copy("de", "tools.websiteChecker.buttonLabel") })
    .click()

  await page.waitForURL(/\/scan\/\d+/, { timeout: 30_000 })
  await expect(page.getByText(copy("de", "publicScan.statusReady"))).toBeVisible({
    timeout: 90_000,
  })
  await expect(page.locator("html")).toHaveAttribute("lang", "de")
  await expect(
    page.getByRole("heading", { name: copy("de", "publicScan.healthChecks") }),
  ).toBeVisible()
  await assertNoRawKeys(page)
})
