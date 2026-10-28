import { readFileSync } from "node:fs"
import { expect, test, type Page } from "@playwright/test"

/**
 * Operator identity: one source, every legal page.
 *
 * `src/config/operator.json` feeds the imprint, the privacy policy, the terms
 * and the withdrawal page. This suite pins the behaviour that matters:
 *
 *  1. every provided value is rendered on /impressum, never replaced by a
 *     placeholder,
 *  2. every missing value shows its *localised* placeholder plus the "must be
 *     replaced" badge — the German page never shows the English placeholder
 *     text and vice versa,
 *  3. fields marked as not applicable disappear from the page,
 *  4. until the identity is complete, /privacy, /terms and /widerruf state that
 *     the provider is named in the imprint instead of rendering an empty
 *     block; once it is complete they render the same values as the imprint.
 *
 * The expectations are read from the data file, so adding the real operator
 * data automatically switches this suite into asserting the propagation path
 * instead of the fallback wording.
 */

type Catalog = Record<string, unknown>

interface RawField {
  requirement: "mandatory" | "conditional" | "optional"
  usedOn: string[]
  labelKey: string
  placeholderKey?: string
  value?: string | null
  notApplicable?: string | null
}

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

const RAW = JSON.parse(
  readFileSync(new URL("../src/config/operator.json", import.meta.url), "utf8"),
) as Record<string, RawField>

const FIELDS = Object.entries(RAW).filter(([key]) => !key.startsWith("_")) as [
  string,
  RawField,
][]

function valueOf(field: RawField | undefined) {
  return field && typeof field.value === "string" && field.value.trim()
    ? field.value.trim()
    : null
}

function notApplicableOf(field: RawField) {
  return typeof field.notApplicable === "string" && field.notApplicable.trim()
    ? field.notApplicable.trim()
    : null
}

const PROVIDED = FIELDS.filter(([, field]) => valueOf(field))
const PLACEHOLDER_ROWS = FIELDS.filter(
  ([, field]) =>
    !valueOf(field) && !notApplicableOf(field) && Boolean(field.placeholderKey),
)
const NOT_APPLICABLE = FIELDS.filter(([, field]) => notApplicableOf(field))
const IDENTITY_COMPLETE = FIELDS.filter(
  ([, field]) => field.requirement === "mandatory",
).every(([, field]) => valueOf(field))
const DISPLAY_NAME = [valueOf(RAW.legalName), valueOf(RAW.legalForm)]
  .filter(Boolean)
  .join(" ")
const CONTACT_EMAIL = valueOf(RAW.email)

function text(locale: "de" | "en", key: string): string {
  const value = (locale === "de" ? DE : EN)[key]
  expect(value, `catalogue ${locale}.json is missing ${key}`).toBeTruthy()
  return value
}

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

test("the imprint renders the configured identity and marks the rest", async ({
  page,
}) => {
  test.setTimeout(240_000)
  const pageErrors: string[] = []
  page.on("pageerror", (error) => pageErrors.push(error.message))

  await seedLocale(page, "en")
  await openApp(page, "/impressum")
  await switchLanguage(page, "de")

  // Values are language-independent: they render identically in both catalogues.
  for (const [, field] of PROVIDED) {
    await expect(page.getByText(valueOf(field) as string).first()).toBeVisible()
  }
  for (const [, field] of PLACEHOLDER_ROWS) {
    await expect(
      page.getByText(text("de", field.placeholderKey as string)).first(),
    ).toBeVisible()
    // The English placeholder must not leak into the German page.
    await expect(
      page.getByText(text("en", field.placeholderKey as string)),
    ).toHaveCount(0)
  }
  // Rows marked not applicable are omitted, not rendered as placeholders.
  for (const [, field] of NOT_APPLICABLE) {
    if (!field.placeholderKey) continue
    await expect(page.getByText(text("de", field.placeholderKey))).toHaveCount(0)
  }
  // One "must be replaced" badge per rendered placeholder row.
  await expect(page.getByText(text("de", "legal.placeholderLabel"))).toHaveCount(
    PLACEHOLDER_ROWS.length,
  )

  await switchLanguage(page, "en")
  for (const [, field] of PROVIDED) {
    await expect(page.getByText(valueOf(field) as string).first()).toBeVisible()
  }
  for (const [, field] of PLACEHOLDER_ROWS) {
    await expect(
      page.getByText(text("en", field.placeholderKey as string)).first(),
    ).toBeVisible()
    await expect(
      page.getByText(text("de", field.placeholderKey as string)),
    ).toHaveCount(0)
  }
  await expect(page.getByText(text("en", "legal.placeholderLabel"))).toHaveCount(
    PLACEHOLDER_ROWS.length,
  )

  await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
})

test("privacy, terms and withdrawal stay on the same source", async ({
  page,
}) => {
  test.setTimeout(240_000)
  await seedLocale(page, "de")

  if (IDENTITY_COMPLETE) {
    for (const path of ["/privacy", "/terms", "/widerruf"]) {
      await openApp(page, path)
      await switchLanguage(page, "de")
      if (DISPLAY_NAME) {
        await expect(page.getByText(DISPLAY_NAME).first()).toBeVisible()
      }
      if (CONTACT_EMAIL) {
        await expect(page.getByText(CONTACT_EMAIL).first()).toBeVisible()
      }
    }
    return
  }

  // Incomplete identity: every page keeps its imprint fallback wording and
  // none of them renders a placeholder badge of its own.
  await openApp(page, "/privacy")
  await expect(
    page.getByText(text("de", "legal.privacyControllerBody")).first(),
  ).toBeVisible()
  await expect(page.getByText(text("de", "legal.placeholderLabel"))).toHaveCount(0)

  await openApp(page, "/terms")
  await expect(
    page.getByText(text("de", "legal.termsScopeBody")).first(),
  ).toBeVisible()
  await expect(
    page.getByText(text("de", "legal.termsScopeAudienceNote")).first(),
  ).toBeVisible()

  await openApp(page, "/widerruf")
  await expect(
    page.getByText(text("de", "legal.withdrawalRecipientTitle")),
  ).toHaveCount(0)
  await expect(
    page.getByText(text("de", "legal.withdrawalProcessBody")).first(),
  ).toBeVisible()

  // The English page keeps the same fallback wording, not the German one.
  await switchLanguage(page, "en")
  await openApp(page, "/privacy")
  await expect(
    page.getByText(text("en", "legal.privacyControllerBody")).first(),
  ).toBeVisible()
})
