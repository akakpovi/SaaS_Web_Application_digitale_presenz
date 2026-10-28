import { readFileSync } from "node:fs"
import { expect, test, type Page } from "@playwright/test"
import { extractPath, messageBody, waitForMessage } from "./helpers/mailpit"

/**
 * Language coverage of the authenticated product surfaces.
 *
 * Companion to `launch-readiness.spec.ts`, which covers the public journey.
 * Here the app is opened *signed in* and every page of the app shell is
 * checked in both languages against things a translation pass can really
 * break:
 *
 *  1. the page still renders its `h1` (a missing key must not break the view),
 *  2. the page shows the *German* copy from `de.json` (not an English
 *     fallback) and the English copy after switching back,
 *  3. no raw catalogue key leaks into the visible text,
 *  4. no uncaught JavaScript error was raised.
 *
 * The expected strings are read from the catalogues themselves rather than
 * copied into the spec, so a deliberate wording change does not turn into a
 * red build while a silently untranslated page still fails.
 *
 * The language is changed through the visible switcher (the real user path),
 * not by writing `localStorage`: the provider persists its detected locale on
 * mount, so a seeded value is only reliable *before* the first page load.
 *
 * The account is created through the real registration + verification flow and
 * removed by the global teardown, like the other e2e accounts.
 */

const PASSWORD = "E2eLaunch123456!"

/* ── Catalogues ──────────────────────────────────────────────────────────── */

type Catalog = Record<string, unknown>

/** Flattens a catalogue into `dotted.key` → string. */
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

/** Reads and flattens one catalogue from disk (ESM-safe via `import.meta`). */
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

/* ── Pages ───────────────────────────────────────────────────────────────── */

/**
 * Every page of the authenticated shell with a copy of its own header that is
 * rendered once the page has settled. The loading branch of a page may render
 * only a spinner, so the assertion retries until the real header is there.
 */
const APP_PAGES: { path: string; marker: string }[] = [
  { path: "/app/dashboard", marker: "dashboard.subtitle" },
  { path: "/app/websites", marker: "websites.subtitle" },
  { path: "/app/scans", marker: "scan.subtitle" },
  { path: "/app/monitoring", marker: "monitoring.subtitle" },
  { path: "/app/alerts", marker: "alerts.subtitle" },
  { path: "/app/reports", marker: "reports.subtitle" },
  { path: "/app/reviews", marker: "reviews.subtitle" },
  { path: "/app/growth", marker: "growth.subtitle" },
  { path: "/app/advisor", marker: "advisorPage.subtitle" },
  { path: "/app/settings", marker: "settings.subtitle" },
  { path: "/app/settings/integrations", marker: "integrations.subtitle" },
  { path: "/app/billing", marker: "billing.subtitle" },
]

/* ── Helpers ─────────────────────────────────────────────────────────────── */

/**
 * Seeds the UI locale before the app boots. It only fills an empty
 * preference, so a choice already stored on the device is respected. Called
 * before the first navigation only — later switches go through the switcher.
 */
async function seedLocale(page: Page, locale: "de" | "en") {
  await page.addInitScript((value: string) => {
    if (!window.localStorage.getItem("presence-locale")) {
      window.localStorage.setItem("presence-locale", value)
    }
  }, locale)
}

/**
 * Opens a route and waits until the client app has actually rendered.
 *
 * The Vite dev server can be mid-compile (or re-optimising dependencies) when
 * a run starts, and `page.goto` resolves inside that window with an empty
 * `#root`. Three bounded attempts turn a cold server into a slow start rather
 * than a five-minute timeout; a genuinely broken page still fails.
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

/**
 * Reloads the current route and waits until the client app rendered again.
 *
 * Vite answers the first request after a change with an outdated
 * dependency-optimisation error from time to time, which leaves a blank
 * document; the bounded retry covers exactly that window. The locale
 * persistence below is still asserted on a page that really rendered, and a
 * genuinely blank app would fail all three attempts.
 */
