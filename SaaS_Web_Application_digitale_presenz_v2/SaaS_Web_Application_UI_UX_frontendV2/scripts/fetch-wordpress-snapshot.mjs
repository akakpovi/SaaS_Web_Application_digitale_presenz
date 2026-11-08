#!/usr/bin/env node
/**
 * Rafraîchit l'instantané des articles WordPress utilisé par le build Docker.
 *
 * `prerender.mjs` ne peut pas joindre la loopback WordPress depuis BuildKit
 * (`network: host` demande une entitlement supplémentaire). Le build lit donc
 * `src/seo/wordpress-posts.snapshot.json`, versionné, et ce script le met à jour
 * depuis le WordPress local. Le JSON brut de l'API est conservé pour que
 * `prerender.mjs` applique exactement le même mapping que sur une réponse live.
 *
 * Usage : `pnpm snapshot:blog`
 *   PRERENDER_WP_API_URL=http://127.0.0.1:8081/wp-json (défaut)
 */

import fs from "node:fs/promises"
import path from "node:path"

const ROOT = path.resolve(import.meta.dirname, "..")
const base = (process.env.PRERENDER_WP_API_URL || "http://127.0.0.1:8081/wp-json")
  .trim()
  .replace(/\/+$/, "")
const api = base.endsWith("/wp-json")
  ? `${base}/wp/v2`
  : `${base}/wp-json/wp/v2`
const url = `${api}/posts?per_page=100&_embed=1&orderby=date&order=desc`

const response = await fetch(url, { headers: { Accept: "application/json" } })
if (!response.ok) {
  throw new Error(`WordPress returned HTTP ${response.status} for ${url}`)
}
const posts = await response.json()
if (!Array.isArray(posts)) {
  throw new Error("WordPress returned an unexpected payload (expected a list).")
}

const output = path.join(ROOT, "src/seo/wordpress-posts.snapshot.json")
await fs.writeFile(output, `${JSON.stringify(posts, null, 2)}\n`, "utf8")
console.log(
  `[snapshot] ${posts.length} WordPress posts written to ${path.relative(ROOT, output)}`,
)
