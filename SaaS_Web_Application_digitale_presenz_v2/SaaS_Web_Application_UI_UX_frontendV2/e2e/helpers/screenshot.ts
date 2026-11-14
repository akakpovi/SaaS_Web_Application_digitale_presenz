import { mkdirSync } from "node:fs"
import path from "node:path"
import type { Page } from "@playwright/test"

/**
 * Every smoke test writes its evidence under `screenshots/`, independently of
 * Playwright's failure-only artifacts.
 */
export async function snap(page: Page, name: string): Promise<void> {
  const dir = path.resolve(process.cwd(), "..", "screenshots")
  mkdirSync(dir, { recursive: true })
  await page.waitForTimeout(150)
  await page.screenshot({ path: path.join(dir, name), fullPage: true })
}
