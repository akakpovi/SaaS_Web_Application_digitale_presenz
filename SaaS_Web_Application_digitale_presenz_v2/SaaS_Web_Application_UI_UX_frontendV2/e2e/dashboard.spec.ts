import { expect, test } from "@playwright/test"
import { HAS_AUTH, login } from "./helpers/auth"
import { snap } from "./helpers/screenshot"

test.describe("Bloc C — dashboard", () => {
  test.skip(!HAS_AUTH, "Set E2E_EMAIL and E2E_PASSWORD to run private smoke tests.")

  test("C1 — dashboard allemand et titre correct", async ({ page }) => {
    await login(page)
    await page.goto("/app/dashboard")
    await expect(page).toHaveTitle(/Übersicht \| Presence/)
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    await snap(page, "E2E_C1_dashboard.png")
  })

  test("C2 — navigation latérale complète", async ({ page }) => {
    await login(page)
    await page.goto("/app/dashboard")
    const sidebar = page.locator("aside nav").first()
    await expect(sidebar.locator("a")).toHaveCount(9)
    for (const label of ["Websites", "Scans", "Überwachung", "Warnungen", "Berichte"]) {
      await expect(sidebar).toContainText(label)
    }
    await expect(page.locator("aside")).toContainText("Abrechnung")
    await expect(page.locator("aside")).toContainText("Einstellungen")
    await expect(page.locator("aside")).toContainText("Hilfe")
    await snap(page, "E2E_C2_sidebar.png")
  })

  test("C3 — dashboard français", async ({ page }) => {
    await login(page)
    await page.goto("/fr/app/dashboard")
    await expect(page.locator("html")).toHaveAttribute("lang", "fr")
    await expect(page).toHaveTitle(/Aperçu \| Presence/)
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    await snap(page, "E2E_C3_dashboard_fr.png")
  })
})
