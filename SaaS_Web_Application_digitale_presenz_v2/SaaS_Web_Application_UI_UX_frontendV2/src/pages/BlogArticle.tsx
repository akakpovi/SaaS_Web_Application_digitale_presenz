import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, Clock, Tag, ArrowRight, Loader2, AlertTriangle } from "lucide-react"
import SEO, { articleSchema } from "../components/SEO"
import BlogBody from "../components/BlogBody"
import LanguageSwitcher from "../components/LanguageSwitcher"
import NotFound from "./NotFound"
import { useI18n } from "../i18n"
import { fetchPostBySlug, fetchPosts, type BlogPost } from "../api/blog"

function PublicNav() {
  const { t } = useI18n()
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="white" strokeWidth="1.5" opacity="0.5" />
              <circle cx="8" cy="8" r="3" fill="white" />
            </svg>
          </div>
          <span className="font-bold text-slate-900 text-sm">Presence</span>
        </Link>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <Link
            to="/blog"
            className="text-sm text-slate-600 hover:text-slate-900 px-3 py-1.5"
          >
            {t("blog.backToBlog")}
          </Link>
          <Link
            to="/register"
            className="px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors"
          >
            {t("common.startFree")}
          </Link>
        </div>
      </div>
    </header>
  )
}

export default function BlogArticle() {
  const { slug } = useParams<{ slug: string }>()
  const { locale, t } = useI18n()
  const [article, setArticle] = useState<BlogPost | null>(null)
  const [related, setRelated] = useState<BlogPost[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!slug) return
    setLoading(true)
    setError(null)
    try {
      const [post, all] = await Promise.all([
        fetchPostBySlug(slug),
        fetchPosts(12, locale).catch(() => [] as BlogPost[]),
      ])
      setArticle(post)
      if (post) {
        setRelated(all.filter((candidate) => post.related.includes(candidate.slug)).slice(0, 2))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("blog.articleError"))
    } finally {
      setLoading(false)
    }
  }, [slug, locale, t])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return (
      <>
        <PublicNav />
        <main className="max-w-3xl mx-auto px-4 py-12 flex items-center gap-2 text-slate-500">
          <Loader2 size={16} className="animate-spin" /> {t("blog.loadingArticle")}
        </main>
      </>
    )
  }

  if (error) {
    return (
      <>
        <PublicNav />
        <main className="max-w-3xl mx-auto px-4 py-12">
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle size={16} className="mt-0.5" />
            <div>
              <p>{error}</p>
            <button onClick={() => void load()} className="mt-2 font-semibold underline">
              {t("blog.retry")}
            </button>
            </div>
          </div>
        </main>
      </>
    )
  }

  if (!article) return <NotFound />

  return (
    <>
      {/* An article keeps its own language: a German article read with the
          English UI must not claim lang="en", and its hreflang alternates
          have to point at the translated slug, not at ?lang= on this one.
          `bilingual={false}` keeps that URL/language pair stable: no `?lang=`
          variant of the slug is advertised, and the canonical stays on the
          article's own path. */}
      <SEO
        title={`${article.title} | Presence Blog`}
        description={article.excerpt}
        path={`/blog/${article.slug}`}
        bilingual={false}
        lang={article.lang === "de" ? "de" : "en"}
        alternates={[
          { lang: article.lang, path: `/blog/${article.slug}` },
          ...article.translations.map((translation) => ({
            lang: translation.lang,
            path: `/blog/${translation.slug}`,
          })),
        ]}
        ogType="article"
        ogImage={article.image}
        structuredData={articleSchema({
          title: article.title,
          description: article.excerpt,
          slug: article.slug,
          date: article.date,
          author: article.author,
        })}
      />
      <PublicNav />
      <main className="max-w-3xl mx-auto px-4 py-12">
        <Link
          to="/blog"
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-8 transition-colors"
        >
          <ArrowLeft size={14} /> {t("blog.backToBlog")}
        </Link>

        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full px-2.5 py-1">
              <Tag size={11} /> {article.category}
            </span>
            <span className="flex items-center gap-1.5 text-xs text-slate-400">
              <Clock size={11} />{" "}
              {t("blog.readTime", {
                minutes: `${article.readTime} ${t("blog.minutes")}`,
              })}
            </span>
          </div>

          {/* Language switch — only languages that really have a published
              translation, so no visitor lands on an empty page. */}
          {article.translations.length > 0 && (
            <div className="flex items-center gap-2 mb-4">
              <span className="text-xs text-slate-400">
                {t("blog.otherLanguages")}:
              </span>
              {article.translations.map((translation) => (
                <Link
                  key={translation.slug}
                  to={`/blog/${translation.slug}`}
                  className="px-2.5 py-1 text-xs font-semibold rounded-lg border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-700 transition-colors"
                >
                  {translation.lang.toUpperCase()}
                </Link>
              ))}
            </div>
          )}
          <h1 className="text-3xl font-black text-slate-900 leading-tight mb-3">
            {article.title}
          </h1>
          <p className="text-slate-500 text-base leading-relaxed mb-4">
            {article.excerpt}
          </p>
          <div className="flex items-center gap-2 text-xs text-slate-400 border-t border-slate-100 pt-4">
            <div className="w-6 h-6 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-600 font-bold text-[10px]">
              P
            </div>
            <span>{article.author}</span>
            <span>·</span>
            <time dateTime={article.date}>
              {new Date(article.date).toLocaleDateString(
                locale === "de" ? "de-DE" : "en-GB",
                { day: "numeric", month: "long", year: "numeric" },
              )}
            </time>
          </div>
        </div>

        {article.image && (
          <img
            src={article.image}
            alt=""
            className="w-full rounded-2xl mb-8 object-cover"
          />
        )}

        <article className="text-slate-700">
          <BlogBody html={article.contentHtml} />
        </article>

        <div className="mt-12 p-6 bg-indigo-50 border border-indigo-200 rounded-2xl">
          <p className="font-bold text-indigo-900 mb-1">
            {t("blog.ctaTitle")}
          </p>
          <p className="text-sm text-indigo-700 mb-4">{t("blog.ctaText")}</p>
          <div className="flex gap-3 flex-wrap">
            <Link
              to="/tools/website-checker"
              className="px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors"
            >
              {t("blog.ctaButton")}
            </Link>
            <Link
              to="/register"
              className="px-4 py-2 bg-white border border-indigo-300 text-indigo-700 text-sm font-semibold rounded-xl hover:bg-indigo-50 transition-colors"
            >
              {t("common.signup")}
            </Link>
          </div>
        </div>

        {related.length > 0 && (
          <div className="mt-12">
            <h2 className="text-lg font-bold text-slate-900 mb-4">
              {t("blog.relatedTitle")}
            </h2>
            <div className="grid sm:grid-cols-2 gap-4">
              {related.map((rel) => (
                <Link
                  key={rel.slug}
                  to={`/blog/${rel.slug}`}
                  className="group p-4 bg-white border border-slate-200 rounded-xl hover:border-indigo-300 hover:shadow-sm transition-all"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 rounded-full px-2 py-0.5">
                      {rel.category}
                    </span>
                    <span className="text-xs text-slate-400">{rel.readTime}</span>
                  </div>
                  <p className="text-sm font-semibold text-slate-800 group-hover:text-indigo-700 transition-colors leading-snug mb-1">
                    {rel.title}
                  </p>
                  <p className="text-xs text-slate-500 line-clamp-2">{rel.excerpt}</p>
                  <span className="inline-flex items-center gap-1 text-xs text-indigo-600 mt-2">
                    {t("blog.readArticle")} <ArrowRight size={11} />
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </main>
      <footer className="border-t border-slate-200 py-8 px-4 text-center mt-12">
        <p className="text-sm text-slate-400">
          {t("footer.rights")} ·{" "}
          <Link to="/privacy" className="hover:text-slate-600">
            {t("footer.privacy")}
          </Link>{" "}
          ·{" "}
          <Link to="/terms" className="hover:text-slate-600">
            {t("footer.terms")}
          </Link>{" "}
          ·{" "}
          <Link to="/impressum" className="hover:text-slate-600">
            {t("footer.impressum")}
          </Link>
        </p>
      </footer>
    </>
  )
}
