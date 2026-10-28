#!/usr/bin/env bash
# Recette HTTP réelle — surveillance continue, alertes, notifications et AKA IA.
#
# Vérifie le comportement par défaut (surveillance désactivée), l'activation
# explicite, la pause, les préférences d'alerte, le canal de notification créé
# par défaut et ce que répond l'assistant IA lorsqu'il est désactivé.
#
# Usage: bash scripts/recette_monitoring_ai.sh
# Aucun scan lourd n'est lancé : seule la planification est observée.

set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:5173}"
API="$BASE_URL/api/v1"
STAMP="$(date +%s)"
PASSWORD="Recette-$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 24)!"
EMAIL="recette-mon-$STAMP@example.com"
DOMAIN="recette-mon-$STAMP.example.com"
FAILURES=0

say() { printf '%s\n' "$*"; }
check() {
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
  local args=(-s -o /tmp/recette_mon_body.json -w '%{http_code}' -X "$method" "$API$path")
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  if [ -n "$body" ]; then
    args+=(-H 'Content-Type: application/json' -d "$body")
  fi
  curl "${args[@]}"
}

jqf() { python3 -c "import json,sys;d=json.load(open('/tmp/recette_mon_body.json'));print(eval(sys.argv[1],{'d':d}))" "$1" 2>/dev/null || echo '<absent>'; }

say "== Base: $BASE_URL =="

say ""
say "-- A. Compte de test --"
check "inscription" "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/auth/register/" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"full_name\":\"Recette Mon\",\"password\":\"$PASSWORD\",\"language\":\"de\"}")" 201
TOKEN="$(curl -s -X POST "$API/auth/login/" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | python3 -c "import json,sys;print(json.load(sys.stdin).get('access',''))")"
[ -n "$TOKEN" ] && say "PASS  connexion -> jeton obtenu" || { say "FAIL  connexion"; FAILURES=$((FAILURES + 1)); }

check "création du site" "$(code POST /websites/ "$TOKEN" "{\"domain\":\"$DOMAIN\"}")" 201
SITE_ID="$(jqf "d.get('id')")"
say "      site #$SITE_ID ($DOMAIN)"

say ""
say "-- B. Surveillance désactivée par défaut (opt-in) --"
check "lecture config" "$(code GET "/monitoring/websites/$SITE_ID/" "$TOKEN")" 200
say "      enabled=$(jqf "d.get('enabled')") interval=$(jqf "d.get('interval')") scan_type=$(jqf "d.get('scan_type')") next_scan_at=$(jqf "d.get('next_scan_at')")"
check "aucun scan planifié sans activation" "$(jqf "str(d.get('next_scan_at'))")" None

say ""
say "-- C. Activation explicite --"
check "activation" "$(code PATCH "/monitoring/websites/$SITE_ID/" "$TOKEN" '{"enabled":true,"interval":"24h","scan_type":"health"}')" 200
say "      enabled=$(jqf "d.get('enabled')") next_scan_at=$(jqf "d.get('next_scan_at')")"
python3 -c "
import json
d = json.load(open('/tmp/recette_mon_body.json'))
print('PASS  premier contrôle planifié immédiatement' if d.get('next_scan_at') else 'FAIL  next_scan_at vide après activation')
"

say ""
say "-- D. Pause explicite --"
check "pause" "$(code PATCH "/monitoring/websites/$SITE_ID/" "$TOKEN" '{"enabled":false}')" 200
check "planification effacée" "$(jqf "str(d.get('next_scan_at'))")" None

say ""
say "-- E. Alertes et notifications --"
check "préférences d'alerte" "$(code GET /alerts/preferences/ "$TOKEN")" 200
check "règles d'alerte" "$(code GET /alerts/rules/ "$TOKEN")" 200
check "liste des alertes" "$(code GET /alerts/ "$TOKEN")" 200
say "      alertes visibles=$(jqf "len(d) if isinstance(d,list) else len(d.get('results',[]))")"
check "canaux de notification" "$(code GET /notifications/channels/ "$TOKEN")" 200
say "      canaux=$(jqf "[c.get('channel_type') for c in (d if isinstance(d,list) else d.get('results',[]))]")"

say ""
say "-- F. AKA IA --"
# Le chat IA n'est pas appelé ici : l'endpoint interactif n'est pas protégé par
# AI_ADVISOR_ENABLED (seule l'analyse automatique l'est) et un appel réel
# consommerait des crédits de la passerelle AKA IA.
check "recommandations sans scan_id (contrat d'API)" "$(code GET /advisory/recommendations/ "$TOKEN")" 400
say "      detail=$(jqf "d.get('detail') or d.get('code')")"
FOREIGN_SCAN="$(docker compose exec -T web python manage.py shell -c "
from scans.models import Scan
s = Scan.objects.exclude(website__owner__email__startswith='recette-').order_by('id').first()
print(s.id if s else '')
" 2>/dev/null | tr -d '\r' | tail -1)"
if [ -n "$FOREIGN_SCAN" ]; then
  check "recommandations d'un scan étranger" "$(code GET "/advisory/recommendations/?scan_id=$FOREIGN_SCAN" "$TOKEN")" 403 404
else
  say "SKIP  recommandations: aucun scan étranger en base"
fi
check "chat IA sur une organisation inconnue" "$(code POST /organizations/00000000-0000-0000-0000-000000000000/ai-advisor/chat/ "$TOKEN" '{"message":"Explique mes résultats"}')" 403 404
say "      code=$(jqf "d.get('code') or d.get('detail')")"

say ""
say "-- G. Isolation --"
OTHER_ID="$(docker compose exec -T web python manage.py shell -c "
from websites.models import Website
w = Website.objects.exclude(owner__email__startswith='recette-').order_by('id').first()
print(w.id if w else '')
" 2>/dev/null | tr -d '\r' | tail -1)"
if [ -n "$OTHER_ID" ]; then
  check "surveillance d'un site étranger" "$(code GET "/monitoring/websites/$OTHER_ID/" "$TOKEN")" 404 403
else
  say "SKIP  isolation: aucun site étranger en base"
fi

say ""
if [ "$FAILURES" = "0" ]; then
  say "RESULTAT: tous les contrôles sont passés."
else
  say "RESULTAT: $FAILURES contrôle(s) en échec."
fi
exit "$FAILURES"
