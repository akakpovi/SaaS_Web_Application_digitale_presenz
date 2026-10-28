import { useEffect, useRef } from "react"
import { useLocation } from "react-router-dom"
import { localeFromPath, localeFromSearch, useI18n } from "../i18n"

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
  const { locale, setLocale } = useI18n()
  const current = useRef(locale)
  current.current = locale

  useEffect(() => {
    const fromUrl = localeFromPath(pathname) ?? localeFromSearch(search)
    if (fromUrl && fromUrl !== current.current) setLocale(fromUrl)
  }, [pathname, search, setLocale])

  return null
}
