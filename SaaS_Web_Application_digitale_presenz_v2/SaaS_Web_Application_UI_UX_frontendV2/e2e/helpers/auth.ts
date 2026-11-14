import { expect, type Page } from "@playwright/test"

/** Credentials come from the shell, never from a tracked file. */
export const EMAIL = process.env.E2E_EMAIL?.trim()
export const PASSWORD = process.env.E2E_PASSWORD
export const HAS_AUTH = Boolean(EMAIL && PASSWORD)

export function requireCredentials(): { email: string; password: string } {
  if (!EMAIL || !PASSWORD) {
    throw new Error("E2E_EMAIL and E2E_PASSWORD are required for this test.")
  }
  return { email: EMAIL, password: PASSWORD }
}

/**
 * Signs in through the real form. The app redirects to `/app/dashboard` (or
 * its localized equivalent) after a successful login.
 */
export async function login(page: Page): Promise<void> {
  const { email, password } = requireCredentials()
  await page.goto("/login/", { waitUntil: "domcontentloaded" })
  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button[type="submit"]').first().click()
  await page.waitForURL(/\/app\/dashboard/, { timeout: 20_000 })
  await expect(page.locator("#root")).not.toBeEmpty()
}

/** Opens a protected page after login (used by the localized dashboard test). */
export async function ensureLoggedIn(page: Page, path = "/app/dashboard"): Promise<void> {
  if (!/\/app\//.test(new URL(page.url()).pathname)) {
    await login(page)
  }
  await page.goto(path, { waitUntil: "domcontentloaded" })
}

/** Signs out through the visible sidebar action and checks the session tokens. */
export async function logout(page: Page): Promise<void> {
  const button = page
    .locator(
      'button[aria-label="Abmelden"], button[aria-label="Log out"], button[aria-label="Déconnexion"]',
    )
    .first()
  await expect(button).toBeVisible()
  await button.click()
  await page.waitForURL(/\/login/, { timeout: 20_000 })
  const tokens = await page.evaluate(() => ({
    access: localStorage.getItem("presence_access"),
    refresh: localStorage.getItem("presence_refresh"),
  }))
  expect(tokens).toEqual({ access: null, refresh: null })
}

/** Returns the JWT stored by the real login flow. */
export async function accessToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => localStorage.getItem("presence_access"))
  expect(token, "the app did not store an access token").toBeTruthy()
  return token!
}

/**
 * Deletes only sites created by this suite. It is safe to call in afterEach
 * even when the test failed before creating its site.
 */
export async function deleteSmokeWebsites(page: Page): Promise<void> {
  let token: string
  try {
    token = await accessToken(page)
  } catch {
    return
  }
  const headers = { Authorization: `Bearer ${token}` }
  const response = await page.request.get("/api/v1/websites/", { headers })
  if (!response.ok()) return
  const payload = (await response.json()) as
    | { results?: { id: number; domain: string }[] }
    | { id: number; domain: string }[]
  const sites = Array.isArray(payload) ? payload : (payload.results ?? [])
  for (const site of sites) {
    if (site.domain.startsWith("e2e-smoke-")) {
      await page.request.delete(`/api/v1/websites/${site.id}/`, { headers })
    }
  }
}
