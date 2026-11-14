import { defineConfig } from "@playwright/test"

/**
 * Smoke / E2E suite for the local Docker stack.
 *
 * This is deliberately separate from `playwright.config.ts`: the historical
 * suite runs against the Vite dev server and has its own global setup. The
 * smoke suite talks to the real nginx entry point, uses the self-signed
 * certificate, and is run with:
 *
 *   E2E_EMAIL=... E2E_PASSWORD=... \
 *     npx playwright test --config=playwright.smoke.config.ts
 */
const baseURL = process.env.E2E_BASE_URL ?? "https://localhost"

export default defineConfig({
  testDir: "./e2e",
  testMatch:
    /(public-pages|auth|dashboard|websites|i18n-routing|admin|mobile|security|i18n-french)\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report-smoke" }],
  ],
  outputDir: "test-results-smoke",
  use: {
    baseURL,
    ignoreHTTPSErrors: true,
    // Local runs are intentionally visible; CI has no display.
    headless: Boolean(process.env.CI),
    viewport: { width: 1280, height: 720 },
    locale: "de-DE",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
})
