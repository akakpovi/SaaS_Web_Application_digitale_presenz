import { readFileSync, readdirSync, existsSync } from "node:fs"
import path from "node:path"
import { expect, test, type APIRequestContext, type Page } from "@playwright/test"
import { DIST, ROOT, message, startDistServer } from "./helpers/static-dist"

/**
 * The SSG artifact itself.
 *
 * `scripts/check-seo-build.mjs` guards the head, the sitemap and the presence
 * of a page-specific body. This suite adds what a static check cannot prove:
 * the raw HTML really contains the marketing sections, the plan table, the FAQ
 * answers and the legal copy; CMS articles carry their real body; and the
 * browser hydrates that markup without replacing or complaining about it.
 *
 * `pnpm build` must have run first (the suite fails with that instruction
 * instead of skipping).
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

async function raw(request: APIRequestContext, url: string) {
  const response = await request.get(`${origin}${url}`)
  return { status: response.status(), body: await response.text() }
}

/** Inner HTML of the pre-rendered root, i.e. what a crawler reads. */
function rootBody(html: string) {
  const start = html.indexOf('<div id="root"')
  const end = html.indexOf("</body>", start)
  return start >= 0 && end > start ? html.slice(start, end) : ""
}

test("the landing page ships its marketing sections, not a shell", async ({
  request,
}) => {
  for (const [locale, url] of [
    ["de", "/"],
    ["en", "/en"],
  ] as const) {
    const { status, body } = await raw(request, url)
    expect(status, `${url}: status`).toBe(200)
    const content = rootBody(body)
    expect(content, `${url}: no SSG root`).toContain('data-ssg="true"')

    // Hero, social proof, feature and pricing teaser blocks of the real page.
    for (const copy of [
      message(locale, "landing.titleLead"),
      message(locale, "landing.checkCta"),
      message(locale, "landing.faqTitle"),
    ]) {
      expect(content, `${url}: missing "${copy}"`).toContain(copy)
    }
    // The footer and its legal links are part of the page, not injected later.
    expect(content, `${url}: no footer`).toContain(
      locale === "de" ? "Impressum" : "Imprint",
    )
  }
})

test("pricing contains every plan and the real prices in both languages", async ({
  request,
}) => {
  for (const [locale, url, perMonth] of [
    ["de", "/pricing", "/Monat"],
    ["en", "/en/pricing", "/month"],
  ] as const) {
    const { status, body } = await raw(request, url)
    expect(status, `${url}: status`).toBe(200)
    const content = rootBody(body)
    for (const plan of ["Free", "Pro", "Business", "Agency"]) {
      expect(content, `${url}: no ${plan} card`).toContain(plan)
    }
    for (const price of ["€0", "€9", "€29", "€79"]) {
      expect(content, `${url}: no ${price} price`).toContain(price)
    }
    expect(content, `${url}: prices are not per month`).toContain(perMonth)
  }
})

test("FAQ answers are in the HTML even while the accordion is closed", async ({
  request,
}) => {
  for (const [locale, url] of [
    ["de", "/faq"],
    ["en", "/en/faq"],
  ] as const) {
    const { body } = await raw(request, url)
    const content = rootBody(body)
    const answer = message(locale, "faqPage.categories.general.i1.a")
    expect(content, `${url}: the first answer is not rendered`).toContain(
      answer.slice(0, 120),
    )
    // Collapsed with the `hidden` attribute, so the answer is invisible but
    // crawlable; a conditional render would drop it from the document.
    expect(content, `${url}: answers are not collapsed`).toContain(
      '<div hidden=""',
    )
  }
})

test("feature pages contain their own sections, not the generic fallback", async ({
  request,
}) => {
  for (const [locale, url] of [
    ["de", "/features/ssl-monitoring"],
    ["en", "/en/features/ssl-monitoring"],
  ] as const) {
    const { body } = await raw(request, url)
    const content = rootBody(body)
    for (const heading of [
      message(locale, "features.shared.whatWeCheck"),
      message(locale, "features.shared.faqTitle"),
      message(locale, "features.shared.relatedTitle"),
    ]) {
      expect(content, `${url}: missing "${heading}"`).toContain(heading)
    }
    expect(content, `${url}: fallback shell`).not.toContain(
      'data-prerender="true"',
    )
  }
})

