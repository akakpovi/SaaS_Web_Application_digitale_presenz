import { Writable } from "node:stream"
import { renderToPipeableStream } from "react-dom/server"
import type { HelmetServerState } from "react-helmet-async"
import { StaticRouter } from "react-router-dom"
import { AppRoutes } from "./App"
import { AppProviders } from "./AppProviders"
import { ThemeProvider } from "./components/AppShell"
import type { InitialBlogData } from "./contexts/BlogDataContext"
import type { Locale } from "./i18n"

export interface RenderOptions {
  /** Posts fetched at build time, only for the blog index. */
  blogData?: InitialBlogData | null
  /** Abort a page that would otherwise hang the build. */
  timeoutMs?: number
  /**
   * Exact URL the written file serves. Defaults to `routePath`, plus
   * `?lang=en` for the English variant — the historical alias. The build passes
   * the prefixed `/en/...` URL for the canonical English file, so the router
   * state (and anything reading `useLocation`) matches what the browser will
   * hydrate on that URL.
   */
  url?: { pathname: string; search: string }
}

/**
 * Render one public route to a complete HTML string.
 *
 * `AppRoutes` keeps the pages lazy-loaded for the browser. React's streaming
 * renderer resolves those boundaries on the server, and `onAllReady` waits for
 * every one of them before the HTML is written: a crawler never receives the
 * `<PageLoader />` fallback instead of the page.
 *
 * The router is `StaticRouter`, so the tree is the same one the browser mounts;
 * only the history implementation differs. `options.url` mirrors the URL nginx
 * serves for that file (`/en/<route>` for the canonical English page,
 * `<route>?lang=en` for the legacy alias), which keeps canonical/hreflang
 * identical between the static head and the hydrated one.
 */
export async function renderRoute(
  routePath: string,
  locale: Locale,
  options: RenderOptions = {},
): Promise<string> {
  const helmetContext: { helmet?: HelmetServerState | null } = {}
  const location = options.url ?? {
    pathname: routePath,
    search: locale === "en" ? "?lang=en" : "",
  }
  const errors: unknown[] = []

  return new Promise<string>((resolve, reject) => {
    let settled = false
    const finish = (error?: unknown, html?: string) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      if (error) reject(error)
      else resolve(html ?? "")
    }

    const timer = setTimeout(() => {
      finish(new Error(`SSG render timed out for ${routePath} (${locale})`))
      stream.abort()
    }, options.timeoutMs ?? 30_000)

    const chunks: Buffer[] = []
    const sink = new Writable({
      write(chunk, _encoding, callback) {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
        callback()
      },
    })
    sink.on("finish", () => {
      if (errors.length > 0) {
        finish(
          new Error(
            `SSG render reported ${errors.length} error(s) for ${routePath} (${locale}): ` +
              errors
                .map((error) =>
                  error instanceof Error ? error.message : String(error),
                )
                .join(" | "),
          ),
        )
        return
      }
      finish(undefined, Buffer.concat(chunks).toString("utf8"))
    })

    const stream = renderToPipeableStream(
      <AppProviders
        initialLocale={locale}
        initialBlogData={options.blogData ?? null}
        helmetContext={helmetContext}
      >
        <ThemeProvider>
          <StaticRouter location={location}>
            <AppRoutes />
          </StaticRouter>
        </ThemeProvider>
      </AppProviders>,
      {
        onAllReady() {
          stream.pipe(sink)
        },
        onShellError(error) {
          finish(error)
        },
        onError(error) {
          errors.push(error)
        },
      },
    )
  })
}
