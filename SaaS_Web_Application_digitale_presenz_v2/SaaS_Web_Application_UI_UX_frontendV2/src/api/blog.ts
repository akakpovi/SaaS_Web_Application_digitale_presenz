/**
 * Client du blog headless WordPress.
 *
 * Le contenu éditorial vit uniquement dans le CMS. Aucun article local n'est
 * servi : si `VITE_WP_API_URL` est absente ou si le CMS est injoignable, la
 * page affiche une erreur explicite plutôt qu'un contenu de démonstration.
 */

export interface BlogPost {
  slug: string
  title: string
  excerpt: string
  contentHtml: string
  date: string
  category: string
  author: string
  readTime: string
  related: string[]
  image?: string
  /** Language of this article as stored in the CMS (`de` | `en` | `fr`). */
  lang: string
  /** Published sibling articles, used for the language switch and hreflang. */
  translations: { lang: string; slug: string; title: string }[]
}

interface WpRendered {
  rendered?: string
}

interface WpPost {
  slug: string
  date: string
  title: WpRendered
  excerpt: WpRendered
  content: WpRendered
  // Fields added by wordpress/mu-plugins/presence-i18n.php.
  presence_lang?: { code?: string; name?: string }
  presence_translations?: { lang?: string; slug?: string; title?: string }[]
  _embedded?: {
    "wp:term"?: Array<Array<{ name?: string; taxonomy?: string }>>
    author?: Array<{ name?: string }>
    "wp:featuredmedia"?: Array<{ source_url?: string }>
  }
}

const WP_API_URL = (import.meta.env.VITE_WP_API_URL as string | undefined)
  ?.trim()
  .replace(/\/+$/, "")

function postsEndpoint(): string {
  if (!WP_API_URL) {
    throw new Error("Blog CMS is not configured (VITE_WP_API_URL is empty).")
  }
  // Accept both "https://cms.example.com" and
  // "https://cms.example.com/wp-json" without doubling the prefix.
  const base = WP_API_URL!.endsWith("/wp-json")
    ? `${WP_API_URL}/wp/v2`
    : `${WP_API_URL}/wp-json/wp/v2`
  return `${base}/posts`
}

function decodeEntities(value: string): string {
  return value
    .replace(/&#8217;|&#039;|&#39;/g, "'")
    .replace(/&#8211;|&ndash;/g, "–")
    .replace(/&#8212;|&mdash;/g, "—")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
}

export function stripHtml(value: string): string {
  // Never assign CMS HTML to a live element: an <img onerror> (or an SVG
  // load handler) in a detached div still fires its handler and would run
  // before DOMPurify sees the markup. DOMParser documents are inert.
  if (typeof DOMParser !== "undefined") {
    const doc = new DOMParser().parseFromString(value, "text/html")
    return decodeEntities((doc.body.textContent ?? "").replace(/\s+/g, " ").trim())
  }
  return decodeEntities(value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim())
}

function readingTime(html: string): string {
  const words = stripHtml(html).split(/\s+/).filter(Boolean).length
  return `${Math.max(1, Math.ceil(words / 200))} min`
}

function toBlogPost(post: WpPost, all: WpPost[] = []): BlogPost {
  const terms = post._embedded?.["wp:term"]?.flat() ?? []
  const category =
    terms.find((term) => term.taxonomy === "category")?.name ?? "Blog"
  const author = post._embedded?.author?.[0]?.name ?? "Presence Team"
  const image = post._embedded?.["wp:featuredmedia"]?.[0]?.source_url
  const contentHtml = post.content?.rendered ?? ""

  return {
    slug: post.slug,
    title: decodeEntities(stripHtml(post.title?.rendered ?? post.slug)),
    excerpt: decodeEntities(stripHtml(post.excerpt?.rendered ?? "")),
    contentHtml,
    date: post.date?.slice(0, 10) ?? "",
    category,
    author,
    readTime: readingTime(contentHtml || post.excerpt?.rendered || ""),
    related: all
      .filter((candidate) => candidate.slug !== post.slug)
      .slice(0, 2)
      .map((candidate) => candidate.slug),
    image,
    lang: ["de", "en", "fr"].includes(post.presence_lang?.code ?? "")
      ? post.presence_lang!.code!
      : "en",
    translations: (post.presence_translations ?? [])
      .filter((entry) => entry.slug && entry.lang)
      .map((entry) => ({
        lang: String(entry.lang),
        slug: String(entry.slug),
        title: decodeEntities(stripHtml(entry.title ?? "")),
      })),
  }
}

async function wpFetch(path: string): Promise<WpPost[]> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
  })
  if (!response.ok) {
    throw new Error(`Blog API responded with HTTP ${response.status}`)
  }
  const data = (await response.json()) as unknown
  if (!Array.isArray(data)) {
    throw new Error("Blog API returned an unexpected payload")
  }
  return data as WpPost[]
}

export async function fetchPosts(
  perPage = 12,
  locale?: string,
): Promise<BlogPost[]> {
  const language = locale ? `&presence_lang=${encodeURIComponent(locale)}` : ""
  const posts = await wpFetch(
    `${postsEndpoint()}?per_page=${perPage}&_embed=1&orderby=date&order=desc${language}`,
  )
  // The CMS filter is authoritative when it knows the locale. French has no
  // language term yet, so WordPress returns the whole catalogue for
  // `presence_lang=fr`; never let that fallback leak DE/EN articles onto a
  // French page (or let a future CMS change reintroduce a mixed list).
  const localized = locale
    ? posts.filter(
        (post) => (post.presence_lang?.code ?? "en") === locale,
      )
    : posts
  return localized.map((post) => toBlogPost(post, localized))
}

export async function fetchPostBySlug(
  slug: string,
  locale?: string,
): Promise<BlogPost | null> {
  if (!slug) return null

  const language = locale ? `&presence_lang=${encodeURIComponent(locale)}` : ""
  const posts = await wpFetch(
    `${postsEndpoint()}?slug=${encodeURIComponent(slug)}&_embed=1${language}`,
  )
  const localized = locale
    ? posts.filter(
        (post) => (post.presence_lang?.code ?? "en") === locale,
      )
    : posts
  if (localized.length === 0) return null
  return toBlogPost(localized[0], localized)
}

/**
 * Same article in the requested language, found through the translation links.
 * Returns `null` when no translation is published yet, which is the normal
 * case for an article that only exists in one language.
 */
export async function fetchTranslation(
  slug: string,
  locale: string,
): Promise<BlogPost | null> {
  const localized = await fetchPostBySlug(slug, locale)
  if (localized) return localized
  return null
}
