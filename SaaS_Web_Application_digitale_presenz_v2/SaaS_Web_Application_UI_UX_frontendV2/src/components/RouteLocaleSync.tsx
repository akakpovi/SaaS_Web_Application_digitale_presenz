import { useEffect, useRef } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import {
  DEFAULT_LOCALE,
  getStoredLocale,
  localeFromPath,
  localeFromSearch,
  localizedPath,
  useI18n,
} from "../i18n"
import { isPublicRoutePath } from "../seo/publicPaths"

function withoutTrailingSlash(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname
}

function localizedPublicUrl(pathname: string, locale: "de" | "en" | "fr"): string {
  const path = localizedPath(withoutTrailingSlash(pathname), locale)
  return path === "/" ? path : `${path}/`
}

/**
 * Keeps the interface language in step with the URL.
 *
 * `/en/...` is the English site and `?lang=en` its legacy alias; both must win
 * over a stored preference so an advertised URL never opens in the other
 * language. Bare paths keep the previous behaviour (the stored/browser
 * preference applies), which is why this only acts when the URL names a
 * language.
 *
 * The effect runs after hydration, so the first client tree is still the one
 * the pre-rendered document contains (`<html lang>` seeds the provider). It
 * deliberately does not re-run when the visitor uses the switcher: choosing DE
 * on an English page changes the interface in place, exactly as before.
 */
export default function RouteLocaleSync() {
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const { locale, setLocale } = useI18n()
  const current = useRef(locale)
  const firstRender = useRef(true)
  current.current = locale

  useEffect(() => {
    const fromUrl = localeFromPath(pathname) ?? localeFromSearch(search)
    if (fromUrl) {
      firstRender.current = false
      if (fromUrl !== current.current) setLocale(fromUrl)
      return
    }

    // On a cold load of a bare public path, a previously chosen FR/EN locale
    // upgrades the URL to its canonical localized form. This is deliberately
    // limited to the first render: later in-app navigation is handled by the
    // localized links and the switcher, so choosing DE never bounces back to
    // the old preference.
    if (!firstRender.current) return
    firstRender.current = false
    const remembered = getStoredLocale()
    if (
      remembered &&
      remembered !== DEFAULT_LOCALE &&
      isPublicRoutePath(withoutTrailingSlash(pathname))
    ) {
      navigate(localizedPublicUrl(pathname, remembered), { replace: true })
    }
  }, [navigate, pathname, search, setLocale])

  return null
}
