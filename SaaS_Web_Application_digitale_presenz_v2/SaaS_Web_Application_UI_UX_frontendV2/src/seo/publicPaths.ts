/**
 * Canonical paths of the public, indexable, bilingual pages.
 *
 * One source of truth for two consumers that must never drift:
 *
 *  - `src/App.tsx` mounts every path bare (German) and under `/en` (English);
 *  - `src/components/LocaleLink.tsx` decides whether a link may be prefixed.
 *
 * Only those exact paths are localized. A private or data-driven route
 * (`/login`, `/register`, `/app/…`, `/scan/…`, `/blog/<slug>`) is never in this
 * list, so it keeps the URL it always had.
 */
export const PUBLIC_PATHS = [
  "/",
  "/pricing",
  "/faq",
  "/blog",
  "/about",
  "/contact",
  "/privacy",
  "/terms",
  "/impressum",
  "/cookies",
  "/widerruf",
  "/solutions/small-business",
  "/solutions/freelancers",
  "/solutions/agencies",
  "/solutions/restaurants",
  "/solutions/ecommerce",
  "/solutions/local-business",
  "/features/website-monitoring",
  "/features/ssl-monitoring",
  "/features/dns-monitoring",
  "/features/email-security",
  "/features/uptime-monitoring",
  "/features/website-performance",
  "/features/security-headers",
  "/features/review-monitoring",
  "/tools/website-checker",
  "/tools/ssl-checker",
  "/tools/dns-checker",
  "/tools/email-security-checker",
] as const

export type PublicPath = (typeof PUBLIC_PATHS)[number]

const PUBLIC_PATH_SET: ReadonlySet<string> = new Set(PUBLIC_PATHS)

/**
 * `true` for a public bilingual path, with or without a trailing slash.
 *
 * An article slug (`/blog/what-is-dmarc`) is deliberately **not** a public
 * path here: its translation lives on its own slug, so prefixing it with `/en`
 * would point at a page that does not exist.
 */
export function isPublicRoutePath(path: string): boolean {
  const normalized = path.length > 1 ? path.replace(/\/+$/, "") : path
  return PUBLIC_PATH_SET.has(normalized)
}
