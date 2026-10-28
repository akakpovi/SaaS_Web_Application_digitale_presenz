import DOMPurify from "dompurify"

/**
 * Minimal, safe Markdown renderer for AI answers.
 *
 * The project has no Markdown dependency on purpose (the only previous need
 * was CMS HTML, sanitised by DOMPurify).  AI output is untrusted text, so:
 *
 * 1. the whole source is HTML-escaped first — no raw tag can survive,
 * 2. a deliberately small subset is then recognised (fenced code, inline code,
 *    bold/italic, links, headings, ordered/unordered lists, paragraphs),
 * 3. the produced HTML is sanitised again with a tag/attribute allow-list.
 *
 * Anything outside that subset is displayed as literal text.
 */

const ALLOWED_TAGS = [
  "p",
  "br",
  "strong",
  "em",
  "code",
  "pre",
  "ul",
  "ol",
  "li",
  "h3",
  "h4",
  "h5",
  "h6",
  "a",
  "blockquote",
]

const ALLOWED_ATTR = ["href", "target", "rel", "class"]

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char] ?? char)
}

function renderInline(text: string): string {
  let out = text
  // Inline code first: its content must not be re-interpreted as Markdown.
  out = out.replace(/`([^`\n]+)`/g, "<code>$1</code>")
  out = out.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
  out = out.replace(/(^|[\s(>])\*([^*\n]+)\*/g, "$1<em>$2</em>")
  // Only http(s) links: no javascript:, data: or protocol-relative URLs.
  out = out.replace(
    /\[([^\n\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  )
  return out
}

export function renderMarkdown(source: string): string {
  if (!source || !source.trim()) return ""

  const escaped = escapeHtml(source.replace(/\r\n/g, "\n").trim())
  const codeBlocks: string[] = []

  // Fenced code blocks are extracted before line parsing so their content is
  // never treated as a list, a heading or bold text.
  const withPlaceholders = escaped.replace(
    /```([a-zA-Z0-9+#._-]*)[ \t]*\n?([\s\S]*?)```/g,
    (_match, language: string, code: string) => {
      const lang = language
        ? ` class="language-${language.toLowerCase()}"`
        : ""
      codeBlocks.push(
        `<pre><code${lang}>${code.replace(/\n$/, "")}</code></pre>`,
      )
      return `\u0000CODE${codeBlocks.length - 1}\u0000`
    },
  )

  const html: string[] = []
  let paragraph: string[] = []
  let listItems: string[] = []
  let listOrdered = false

  const flushParagraph = () => {
    if (!paragraph.length) return
    html.push(`<p>${paragraph.map(renderInline).join("<br />")}</p>`)
    paragraph = []
  }

  const flushList = () => {
    if (!listItems.length) return
    const tag = listOrdered ? "ol" : "ul"
    const items = listItems
      .map((item) => `<li>${renderInline(item)}</li>`)
      .join("")
    html.push(`<${tag}>${items}</${tag}>`)
    listItems = []
  }

  const flushAll = () => {
    flushParagraph()
    flushList()
  }

  for (const line of withPlaceholders.split("\n")) {
    const trimmed = line.trim()

    if (!trimmed) {
      flushAll()
      continue
    }

    const codeMatch = trimmed.match(/^\u0000CODE(\d+)\u0000$/)
    if (codeMatch) {
      flushAll()
      html.push(codeBlocks[Number(codeMatch[1])] ?? "")
      continue
    }

    const heading = trimmed.match(/^(#{1,4})\s+(.*)$/)
    if (heading) {
      flushAll()
      const level = Math.min(6, heading[1].length + 2)
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      continue
    }

    const bullet = line.match(/^\s*[-*+]\s+(.*)$/)
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (bullet || numbered) {
      flushParagraph()
      const ordered = Boolean(numbered)
      if (listItems.length > 0 && listOrdered !== ordered) flushList()
      listOrdered = ordered
      listItems.push((bullet ?? numbered)?.[1] ?? "")
      continue
    }

    flushList()
    paragraph.push(trimmed)
  }

  flushAll()

  return DOMPurify.sanitize(html.join(""), {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOW_DATA_ATTR: false,
  })
}
