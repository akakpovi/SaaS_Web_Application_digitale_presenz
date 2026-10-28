import { expect, test, type APIRequestContext } from "@playwright/test"
import { canonicalOf, message, startDistServer } from "./helpers/static-dist"

/**
 * Internal links stay in the language of the page they are on.
 *
 * `/en/...` is the English site and the bare paths the German one. A plain
 * `<Link to="/pricing">` is absolute, so before this lot every English page
 * sent the next click to the German URL. `src/components/LocaleLink.tsx`
 * prefixes only the public bilingual paths; private routes (`/login`,
 * `/register`) and CMS article slugs keep their single URL.
 *
 * The assertions read the *built* HTML and then click in a real browser, so
 * both the href a crawler sees and the navigation a visitor gets are covered.
 * `pnpm build` must have run first.
 */

let origin = ""
let stop: (() => Promise<void>) | undefined

test.beforeAll(async () => {
  const server = await startDistServer()
  origin = server.origin
  stop = server.close
})

test.afterAll(async () => {
  await stop?.()
})

async function fetchHtml(request: APIRequestContext, url: string) {
  const response = await request.get(`${origin}${url}`)
  return { status: response.status(), body: await response.text() }
}

/** Links the page renders, minus assets and icons. */
function pageHrefs(html: string): string[] {
  return [
    ...new Set(
      [...html.matchAll(/href="(\/[^"]*)"/g)]
        .map((match) => match[1])
        .filter(
          (href) =>
            !href.startsWith("/assets/") &&
            !href.startsWith("/icons/") &&
            !href.startsWith("/apple-touch") &&
            !href.startsWith("/favicon") &&
            !href.startsWith("/manifest"),
        ),
    ),
  ].sort()
}

test("the pre-rendered English HTML links to /en, never to a bare public path", async ({
  request,
}) => {
  const { status, body } = await fetchHtml(request, "/en/features/ssl-monitoring")
  expect(status, "/en/features/ssl-monitoring is not served").toBe(200)

  for (const href of [
    "/en",
    "/en/pricing",
    "/en/faq",
    "/en/about",
    "/en/features/website-monitoring",
    "/en/tools/ssl-checker",
  ]) {
    expect(pageHrefs(body), `/en page does not link to ${href}`).toContain(href)
  }

  for (const bare of [
    "/pricing",
    "/faq",
    "/about",
    "/features/website-monitoring",
    "/tools/ssl-checker",
  ]) {
    expect(
      pageHrefs(body),
      `the English page still renders the bare public link ${bare}`,
    ).not.toContain(bare)
  }

  // Private entry points have one URL, whatever the language of the page.
  expect(pageHrefs(body)).toContain("/login")
  expect(pageHrefs(body)).toContain("/register")
  expect(pageHrefs(body), "a private route was mounted under /en").not.toContain(
    "/en/login",
  )
})

test("the pre-rendered German HTML keeps every bare path", async ({ request }) => {
  const { status, body } = await fetchHtml(request, "/features/ssl-monitoring")
  expect(status, "/features/ssl-monitoring is not served").toBe(200)
  const hrefs = pageHrefs(body)

  for (const href of [
    "/",
    "/pricing",
    "/faq",
    "/about",
    "/features/website-monitoring",
    "/tools/ssl-checker",
  ]) {
    expect(hrefs, `German page does not link to ${href}`).toContain(href)
  }
  expect(
    hrefs.filter((href) => href.startsWith("/en")),
    "a German page links into the English site",
  ).toEqual([])
})

test("a click on an English page stays under /en; a German click stays bare", async ({
  page,
}) => {
  test.setTimeout(180_000)

  // English: feature page → header "Pricing" → canonical /en/pricing.
  await page.goto(`${origin}/en/features/ssl-monitoring`)
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
  await page
    .getByRole("link", { name: message("en", "nav.pricing"), exact: true })
    .first()
    .click()
  await expect(page).toHaveURL(`${origin}/en/pricing`)
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
  const canonical = canonicalOf(await page.content())
  expect(canonical).toBeTruthy()
  expect(new URL(canonical!).pathname).toBe("/en/pricing")

  // English: /en/pricing → back to the site → /en → a "Website Monitoring"
  // card → /en/features/website-monitoring, still in English.
  await page.getByRole("link", { name: message("en", "pricing.backToSite") }).click()
  await expect(page).toHaveURL(`${origin}/en`)
  await page
    .getByRole("link", {
      name: message("en", "landing.features.websiteMonitoring.title"),
    })
    .first()
    .click()
  await expect(page).toHaveURL(`${origin}/en/features/website-monitoring`)
  await expect(page.locator("html")).toHaveAttribute("lang", "en")

  // German: the same card on the bare landing page keeps the bare path.
  await page.goto(`${origin}/pricing`)
  await expect(page.locator("html")).toHaveAttribute("lang", "de")
  await page.getByRole("link", { name: message("de", "pricing.backToSite") }).click()
  await expect(page).toHaveURL(`${origin}/`)
  await page
    .getByRole("link", {
      name: message("de", "landing.features.websiteMonitoring.title"),
    })
    .first()
    .click()
  await expect(page).toHaveURL(`${origin}/features/website-monitoring`)
  await expect(page.locator("html")).toHaveAttribute("lang", "de")
})
