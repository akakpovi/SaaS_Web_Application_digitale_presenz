import { expect, test } from "@playwright/test"
import { snap } from "./helpers/screenshot"

test.describe("Bloc J — mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test("J1 — hamburger et drawer plein écran", async ({ page }) => {
    await page.goto("/")
    const trigger = page.locator('button[aria-controls="public-mobile-menu"]')
    await expect(trigger).toBeVisible()
    await trigger.click()
    const drawer = page.locator("#public-mobile-menu")
    await expect(drawer).toBeVisible()
    await expect(drawer.getByRole("link", { name: "Funktionen" })).toBeVisible()
    const height = await drawer.evaluate((element) => element.getBoundingClientRect().height)
    expect(height).toBeGreaterThanOrEqual(800)
    await snap(page, "E2E_J1_mobile.png")
  })

  test("J3 — login mobile", async ({ page }) => {
    await page.goto("/login/")
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]').first()).toBeVisible()
    await snap(page, "E2E_J3_mobile_login.png")
  })
})
