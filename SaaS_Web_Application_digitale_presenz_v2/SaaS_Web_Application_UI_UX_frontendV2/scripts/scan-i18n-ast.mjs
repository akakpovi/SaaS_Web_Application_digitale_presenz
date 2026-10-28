/**
 * AST-based i18n coverage scan (TypeScript compiler API).
 * Finds JSX text nodes and user-visible string attributes that are literal,
 * not produced by t(...). Far fewer false positives than a regex pass.
 *
 * Usage: node scripts/scan-i18n-ast.mjs [file ...]  (defaults to every .ts/.tsx under src)
 */
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join, relative } from "node:path"
import ts from "typescript"

const ROOT = process.cwd()
const ATTRS = new Set([
  "label", "title", "placeholder", "aria-label", "alt", "subtitle",
  "description", "tooltip", "ariaLabel", "emptyTitle", "emptyDescription",
])

// Strings that are legitimately literal: brands, acronyms, symbols, keys.
const ALLOWED = /^(Presence|AKA(?:\s*IA)?|SSL|DNS|SPF|DKIM|DMARC|TLS|HTTP|HTTPS|API|JSON|CSV|PDF|ID|IP|URL|UX|UI|SEO|CRM|GDPR|RGPD|DSGVO|DE|EN|OK|•|—|–|·|→|←|×|✓|✕|•|…|:|%|\/|[0-9]+|GET|POST|PUT|DELETE|PATCH|EU|USA|SaaS|Paddle|Stripe|WordPress|Nmap|Nikto|WhatWeb|testssl\.sh|DNSRecon|Gobuster|Nuclei|ZAP|Google|LinkedIn|Slack|PostHog|Mailpit|Hetzner|Impressum|Datenschutz|AGB|Widerruf)$/

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) walk(full, out)
    else if (/\.tsx?$/.test(entry)) out.push(full)
  }
  return out
}

function scan(file) {
  const source = readFileSync(file, "utf8")
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const hits = []
  const record = (node, text, kind) => {
    const clean = text.replace(/\s+/g, " ").trim()
    if (!clean) return
    if (!/[A-Za-zÄÖÜäöüß]/.test(clean)) return
    if (ALLOWED.test(clean)) return
    const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
    hits.push({ line: line + 1, text: clean.length > 90 ? clean.slice(0, 90) + "…" : clean, kind })
  }
  const visit = (node) => {
    if (ts.isJsxText(node)) {
      // Skip whitespace-only text and text made of punctuation.
      record(node, node.text, "text")
    } else if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
      const name = node.name.getText(sf)
      if (ATTRS.has(name)) record(node, node.initializer.text, `attr:${name}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return hits
}

let files = process.argv.slice(2)
if (!files.length) files = walk(join(ROOT, "src"))
files = files.map((f) => f.replace(/^\.\//, ""))
if (process.argv.includes("--all")) {
  // aggregate mode is the default when no files are given
}
let total = 0
const per = []
for (const f of files) {
  const hits = scan(f)
  if (hits.length) per.push({ file: relative(ROOT, f), hits })
  total += hits.length
}
if (files.length > 4) {
  per.sort((a, b) => b.hits.length - a.hits.length)
  console.log(`files with literals: ${per.length}   total literals: ${total}`)
  for (const p of per) console.log(`  ${String(p.hits.length).padStart(4)}  ${p.file}`)
} else {
  for (const p of per) {
    console.log(`\n### ${p.file} (${p.hits.length})`)
    for (const h of p.hits) console.log(`  L${h.line} [${h.kind}] ${JSON.stringify(h.text)}`)
  }
  console.log(`\ntotal: ${total}`)
}
