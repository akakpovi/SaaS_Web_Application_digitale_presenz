import { readFileSync } from "node:fs"
import { expect, test, type Page } from "@playwright/test"

/**
 * French non-regression coverage.
 *
 * The private checks use a real account supplied through environment
 * variables, so no password is committed and CI can provide its own account.
 * They are skipped when those variables are absent; the public/login checks
 * always run. The expected copy is read from `fr.json`, which means a
 * deliberate wording change does not fail the suite while an untranslated
 * screen still does.
 */

type Catalog = Record<string, unknown>

function flatten(
  catalog: Catalog,
  prefix = "",
  into: Record<string, string> = {},
): Record<string, string> {
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

function loadCatalog(file: "fr.json" | "en.json"): Record<string, string> {
  const url = new URL(`../src/i18n/${file}`, import.meta.url)
  return flatten(JSON.parse(readFileSync(url, "utf8")) as Catalog)
}

const FR = loadCatalog("fr.json")
const EN = loadCatalog("en.json")
const ALL_KEYS = [...new Set([...Object.keys(FR), ...Object.keys(EN)])]

/** A catalogue value safe to assert verbatim (no interpolation). */
function copy(key: string): string {
  const value = FR[key]
  expect(value, `fr.json is missing ${key}`).toBeTruthy()
  expect(value).not.toContain("{")
  return value
}

async function assertNoRawKeys(page: Page): Promise<void> {
  const leaked = await page.evaluate((keys) => {
    const text = document.body.innerText
    if (!text) return []
    const normalised = text.replace(/\s+/g, " ")
    return keys.filter((key) => normalised.includes(key))
  }, ALL_KEYS)
  expect(leaked, `raw i18n keys visible: ${leaked.join(", ")}`).toEqual([])
}

async function expectFrenchPage(page: Page): Promise<void> {
  await expect(page.locator("html")).toHaveAttribute("lang", "fr")
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
  await assertNoRawKeys(page)
}

async function openPrivate(page: Page, path: string): Promise<void> {
  await page.goto(`/fr/app/${path}`)
  await page.waitForURL(new RegExp(`/app/${path}\\?lang=fr$`), {
    timeout: 30_000,
  })
  await expect(page.locator("#root")).not.toBeEmpty()
}

const EMAIL = process.env.E2E_EMAIL?.trim()
const PASSWORD = process.env.E2E_PASSWORD
const WEBSITE_ID = process.env.E2E_WEBSITE_ID?.trim()
const HAS_AUTH = Boolean(EMAIL && PASSWORD)

async function signIn(page: Page): Promise<void> {
  if (!EMAIL || !PASSWORD) {
    throw new Error("E2E_EMAIL and E2E_PASSWORD are required for private tests.")
  }

  await page.goto("/fr/login")
  await page.waitForURL(/\/login\?lang=fr$/, { timeout: 20_000 })
  await page.locator('input[type="email"]').fill(EMAIL)
  await page.locator('input[type="password"]').fill(PASSWORD)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(/\/app\/dashboard/, { timeout: 30_000 })
}

test("French public pages and login use the French catalogue", async ({
  page,
}) => {
  test.setTimeout(120_000)
  const pageErrors: string[] = []
  page.on("pageerror", (error) => pageErrors.push(error.message))

  await page.goto("/fr/")
  await expect(page.locator("html")).toHaveAttribute("lang", "fr")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    copy("landing.titleLead"),
  )
  await assertNoRawKeys(page)

  await page.goto("/fr/pricing")
  await expectFrenchPage(page)

  await page.goto("/fr/login")
  await page.waitForURL(/\/login\?lang=fr$/, { timeout: 20_000 })
  await expectFrenchPage(page)
  await expect(page.locator("body")).toContainText(copy("auth.loginTitle"))
  await expect(page.locator('button[type="submit"]')).toContainText(
    copy("auth.signIn"),
  )

  await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
})

test.describe("French private screens", () => {
  test.skip(
    !HAS_AUTH,
    "Set E2E_EMAIL and E2E_PASSWORD to run the authenticated French checks.",
  )

  test("dashboard and navigation are translated", async ({ page }) => {
    test.setTimeout(180_000)
    const pageErrors: string[] = []
    page.on("pageerror", (error) => pageErrors.push(error.message))

    await signIn(page)
    await openPrivate(page, "dashboard")
    await expectFrenchPage(page)
    await expect(page.locator("body")).toContainText(copy("dashboard.subtitle"))

    for (const key of [
      "app.navOverview",
      "app.navWebsites",
      "app.navScans",
      "app.navMonitoring",
      "app.navAlerts",
      "app.navReports",
      "app.navSettings",
    ]) {
      await expect(page.locator("body")).toContainText(copy(key))
    }

    await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual(
      [],
    )
  })

  test("website list and detail keep their French actions", async ({ page }) => {
    test.setTimeout(180_000)
    const pageErrors: string[] = []
    page.on("pageerror", (error) => pageErrors.push(error.message))

    await signIn(page)
    await openPrivate(page, "websites")
    await expectFrenchPage(page)
    await expect(page.locator("body")).toContainText(copy("websites.subtitle"))

    let websiteId = WEBSITE_ID
    if (!websiteId) {
      const href = await page
        .locator('a[href*="/app/websites/"]')
        .first()
        .getAttribute("href")
        .catch(() => null)
      websiteId = href?.match(/\/app\/websites\/(\d+)/)?.[1]
    }
    test.skip(!websiteId, "The test account has no website to open.")

    await page.goto(`/fr/app/websites/${websiteId}`)
    await page.waitForURL(new RegExp(`/app/websites/${websiteId}\\?lang=fr$`), {
      timeout: 30_000,
    })
    await expectFrenchPage(page)

    const body = page.locator("body")
    await expect(body).toContainText(copy("websiteDetails.allWebsites"))
    await expect(body).toContainText(copy("websiteDetails.runCheck"))

    const text = await body.innerText()
    for (const english of [
      "Website not found",
      "No summary",
      "Run full analysis",
      "Include resolved",
    ]) {
      expect(text, `English website-detail text: ${english}`).not.toContain(
        english,
      )
    }

    await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual(
      [],
    )
  })

  test("settings sections and privacy copy are French", async ({ page }) => {
    test.setTimeout(180_000)
    const pageErrors: string[] = []
    page.on("pageerror", (error) => pageErrors.push(error.message))

    await signIn(page)
    await openPrivate(page, "settings")
    await expectFrenchPage(page)
    await expect(page.locator("body")).toContainText(copy("settings.subtitle"))

    for (const key of [
      "settings.sectionAccount",
      "settings.sectionBusiness",
      "settings.sectionNotifications",
      "settings.sectionAppearance",
      "settings.sectionPwa",
      "settings.sectionSecurity",
      "settings.sectionSubscription",
      "settings.sectionApi",
      "settings.sectionIntegrations",
      "settings.sectionPrivacy",
    ]) {
      await expect(page.locator("body")).toContainText(copy(key))
    }

    const text = await page.locator("body").innerText()
    for (const english of [
      "Appearance",
      "Subscription",
      "Privacy and data",
      "Delete account",
    ]) {
      expect(text, `English settings text: ${english}`).not.toContain(english)
    }

    await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual(
      [],
    )
  })
})

// TEMPORARY: force failure to verify artifact upload — REMOVE AFTER VALIDATION
test("TEMP: force failure for artifact upload test", async () => {
  expect(true).toBe(false)
})