async function reloadUntilReady(page: Page) {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    await page.reload()
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
  const label = locale === "de" ? "Deutsch" : "English"
  await page.getByRole("button", { name: label }).first().click()
  await expect(page.locator("html")).toHaveAttribute("lang", locale)
}

/**
 * Visible text must never contain a catalogue key (`billing.checkout.error`).
 * The candidate list *is* the catalogue, so there is no heuristic to tune:
 * anything matched here is a key the user was shown raw.
 */
async function assertNoRawKeys(page: Page, candidates: string[]) {
  const leaked = await page.evaluate((keys) => {
    const text = document.body.innerText
    if (!text) return []
    const normalised = text.replace(/\s+/g, " ")
    return keys.filter((key) => normalised.includes(key))
  }, candidates)
  expect(leaked, `raw i18n keys visible: ${leaked.join(", ")}`).toEqual([])
}

async function expectPage(page: Page, locale: "de" | "en", marker: string) {
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
  await expect(page.locator("html")).toHaveAttribute("lang", locale)
  await expect(page.locator("body")).toContainText(copy(locale, marker))
  await assertNoRawKeys(page, ALL_KEYS)
}

async function registerAndVerify(page: Page, email: string) {
  await openApp(page, "/register")
  await page.locator('input[placeholder="Maria Schmidt"]').fill("I18n Tester")
  await page.locator('input[placeholder="you@example.com"]').fill(email)
  await page.locator('input[placeholder="Min. 12 characters"]').fill(PASSWORD)
  await page.getByRole("button", { name: "Create account" }).click()
  await page.waitForURL(/\/login\?registered=true/, { timeout: 20_000 })

  const message = await waitForMessage(email)
  const verifyPath = extractPath(await messageBody(message.ID), "/verify-email")
  await openApp(page, verifyPath)
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible()
}

async function signIn(page: Page, email: string) {
  await openApp(page, "/login")
  await page.locator('input[placeholder="you@example.com"]').fill(email)
  await page.locator('input[type="password"]').fill(PASSWORD)
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL(/\/app\/dashboard/, { timeout: 20_000 })
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

test("authenticated pages render in German and switch to English", async ({
  page,
}) => {
  test.setTimeout(300_000)
  const email = `e2e-i18n-${Date.now()}@example.com`

  // English for the registration flow: the selectors below are the copy the
  // auth screens show in English.
  await seedLocale(page, "en")
  await registerAndVerify(page, email)
  await signIn(page, email)

  const pageErrors: string[] = []
  page.on("pageerror", (error) => pageErrors.push(error.message))

  // Grown-up path: the visitor picks German in the product header.
  await switchLanguage(page, "de")
  for (const entry of APP_PAGES) {
    await openApp(page, entry.path)
    await expectPage(page, "de", entry.marker)
  }

  // The choice survives a reload instead of snapping back to the detected one.
  await openApp(page, "/app/dashboard")
  await reloadUntilReady(page)
  await expectPage(page, "de", "dashboard.subtitle")

  // …and switching back gives English everywhere, not a mixed page.
  await switchLanguage(page, "en")
  for (const entry of APP_PAGES) {
    await openApp(page, entry.path)
    await expectPage(page, "en", entry.marker)
  }

  await openApp(page, "/app/dashboard")
  await reloadUntilReady(page)
  await expectPage(page, "en", "dashboard.subtitle")

  await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
})

test("authenticated pages fit a mobile viewport in both languages", async ({
  page,
}) => {
  test.setTimeout(300_000)
  const email = `e2e-i18n-mobile-${Date.now()}@example.com`

  await seedLocale(page, "en")
  await registerAndVerify(page, email)
  await signIn(page, email)

  await page.setViewportSize({ width: 390, height: 844 })

  for (const locale of ["de", "en"] as const) {
    await switchLanguage(page, locale)
    for (const entry of APP_PAGES) {
      await openApp(page, entry.path)
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
      await expect(page.locator("html")).toHaveAttribute("lang", locale)
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
