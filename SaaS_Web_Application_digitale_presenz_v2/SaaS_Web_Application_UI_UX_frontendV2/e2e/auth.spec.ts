import { expect, test } from "@playwright/test"
import { EMAIL, HAS_AUTH, PASSWORD, login, logout } from "./helpers/auth"
import { snap } from "./helpers/screenshot"

test.describe("Bloc B — authentification", () => {
  test("B1 — inscription avec deux champs de mot de passe", async ({ page }) => {
    await page.goto("/register/")
    await expect(page.locator('input[type="password"]')).toHaveCount(2)
    const passwords = page.locator('input[type="password"]')
    await passwords.nth(0).fill("E2ePassword12345!")
    await passwords.nth(1).fill("DifferentPassword123!")
    await page.locator("button[type=submit]").first().click()
    await expect(page.locator("body")).toContainText(
      "Die Passwörter stimmen nicht überein",
    )
    await snap(page, "E2E_B1_inscription.png")
  })

  test.describe("compte QA", () => {
    test.skip(!HAS_AUTH, "Set E2E_EMAIL and E2E_PASSWORD to run private smoke tests.")

    test("B2 — doublon affiche une erreur localisée", async ({ page }) => {
      await page.goto("/register/")
      await page.locator('input[type="email"]').fill(EMAIL!)
      await page.locator('input[type="password"]').nth(0).fill(PASSWORD!)
      await page.locator('input[type="password"]').nth(1).fill(PASSWORD!)
      await page.locator("button[type=submit]").first().click()
      await expect(page.locator("body")).toContainText(
        "Diese E-Mail-Adresse wird bereits verwendet.",
        { timeout: 20_000 },
      )
      await snap(page, "E2E_B2_doublon.png")
    })

    test("B3 — connexion QA et dashboard", async ({ page }) => {
      await login(page)
      await expect(page).toHaveURL(/\/app\/dashboard/)
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
      await snap(page, "E2E_B3_login.png")
    })

    test("B4 — échec de connexion localisé", async ({ page }) => {
      await page.goto("/login/")
      await page.locator('input[type="email"]').fill(EMAIL!)
      await page.locator('input[type="password"]').fill("WrongPassword!2026")
      await page.locator('button[type="submit"]').first().click()
      await expect(page.locator("body")).toContainText(
        "E-Mail-Adresse oder Passwort ist falsch.",
        { timeout: 20_000 },
      )
      await snap(page, "E2E_B4_echec.png")
    })

    test("L1 — déconnexion et suppression des tokens", async ({ page }) => {
      await login(page)
      await logout(page)
      await snap(page, "E2E_L1_logout.png")
    })
  })
})
