import { expect, test } from "@playwright/test"
import { HAS_AUTH, accessToken, login } from "./helpers/auth"
import { snap } from "./helpers/screenshot"

test.describe("Bloc K — sécurité", () => {
  test("K1 — anonyme redirigé depuis une page privée", async ({ page }) => {
    await page.goto("/app/dashboard")
    await page.waitForURL(/\/login/, { timeout: 20_000 })
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await snap(page, "E2E_K1_redirect.png")
  })

  test.describe("JWT", () => {
    test.skip(!HAS_AUTH, "Set E2E_EMAIL and E2E_PASSWORD to run the JWT test.")

    test("K3 — le JWT ouvre /auth/me/", async ({ page }) => {
      await login(page)
      const token = await accessToken(page)
      const response = await page.request.get("/api/v1/auth/me/", {
        headers: { Authorization: `Bearer ${token}` },
      })
      expect(response.status()).toBe(200)
      const profile = (await response.json()) as { email?: string }
      expect(profile.email).toBe(process.env.E2E_EMAIL?.trim())
      await snap(page, "E2E_K3_jwt.png")
    })
  })
})
