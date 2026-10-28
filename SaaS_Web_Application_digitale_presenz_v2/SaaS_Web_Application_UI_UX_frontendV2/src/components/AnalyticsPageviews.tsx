import { useEffect, useRef } from "react"
import { useLocation } from "react-router-dom"
import { trackPageview } from "../lib/analytics"

/**
 * Reports client-side route changes to Umami.
 *
 * The tracker script already counts the first page load, so the initial render
 * is skipped: without this guard every entry would be counted twice. Path and
 * query string are sent together — the UTM parameters preserved through the
 * `?lang=` 301s are what make campaign attribution possible.
 *
 * `trackPageview` is a no-op during SSR and whenever analytics is disabled, so
 * this component is safe in the static build.
 */
export default function AnalyticsPageviews() {
  const location = useLocation()
  const isFirstRender = useRef(true)

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    trackPageview(`${location.pathname}${location.search}`)
  }, [location.pathname, location.search])

  return null
}
