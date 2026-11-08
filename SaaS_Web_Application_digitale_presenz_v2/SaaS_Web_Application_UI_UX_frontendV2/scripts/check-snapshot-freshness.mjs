#!/usr/bin/env node
/**
 * Checks that the committed WordPress blog snapshot is recent enough.
 *
 * The snapshot is refreshed manually (or by the scheduled workflow) and
 * committed, because BuildKit cannot reach the loopback WordPress container.
 * Using the JSON file's mtime would be meaningless in CI: a fresh checkout
 * gives every file the checkout time, so a months-old snapshot would look
 * new. The age is therefore derived from the last commit that changed the
 * snapshot. A locally modified (dirty) snapshot is considered fresh until it
 * is committed.
 *
 * Usage:
 *   node scripts/check-snapshot-freshness.mjs [--max-age-days 7]
 *
 * Exit codes:
 *   0 — snapshot is fresh
 *   1 — snapshot is older than the threshold
 *   2 — snapshot/config/history cannot be read
 */

import { execFileSync } from "node:child_process"
import { existsSync, readFileSync, statSync } from "node:fs"
import path from "node:path"

const ROOT = path.resolve(import.meta.dirname, "..")
const SNAPSHOT = path.join(ROOT, "src/seo/wordpress-posts.snapshot.json")
const DAY_MS = 24 * 60 * 60 * 1000
const DEFAULT_MAX_AGE_DAYS = 7

function fail(message) {
  console.error(`[snapshot] ${message}`)
  process.exit(2)
}

const args = process.argv.slice(2)
const flagIndex = args.indexOf("--max-age-days")
const rawMaxAge =
  flagIndex === -1 ? String(DEFAULT_MAX_AGE_DAYS) : args[flagIndex + 1]
const maxAgeDays = Number(rawMaxAge)

if (!rawMaxAge || !Number.isFinite(maxAgeDays) || maxAgeDays < 0) {
  fail("--max-age-days must be a non-negative number.")
}
if (!existsSync(SNAPSHOT)) {
  fail(`missing snapshot: ${path.relative(ROOT, SNAPSHOT)}`)
}

let posts
try {
  posts = JSON.parse(readFileSync(SNAPSHOT, "utf8"))
} catch (error) {
  fail(`invalid JSON: ${error.message}`)
}
if (!Array.isArray(posts)) {
  fail("snapshot must be a JSON list of WordPress posts.")
}

/** Runs git in the frontend checkout and returns trimmed stdout. */
function git(...commands) {
  return execFileSync("git", ["-C", ROOT, ...commands], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim()
}

const relativeSnapshot = path.relative(ROOT, SNAPSHOT)
let timestamp = statSync(SNAPSHOT).mtimeMs
let source = "file mtime"

try {
  if (git("rev-parse", "--is-shallow-repository") === "true") {
    fail(
      "shallow clone; fetch full history (git fetch --unshallow) before checking snapshot age.",
    )
  }

  const dirty = git("status", "--porcelain", "--", relativeSnapshot)
  if (dirty) {
    source = "uncommitted working tree"
  } else {
    const committedAt = git("log", "-1", "--format=%ct", "--", relativeSnapshot)
    if (!committedAt) {
      fail("snapshot has no commit history; commit it first.")
    }
    timestamp = Number(committedAt) * 1000
    source = "last commit"
  }
} catch (error) {
  if (error instanceof Error) {
    if (error.message.startsWith("shallow clone;")) throw error
    if (error.message.startsWith("snapshot has no")) throw error
  }
  // A tarball without Git history is still usable; fall back to the mtime.
  source = "file mtime (git history unavailable)"
}

const ageDays = Math.max(0, (Date.now() - timestamp) / DAY_MS)
const age = ageDays.toFixed(1)
const count = posts.length

if (ageDays > maxAgeDays) {
  console.error(
    `[snapshot] stale: ${count} posts, ${age} days old (${source}; max ${maxAgeDays}).`,
  )
  console.error("[snapshot] refresh it with `pnpm snapshot:blog` and commit the file.")
  process.exit(1)
}

console.log(
  `[snapshot] fresh: ${count} posts, ${age} days old (${source}; max ${maxAgeDays}).`,
)
