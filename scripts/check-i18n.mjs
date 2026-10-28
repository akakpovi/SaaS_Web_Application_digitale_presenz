#!/usr/bin/env node
/**
 * i18n audit for the Presence frontend.
 *
 * 1. Parity: both catalogues must expose exactly the same keys, the same
 *    nesting and the same list lengths. A gap here is what produces a raw key
 *    (or an English string) in the German UI.
 * 2. Coverage: counts user-visible strings that are still hardcoded in a page
 *    or component, so the remaining translation work is measurable instead of
 *    guessed.
 *
 * The coverage scan walks the real JSX syntax tree. An earlier regex version
 * counted arrow-function bodies as text nodes (`>(\"All\") const [x, setX] …`),
 * which inflated the number with strings no user ever sees; the AST scan only
 * reports `JsxText`, string children and the user-visible attributes
 * (`placeholder`, `aria-label`, `title`, `alt`).
 *
 * Usage: node scripts/check-i18n.mjs [--verbose]
 */
import { readFileSync, readdirSync, statSync } from "node:fs"
import { createRequire } from "node:module"
import { join, relative } from "node:path"

const ROOT = new URL("..", import.meta.url).pathname
const FRONTEND = join(
  ROOT,
  "SaaS_Web_Application_digitale_presenz_v2",
  "SaaS_Web_Application_UI_UX_frontendV2",
)
const CATALOG_DIR = join(FRONTEND, "src", "i18n")
const verbose = process.argv.includes("--verbose")

// `typescript` is installed in the frontend workspace, not at the repo root.
const frontendRequire = createRequire(join(FRONTEND, "package.json"))
const ts = frontendRequire("typescript")

function flatten(node, path = "", out = {}) {
  if (Array.isArray(node)) {
    out[path] = `list[${node.length}]`
  } else if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) {
      flatten(value, path ? `${path}.${key}` : key, out)
    }
  } else {
    out[path] = typeof node
  }
  return out
}

function readCatalog(locale) {
  return JSON.parse(readFileSync(join(CATALOG_DIR, `${locale}.json`), "utf8"))
}

function walkFiles(dir) {
  const out = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      out.push(...walkFiles(full))
    } else if (/\.tsx?$/.test(entry)) {
      out.push(full)
    }
  }
  return out
}

/** Attributes whose literal value is read by a human. */
const USER_VISIBLE_ATTRS = new Set(["placeholder", "aria-label", "title", "alt"])

/** At least two letters: skips punctuation, symbols and stray whitespace. */
const HAS_WORDS = /[A-Za-zÄÖÜäöüß]{2,}/

/**
 * User-visible literals of one file, read from the JSX syntax tree:
 * `JsxText` children, string children (`{"…"}`) and literal values of the
 * user-visible attributes above.
 */
function findHardcodedStrings(file) {
  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf8"),
    ts.ScriptTarget.ESNext,
    /* setParentNodes */ true,
    ts.ScriptKind.TSX,
  )
  const found = []

  const record = (node, value, kind) => {
    const text = value.replace(/\s+/g, " ").trim()
    if (!text || !HAS_WORDS.test(text)) return
    const { line } = source.getLineAndCharacterOfPosition(node.getStart(source))
    found.push({ line: line + 1, kind, text })
  }

  const visit = (node) => {
    if (ts.isJsxText(node)) {
      record(node, node.text, "text")
    } else if (ts.isJsxExpression(node) && node.expression) {
      const expression = node.expression
      if (
        ts.isStringLiteral(expression) ||
        ts.isNoSubstitutionTemplateLiteral(expression)
      ) {
        record(expression, expression.text, "text")
      }
    } else if (ts.isJsxAttribute(node) && node.initializer) {
      const name = node.name.getText(source)
      if (USER_VISIBLE_ATTRS.has(name) && ts.isStringLiteral(node.initializer)) {
        record(node.initializer, node.initializer.text, `attr:${name}`)
      }
    }
    ts.forEachChild(node, visit)
  }

  visit(source)
  return found
}

const en = flatten(readCatalog("en"))
const de = flatten(readCatalog("de"))

const parityProblems = []
for (const [key, shape] of Object.entries(en)) {
  if (!(key in de)) parityProblems.push(`missing in de.json: ${key}`)
  else if (de[key] !== shape) {
    parityProblems.push(
      `shape mismatch for ${key}: en=${shape} de=${de[key]}`,
    )
  }
}
for (const key of Object.keys(de)) {
  if (!(key in en)) parityProblems.push(`missing in en.json: ${key}`)
}

/**
 * Interpolation parity: the same `{placeholders}` in both languages.
 * A German string that dropped `{count}` renders a sentence with a hole in it,
 * and one that invented `{date}` shows the literal braces to the user.
 */
function placeholdersOf(value) {
  if (typeof value !== "string") return null
  return [...value.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",")
}

const interpolationProblems = []
for (const [key, enShape] of Object.entries(en)) {
  if (!(key in de)) continue
  const enVars = placeholdersOf(enShape)
  const deVars = placeholdersOf(de[key])
  if (enVars === null || deVars === null) continue
  if (enVars !== deVars) {
    interpolationProblems.push(
      `${key}: en={${enVars}} de={${deVars}}`,
    )
  }
}

const files = [
  ...walkFiles(join(FRONTEND, "src", "pages")),
  ...walkFiles(join(FRONTEND, "src", "components")),
].filter((file) => !file.endsWith(".d.ts"))

const coverage = files
  .map((file) => ({
    file: relative(FRONTEND, file),
    strings: findHardcodedStrings(file),
  }))
  .filter((entry) => entry.strings.length > 0)
  .sort((a, b) => b.strings.length - a.strings.length)

console.log("── Catalogue parity ──────────────────────────────────────────")
console.log(`en.json keys: ${Object.keys(en).length}`)
console.log(`de.json keys: ${Object.keys(de).length}`)
if (parityProblems.length === 0) {
  console.log("✅ German catalogue matches the English reference exactly.")
} else {
  console.log(`❌ ${parityProblems.length} problem(s):`)
  for (const problem of parityProblems) console.log(`   - ${problem}`)
}

if (interpolationProblems.length === 0) {
  console.log("✅ Interpolations match in both languages.")
} else {
  console.log(`❌ ${interpolationProblems.length} interpolation problem(s):`)
  for (const problem of interpolationProblems) console.log(`   - ${problem}`)
}

console.log("\n── Hardcoded user-visible strings (JSX AST) ──────────────────")
const total = coverage.reduce((sum, entry) => sum + entry.strings.length, 0)
console.log(`Files with remaining literals: ${coverage.length}`)
console.log(`Total remaining literals: ${total}`)
for (const entry of coverage) {
  console.log(`   ${String(entry.strings.length).padStart(4)}  ${entry.file}`)
  if (verbose) {
    for (const item of entry.strings) {
      console.log(
        `         L${item.line} [${item.kind}] ${item.text.slice(0, 120)}`,
      )
    }
  }
}
if (!verbose) console.log("   (run with --verbose for lines and text)")

process.exit(
  parityProblems.length === 0 && interpolationProblems.length === 0 ? 0 : 1,
)
