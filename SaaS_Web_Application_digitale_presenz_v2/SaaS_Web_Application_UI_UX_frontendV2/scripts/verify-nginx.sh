#!/usr/bin/env bash
#
# Exécute la configuration nginx de production (nginx.conf, tel quel) contre le
# `dist/` réellement construit, dans un conteneur jetable, et vérifie que
# chaque URL annoncée par hreflang répond bien dans la langue déclarée.
#
# Pourquoi : le pré-rendu et le modèle de résolution en Node (check-seo-build,
# e2e/helpers/static-dist.ts) rejouent les règles de nginx. Ce script ne rejoue
# rien : c'est le vrai nginx qui lit le vrai nginx.conf. Il répond à la seule
# question que le modèle ne peut pas trancher — `try_files` sert-il bien le
# fichier du dossier `internal`, et ce dossier reste-t-il inadressable ?
#
# Prérequis : Docker et une image nginx locale (aucune connexion requise si
# l'image est déjà présente). Le script ne touche à aucune autre ressource : un
# seul conteneur jetable, supprimé à la fin.
#
# Usage : bash scripts/verify-nginx.sh [--keep]   (--keep laisse le conteneur)
# Sortie : 0 = toutes les vérifications passent, 1 = au moins un échec,
#          0 avec "SKIP" si Docker est indisponible (aucune vérification jouée).

set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$FRONTEND_DIR/dist"
NGINX_CONF="$FRONTEND_DIR/nginx.conf"
IMAGE="${NGINX_IMAGE:-nginx:1.27-alpine}"
CONTAINER="presence-nginx-config-check"
PORT="${NGINX_CHECK_PORT:-18443}"
WORK="$(mktemp -d)"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

cleanup() {
  if [ "$KEEP" -eq 0 ]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    rm -rf "$WORK"
  else
    echo "[verify-nginx] work dir kept at $WORK (container $CONTAINER)"
  fi
}
trap cleanup EXIT

if ! command -v docker >/dev/null 2>&1; then
  echo "[verify-nginx] SKIP — Docker is not available, the nginx rule was NOT executed."
  exit 0
fi
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "[verify-nginx] SKIP — image $IMAGE is not present locally (no pull attempted)."
  exit 0
fi
if [ ! -f "$DIST/index.html" ]; then
  echo "[verify-nginx] dist/index.html is missing — run \`pnpm build\` first." >&2
  exit 1
fi

