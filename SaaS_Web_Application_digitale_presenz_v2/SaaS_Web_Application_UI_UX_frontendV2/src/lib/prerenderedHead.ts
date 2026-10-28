/**
 * Deduplicates the head of a pre-rendered page.
 *
 * `scripts/prerender.mjs` writes a real `<title>`, description, canonical,
 * hreflang alternates and og/twitter tags into every public shell, because
 * clients that never run JavaScript (crawlers, social previews) need them in
 * the response itself. The app then renders its own head — the correct one for
 * the language that is actually displayed, and on the origin it was built for.
 *
 * Those two sets do not replace each other: with React 19, react-helmet-async
 * renders the head through React's element hoisting instead of adopting
 * pre-existing tags, so a hydrated page would publish *two* canonicals, two
 * descriptions, a stale title from the other language and six hreflang links.
 * Search engines and previews then have to guess.
 *
 * This drops a pre-rendered tag only when the app rendered its own equivalent:
 * the tag is matched by type and by its identifying attribute(s), so a page
 * that renders no title keeps the one the shell shipped, and the article case
 * (hreflang per translated slug) keeps the languages the app did not re-declare.
 */

/** Attribute the pre-rendered tags carry, so they are identifiable here. */
export const PRE_RENDERED_HEAD_ATTRIBUTE = "data-prerender-head"

/**
 * Identifying attributes of a head tag: the ones that make two tags "the same
 * tag" for a crawler. `rel` distinguishes canonical from alternates, `hreflang`
 * distinguishes one language from another, `name`/`property` distinguish one
 * meta from another.
 */
const IDENTITY_ATTRIBUTES = [
  "rel",
  "name",
  "property",
  "charset",
  "http-equiv",
  "hreflang",
  // Distinguishes the JSON-LD script from the module script in <head>.
  "type",
] as const

function headIdentity(element: Element): string {
  const parts = [element.tagName.toLowerCase()]
  for (const attribute of IDENTITY_ATTRIBUTES) {
    const value = element.getAttribute(attribute)
    if (value) parts.push(`${attribute}=${value}`)
  }
  return parts.join("|")
}

/**
 * Removes the pre-rendered head tags the application has replaced. Safe to call
 * more than once (and from a React effect, which runs after the app committed
 * its own head).
 */
export function dropPreRenderedDuplicates(
  doc: Document | undefined = typeof document === "undefined"
    ? undefined
    : document,
): void {
  if (!doc) return
  const head = doc.head
  if (!head) return

  const preRendered = Array.from(
    head.querySelectorAll(`[${PRE_RENDERED_HEAD_ATTRIBUTE}]`),
  )
  if (preRendered.length === 0) return

  const rendered = new Set(
    Array.from(head.children)
      .filter((element) => !element.hasAttribute(PRE_RENDERED_HEAD_ATTRIBUTE))
      .map(headIdentity),
  )

  for (const element of preRendered) {
    if (rendered.has(headIdentity(element))) element.remove()
  }
}
