import { readFileSync } from "node:fs"
import { expect, test, type Page } from "@playwright/test"

/**
 * Language coverage of the legal pages.
 *
 * The privacy policy and the terms carry real content in both languages, so a
 * page that silently fell back to English would look plausible to a reviewer
 * while being wrong. These checks are deliberately stricter than the generic
 * public-page scan:
 *
 *  1. `h1`, page title and a distinctive body passage come from the catalogue,
 *  2. the German page does not show the English passage and vice versa,
 *  3. the "working draft" banner stays visible in both languages,
 *  4. no raw catalogue key leaks into the visible text,
 *  5. the language switcher works from the page header and survives a reload,
 *  6. nothing overflows a 390 px viewport.
 *
 * This verifies the product and the translation, not the legal validity of any
 * clause — a qualified person still has to review the wording.
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

function copy(locale: "de" | "en", key: string): string {
  const value = (locale === "de" ? DE : EN)[key]
  expect(value, `catalogue ${locale}.json is missing ${key}`).toBeTruthy()
  expect(value).not.toContain("{")
  return value
}

/** A passage only the German (or only the English) text can contain. */
const PASSAGES = {
  privacy: {
    heading: "legal.privacyAiTitle",
    de: "Wartefrist von 30 Tagen gibt es nicht",
    en: "there is no 30-day waiting period",
  },
  terms: {
    heading: "legal.termsScopeTitle",
    de: "offene Produktentscheidung",
    en: "open product decision",
  },
} as const

interface LegalPage {
  path: string
  h1: string
  /** Key of the warning band that page actually carries. */
  notice: string
  passage?: (typeof PASSAGES)[keyof typeof PASSAGES]
}

const PAGES: LegalPage[] = [
  {
    path: "/privacy",
    h1: "legal.privacyTitle",
    notice: "legal.reviewNoticeTitle",
    passage: PASSAGES.privacy,
  },
  {
    path: "/terms",
    h1: "legal.termsTitle",
    notice: "legal.reviewNoticeTitle",
    passage: PASSAGES.terms,
  },
  // The withdrawal, cookie and imprint pages carry the shorter provider notice
  // (`legal.legalNoticeTitle`) instead of the full review checklist.
  { path: "/widerruf", h1: "legal.withdrawalTitle", notice: "legal.legalNoticeTitle" },
  { path: "/cookies", h1: "legal.cookiesTitle", notice: "legal.withdrawalNotice" },
  { path: "/impressum", h1: "legal.impressumTitle", notice: "legal.legalNoticeTitle" },
]

async function seedLocale(page: Page, locale: "de" | "en") {
  await page.addInitScript((value: string) => {
    if (!window.localStorage.getItem("presence-locale")) {
      window.localStorage.setItem("presence-locale", value)
    }
  }, locale)
}

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

async function expectLegalPage(
  page: Page,
  locale: "de" | "en",
  entry: LegalPage,
) {
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    copy(locale, entry.h1),
  )
  await expect(page.locator("html")).toHaveAttribute("lang", locale)
  await expect(page).toHaveTitle(new RegExp(`^${copy(locale, entry.h1)}`))

  // The draft banner is the guard against reading these as approved terms.
  await expect(page.getByText(copy(locale, entry.notice))).toBeVisible()

  if (entry.passage) {
    await expect(
      page.getByRole("heading", { name: copy(locale, entry.passage.heading) }),
    ).toBeVisible()
    await expect(page.getByText(entry.passage[locale])).toBeVisible()
    const other = locale === "de" ? entry.passage.en : entry.passage.de
    await expect(
      page.getByText(other),
      `${entry.path} shows the ${locale === "de" ? "English" : "German"} passage`,
    ).toHaveCount(0)
  }

  await assertNoRawKeys(page)
}

test("legal pages render in German and in English", async ({ page }) => {
  test.setTimeout(240_000)
  const pageErrors: string[] = []
  page.on("pageerror", (error) => pageErrors.push(error.message))

  await seedLocale(page, "en")
  await openApp(page, "/privacy")
  await switchLanguage(page, "de")

  for (const entry of PAGES) {
    await openApp(page, entry.path)
    await expectLegalPage(page, "de", entry)
  }

  // Internal links between the legal pages keep the chosen language.
  await openApp(page, "/terms")
  await page.getByRole("link", { name: copy("de", "legal.termsWithdrawalLink") }).click()
  await expect(page).toHaveURL(/\/widerruf$/)
  await expect(page.locator("html")).toHaveAttribute("lang", "de")

  await openApp(page, "/privacy")
  await page.reload()
  await expect(page.locator("html")).toHaveAttribute("lang", "de")

  await switchLanguage(page, "en")
  for (const entry of PAGES) {
    await openApp(page, entry.path)
    await expectLegalPage(page, "en", entry)
  }

  await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
})

test("legal pages fit a mobile viewport in both languages", async ({ page }) => {
  test.setTimeout(240_000)
  await seedLocale(page, "en")
  await openApp(page, "/privacy")
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
