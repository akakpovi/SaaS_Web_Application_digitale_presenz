import type { ReactNode } from "react"
import { HelmetProvider, type HelmetServerState } from "react-helmet-async"
import { AuthProvider } from "./contexts/AuthContext"
import { BlogDataProvider, type InitialBlogData } from "./contexts/BlogDataContext"
import { ToastProvider } from "./components/Toast"
import { I18nProvider, type Locale } from "./i18n"

/**
 * Providers shared by the browser entry and the build-time renderer.
 *
 * Keeping one stack avoids the classic SSG drift where the server renders
 * inside a different context than the browser hydrates: the locale is fixed
 * per URL, the helmet context only exists during rendering, and the build can
 * hand the blog its already-fetched posts.
 */
export function AppProviders({
  children,
  initialLocale,
  initialBlogData,
  helmetContext,
}: {
  children: ReactNode
  initialLocale?: Locale
  initialBlogData?: InitialBlogData | null
  helmetContext?: { helmet?: HelmetServerState | null }
}) {
  return (
    <HelmetProvider context={helmetContext}>
      <AuthProvider>
        <I18nProvider initialLocale={initialLocale}>
          <ToastProvider>
            <BlogDataProvider value={initialBlogData ?? null}>
              {children}
            </BlogDataProvider>
          </ToastProvider>
        </I18nProvider>
      </AuthProvider>
    </HelmetProvider>
  )
}
