import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"
import { AppProviders } from "./AppProviders"
import type { InitialBlogData } from "./contexts/BlogDataContext"
import { isLocale, type Locale } from "./i18n"
import "./index.css"

// Web Push needs a service worker registration before the browser can create a
// subscription (see public/sw.js). Registration is idempotent; a failure only
// disables push, so it must never block the app from starting.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.warn("[pwa] service worker registration failed", error)
    })
  })
}

const root = document.getElementById("root")!

/**
 * The build renders a full page and marks it; only then may the browser
 * hydrate. A route that still carries the generic fallback shell must keep
 * using `createRoot`, otherwise React would try to hydrate a markup the page
 * never rendered.
 */
const isStaticPage = root.dataset.ssg === "true"

/** The static document owns the initial language; a stored preference may not
 * produce an English tree inside a German page (or the reverse). */
const documentLocale = document.documentElement.lang
const initialLocale: Locale | undefined =
  isStaticPage && isLocale(documentLocale) ? documentLocale : undefined

/** Build-time posts embedded by `scripts/prerender.mjs` for the blog index. */
function readInitialBlogData(): InitialBlogData | null {
  const node = document.getElementById("__blog-data")
  if (!node?.textContent) return null
  try {
    const parsed = JSON.parse(node.textContent) as InitialBlogData
    if (
      parsed &&
      isLocale(parsed.locale) &&
      Array.isArray(parsed.posts)
    ) {
      return parsed
    }
  } catch {
    // Corrupt build data must not block the page; the effect will refetch.
  }
  return null
}

const app = (
  <React.StrictMode>
    <AppProviders
      initialLocale={initialLocale}
      initialBlogData={isStaticPage ? readInitialBlogData() : null}
    >
      <App />
    </AppProviders>
  </React.StrictMode>
)

if (isStaticPage) {
  ReactDOM.hydrateRoot(root, app)
} else {
  ReactDOM.createRoot(root).render(app)
}
