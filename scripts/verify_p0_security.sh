#!/usr/bin/env bash
# Vérification P0-03 (IDOR /convert/) et P0-04 (lecture anonyme /status/).
#
# Exécute les scénarios sur la pile réellement déployée (port 80 → nginx → web)
# et échoue si une seule assertion est fausse.
#
# Usage: bash scripts/verify_p0_security.sh
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API="${API:-http://localhost/api/v1}"
WEB="${WEB:-saas_web_application_digitale_presenz-web-1}"
TMP="$(mktemp -d)"
JAR_GUEST="$TMP/guest.jar"      # navigateur du visiteur (scans invités)
JAR_OTHER="$TMP/other.jar"      # navigateur différent (attaquant)
FAILURES=0

pass() { echo "  PASS  $1"; }
fail() { echo "  FAIL  $1"; FAILURES=$((FAILURES + 1)); }
check() { # check <actual> <expected> <label>
  if [ "$1" = "$2" ]; then pass "$3 (HTTP $1)"; else fail "$3 — attendu $2, obtenu $1"; fi
}

echo "==> Fixtures (utilisateurs A/B + scan privé de A)"
docker exec -i "$WEB" python manage.py shell <<'PY'
from django.contrib.auth import get_user_model
from websites.models import Website
from scans.models import Scan

U = get_user_model()
for email in ("idor_a@example.com", "idor_b@example.com"):
    u, _ = U.objects.get_or_create(email=email)
    u.set_password("IdorTest!2026")
    u.is_email_verified = True
    u.save()

a = U.objects.get(email="idor_a@example.com")
w, _ = Website.objects.get_or_create(owner=a, domain="private-a.example.com", defaults={"is_guest": False})
scan = Scan.objects.create(
    website=w, status="completed", trigger="manual", scan_type="health",
    health_score=77, is_guest=False,
)
print("PRIVATE_SCAN_ID=%d" % scan.id)
PY

PRIVATE_SCAN_ID="$(docker exec -i "$WEB" python manage.py shell -c "
from scans.models import Scan
print(Scan.objects.filter(website__domain='private-a.example.com').order_by('-id').values_list('id', flat=True).first())
" | tail -1 | tr -d '\r')"
echo "    scan privé de A = $PRIVATE_SCAN_ID"

ACCESS_A="$(curl -s -X POST "$API/auth/login/" -H 'Content-Type: application/json' \
  -d '{"email":"idor_a@example.com","password":"IdorTest!2026"}' | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access",""))')"
ACCESS_B="$(curl -s -X POST "$API/auth/login/" -H 'Content-Type: application/json' \
  -d '{"email":"idor_b@example.com","password":"IdorTest!2026"}' | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access",""))')"
[ -n "$ACCESS_A" ] && [ -n "$ACCESS_B" ] || { echo "ABORT: authentification impossible"; exit 2; }

echo
echo "==> P0-04 : lecture des scans sur /public/scan/<id>/status/"
code=$(curl -s -o /dev/null -w '%{http_code}' "$API/public/scan/$PRIVATE_SCAN_ID/status/")
check "$code" 404 "Anonyme → scan privé d'un compte"

code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $ACCESS_A" \
  "$API/public/scan/$PRIVATE_SCAN_ID/status/")
check "$code" 200 "Propriétaire (A) → son propre scan privé"

code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $ACCESS_B" \
  "$API/public/scan/$PRIVATE_SCAN_ID/status/")
check "$code" 404 "Autre compte (B) → scan privé de A"

echo
echo "==> Scan invité créé par le visiteur (session du navigateur 1)"
GUEST_JSON=$(curl -s -c "$JAR_GUEST" -b "$JAR_GUEST" -X POST "$API/public/scan/" \
  -H 'Content-Type: application/json' -d '{"domain":"idor-guest.example.com"}')
GUEST_SCAN_ID=$(echo "$GUEST_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("scan_id",""))')
echo "    scan invité = $GUEST_SCAN_ID"

code=$(curl -s -o /dev/null -w '%{http_code}' "$API/public/scan/$GUEST_SCAN_ID/status/")
check "$code" 200 "Anonyme → scan invité (public par conception)"

echo
echo "==> P0-03 : /public/scan/<id>/convert/"
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR_OTHER" \
  -H "Authorization: Bearer $ACCESS_B" -X POST "$API/public/scan/$GUEST_SCAN_ID/convert/")
check "$code" 404 "Compte B, navigateur étranger → vol de scan invité bloqué"

code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR_OTHER" \
  -H "Authorization: Bearer $ACCESS_B" -X POST "$API/public/scan/$PRIVATE_SCAN_ID/convert/")
check "$code" 404 "Compte B → conversion d'un scan d'un autre compte bloquée"

echo
echo "==> P0 : /public/scan/<id>/email/ (exfiltration de rapport)"
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR_OTHER" -X POST "$API/public/scan/$PRIVATE_SCAN_ID/email/" \
  -H 'Content-Type: application/json' -d '{"email":"attacker@example.com"}')
check "$code" 404 "Anonyme → email du rapport d'un scan privé bloqué"

echo
echo "==> Parcours légitime : le visiteur récupère son propre scan invité"
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR_GUEST" \
  -H "Authorization: Bearer $ACCESS_B" -X POST "$API/public/scan/$GUEST_SCAN_ID/convert/")
check "$code" 200 "Visiteur (même session) → conversion de son scan invité"

echo
echo "==> Nettoyage des fixtures"
docker exec -i "$WEB" python manage.py shell <<'PY' >/dev/null
from django.contrib.auth import get_user_model
from scans.models import Scan
from websites.models import Website

U = get_user_model()
Scan.objects.filter(website__domain__in=["private-a.example.com", "idor-guest.example.com"]).delete()
Website.objects.filter(domain__in=["private-a.example.com", "idor-guest.example.com"]).delete()
U.objects.filter(email__in=["idor_a@example.com", "idor_b@example.com"]).delete()
PY
rm -rf "$TMP"

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "RÉSULTAT: toutes les assertions de sécurité P0-03 / P0-04 sont vérifiées."
  exit 0
fi
echo "RÉSULTAT: $FAILURES assertion(s) en échec."
exit 1
