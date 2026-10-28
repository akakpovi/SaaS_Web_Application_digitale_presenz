import { expect, test } from "@playwright/test"
import { waitForMessage } from "./helpers/mailpit"

/**
 * Vital flow #2: an anonymous visitor scans a real domain, sees the backend's
 * report, shares it, and leaves an e-mail to receive it — the lead funnel.
 */
test("public scan → real report → shared link → lead capture", async ({
  page,
  request,
  context,
  baseURL,
}) => {
  const lead = `e2e-lead-${Date.now()}@example.com`
  await context.grantPermissions(["clipboard-read", "clipboard-write"], {
    origin: new URL(baseURL!).origin,
  })

  await page.goto("/tools/website-checker?domain=example.com")
  await page.waitForURL(/\/scan\/\d+/, { timeout: 30_000 })

  const scanId = page.url().match(/\/scan\/(\d+)/)?.[1]
  expect(scanId).toBeTruthy()

  await expect(page.getByText("Report ready")).toBeVisible({ timeout: 75_000 })
  await expect(page.getByRole("heading", { name: "Health checks" })).toBeVisible()

  // The page must render the API report, not a fixture: read the same scan
  // through the backend and compare the displayed score.
  const apiResponse = await request.get(
    `/api/v1/public/scan/${scanId}/status/`,
  )
  expect(apiResponse.ok()).toBeTruthy()
  const report = (await apiResponse.json()) as {
    status: string
    score: number
    checks: Record<string, { status: string }>
  }
  expect(report.status).toBe("completed")
  await expect(
    page.getByText(String(report.score), { exact: true }).first(),
  ).toBeVisible()
  expect(Object.keys(report.checks)).toHaveLength(7)

  // `/report/:id` is the legacy share URL: it must redirect to the real report.
  await page.goto(`/report/${scanId}`)
  await expect(page).toHaveURL(new RegExp(`/scan/${scanId}$`))
  await expect(page.getByText("Report ready")).toBeVisible({ timeout: 30_000 })

  // Sharing exposes the real, reloadable public URL.
  await page.getByRole("button", { name: "Share" }).click()
  await expect(page.getByText("Link copied")).toBeVisible()
  const clipboard = await page.evaluate(() => navigator.clipboard.readText())
  expect(clipboard).toContain(`/scan/${scanId}`)

  // Lead capture: the address is stored and the report e-mail is really sent.
  await page.getByPlaceholder("you@example.com").fill(lead)
  await page.getByRole("button", { name: "Send report" }).click()
  await expect(page.getByText(`Report sent to ${lead}`)).toBeVisible({
    timeout: 20_000,
  })

  const delivered = await waitForMessage(lead, 30_000)
  expect(delivered.To[0].Address.toLowerCase()).toBe(lead)
})
