import { existsSync, readFileSync } from "node:fs"
import path from "node:path"
import { expect, test, type APIRequestContext } from "@playwright/test"
import { PUBLIC_PATHS } from "../src/seo/publicPaths"
import { DIST, ROOT, startDistServer } from "./helpers/static-dist"

/**
 * `?lang=` is not a URL any more — it is a redirect.
 *
 * Before `/en/...` existed, English lived on the German URL plus a query
 * parameter. Every published link, bookmark and search result may still carry
 * that form, so nginx answers 301 to the canonical page instead of serving a
 * second copy. This spec pins that contract on the *generated* artifact and the
 * real nginx rules (helpers/static-dist.ts):
 *
 *   1. each of the 29 public routes redirects `?lang=en` to `/en/...` and
 *      `?lang=de` to the bare path, with the exact `Location`;
 *   2. following the redirect lands on a 200 in the declared language, and the
 *      target never redirects again (no loop);
 *   3. the five noindex screens do not redirect at all: `/en/login` does not
 *      exist, so a 301 there would be a 404;
 *   4. the `_i18n` copies of the public routes are gone from the build, while
 *      the private ones remain.
 *
 * `pnpm build` must have run first (the suite fails with that instruction
 * rather than skipping).
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

interface SeoRoute {
  path: string
  noindex?: boolean
}

const ROUTES: SeoRoute[] = JSON.parse(
  readFileSync(path.join(ROOT, "src", "seo", "routes.json"), "utf8"),
)
const NOINDEX_PATHS = ROUTES.filter((route) => route.noindex).map(
  (route) => route.path,
)

/** English URL of a public route. */
function englishUrl(routePath: string): string {
  return routePath === "/" ? "/en" : `/en${routePath}`
}

async function statusAndLocation(
  request: APIRequestContext,
  url: string,
): Promise<{ status: number; location: string | undefined }> {
  const response = await request.get(`${origin}${url}`, { maxRedirects: 0 })
  return {
    status: response.status(),
    location: response.headers()["location"],
  }
}

test("every public route sends ?lang= to its canonical URL with a 301", async ({
  request,
}) => {
  // publicPaths.ts is the same list the nginx map is generated from; a route
  // added there without a redirect fails here instead of silently serving the
  // legacy parameter.
  expect(PUBLIC_PATHS.length).toBe(29)

  for (const routePath of PUBLIC_PATHS) {
    // nginx builds an absolute Location from the requested host and port, so
    // the exact value is the test server's origin plus the canonical path.
    const english = await statusAndLocation(request, `${routePath}?lang=en`)
    expect(english.status, `${routePath}?lang=en is not a 301`).toBe(301)
    expect(english.location, `${routePath}?lang=en: Location`).toBe(
      `${origin}${englishUrl(routePath)}`,
    )

    const german = await statusAndLocation(request, `${routePath}?lang=de`)
    expect(german.status, `${routePath}?lang=de is not a 301`).toBe(301)
    expect(german.location, `${routePath}?lang=de: Location`).toBe(
      `${origin}${routePath}`,
    )
  }
})

test("following the redirect lands on a 200 and never redirects again", async ({
  request,
}) => {
  for (const routePath of PUBLIC_PATHS) {
    const target = englishUrl(routePath)

    // One hop only: `maxRedirects: 1` throws when a second redirect is needed,
    // which is exactly how a loop between /en and ?lang=en would surface.
    const followed = await request.get(`${origin}${routePath}?lang=en`, {
      maxRedirects: 1,
    })
    expect(followed.status(), `${routePath}?lang=en: final status`).toBe(200)
    expect(
      new URL(followed.url()).pathname,
      `${routePath}?lang=en: final URL`,
    ).toBe(target)

    // The destination itself is not a redirect: a 301 chain ending on a 301
    // would leave the crawler without a page.
    const direct = await statusAndLocation(request, target)
    expect(direct.status, `${target} redirects instead of serving`).toBe(200)
    expect(direct.location, `${target}: unexpected Location`).toBeUndefined()

    // The German redirect target is the bare path, which must also be final.
    const german = await statusAndLocation(request, routePath)
    expect(german.status, `${routePath} redirects instead of serving`).toBe(200)
    expect(german.location, `${routePath}: unexpected Location`).toBeUndefined()
  }
})

