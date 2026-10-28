#!/usr/bin/env node
/**
 * Operator identity audit for the Presence legal pages.
 *
 * `src/config/operator.json` is the single source of truth for /impressum,
 * /privacy, /terms and /widerruf. This script checks that the data file is
 * well-formed and cannot silently rot:
 *
 *  1. schema — requirements, usedOn pages, label/placeholder keys, and the
 *     three states (provided / missing / not applicable) stay apart;
 *  2. no placeholder leaks into a provided value (a bracketed "eintragen"
 *     pasted as a real company name would otherwise render as data);
 *  3. every label/placeholder key exists in *both* catalogues;
 *  4. an inventory of what is provided, missing and not applicable, with the
 *     pages each missing field is required on.
 *
 * `--require-complete` turns the inventory into a launch gate: it fails until
 * every field is either provided or explicitly marked not applicable (which
 * needs the documented reason). Use it before publishing.
 *
 * Usage: node scripts/check-operator-identity.mjs [--require-complete]
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"

const ROOT = new URL("..", import.meta.url).pathname
const FRONTEND = join(
  ROOT,
  "SaaS_Web_Application_digitale_presenz_v2",
  "SaaS_Web_Application_UI_UX_frontendV2",
)
const CONFIG = join(FRONTEND, "src", "config", "operator.json")
const CATALOG_DIR = join(FRONTEND, "src", "i18n")

const REQUIREMENTS = new Set(["mandatory", "conditional", "optional"])
const requireComplete = process.argv.includes("--require-complete")

function nonEmpty(value) {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null
}

function lookup(catalog, key) {
  return key.split(".").reduce((node, part) => {
    if (typeof node !== "object" || node === null) return undefined
    return node[part]
  }, catalog)
}

const fields = JSON.parse(readFileSync(CONFIG, "utf8"))
const catalogs = Object.fromEntries(
  ["de", "en"].map((locale) => [
    locale,
    JSON.parse(readFileSync(join(CATALOG_DIR, `${locale}.json`), "utf8")),
  ]),
)

const problems = []
const entries = Object.entries(fields).filter(([key]) => !key.startsWith("_"))

if (entries.length === 0) problems.push("no fields found in operator.json")

for (const [key, field] of entries) {
  if (!field || typeof field !== "object" || Array.isArray(field)) {
    problems.push(`${key}: must be an object`)
    continue
  }
  if (!REQUIREMENTS.has(field.requirement)) {
    problems.push(
      `${key}: requirement must be one of ${[...REQUIREMENTS].join(", ")}`,
    )
  }
  if (field.requirement === "conditional" && !nonEmpty(field.condition)) {
    problems.push(`${key}: a conditional field must document \`condition\``)
  }
  if (
    !Array.isArray(field.usedOn) ||
    field.usedOn.length === 0 ||
    field.usedOn.some((path) => typeof path !== "string" || !path.startsWith("/"))
  ) {
    problems.push(`${key}: usedOn must list the pages as "/…" strings`)
  }
  for (const keyName of ["labelKey", "placeholderKey"]) {
    const messageKey = nonEmpty(field[keyName])
    if (!field[keyName]) continue
    if (!messageKey) {
      problems.push(`${key}: ${keyName} must be a non-empty i18n key`)
      continue
    }
    for (const [locale, catalog] of Object.entries(catalogs)) {
      if (!nonEmpty(lookup(catalog, messageKey))) {
        problems.push(
          `${key}: ${keyName} "${messageKey}" is missing from ${locale}.json`,
        )
      }
    }
  }

  const value = nonEmpty(field.value)
  const notApplicable = nonEmpty(field.notApplicable)
  const status = value ? "provided" : notApplicable ? "not-applicable" : "missing"

  if (value && notApplicable) {
    problems.push(`${key}: provide a value or mark not-applicable, not both`)
  }
  if (status === "not-applicable" && field.requirement === "mandatory") {
    problems.push(`${key}: a mandatory field cannot be marked not-applicable`)
  }
  if (value && /[[\]]|TODO|FIXME|eintragen|to be completed/i.test(value)) {
    problems.push(
      `${key}: the value still looks like a placeholder — remove the brackets/TODO text before it renders as data`,
    )
  }
}

const statusOf = (field) =>
  nonEmpty(field.value)
    ? "provided"
    : nonEmpty(field.notApplicable)
      ? "not-applicable"
      : "missing"

const rows = entries.map(([key, field]) => ({
  key,
  requirement: field.requirement,
  usedOn: Array.isArray(field.usedOn) ? field.usedOn.join(", ") : "?",
  status: statusOf(field),
}))

const count = (status) => rows.filter((row) => row.status === status).length
const missingMandatory = rows.filter(
  (row) => row.status === "missing" && row.requirement === "mandatory",
)
const missingConditional = rows.filter(
  (row) => row.status === "missing" && row.requirement === "conditional",
)

console.log("── Operator identity (src/config/operator.json) ──────────────")
console.log(`Fields: ${rows.length}`)
for (const row of rows) {
  const mark =
    row.status === "provided" ? "✅" : row.status === "not-applicable" ? "➖" : "⏳"
  console.log(
    `   ${mark} ${row.key.padEnd(22)} ${row.status.padEnd(15)} ${row.requirement.padEnd(12)} ${row.usedOn}`,
  )
}
console.log(
  `\nProvided: ${count("provided")} · missing: ${count("missing")} · not applicable: ${count("not-applicable")}`,
)

if (problems.length > 0) {
  console.log(`\n❌ ${problems.length} problem(s) in operator.json:`)
  for (const problem of problems) console.log(`   - ${problem}`)
} else {
  console.log("\n✅ Schema, keys and states are valid.")
}

if (missingMandatory.length > 0) {
  console.log(
    `\n⏳ Mandatory values still missing (${missingMandatory.length}) — the imprint renders marked placeholders:`,
  )
  for (const row of missingMandatory) console.log(`   - ${row.key} (${row.usedOn})`)
}
if (missingConditional.length > 0) {
  console.log(
    `\n⏳ Conditional values still undecided (${missingConditional.length}) — provide a value or a documented notApplicable reason:`,
  )
  for (const row of missingConditional) console.log(`   - ${row.key} (${row.usedOn})`)
}
const notApplicableRows = rows.filter((row) => row.status === "not-applicable")
if (notApplicableRows.length > 0) {
  console.log("\n➖ Documented as not applicable:")
  for (const row of notApplicableRows) console.log(`   - ${row.key}`)
}

let failed = problems.length > 0
if (requireComplete) {
  const undecided = rows.filter((row) => row.status === "missing")
  if (undecided.length > 0) {
    failed = true
    console.log(
      `\n❌ --require-complete: ${undecided.length} field(s) are neither provided nor marked not-applicable.`,
    )
  } else {
    console.log("\n✅ Identity is complete: every field is provided or not applicable.")
  }
}

process.exit(failed ? 1 : 0)