# Origin the artifact was built for: given explicitly, or read from the canonical
# URL it carries. A build made for the public domain must not be checked against
# `http://localhost:8443`, or every absolute canonical looks wrong.
BUILD_ORIGIN="${VITE_BASE_URL:-${SITE_URL:-$(sed -n 's/.*<link rel="canonical" href="\([^"]*\)".*/\1/p' "$DIST/index.html" | head -1)}}"
BUILD_ORIGIN="${BUILD_ORIGIN%/}"
if [ -z "$BUILD_ORIGIN" ]; then
  echo "[verify-nginx] no build origin found — pass VITE_BASE_URL or build with one." >&2
  exit 1
fi
echo "[verify-nginx] build origin: $BUILD_ORIGIN"

# Certificat auto-signé + le fichier que nginx.conf inclut. Le déploiement réel
# utilise le même emplacement (scripts/setup_local_tls.sh / Let's Encrypt).
mkdir -p "$WORK/ssl" "$WORK/conf.d"
if ! openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -subj "/CN=localhost" \
  -keyout "$WORK/ssl/key.pem" -out "$WORK/ssl/cert.pem" >/dev/null 2>&1; then
  echo "[verify-nginx] SKIP — openssl could not create a test certificate." >&2
  exit 0
fi
# Paths as seen *inside* the container: $WORK/ssl is mounted at /etc/nginx/ssl.
{
  echo "ssl_certificate     /etc/nginx/ssl/cert.pem;"
  echo "ssl_certificate_key /etc/nginx/ssl/key.pem;"
} > "$WORK/ssl/tls.conf"
cp "$NGINX_CONF" "$WORK/conf.d/default.conf"

# The `?lang=` redirect map is generated from src/seo/publicPaths.ts; nginx
# `include`s it, so it must exist before the container starts. Regenerating it
# here also proves the source of truth still produces a loadable map.
MAP_FILE="$FRONTEND_DIR/nginx.locale-map.conf"
if ! node "$FRONTEND_DIR/scripts/generate-nginx-locale-map.mjs" >/dev/null; then
  echo "[verify-nginx] could not generate nginx.locale-map.conf" >&2
  exit 1
fi

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run --rm -d --name "$CONTAINER" \
  -p "127.0.0.1:$PORT:443" \
  -v "$DIST:/usr/share/nginx/html:ro" \
  -v "$WORK/conf.d/default.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$MAP_FILE:/etc/nginx/conf.d/presence-locale-map.conf:ro" \
  -v "$WORK/ssl:/etc/nginx/ssl:ro" \
  "$IMAGE" >/dev/null

# Attendre que nginx serve *le bon contenu*, pas seulement qu'il accepte une
# connexion TCP : lors d'un démarrage à froid, le conteneur peut répondre avant
# que la configuration et les fichiers montés soient réellement servis. La
# sonde vérifie donc la page anglaise `/en` avec son statut et son contenu
# exacts, ce qui couvre aussi le faux négatif SIGPIPE corrigé plus bas.
ready=0
for _ in $(seq 1 60); do
  code="$(curl -sk -o "$WORK/probe.html" -w '%{http_code}' \
    "https://127.0.0.1:$PORT/en" 2>/dev/null || true)"
  if [ "$code" = "200" ] && grep -qF '<html lang="en"' "$WORK/probe.html" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 0.5
done

if [ "$ready" -ne 1 ] || ! docker exec "$CONTAINER" nginx -t >/dev/null 2>&1; then
  echo "[verify-nginx] the container did not serve the config:" >&2
  docker logs "$CONTAINER" 2>&1 | tail -20 >&2 || true
  exit 1
fi

FAILURES=0
# request(url, status attendu, fragment attendu, libellé)
request() {
  local url="$1" want_status="$2" want_text="$3" label="$4"
  local body code
  body="$(curl -sk "https://127.0.0.1:$PORT$url")"
  code="$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1:$PORT$url")"
  if [ "$code" != "$want_status" ]; then
    echo "  FAIL  $label — $url answered $code, expected $want_status"
    FAILURES=$((FAILURES + 1))
    return
  fi
  # Write the body to a file before grepping. `printf | grep -q` under
  # `set -o pipefail` is a false negative for large pages: `grep -q` closes the
  # pipe at the first match, `printf` gets SIGPIPE, and the pipeline is reported
  # as failed even though the text was found. That is exactly why only the
  # ~60 KB home pages used to fail.
  printf '%s' "$body" > "$WORK/response.html"
  if ! grep -qF -- "$want_text" "$WORK/response.html"; then
    echo "  FAIL  $label — $url does not contain: $want_text"
    FAILURES=$((FAILURES + 1))
    return
  fi
  echo "  ok    $label — $url ($code)"
}

http_code() {
  curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1:$PORT$1"
}

http_location() {
  curl -sk -o /dev/null -D - "https://127.0.0.1:$PORT$1" \
    | tr -d '\r' \
    | awk 'tolower($1) == "location:" { print $2; exit }'
}

# expect_redirect(url, chemin cible, libellé)
# nginx renvoie une URL absolue construite avec $scheme://$http_host, donc le
# port publié du conteneur doit se retrouver tel quel dans `Location`.
expect_redirect() {
  local url="$1" target="$2" label="$3" code loc expected
  expected="https://127.0.0.1:$PORT$target"
  code="$(http_code "$url")"
  loc="$(http_location "$url")"
  if [ "$code" != "301" ] || [ "$loc" != "$expected" ]; then
    echo "  FAIL  $label — $url answered $code with Location \"$loc\", expected 301 \"$expected\""
    FAILURES=$((FAILURES + 1))
    return
  fi
  echo "  ok    $label — $url → 301 $loc"
}

# expect_no_redirect(url, statut, fragment, libellé) : 301 interdit.
expect_no_redirect() {
  local url="$1" want="$2" text="$3" label="$4" loc
  loc="$(http_location "$url")"
  if [ -n "$loc" ]; then
    echo "  FAIL  $label — $url redirects to \"$loc\""
    FAILURES=$((FAILURES + 1))
    return
  fi
  request "$url" "$want" "$text" "$label"
}

# expect_follow(url, cible, langue, libellé) : exactement un saut, 200, bonne langue.
expect_follow() {
  local url="$1" target="$2" lang="$3" label="$4" out code hops final
  out="$(curl -sk -L --max-redirs 1 -o "$WORK/follow.html" \
    -w '%{http_code} %{num_redirects} %{url_effective}' \
    "https://127.0.0.1:$PORT$url")"
  read -r code hops final <<<"$out"
  if [ "$code" != "200" ] || [ "$hops" != "1" ]; then
    echo "  FAIL  $label — $url ended $code after $hops redirect(s) (loop or dead end)"
    FAILURES=$((FAILURES + 1))
    return
  fi
  if [ "$final" != "https://127.0.0.1:$PORT$target" ]; then
    echo "  FAIL  $label — $url landed on $final, expected $target"
    FAILURES=$((FAILURES + 1))
    return
  fi
  if ! grep -qF "<html lang=\"$lang\"" "$WORK/follow.html"; then
    echo "  FAIL  $label — $url landed on a page that is not $lang"
    FAILURES=$((FAILURES + 1))
    return
  fi
  echo "  ok    $label — $url → 301 → $target (200, $lang, 1 hop)"
}

# Public routes in their canonical form, read from the generated map (which is
# itself generated from src/seo/publicPaths.ts).
ROUTES_FILE="$WORK/public-routes.txt"
sed -n 's/^    "\([^|]*\)|en" "\([^"]*\)";/\1 \2/p' "$MAP_FILE" > "$ROUTES_FILE"
if [ ! -s "$ROUTES_FILE" ]; then
  echo "[verify-nginx] the generated map lists no public route" >&2
  exit 1
fi

echo "[verify-nginx] config=$NGINX_CONF image=$IMAGE port=$PORT"
echo "— German (default) is the bare path"
request "/pricing" 200 '<title data-prerender-head="true">Website-Monitoring: einfache Preise | Presence</title>' "pricing DE"
request "/impressum" 200 '<html lang="de"' "impressum DE"
expect_redirect "/pricing?lang=de" "/pricing" "pricing DE via ?lang=de → 301"
expect_redirect "/?lang=de" "/" "home DE via ?lang=de → 301"

echo "— English lives at /en (its own canonical URL)"
request "/en/pricing" 200 '<html lang="en"' "pricing EN lang"
request "/en/pricing" 200 '<title data-prerender-head="true">Simple Website Monitoring Pricing | Presence</title>' "pricing EN title"
request "/en/pricing" 200 "$BUILD_ORIGIN/en/pricing" "pricing EN canonical"
request "/en/impressum" 200 '<title data-prerender-head="true">Imprint | Presence</title>' "impressum EN title"
request "/en" 200 '<html lang="en"' "home EN"
request "/en/blog" 200 '<html lang="en"' "blog listing EN"

# L'ancienne forme ?lang= n'est plus une URL : c'est une redirection 301 vers
# l'URL canonique. Aucune boucle : un seul saut, puis 200 dans la langue servie.
echo "— ?lang=en is a 301 to /en/... (all public routes)"
while read -r route target; do
  expect_redirect "${route}?lang=en" "$target" "$route EN"
done < "$ROUTES_FILE"

echo "— Following the redirect: exactly one hop, 200, declared language"
while read -r route target; do
  expect_follow "${route}?lang=en" "$target" en "$route EN"
done < "$ROUTES_FILE"
expect_follow "/?lang=de" "/" de "home DE"

echo "— Every parameter except lang survives the redirect, in order"
expect_redirect "/pricing?lang=en&utm_source=newsletter&utm_medium=email&utm_campaign=launch" \
  "/en/pricing?utm_source=newsletter&utm_medium=email&utm_campaign=launch" "UTM after lang"
expect_redirect "/pricing?utm_source=newsletter&lang=en&utm_medium=email" \
  "/en/pricing?utm_source=newsletter&utm_medium=email" "UTM around lang"
expect_redirect "/pricing?utm_source=newsletter&lang=en" \
  "/en/pricing?utm_source=newsletter" "UTM before lang"
expect_redirect "/pricing?lang=en" "/en/pricing" "lang alone keeps no query"
expect_redirect "/pricing?lang=de&a=1&b=2" "/pricing?a=1&b=2" "params after lang (DE)"
expect_follow "/pricing?lang=en&utm_source=newsletter&utm_medium=email" \
  "/en/pricing?utm_source=newsletter&utm_medium=email" en "UTM end-to-end"

# `map` compare ses clés sans tenir compte de la casse : `?lang=EN` redirige
# déjà, et son UTM doit survivre comme les autres.
expect_redirect "/pricing?lang=EN" "/en/pricing" "?lang=EN (map casse-insensible)"
expect_redirect "/pricing?lang=EN&utm_source=x" "/en/pricing?utm_source=x" "?lang=EN + UTM"

echo "— Forms outside the map are unchanged (no redirect, German page)"
expect_no_redirect "/pricing?lang=en+" 200 '<html lang="de"' "?lang=en+ (encodage)"
expect_no_redirect "/pricing/?lang=en" 200 '<html lang="de"' "trailing slash + ?lang=en"

echo "— The five noindex screens never redirect"
for route in /login /register /forgot-password /reset-password /onboarding; do
  expect_no_redirect "$route?lang=en" 200 '<html lang="en"' "$route EN shell"
  expect_no_redirect "$route?lang=de" 200 '<html lang="de"' "$route DE"
done
expect_no_redirect "/login?lang=en" 200 '<meta name="robots" content="noindex,nofollow"' "login EN stays noindex"

echo "— The variant folder is internal, unknown URLs stay 404"
request "/_i18n/pricing/index.html" 404 "Seite nicht gefunden" "variant folder not addressable"
request "/_i18n/index.html" 404 "Seite nicht gefunden" "variant home not addressable"
request "/definitely-not-a-page?lang=en" 404 "Seite nicht gefunden" "unknown URL is a real 404"
request "/definitely-not-a-page" 404 "Seite nicht gefunden" "unknown URL is a real 404 (DE)"
request "/en/definitely-not-a-page" 404 "Seite nicht gefunden" "unknown /en URL is a real 404"

echo "— Non-HTML assets and client-rendered routes keep working"
request "/sitemap.xml?lang=en" 200 "<loc>$BUILD_ORIGIN/pricing</loc>" "sitemap unaffected by ?lang=en"
request "/sitemap.xml" 200 "<loc>$BUILD_ORIGIN/en/pricing</loc>" "sitemap lists the English URL"
request "/robots.txt" 200 "Disallow: /app/" "robots.txt"
request "/app/dashboard?lang=en" 200 '<html lang="de"' "SPA shell for /app/ (unchanged)"

echo "— The analytics prefix stays closed except tracker + collect API"
request "/stats/" 404 "Seite nicht gefunden" "/stats/ stays closed"
request "/stats/dashboard" 404 "Seite nicht gefunden" "/stats/<anything> stays closed"
# Dans ce conteneur jetable, l'hôte `umami` n'existe pas : nginx répond 502
# dès que le bloc proxy est atteint. Un 404 signifierait que /stats/ est
# retombé sur le fourre-tout fermé, donc que le bloc proxy ne matche pas.
# Le 200 réel est vérifié contre la pile vivante (étape 7 du brouillon).
STATS_CODE="$(http_code "/stats/script.js")"
if [ "$STATS_CODE" = "404" ]; then
  echo "  FAIL  /stats/script.js answered 404 — the proxy block is not reachable"
  FAILURES=$((FAILURES + 1))
elif [ "$STATS_CODE" = "502" ]; then
  echo "  ok    /stats/script.js reaches the proxy (502: no umami host in this container)"
else
  echo "  ok    /stats/script.js reaches the proxy ($STATS_CODE)"
fi

# L'injection décidée au build est vérifiée par check-seo-build (qui lit la
# même variable). Ici, le vrai nginx sert le dist tel quel : on contrôle la
# forme et l'unicité, pas la décision elle-même — un build activé doit livrer
# exactement une balise bien formée, un build désactivé aucune.
echo "— Tracker injection is well-formed and never duplicated"
curl -sk "https://127.0.0.1:$PORT/" -o "$WORK/home-analytics.html"
TRACKER_COUNT="$( { grep -oF '/stats/script.js' "$WORK/home-analytics.html" || true; } | wc -l | tr -d ' ')"
if [ "$TRACKER_COUNT" -gt 1 ]; then
  echo "  FAIL  the home page references the tracker $TRACKER_COUNT times"
  FAILURES=$((FAILURES + 1))
elif [ "$TRACKER_COUNT" -eq 1 ] && ! grep -qE '<script defer src="/stats/script\.js" data-website-id="[0-9a-f-]{36}"></script>' "$WORK/home-analytics.html"; then
  echo "  FAIL  the tracker tag is malformed"
  FAILURES=$((FAILURES + 1))
elif grep -qF '<!-- presence:analytics -->' "$WORK/home-analytics.html"; then
  echo "  FAIL  the raw analytics marker was served"
  FAILURES=$((FAILURES + 1))
elif [ "$TRACKER_COUNT" -eq 1 ]; then
  echo "  ok    exactly one well-formed tracker tag (enabled build)"
else
  echo "  ok    no tracker tag (analytics disabled in this build)"
fi

echo "— Security headers still applied by the real config"
HEADERS="$(curl -skI "https://127.0.0.1:$PORT/pricing")"
for header in "Strict-Transport-Security" "X-Frame-Options: DENY" "X-Content-Type-Options: nosniff"; do
  if printf '%s' "$HEADERS" | grep -qi -- "$header"; then
    echo "  ok    header $header"
  else
    echo "  FAIL  header $header missing"
    FAILURES=$((FAILURES + 1))
  fi
done

if [ "$FAILURES" -eq 0 ]; then
  echo "✅ nginx.conf serves every advertised language variant (real nginx, real config)."
  exit 0
fi
echo "❌ $FAILURES nginx check(s) failed." >&2
exit 1
