import { Link as RouterLink, useLocation, type LinkProps } from "react-router-dom"
import { localeFromPath, localizedPath, type Locale } from "../i18n"
import { isPublicRoutePath } from "../seo/publicPaths"

/**
 * Internal links that stay in the current language.
 *
 * The public site exists twice under the same router: German on the bare paths
 * (`/pricing`) and English under `/en` (`/en/pricing`). A plain
 * `<Link to="/pricing">` is absolute, so an English page would send the visitor
 * back to the German URL. This wrapper prefixes the public routes when the
 * current URL is English, and leaves everything else alone:
 *
 *  - private/noindex routes (`/login`, `/register`, `/scan/…`, `/app/…`) keep
 *    their single URL, whatever the language of the page;
 *  - CMS articles (`/blog/<slug>`) keep their slug: a translation has its own
 *    slug, so `/en/blog/<slug>` would be a 404;
 *  - external, hash-only and relative links are untouched.
 *
 * It renders a real `<a href="/en/…">`, so crawlers, middle-click and
 * open-in-new-tab see the right URL — a click interceptor would not.
 */
export function localizeTo(
  to: LinkProps["to"],
  locale: Locale | null,
): LinkProps["to"] {
  if (!locale) return to

  if (typeof to === "string") {
    if (!to.startsWith("/") || to.startsWith("//")) return to
    const [beforeHash, ...hashParts] = to.split("#")
    const hash = hashParts.length > 0 ? `#${hashParts.join("#")}` : ""
    const [rawPath, ...searchParts] = beforeHash.split("?")
    const search =
      searchParts.length > 0 ? `?${searchParts.join("?")}` : ""
    const path = rawPath.length > 1 ? rawPath.replace(/\/+$/, "") : rawPath
    if (!isPublicRoutePath(path)) return to
    return `${localizedPath(path, locale)}${search}${hash}`
  }

  if (
    typeof to === "object" &&
    to !== null &&
    typeof to.pathname === "string" &&
    to.pathname.startsWith("/") &&
    isPublicRoutePath(to.pathname)
  ) {
    const path =
      to.pathname.length > 1
        ? to.pathname.replace(/\/+$/, "")
        : to.pathname
    return { ...to, pathname: localizedPath(path, locale) }
  }

  return to
}

export default function Link({ to, ...rest }: LinkProps) {
  const { pathname } = useLocation()
  const locale = localeFromPath(pathname)
  return <RouterLink to={localizeTo(to, locale)} {...rest} />
}
