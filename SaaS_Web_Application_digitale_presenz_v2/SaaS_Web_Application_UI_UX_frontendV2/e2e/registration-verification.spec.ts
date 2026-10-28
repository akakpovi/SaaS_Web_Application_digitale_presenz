import { expect, test } from "@playwright/test"
import { extractPath, messageBody, waitForMessage } from "./helpers/mailpit"

/**
 * Vital flow #1: sign-up must deliver a real verification e-mail whose link
 * actually verifies the account — the exact chain that was broken before the
 * `/verify-email` page existed.
 */
test("registration → e-mail link → verified account → login", async ({
  page,
}) => {
  const email = `e2e-reg-${Date.now()}@example.com`
  const password = "E2ePassword12345!"

  await page.goto("/register")
  await page.locator('input[placeholder="Maria Schmidt"]').fill("E2E Tester")
  await page.locator('input[placeholder="you@example.com"]').fill(email)
  await page.locator('input[placeholder="Min. 12 characters"]').fill(password)
  await page.getByRole("button", { name: "Create account" }).click()

  await page.waitForURL(/\/login\?registered=true/, { timeout: 20_000 })

  // The backend sends the message synchronously during registration; Mailpit
  // received it, so the test follows the exact link a user would click.
  const message = await waitForMessage(email)
  expect(message.Subject.toLowerCase()).toContain("verify")
  const body = await messageBody(message.ID)
  const verifyPath = extractPath(body, "/verify-email")

  await page.goto(verifyPath)
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible()

  // The account is usable and no longer flagged as unverified.
  await page.goto("/login")
  await page.locator('input[placeholder="you@example.com"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.getByRole("button", { name: "Sign in" }).click()

  await page.waitForURL(/\/app\/dashboard/, { timeout: 20_000 })
  await expect(page.getByText("E2E Tester", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Verified", { exact: true }).first()).toBeVisible()
})
