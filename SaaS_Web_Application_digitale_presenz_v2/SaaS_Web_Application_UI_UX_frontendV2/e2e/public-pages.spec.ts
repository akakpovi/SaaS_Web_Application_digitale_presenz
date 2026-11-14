import { expect, test } from "@playwright/test"
import { snap } from "./helpers/screenshot"

test.describe("Bloc A — pages publiques", () => {
  test("A1 — accueil DE", async ({ page }) => {
    await page.goto("/")
    await expect(page.locator("html")).toHaveAttribute("lang", "de")
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    await expect(page.locator("body")).toContainText("Ihre digitale Präsenz")
    await snap(page, "E2E_A1_accueil_de.png")
  })

  test("A2 — accueil FR", async ({ page }) => {
    await page.goto("/fr/")
    await expect(page.locator("html")).toHaveAttribute("lang", "fr")
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    await expect(page.locator("body")).toContainText("présence numérique")
    await snap(page, "E2E_A2_accueil_fr.png")
  })

  test("A3 — accueil EN", async ({ page }) => {
    await page.goto("/en/")
    await expect(page.locator("html")).toHaveAttribute("lang", "en")
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    await snap(page, "E2E_A3_accueil_en.png")
  })

  test("A4 — /de/ redirige en 301 vers /", async ({ request }) => {
    const response = await request.get("/de/", {
      maxRedirects: 0,
      failOnStatusCode: false,
    })
    expect(response.status()).toBe(301)
    expect(response.headers()["location"]).toMatch(/^\/$|^https:\/\/localhost\/$/)
  })

  test("A5 — pricing public sans plan QA", async ({ page }) => {
    await page.goto("/pricing/")
    await expect(page.locator("html")).toHaveAttribute("lang", "de")
    for (const plan of ["Free", "Pro", "Business", "Agency"]) {
      await expect(page.locator("body")).toContainText(plan)
    }
    await expect(page.locator("body")).not.toContainText("QA Interne")
    await expect(page.locator("body")).not.toContainText("AKTUELLER TARIF")
    await snap(page, "E2E_A5_pricing.png")
  })

  test("A7 — blog DE ne contient que les articles allemands", async ({ page }) => {
    await page.goto("/blog/")
    await expect(page.locator("html")).toHaveAttribute("lang", "de")
    const cards = page.locator("main article h2")
    await expect(cards).toHaveCount(2)
    await expect(page.locator("main")).toContainText("Was ist Website-Monitoring?")
    await expect(page.locator("main")).toContainText("So prüfen Sie Ihr SSL-Zertifikat")
    await expect(page.locator("main")).not.toContainText(
      "Digital presence checklist for small businesses",
    )
    await snap(page, "E2E_A7_blog_de.png")
  })

  test("A9 — blog FR sans aucun article allemand", async ({ page }) => {
    await page.goto("/fr/blog/")
    await expect(page.locator("html")).toHaveAttribute("lang", "fr")
    await expect(page.locator("main article")).toHaveCount(0)
    await expect(page.locator("main")).toContainText(
      "Aucun article disponible en français pour le moment.",
    )
    await expect(page.locator("main")).not.toContainText("Was ist Website-Monitoring?")
    await expect(page.locator("main")).not.toContainText("So prüfen Sie Ihr SSL-Zertifikat")
    await snap(page, "E2E_A9_blog_fr.png")
  })

  test("A10 — login DE", async ({ page }) => {
    await page.goto("/login/")
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await snap(page, "E2E_A10_login_de.png")
  })

  test("A11 — login FR", async ({ page }) => {
    await page.goto("/fr/login/")
    await expect(page.locator("html")).toHaveAttribute("lang", "fr")
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await snap(page, "E2E_A11_login_fr.png")
  })

  test("A12 — 404 localisée", async ({ page }) => {
    const response = await page.goto("/page-e2e-introuvable/")
    expect(response?.status()).toBe(404)
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Seite nicht gefunden",
    )
    await snap(page, "E2E_A12_404.png")
  })
})
