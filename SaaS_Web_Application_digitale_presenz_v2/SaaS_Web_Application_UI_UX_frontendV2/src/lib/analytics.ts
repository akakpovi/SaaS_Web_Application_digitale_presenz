/**
 * Analytics scaffolding — deliberately inert.
 *
 * No tracker is loaded by this module. It exists so that activation, once the
 * legal pages are finalised, is a configuration change and not a refactor:
 * the call sites can be written today and stay no-ops until the build enables
 * them.
 *
 * Two independent gates must both be open for anything to be sent:
 *
 *  1. `VITE_ANALYTICS_ENABLED === "true"` at build time — absent or `false`
 *     means the module never touches the network;
 *  2. the page actually loaded the tracker (`window.umami.track`), which only
 *     happens when the build injects the script tag into the HTML shell.
 *
 * The server render has neither: `typeof window === "undefined"` keeps it a
 * no-op during prerender, so the static HTML stays free of tracking calls.
 *
 * See `docs/audits/PRESENCE_ANALYTICS_PLAN_2026-10-28.md` for the activation
 * checklist, which is blocked on the Datenschutz/Cookies pages leaving draft.
 */

type EventProperties = Record<string, string | number | boolean | undefined>

interface PageviewProperties {
  url?: string
  title?: string
  name?: string
  data?: EventProperties
}

interface UmamiClient {
  track: (
    eventOrPageview?: string | PageviewProperties,
    data?: EventProperties,
  ) => void
}

declare global {
  interface Window {
    umami?: UmamiClient
  }
}

const ENABLED = import.meta.env.VITE_ANALYTICS_ENABLED === "true"

/**
 * `true` only when the build opted in *and* the tracker is actually present.
 * Safe to call from a component: it never throws during SSR.
 */
export function isAnalyticsEnabled(): boolean {
  if (!ENABLED) return false
  if (typeof window === "undefined") return false
  return typeof window.umami?.track === "function"
}

/**
 * Record a named event (signup, CTA click, scan started…).
 * No-op while analytics is disabled.
 */
export function trackEvent(name: string, data?: EventProperties): void {
  if (!isAnalyticsEnabled()) return
  window.umami?.track(name, data)
}

/**
 * Record a virtual page view. The first page load is already counted by the
 * tracker script itself; this is for client-side route changes, so the SPA
 * does not report a single page per session.
 */
export function trackPageview(path: string): void {
  if (!isAnalyticsEnabled()) return
  if (!path.startsWith("/")) return
  window.umami?.track({ url: path })
}
