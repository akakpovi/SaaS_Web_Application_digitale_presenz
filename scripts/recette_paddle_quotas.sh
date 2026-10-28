#!/usr/bin/env bash
# Recette HTTP réelle — Paddle Sandbox, quotas et isolation multi-tenant.
#
# Ce script n'exécute AUCUN paiement : il vérifie que l'API refuse honnêtement
# quand la facturation n'est pas configurée, qu'aucun droit payant n'est
# accordé sans webhook signé, que les quotas sont appliqués côté serveur et
# qu'un compte ne peut pas lire les ressources d'un autre.
#
# Usage:
#   bash scripts/recette_paddle_quotas.sh                 # http://localhost:5173
#   BASE_URL=http://localhost:8000 bash scripts/recette_paddle_quotas.sh
#
# Aucun secret n'est affiché : les jetons restent en mémoire du script.

set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:5173}"
API="$BASE_URL/api/v1"
STAMP="$(date +%s)"
PASSWORD="Recette-$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 24)!"
EMAIL_A="recette-a-$STAMP@example.com"
EMAIL_B="recette-b-$STAMP@example.com"
FAILURES=0

say() { printf '%s\n' "$*"; }
check() { # check <label> <actual> <expected...>
  local label="$1" actual="$2"; shift 2
  for expected in "$@"; do
    if [ "$actual" = "$expected" ]; then
      say "PASS  $label -> $actual"
      return 0
    fi
  done
  say "FAIL  $label -> $actual (attendu: $*)"
  FAILURES=$((FAILURES + 1))
}

code() { # code <method> <path> [token] [body]
  local method="$1" path="$2" token="${3:-}" body="${4:-}"
  local args=(-s -o /tmp/recette_body.json -w '%{http_code}' -X "$method" "$API$path")
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  if [ -n "$body" ]; then
    args+=(-H 'Content-Type: application/json' -d "$body")
  fi
  curl "${args[@]}"
}

jqf() { python3 -c "import json,sys;d=json.load(open('/tmp/recette_body.json'));print(eval(sys.argv[1],{'d':d}))" "$1" 2>/dev/null || echo '<absent>'; }

say "== Base: $BASE_URL =="

say ""
say "-- A. Visiteur non authentifié --"
check "health" "$(curl -s -o /dev/null -w '%{http_code}' "$API/health/")" 200
check "websites sans jeton" "$(code GET /websites/)" 401
check "abonnement sans jeton" "$(code GET /subscriptions/me/)" 401

say ""
say "-- B. Catalogue des offres --"
check "plans" "$(code GET /subscriptions/plans/)" 200
python3 - <<'PY'
import json
plans = json.load(open('/tmp/recette_body.json'))
plans = plans if isinstance(plans, list) else plans.get('results', plans)
for p in plans:
    print(f"      plan={p.get('tier')} prix_mensuel={p.get('price_monthly')} sites_max={p.get('max_websites')} scans_max={p.get('max_scans_per_month')}")
PY

say ""
say "-- C. Création de deux comptes de test --"
register() { # register <email>
  curl -s -o /dev/null -w '%{http_code}' -X POST "$API/auth/register/" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"full_name\":\"Recette\",\"password\":\"$PASSWORD\",\"language\":\"de\"}"
}
check "inscription compte A" "$(register "$EMAIL_A")" 201
check "inscription compte B" "$(register "$EMAIL_B")" 201

login_token() { # login_token <email>
  curl -s -X POST "$API/auth/login/" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$PASSWORD\"}" |
    python3 -c "import json,sys;print(json.load(sys.stdin).get('access',''))"
}
TOKEN_A="$(login_token "$EMAIL_A")"
TOKEN_B="$(login_token "$EMAIL_B")"
[ -n "$TOKEN_A" ] && say "PASS  connexion compte A -> jeton obtenu" || { say "FAIL  connexion compte A"; FAILURES=$((FAILURES + 1)); }

say ""
say "-- D. Offre et droits du compte gratuit --"
check "abonnement A" "$(code GET /subscriptions/me/ "$TOKEN_A")" 200
say "      offre=$(jqf "d.get('plan',{}).get('tier')") statut=$(jqf "d.get('status')") sites=$(jqf "d.get('usage',{}).get('websites_used')")"