test("legal pages carry their content and the draft warning", async ({
  request,
}) => {
  for (const [locale, route, marker] of [
    ["de", "/privacy", "Verantwortlicher"],
    ["en", "/en/privacy", "Controller"],
    ["de", "/impressum", "Impressum"],
    ["en", "/en/impressum", "Imprint"],
    ["de", "/terms", "Kündigung"],
    ["en", "/en/terms", "cancellation"],
    ["de", "/widerruf", "Widerruf"],
    ["en", "/en/widerruf", "withdrawal"],
  ] as const) {
    const { status, body } = await raw(request, route)
    expect(status, `${route}: status`).toBe(200)
    const content = rootBody(body)
    expect(content, `${route}: missing ${marker}`).toContain(marker)
    expect(content, `${route}: no draft notice`).toMatch(
      /Arbeitsentwurf|Working draft|vor dem Livegang|before publication|must be completed before launch/,
    )
  }
})

test("CMS articles ship their real body and title", async () => {
  // No network here: the assertion is about the artifact the build produced.
  // The directory exists only when the CMS answered at build time.
  const blogDir = path.join(DIST, "blog")
  test.skip(!existsSync(blogDir), "no pre-rendered articles in this build")
  const articles = readdirSync(blogDir, { withFileTypes: true }).filter(
    (entry) => entry.isDirectory(),
  )
  expect(articles.length, "no article was pre-rendered").toBeGreaterThan(0)

  for (const entry of articles) {
    const file = path.join(blogDir, entry.name, "index.html")
    const html = readFileSync(file, "utf8")
    const title = html.match(/<title[^>]*>([^<]*)<\/title>/)?.[1]
    expect(title, `${entry.name}: no title`).toBeTruthy()

    const article = html.match(/<article>([\s\S]*?)<\/article>/)?.[1] ?? ""
    const text = article.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
    // A real WordPress body, not a placeholder paragraph. The article pages are
    // deliberately written as static shells (no React SSG): their content comes
    // from the CMS, so only the body matters here.
    expect(text.length, `${entry.name}: body too short`).toBeGreaterThan(500)
  }
})

/** Console errors the browser reported while hydrating. */
async function hydrationErrors(page: Page) {
  const errors: string[] = []
  page.on("console", (message) => {
    if (message.type() !== "error") return
    const text = message.text()
    if (/hydrat|did not match|server rendered/i.test(text)) errors.push(text)
  })
  page.on("pageerror", (error) => errors.push(error.message))
  return errors
}

test("the pre-rendered pages hydrate without errors or full replacement", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000)

  for (const [locale, url] of [
    ["de", "/"],
    ["en", "/en"],
    ["de", "/pricing"],
    ["en", "/en/pricing"],
    ["de", "/faq"],
    ["en", "/en/faq"],
  ] as const) {
    const { body } = await raw(request, url)
    const serverH1 = body
      .match(/<h1[^>]*>([\s\S]*?)<\/h1>/)?.[1]
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim()
    expect(serverH1, `${url}: no <h1> in the pre-rendered HTML`).toBeTruthy()
    const errors = await hydrationErrors(page)

    const response = await page.goto(`${origin}${url}`)
    expect(response?.status(), `${url}: status`).toBe(200)
    await expect(page.locator("html")).toHaveAttribute("lang", locale)
    // The same heading the crawler received is still on screen: the app did
    // not replace the document with a different tree.
    await expect(page.getByRole("heading", { level: 1 }).first()).toContainText(
      serverH1!.slice(0, 40),
    )
    await expect(page.locator('[data-prerender="true"]')).toHaveCount(0)

    // The switcher and an internal link still work after hydration. Both the
    // header and the footer expose a switcher, so target the first one.
    await page
      .getByRole("button", { name: message("de", "nav.german") })
      .first()
      .click()
    await expect(page.locator("html")).toHaveAttribute("lang", "de")
    await page
      .getByRole("button", { name: message("en", "nav.english") })
      .first()
      .click()
    await expect(page.locator("html")).toHaveAttribute("lang", "en")

    page.removeAllListeners("console")
    page.removeAllListeners("pageerror")
    expect(errors, `${url}: hydration errors`).toEqual([])
  }
})

test("the blog index lists the build-time posts after hydration", async ({
  page,
}) => {
  const blogDir = path.join(DIST, "blog")
  test.skip(!existsSync(blogDir), "no pre-rendered articles in this build")

  const list = await page.goto(`${origin}/blog`)
  expect(list?.status()).toBe(200)
  // Posts come from `#__blog-data`, so they are visible without waiting for a
  // network round-trip to the CMS.
  const data = await page.locator("#__blog-data").textContent()
  const parsed = JSON.parse(data!) as { posts: { title: string }[] }
  expect(parsed.posts.length).toBeGreaterThan(0)
  await expect(page.getByText(parsed.posts[0].title, { exact: false })).toBeVisible()
})
