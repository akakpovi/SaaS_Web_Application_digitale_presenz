import { createContext, useContext } from "react"
import type { BlogPost } from "../api/blog"
import type { Locale } from "../i18n"

/**
 * Blog posts fetched once at build time.
 *
 * `BlogPage` normally loads them in an effect. That cannot run during SSG, so
 * the build renders the page with the same list it embeds in the document
 * (`#__blog-data`). Hydration starts from that list instead of an empty
 * loading state, and a later language change still refetches normally.
 */
export interface InitialBlogData {
  locale: Locale
  posts: BlogPost[]
}

const BlogDataContext = createContext<InitialBlogData | null>(null)

export function BlogDataProvider({
  value,
  children,
}: {
  value: InitialBlogData | null
  children: React.ReactNode
}) {
  return (
    <BlogDataContext.Provider value={value}>
      {children}
    </BlogDataContext.Provider>
  )
}

export function useInitialBlogData(): InitialBlogData | null {
  return useContext(BlogDataContext)
}
