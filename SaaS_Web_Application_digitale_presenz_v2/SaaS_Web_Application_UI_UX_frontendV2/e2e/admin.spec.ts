import { expect, test, type Page } from "@playwright/test"
import { EMAIL, PASSWORD } from "./helpers/auth"
import { snap } from "./helpers/screenshot"

const ADMIN_USER = process.env.E2E_ADMIN_USER?.trim() ?? EMAIL
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? PASSWORD
const HAS_ADMIN = Boolean(ADMIN_USER && ADMIN_PASSWORD)

async function adminLogin(page: Page) {
  await page.goto("/admin/login/")
  await page.locator("#id_username").fill(ADMIN_USER!)
  await page.locator("#id_password").fill(ADMIN_PASSWORD!)
  await page.locator('input[type="submit"]').click()
  await page.waitForURL(/\/admin\//, { timeout: 20_000 })
}

test.describe("Bloc I — admin Django", () => {
  test.skip(!HAS_ADMIN, "Set E2E_EMAIL/E2E_PASSWORD (or admin env) to run admin tests.")

  test("I1 — login admin", async ({ page }) => {
    await adminLogin(page)
    await expect(page.locator("body")).toContainText(/Site administration|Website-Verwaltung|Administration du site/i)
    await snap(page, "E2E_I1_admin.png")
  })

})

test.describe("Bloc K — admin anonyme", () => {
  test("K2 — /admin/ redirige vers le login Django", async ({ page }) => {
    await page.goto("/admin/")
    await page.waitForURL(/\/admin\/login\/\?next=\/admin\/?/, { timeout: 20_000 })
    await expect(page.locator("#id_username")).toBeVisible()
    await snap(page, "E2E_K2_admin_anon.png")
  })
})