test("the redirect keeps every other query parameter, in its original order", async ({
  request,
}) => {
  // `lang` is the only parameter the migration removes: a campaign URL must
  // still reach its landing page with its attribution intact.
  for (const [url, location] of [
    [
      "/pricing?lang=en&utm_source=newsletter&utm_medium=email&utm_campaign=launch",
      `${origin}/en/pricing?utm_source=newsletter&utm_medium=email&utm_campaign=launch`,
    ],
    [
      "/pricing?utm_source=newsletter&lang=en&utm_medium=email",
      `${origin}/en/pricing?utm_source=newsletter&utm_medium=email`,
    ],
    [
      "/pricing?utm_source=newsletter&lang=en",
      `${origin}/en/pricing?utm_source=newsletter`,
    ],
    // `lang` alone keeps the previous behaviour: no `?` in the Location.
    ["/pricing?lang=en", `${origin}/en/pricing`],
    ["/pricing?lang=de&a=1&b=2", `${origin}/pricing?a=1&b=2`],
    ["/?lang=en&utm_source=x", `${origin}/en?utm_source=x`],
    // nginx `map` compares its keys case-insensitively, so `EN` redirects too —
    // and its campaign parameter still survives (the token regex is `~*`).
    ["/pricing?lang=EN&utm_source=x", `${origin}/en/pricing?utm_source=x`],
  ] as const) {
    const { status, location: found } = await statusAndLocation(request, url)
    expect(status, `${url} is not a 301`).toBe(301)
    expect(found, `${url}: Location`).toBe(location)
  }

  // End to end: after the hop the browser is on the English page *with* its
  // campaign parameters, not on a stripped URL.
  const followed = await request.get(
    `${origin}/pricing?lang=en&utm_source=newsletter&utm_medium=email`,
    { maxRedirects: 1 },
  )
  expect(followed.status()).toBe(200)
  expect(new URL(followed.url()).pathname).toBe("/en/pricing")
  expect(new URL(followed.url()).search).toBe(
    "?utm_source=newsletter&utm_medium=email",
  )
})

test("variants outside the map keep answering 200, with no redirect", async ({
  request,
}) => {
  // Documented, unchanged edge cases: the map matches `$uri` and `lang=en|de`
  // exactly. These forms were already served in German before the redirect
  // existed and must not start redirecting (or looping) now.
  for (const url of ["/pricing?lang=en+", "/pricing/?lang=en"]) {
    const response = await request.get(`${origin}${url}`, { maxRedirects: 0 })
    expect(response.status(), `${url} must stay a 200`).toBe(200)
    expect(
      response.headers()["location"],
      `${url}: unexpected redirect`,
    ).toBeUndefined()
    expect(await response.text(), `${url}: not the German page`).toContain(
      '<html lang="de"',
    )
  }
})

test("the five noindex screens keep answering 200, without a redirect", async ({
  request,
}) => {
  expect(NOINDEX_PATHS.sort()).toEqual(
    [
      "/forgot-password",
      "/login",
      "/onboarding",
      "/register",
      "/reset-password",
    ].sort(),
  )

  for (const routePath of NOINDEX_PATHS) {
    for (const [url, lang] of [
      [routePath, "de"],
      [`${routePath}?lang=de`, "de"],
      [`${routePath}?lang=en`, "en"],
    ] as const) {
      const response = await request.get(`${origin}${url}`, {
        maxRedirects: 0,
      })
      expect(response.status(), `${url} must answer 200`).toBe(200)
      expect(
        response.headers()["location"],
        `${url}: a noindex screen must not redirect`,
      ).toBeUndefined()
      const body = await response.text()
      expect(body, `${url}: wrong language`).toContain(`<html lang="${lang}"`)
      expect(body, `${url}: robots`).toContain(
        '<meta name="robots" content="noindex,nofollow"',
      )
    }
  }
})

test("the build no longer ships a ?lang=en copy of any public page", async () => {
  for (const routePath of PUBLIC_PATHS) {
    const base = routePath === "/" ? "" : routePath
    const file = path.join(DIST, "_i18n", base, "index.html")
    expect(
      existsSync(file),
      `dist/_i18n${routePath}/index.html still exists although nginx 301s it`,
    ).toBe(false)
  }

  // The private shells are the ones that must survive: they are served
  // directly for `?lang=en` and have no `/en` URL.
  for (const routePath of NOINDEX_PATHS) {
    expect(
      existsSync(path.join(DIST, "_i18n", routePath, "index.html")),
      `dist/_i18n${routePath}/index.html is missing`,
    ).toBe(true)
  }
})

test("the sitemap lists canonical URLs only", async ({ request }) => {
  const response = await request.get(`${origin}/sitemap.xml`)
  expect(response.status()).toBe(200)
  const xml = await response.text()

  expect(xml).not.toContain("?lang=")
  expect(xml).not.toContain("_i18n")
  // 29 public routes × 2 languages + the CMS articles of this build.
  const urls = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(
    (match) => match[1],
  )
  expect(urls.length).toBe(66)

  const siteOrigin = new URL(urls[0]).origin
  for (const routePath of PUBLIC_PATHS) {
    // The home page keeps its trailing slash in the sitemap.
    const expected =
      routePath === "/"
        ? [`${siteOrigin}/`, `${siteOrigin}/en`]
        : [`${siteOrigin}${routePath}`, `${siteOrigin}/en${routePath}`]
    for (const url of expected) {
      expect(urls, `sitemap is missing ${url}`).toContain(url)
    }
  }
})
