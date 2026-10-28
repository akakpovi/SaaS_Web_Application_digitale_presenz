import { expect, test, type Page } from "@playwright/test"
import { extractPath, messageBody, waitForMessage } from "./helpers/mailpit"

/**
 * Launch acceptance for the German market.
 *
 * These journeys complement `public-scan.spec.ts` and
 * `registration-verification.spec.ts`: they cover the DE/EN switch, the legal
 * pages, the bilingual WordPress blog, the free-plan quota boundary (client
 * prompt *and* server refusal) and the staff-only admin surface.
 *
 * Everything asserted here is observable in the running local stack; nothing
 * is stubbed. The account created by the free-plan journey is removed by the
 * global teardown, like the other e2e accounts.
 */

const PASSWORD = "E2eLaunch123456!"

/**
 * Seeds the UI locale before the app boots so the first screen is
 * deterministic. It only fills an empty preference: writing on every load
 * would overwrite the choice the test itself makes through the switcher.
 */
async function setLocale(page: Page, locale: "de" | "en") {
  await page.addInitScript((value: string) => {
    if (!window.localStorage.getItem("presence-locale")) {
      window.localStorage.setItem("presence-locale", value)
    }
  }, locale)
}

async function registerAndVerify(page: Page, email: string) {
  await page.goto("/register")
  await page.locator('input[placeholder="Maria Schmidt"]').fill("Launch Tester")
  await page.locator('input[placeholder="you@example.com"]').fill(email)
  await page.locator('input[placeholder="Min. 12 characters"]').fill(PASSWORD)
  await page.getByRole("button", { name: "Create account" }).click()
  await page.waitForURL(/\/login\?registered=true/, { timeout: 20_000 })

  const message = await waitForMessage(email)
  const verifyPath = extractPath(await messageBody(message.ID), "/verify-email")
  await page.goto(verifyPath)
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible()
}

async function signIn(page: Page, email: string) {
  await page.goto("/login")
  await page.locator('input[placeholder="you@example.com"]').fill(email)
  await page.locator('input[type="password"]').fill(PASSWORD)
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL(/\/app\/dashboard/, { timeout: 20_000 })
}

test("public journey: German by default, English switch, legal pages", async ({
  page,
}) => {
  const pageErrors: string[] = []
  page.on("pageerror", (error) => pageErrors.push(error.message))

  await setLocale(page, "de")
  await page.goto("/")
  await expect(page.locator("html")).toHaveAttribute("lang", "de")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Ihre digitale Präsenz",
  )

  // The stored preference survives a reload.
  await page.reload()
  await expect(page.locator("html")).toHaveAttribute("lang", "de")

  await page.getByRole("button", { name: "English" }).first().click()
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Your digital presence",
  )
  await page.reload()
  await expect(page.locator("html")).toHaveAttribute("lang", "en")

  await page.goto("/pricing")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Simple, transparent pricing",
  )

  // Legal pages follow the language switch instead of falling back to English.
  await page.getByRole("button", { name: "Deutsch" }).first().click()
  await expect(page.locator("html")).toHaveAttribute("lang", "de")

  const legalPages: { path: string; heading: string; marker: string }[] = [
    { path: "/terms", heading: "Allgemeine Geschäftsbedingungen", marker: "Arbeitsentwurf" },
    { path: "/privacy", heading: "Datenschutzerklärung", marker: "Arbeitsentwurf" },
    { path: "/impressum", heading: "Impressum", marker: "Platzhalter" },
    { path: "/widerruf", heading: "Widerrufsrecht", marker: "Vor dem Livegang erforderlich" },
    { path: "/cookies", heading: "Cookies und Speicherung", marker: "presence_access" },
  ]

  for (const legalPage of legalPages) {
    await page.goto(legalPage.path)
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      legalPage.heading,
    )
    await expect(page.getByText(legalPage.marker).first()).toBeVisible()
  }

  await expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
})

test("mobile layout stays inside the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setLocale(page, "de")

  for (const path of ["/", "/pricing", "/register", "/impressum"]) {
    await page.goto(path)
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    )
    expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(1)
  }
})

test("blog: German article, translated slug, published posts only", async ({
  page,
}) => {
  await setLocale(page, "de")
  await page.goto("/blog")
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
  // A CMS outage shows an explicit error state; it must not be there.
  await expect(page.getByText("Unable to load articles.")).toHaveCount(0)

  await page.goto("/blog/de-was-ist-website-monitoring")
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Was ist Website-Monitoring?",
  )

  // The article keeps its own language even though the UI is German here.
  await expect(page.locator("html")).toHaveAttribute("lang", "de")
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    /\/blog\/de-was-ist-website-monitoring$/,
  )

  // hreflang must point at the English slug, not at ?lang= on the German one.
  const englishAlternate = page.locator(
    'link[rel="alternate"][hreflang="en"]',
  )
  await expect(englishAlternate).toHaveAttribute(
    "href",
    /\/blog\/what-is-website-monitoring$/,
  )

  // The visible language switch offers the really published translation.
  await expect(
    page.getByRole("link", { name: "EN", exact: true }).first(),
  ).toBeVisible()
})

test("free plan: first website is accepted, the second is refused", async ({
  page,
}) => {
  const email = `e2e-launch-${Date.now()}@example.com`
  await registerAndVerify(page, email)
  await signIn(page, email)

  await page.goto("/app/websites")
  await page.getByRole("button", { name: /Add website/ }).first().click()
  const dialog = page.locator('[role="dialog"][aria-label="Add website"]')
  await dialog.locator('input[placeholder="example.com"]').fill(
    `e2e-site-${Date.now()}.example.com`,
  )
  await dialog.getByRole("button", { name: /^Add website$/ }).click()
  await expect(dialog).toHaveCount(0)

  // Second website: the UI sells the upgrade before the API answers…
  await page.getByRole("button", { name: /Add website/ }).first().click()
  const secondDialog = page.locator('[role="dialog"][aria-label="Add website"]')
  await secondDialog.locator('input[placeholder="example.com"]').fill(
    `e2e-blocked-${Date.now()}.example.com`,
  )
  await secondDialog.getByRole("button", { name: /^Add website$/ }).click()
  await expect(
    page.locator('[role="dialog"][aria-labelledby="upgrade-title"]'),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: /See plans/ })).toBeVisible()

  // …and the server refuses it anyway: hiding a button is not access control.
  const response = await page.evaluate(async () => {
    const token = window.localStorage.getItem("presence_access")
    const result = await fetch("/api/v1/websites/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token ?? ""}`,
      },
      body: JSON.stringify({ domain: "e2e-forbidden.example.com" }),
    })
    return { status: result.status, body: await result.json() }
  })

  expect(response.status).toBe(403)
  expect(response.body.code).toBe("website_limit_reached")
})

test("admin surface is staff-only", async ({ page }) => {
  const email = `e2e-admin-${Date.now()}@example.com`
  await registerAndVerify(page, email)
  await signIn(page, email)

  const forbidden = page.waitForResponse(
    (response) =>
      response.url().includes("/analytics/admin/overview/") &&
      response.status() === 403,
  )
  await page.goto("/admin")

  await expect(page.getByText("Staff access required")).toBeVisible()
  // The metrics section itself never renders for a non-staff account.
  await expect(page.getByText("Traffic — last 14 days")).toHaveCount(0)
  await expect(page.getByText("MRR", { exact: true })).toHaveCount(0)

  await forbidden
})
