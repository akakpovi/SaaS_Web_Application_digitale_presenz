import { expect, type Page } from "@playwright/test"

export type SmokeLocale = "de" | "en" | "fr"

const NAMES: Record<SmokeLocale, RegExp> = {
  de: /Deutsch|German|Allemand/i,
  en: /Englisch|English|Anglais/i,
  fr: /Französisch|French|Français/i,
}

/** Clicks the visible language switcher (real user path, not localStorage). */
export async function switchLocale(page: Page, locale: SmokeLocale): Promise<void> {
  const button = page.getByRole("button", { name: NAMES[locale] }).first()
  await expect(button).toBeVisible()
  await button.click()
}

export async function expectLocale(
  page: Page,
  locale: SmokeLocale,
  urlPart?: string,
): Promise<void> {
  await expect(page.locator("html")).toHaveAttribute("lang", locale)
  if (urlPart) await expect(page).toHaveURL(new RegExp(urlPart))
}
