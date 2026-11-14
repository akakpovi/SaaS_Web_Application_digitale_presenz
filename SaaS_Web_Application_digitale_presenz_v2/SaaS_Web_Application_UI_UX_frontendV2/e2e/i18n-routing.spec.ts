import { expect, test } from "@playwright/test"
import { expectLocale, switchLocale } from "./helpers/locale"
import { snap } from "./helpers/screenshot"

test.describe("Bloc H — routage i18n", () => {
  test("H1 — switch FR vers /fr/", async ({ page }) => {
    await page.goto("/")
    await switchLocale(page, "fr")
    await expectLocale(page, "fr", "/fr/$")
    await snap(page, "E2E_H1_fr.png")
  })

  test("H2 — switch EN vers /en/", async ({ page }) => {
    await page.goto("/fr/")
    await switchLocale(page, "en")
    await expectLocale(page, "en", "/en/$")
    await snap(page, "E2E_H2_en.png")
  })

  test("H3 — switch DE vers /", async ({ page }) => {
    await page.goto("/en/")
    await switchLocale(page, "de")
    await expect(page).toHaveURL(/\/$/)
    await expect(page.locator("html")).toHaveAttribute("lang", "de")
    await snap(page, "E2E_H3_de.png")
  })

  test("H4 — persistance de la locale après reload", async ({ page }) => {
    await page.goto("/fr/pricing/")
    await expectLocale(page, "fr", "/fr/pricing/")
    await page.reload()
    await expectLocale(page, "fr", "/fr/pricing/")
    await snap(page, "E2E_H4_persistance.png")
  })
})
