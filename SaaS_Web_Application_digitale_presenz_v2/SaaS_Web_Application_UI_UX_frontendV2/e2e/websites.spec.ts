import { expect, test, type Page } from "@playwright/test"
import {
  HAS_AUTH,
  accessToken,
  deleteSmokeWebsites,
  login,
} from "./helpers/auth"
import { snap } from "./helpers/screenshot"

const domainFor = (label: string) =>
  `e2e-smoke-${label}-${Date.now()}.invalid`

async function authHeaders(page: Page) {
  return { Authorization: `Bearer ${await accessToken(page)}` }
}

test.describe("Bloc D — sites", () => {
  test.skip(!HAS_AUTH, "Set E2E_EMAIL and E2E_PASSWORD to run private smoke tests.")

  test.afterEach(async ({ page }) => {
    await deleteSmokeWebsites(page)
  })

  test("D1 — liste des sites", async ({ page }) => {
    await login(page)
    await page.goto("/app/websites")
    await expect(page.getByRole("heading", { name: "Websites" })).toBeVisible()
    await snap(page, "E2E_D1_sites.png")
  })

  test("D2 — ajout d’un site", async ({ page }) => {
    const domain = domainFor("ajout")
    await login(page)
    await page.goto("/app/websites")
    await page
      .getByRole("button", { name: "Website hinzufügen", exact: true })
      .first()
      .click()
    const dialog = page.getByRole("dialog", { name: "Website hinzufügen" })
    await expect(dialog).toBeVisible()
    await dialog.locator('input[placeholder="example.com"]').fill(domain)
    await dialog
      .getByRole("button", { name: "Website hinzufügen", exact: true })
      .click()
    await expect(page.getByText(domain, { exact: true })).toBeVisible({
      timeout: 20_000,
    })
    await snap(page, "E2E_D2_ajout.png")
  })

  test("D4 — suppression d’un site", async ({ page }) => {
    const domain = domainFor("suppression")
    await login(page)
    const response = await page.request.post("/api/v1/websites/", {
      headers: await authHeaders(page),
      data: { domain },
    })
    expect([200, 201]).toContain(response.status())
    await page.goto("/app/websites")
    const card = page.locator("div.p-5").filter({ hasText: domain }).first()
    await expect(card).toBeVisible({ timeout: 20_000 })
    await card.getByRole("button", { name: "Website löschen" }).click()
    const dialog = page.getByRole("dialog", { name: "Website löschen?" })
    await expect(dialog).toBeVisible()
    await snap(page, "E2E_D4_confirmation.png")
    await dialog.getByRole("button", { name: "Website löschen" }).click()
    await expect(page.getByText(domain, { exact: true })).toHaveCount(0, {
      timeout: 20_000,
    })
    await snap(page, "E2E_D4_suppression.png")
  })
})
