import { defineConfig, devices } from "@playwright/test"

/**
 * End-to-end tests run against the Vite dev server, whose `/api` proxy points
 * at the local Docker stack (nginx + Django + Mailpit).
 *
 * Prerequisites:
 *   docker compose up -d          # API, database, Mailpit
 *   pnpm dev                      # or let Playwright start it (webServer below)
 *
 * The browser only talks to http://localhost:5173, so the self-signed TLS
 * certificate of https://localhost never reaches the test browser.
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "pnpm dev --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
