#!/usr/bin/env bash
# Real validation of the headless WordPress blog.
#
# Checks, against the running stack (no mocks):
#   1. the public REST API is reachable through the frontend proxy;
#   2. only published articles are served, never drafts;
#   3. publishing makes an article appear in its language;
#   4. unpublishing removes it again;
#   5. translations are linked in both directions;
#   6. the WordPress admin is NOT exposed through the public origin;
#   7. data survives a controlled restart of the CMS container only.
#
# Usage: scripts/validate_wordpress_blog.sh [--keep]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE="${PRESENCE_BASE_URL:-https://localhost}"
API="$BASE/cms/wp-json/wp/v2/posts"
TEST_SLUG="presence-i18n-validation-test"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

pass=0
fail=0
ok()   { echo "  ✅ $1"; pass=$((pass + 1)); }
bad()  { echo "  ❌ $1"; fail=$((fail + 1)); }
info() { echo "  ·  $1"; }

wp() { docker compose run --rm --no-deps -T --entrypoint wp wordpress-init --allow-root --path=/var/www/html "$@" 2>/dev/null; }

# Pretty JSON query used for the assertions.
query() {
  curl -sk --max-time 20 "$API?$1"
}

count_lang() {
  query "presence_lang=$1&per_page=50&_fields=slug" |
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
}

slug_present() {
  query "presence_lang=$1&per_page=50&_fields=slug" |
    python3 -c "import json,sys; print('yes' if any(p['slug']=='$2' for p in json.load(sys.stdin)) else 'no')"
}

echo "══ 1. Public REST reachability ═══════════════════════════════"
status="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 20 "$API?per_page=1&_fields=slug")"
if [ "$status" = "200" ]; then ok "GET /cms/wp-json/wp/v2/posts → 200"; else bad "posts endpoint returned $status"; fi

echo "══ 2. Language separation ════════════════════════════════════"
de_count="$(count_lang de)"
en_count="$(count_lang en)"
info "German articles: $de_count · English articles: $en_count"
if [ "$de_count" -ge 2 ]; then ok "German articles are served"; else bad "expected at least 2 German articles, got $de_count"; fi
if [ "$en_count" -ge 6 ]; then ok "English articles are served"; else bad "expected at least 6 English articles, got $en_count"; fi

echo "══ 3. Draft isolation ════════════════════════════════════════"
existing="$(wp post list --post_type=post --name="$TEST_SLUG" --post_status=any --field=ID --format=ids | head -n1)"
[ -n "$existing" ] && wp post delete "$existing" --force >/dev/null

draft_id="$(wp post create --post_type=post --post_status=draft \
  --post_title="Validation draft (must stay private)" \
  --post_name="$TEST_SLUG" --porcelain)"
wp post term set "$draft_id" language de >/dev/null
info "draft created: #$draft_id"
if [ "$(slug_present de "$TEST_SLUG")" = "no" ]; then
  ok "a draft is not exposed by the public API"
else
  bad "draft leaked into the public API"
fi

echo "══ 4. Publish / unpublish cycle ══════════════════════════════"
wp post update "$draft_id" --post_status=publish >/dev/null
if [ "$(slug_present de "$TEST_SLUG")" = "yes" ]; then
  ok "publishing makes the article visible in German"
else
  bad "published article is missing from the German list"
fi
if [ "$(slug_present en "$TEST_SLUG")" = "no" ]; then
  ok "a German article does not leak into the English list"
else
  bad "German article appeared in the English list"
fi

wp post update "$draft_id" --post_status=draft >/dev/null
if [ "$(slug_present de "$TEST_SLUG")" = "no" ]; then
  ok "unpublishing removes the article from the public list"
else
  bad "unpublished article is still listed"
fi
wp post update "$draft_id" --post_status=publish >/dev/null

echo "══ 5. Translation links ══════════════════════════════════════"
links="$(curl -sk --max-time 20 "$API?presence_lang=de&per_page=50&_fields=slug,presence_translations" |
  python3 -c "
import json,sys
data=json.load(sys.stdin)
for post in data:
    if post['slug']=='de-was-ist-website-monitoring':
        print(post.get('presence_translations',[{}])[0].get('slug',''))
")"
if [ "$links" = "what-is-website-monitoring" ]; then
  ok "German article links to its English original ($links)"
else
  bad "translation link missing on the German article (got '$links')"
fi

links_en="$(curl -sk --max-time 20 "$API?presence_lang=en&per_page=50&_fields=slug,presence_translations" |
  python3 -c "
import json,sys
data=json.load(sys.stdin)
for post in data:
    if post['slug']=='what-is-website-monitoring':
        print(','.join(t.get('slug','') for t in post.get('presence_translations',[])))
")"
if echo "$links_en" | grep -q "de-was-ist-website-monitoring"; then
  ok "English original links back to the German translation"
else
  bad "English original has no link to its German translation (got '$links_en')"
fi

echo "══ 6. Admin surface isolation ════════════════════════════════"
admin_status="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 20 "$BASE/cms/wp-login.php")"
if [ "$admin_status" = "404" ]; then
  ok "wp-login.php is not reachable through the public origin (404)"
else
  bad "wp-login.php answered $admin_status — the CMS admin must not be proxied"
fi
loopback="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8081/wp-login.php || true)"
info "loopback admin on 127.0.0.1:8081 → ${loopback:-unreachable} (expected 200, local only)"

echo "══ 7. Persistence across a CMS restart ═══════════════════════"
if [ "$KEEP" = "1" ]; then
  info "restart skipped (--keep)"
else
  docker compose restart wordpress >/dev/null 2>&1
  for _ in $(seq 1 30); do
    code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "$API?per_page=1&_fields=slug" || true)"
    [ "$code" = "200" ] && break
    sleep 2
  done
  if [ "$(slug_present de "$TEST_SLUG")" = "yes" ] && [ "$(count_lang de)" -ge 3 ]; then
    ok "articles and the test post survived the restart (volumes preserved)"
  else
    bad "content disappeared after the restart"
  fi
fi

echo "══ 8. Cleanup ════════════════════════════════════════════════"
if [ "$KEEP" = "1" ]; then
  info "test post #$draft_id kept for manual inspection (slug: $TEST_SLUG)"
else
  wp post delete "$draft_id" --force >/dev/null
  ok "validation post removed (test data only)"
fi

echo
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
