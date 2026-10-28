#!/usr/bin/env node
/**
 * Génère `nginx.locale-map.conf` depuis `src/seo/publicPaths.ts`.
 *
 * Le passage aux URL explicites (`/en/...`) laisse derrière lui les anciennes
 * URL `?lang=en` que portent les liens déjà publiés, les favoris et les
 * campagnes. nginx les redirige en 301 vers l'URL canonique. La liste des
 * routes concernées ne doit pas être recopiée à la main : elle doit venir de la
 * même source que le routeur React et que `LocaleLink`, sinon une route ajoutée
 * plus tard resterait silencieusement sur l'ancien mécanisme.
 *
 * Le fichier produit est inclus par nginx.conf (`include ...presence-locale-map.conf`).
 * `--check` compare le fichier présent sur le disque à la sortie attendue et
 * échoue sans rien écrire : `pnpm check:seo` l'utilise pour détecter une carte
 * périmée.
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const SOURCE = path.join(ROOT, "src", "seo", "publicPaths.ts")
const TARGET = path.join(ROOT, "nginx.locale-map.conf")
const CHECK = process.argv.includes("--check")

const source = fs.readFileSync(SOURCE, "utf8")
const block = source.match(
  /export const PUBLIC_PATHS = \[([\s\S]*?)\]\s*as const/,
)
if (!block) {
  console.error(
    "[locale-map] PUBLIC_PATHS was not found in src/seo/publicPaths.ts — refusing to guess.",
  )
  process.exit(1)
}

const paths = [...block[1].matchAll(/"(\/[^"]*)"/g)].map((match) => match[1])
if (paths.length === 0) {
  console.error("[locale-map] PUBLIC_PATHS is empty — refusing to write a map.")
  process.exit(1)
}
const duplicates = paths.filter((p, index) => paths.indexOf(p) !== index)
if (duplicates.length > 0) {
  console.error(`[locale-map] duplicate public paths: ${duplicates.join(", ")}`)
  process.exit(1)
}

/** URL anglaise d'une route publique, identique à `localizedPath()`. */
function englishUrl(routePath) {
  return routePath === "/" ? "/en" : `/en${routePath}`
}

const lines = [
  "# GÉNÉRÉ — ne pas modifier à la main.",
  "# Source : src/seo/publicPaths.ts, via scripts/generate-nginx-locale-map.mjs.",
  "#",
  "# Le paramètre `?lang=` est un vestige de la période où l'anglais vivait sur",
  "# la même URL que l'allemand. Les pages publiques ont désormais leur propre",
  "# URL `/en/...` : nginx redirige définitivement l'ancienne forme vers elle.",
  "# Les cinq écrans noindex (login, register, mot de passe, onboarding) n'ont",
  "# pas d'URL anglaise et ne figurent donc pas ici : leur `?lang=en` continue",
  "# de servir directement la coquille `_i18n/<route>/index.html`.",
  "#",
  "# Clé : \"$uri|$arg_lang\" ; valeur : cible du 301, chaîne vide = pas de",
  "# redirection. `$uri` est le chemin normalisé, sans query string.",
  'map "$uri|$arg_lang" $presence_locale_redirect {',
  '    default "";',
]

for (const routePath of paths) {
  lines.push(`    "${routePath}|en" "${englishUrl(routePath)}";`)
  lines.push(`    "${routePath}|de" "${routePath}";`)
}
lines.push("}")
lines.push("")
lines.push("# Query string de la cible : tout sauf `lang`, dans l'ordre d'origine.")
lines.push("#")
lines.push("# Une campagne qui pointe `/pricing?lang=en&utm_source=…&utm_medium=…` doit")
lines.push("# arriver sur `/en/pricing?utm_source=…&utm_medium=…` : perdre les UTM")
lines.push("# casserait l'attribution au moment précis de la migration. `lang` peut")
lines.push("# être au début, au milieu ou à la fin ; la valeur est recollée avec son")
lines.push("# `?`, ou vide quand `lang` était le seul paramètre.")
lines.push('map $args $presence_locale_query {')
lines.push('    default "";')
// `~*` : `map` compare ses clés sans tenir compte de la casse, donc
// `?lang=EN` est déjà redirigé. Sans ce drapeau, la query serait perdue
// (`/en/pricing` au lieu de `/en/pricing?utm_source=…`).
lines.push('    "~*^lang=(?:en|de)$"           "";')
lines.push('    "~*^lang=(?:en|de)&(.+)$"      "?$1";')
lines.push('    "~*^(.+)&lang=(?:en|de)&(.+)$" "?$1&$2";')
lines.push('    "~*^(.+)&lang=(?:en|de)$"      "?$1";')
lines.push("}")
lines.push("")

const content = lines.join("\n")

if (CHECK) {
  const current = fs.existsSync(TARGET) ? fs.readFileSync(TARGET, "utf8") : ""
  if (current !== content) {
    console.error(
      "[locale-map] nginx.locale-map.conf is stale — run `node scripts/generate-nginx-locale-map.mjs`.",
    )
    process.exit(1)
  }
  console.log(
    `[locale-map] nginx.locale-map.conf matches src/seo/publicPaths.ts (${paths.length} routes, ${paths.length * 2} redirects).`,
  )
  process.exit(0)
}

fs.writeFileSync(TARGET, content)
console.log(
  `[locale-map] wrote nginx.locale-map.conf: ${paths.length} public routes, ${paths.length * 2} 301 rules.`,
)