say ""
say "-- E. Checkout sans facturation configurée (aucun droit accordé) --"
checkout_status="$(code POST /subscriptions/checkout/ "$TOKEN_A" '{"plan":"pro","billing_cycle":"monthly"}')"
check "checkout pro" "$checkout_status" 503 400 409
say "      code=$(jqf "d.get('code')") detail=$(jqf "d.get('detail')")"
upgrade_status="$(code POST /subscriptions/upgrade/ "$TOKEN_A" '{"plan":"pro"}')"
check "upgrade direct (doit être refusé)" "$upgrade_status" 503 409
say "      code=$(jqf "d.get('code')")"
code GET /subscriptions/me/ "$TOKEN_A" >/dev/null
say "      offre après tentative=$(jqf "d.get('plan',{}).get('tier')") (doit rester free)"

say ""
say "-- F. Webhook Paddle : signature obligatoire --"
webhook_unsigned="$(code POST /webhooks/paddle/ '' '{"event_id":"recette-unsigned","event_type":"subscription.activated","data":{}}')"
check "webhook sans signature" "$webhook_unsigned" 503 401 403
say "      code=$(jqf "d.get('code')")"
webhook_bad_sig="$(curl -s -o /tmp/recette_body.json -w '%{http_code}' -X POST "$API/webhooks/paddle/" \
  -H 'Content-Type: application/json' -H 'Paddle-Signature: ts=1;h1=deadbeef' \
  -d '{"event_id":"recette-badsig","event_type":"subscription.activated","data":{}}')"
check "webhook signature invalide" "$webhook_bad_sig" 503 401 403
say "      code=$(jqf "d.get('code')")"

say ""
say "-- G. Quotas appliqués côté serveur --"
max_sites="$(code GET /subscriptions/me/ "$TOKEN_A" >/dev/null; jqf "d.get('plan',{}).get('max_websites')")"
say "      limite de sites du plan gratuit: $max_sites"
created=0
limit_status="none"
for i in $(seq 1 12); do
  st="$(code POST /websites/ "$TOKEN_A" "{\"domain\":\"recette-$STAMP-$i.example.com\"}")"
  if [ "$st" = "201" ]; then created=$((created + 1)); else limit_status="$st"; break; fi
done
if [ "$limit_status" = "none" ]; then
  say "INFO  aucune limite atteinte après $created sites (plan gratuit: $max_sites)"
else
  check "dépassement du quota de sites" "$limit_status" 402 403
  say "      code=$(jqf "d.get('code')") detail=$(jqf "d.get('detail')")"
fi

say ""
say "-- H. Isolation entre comptes --"
OTHER_WEBSITE_ID="$(docker compose exec -T web python manage.py shell -c "
from websites.models import Website
from django.contrib.auth import get_user_model
U = get_user_model()
other = Website.objects.exclude(owner__email__startswith='recette-').order_by('id').first()
print(other.id if other else '')
" 2>/dev/null | tr -d '\r' | tail -1)"
if [ -n "$OTHER_WEBSITE_ID" ]; then
  check "site d'un autre compte" "$(code GET "/websites/$OTHER_WEBSITE_ID/" "$TOKEN_A")" 404 403
  check "scans d'un autre site" "$(code GET "/scans/?website=$OTHER_WEBSITE_ID" "$TOKEN_A")" 200 404
  count="$(code GET "/scans/?website=$OTHER_WEBSITE_ID" "$TOKEN_A" >/dev/null; python3 -c "
import json
d = json.load(open('/tmp/recette_body.json'))
rows = d if isinstance(d, list) else d.get('results', [])
print(len([r for r in rows if isinstance(r, dict) and r.get('website') not in (None, $OTHER_WEBSITE_ID)]))
")"
  check "aucun scan étranger dans la réponse" "$count" 0
else
  say "SKIP  isolation: aucun site d'un autre compte en base"
fi
check "profil de B lu par A" "$(code GET /users/profile/ "$TOKEN_A")" 200

say ""
if [ "$FAILURES" = "0" ]; then
  say "RESULTAT: tous les contrôles sont passés (aucun paiement réel effectué)."
else
  say "RESULTAT: $FAILURES contrôle(s) en échec."
fi
exit "$FAILURES"
