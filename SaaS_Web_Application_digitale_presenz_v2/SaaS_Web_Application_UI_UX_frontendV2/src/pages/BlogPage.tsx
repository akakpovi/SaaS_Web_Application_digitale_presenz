import { useCallback, useEffect, useRef, useState } from "react"
import Link from "../components/LocaleLink"
import { ArrowRight, Clock, AlertTriangle, Loader2 } from "lucide-react"
import SEO from "../components/SEO"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n } from "../i18n"
import { useInitialBlogData } from "../contexts/BlogDataContext"
import { fetchPosts, type BlogPost } from "../api/blog"

export default function BlogPage() {
  const { locale, t } = useI18n()
  // The build renders this page with the posts it already fetched from
  // WordPress and embeds the same list for hydration. Without it the first
  // server render would only contain the loading state.
  const initial = useInitialBlogData()
  const [posts, setPosts] = useState<BlogPost[]>(initial?.posts ?? [])
  const [loading, setLoading] = useState(!initial)
  const [error, setError] = useState<string | null>(null)
  const loadedLocale = useRef(initial?.locale)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Only articles written in the active language: the German blog shows
      // German posts, the English blog English ones.
      setPosts(await fetchPosts(12, locale))
      loadedLocale.current = locale
    } catch (err) {
      setError(err instanceof Error ? err.message : t("blog.loadError"))
    } finally {
      setLoading(false)
    }
  }, [locale, t])

  useEffect(() => {
    // The initial list belongs to one locale. A later switch must refetch,
    // while the first client render keeps the build-time list (no flash and no
    // markup mismatch during hydration).
    if (loadedLocale.current === locale) return
    void load()
  }, [locale, load])

  return (
    <div className="min-h-full bg-white">
      <SEO
        title={t("blog.listMetaTitle")}
        description={t("blog.listMetaDescription")}
        path="/blog"
      />

      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between gap-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-5 text-sm text-slate-600">
            <Link to="/#features" className="hover:text-slate-900">
              {t("nav.features")}
            </Link>
            <Link to="/pricing" className="hover:text-slate-900">
              {t("nav.pricing")}
            </Link>
            <Link to="/tools/website-checker" className="hover:text-slate-900">
              {t("faqPage.freeChecker")}
            </Link>
            <Link to="/faq" className="hover:text-slate-900">
              {t("nav.faq")}
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <Link to="/register">
              <button className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700">
                {t("common.signup")}
              </button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-16">
        <div className="mb-12">
          <p className="text-xs font-bold uppercase tracking-widest text-indigo-600 mb-3">
            {t("blog.badge")}
          </p>
          <h1 className="text-4xl font-bold text-slate-900 mb-4">
            {t("blog.listTitle")}
          </h1>
          <p className="text-lg text-slate-500">{t("blog.listSubtitle")}</p>
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-slate-500">
            <Loader2 size={16} className="animate-spin" /> {t("blog.loading")}
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle size={16} className="mt-0.5" />
            <div>
              <p>{error}</p>
              <button
                onClick={() => void load()}
                className="mt-2 font-semibold underline"
              >
                {t("blog.retry")}
              </button>
            </div>
          </div>
        )}

        {!loading && !error && posts.length === 0 && (
          <p className="text-slate-500">{t("blog.empty")}</p>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          {posts.map((article) => (
            <article key={article.slug} className="group">
              <Link to={`/blog/${article.slug}`}>
                <div className="border border-slate-200 rounded-2xl p-6 h-full hover:border-indigo-200 hover:shadow-md transition-all duration-200 flex flex-col">
                  {article.image && (
                    <img
                      src={article.image}
                      alt=""
                      loading="lazy"
                      className="w-full h-40 object-cover rounded-xl mb-4"
                    />
                  )}
                  <div className="flex items-center gap-2 mb-3">
                    <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-full">
                      {article.category}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-slate-400">
                      <Clock size={11} />{" "}
                      {t("blog.readTime", {
                        minutes: `${article.readTime} ${t("blog.minutes")}`,
                      })}
                    </span>
                  </div>
                  <h2 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-indigo-700 transition-colors leading-snug">
                    {article.title}
                  </h2>
                  <p className="text-sm text-slate-500 flex-1 leading-relaxed">
                    {article.excerpt}
                  </p>
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
                    <time dateTime={article.date} className="text-xs text-slate-400">
                      {new Date(article.date).toLocaleDateString(
                        locale === "de" ? "de-DE" : "en-GB",
                        { day: "numeric", month: "long", year: "numeric" },
                      )}
                    </time>
                    <span className="text-xs font-medium text-indigo-600 flex items-center gap-1 group-hover:gap-2 transition-all">
                      {t("blog.readArticle")} <ArrowRight size={12} />
                    </span>
                  </div>
                </div>
              </Link>
            </article>
          ))}
        </div>

        <div className="mt-16 p-8 bg-indigo-600 rounded-2xl text-center text-white">
          <h2 className="text-2xl font-bold mb-3">{t("blog.ctaTitle")}</h2>
          <p className="text-indigo-200 mb-6">{t("blog.ctaText")}</p>
          <Link to="/tools/website-checker">
            <button className="px-6 py-3 bg-white text-indigo-700 font-semibold rounded-xl hover:bg-indigo-50 transition-colors">
              {t("blog.ctaButton")}
            </button>
          </Link>
        </div>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center mt-8">
        <p className="text-sm text-slate-400">
          {t("footer.rights")}{" "}
          <Link to="/" className="hover:text-slate-600">
            {t("notFound.home")}
          </Link>{" "}
          ·{" "}
          <Link to="/pricing" className="hover:text-slate-600">
            {t("nav.pricing")}
          </Link>{" "}
          ·{" "}
          <Link to="/impressum" className="hover:text-slate-600">
            {t("footer.impressum")}
          </Link>
        </p>
      </footer>
    </div>
  )
}
