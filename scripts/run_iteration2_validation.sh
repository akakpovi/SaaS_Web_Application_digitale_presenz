#!/usr/bin/env bash
# =============================================================================
# Itération 2 — validation P0-06 (production/TLS) + P0-07 (SSRF)
#
# 1. génère le certificat TLS auto-signé local (nginx/ssl)
# 2. reconstruit et redémarre la pile canonique
# 3. exécute `manage.py check --deploy` (zéro warning security.W*)
# 4. relance l'intégralité des tests backend
# 5. smoke-test SSRF (hosts internes refusés)
#
# Usage: bash scripts/run_iteration2_validation.sh
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> 1/5  Certificat TLS local"
bash scripts/setup_local_tls.sh

echo
echo "==> 2/5  Rebuild + démarrage de la pile canonique"
docker compose build
docker compose up -d

echo "    Attente de la santé des services (max 150s)..."
for i in $(seq 1 30); do
  sleep 5
  state="$(docker compose ps --format '{{.Service}} {{.Health}}')"
  if echo "$state" | grep -q 'frontend healthy' && echo "$state" | grep -q 'web healthy'; then
    echo "$state"
    echo "    Pile saine."
    break
  fi
  echo "    [$i] attente..."
  if [ "$i" -eq 30 ]; then
    echo "ERREUR: la pile n'est pas saine dans le délai imparti."
    docker compose ps
    exit 1
  fi
done

echo
echo "==> 3/5  manage.py check --deploy (doit être sans security.W*)"
echo "--- contrôle ciblé security ---"
docker compose exec -T web python manage.py check --deploy --tag security

echo "--- scan complet : recherche d'avertissements security.W* ---"
full="$(docker compose exec -T web python manage.py check --deploy 2>&1 || true)"
if echo "$full" | grep -q 'security\.W'; then
  echo "$full" | grep 'security\.W'
  echo "ERREUR: des avertissements de sécurité subsistent."
  exit 1
fi
echo "OK : 0 avertissement security.W* (les autres warnings sont des avertissements de schéma drf_spectacular, hors périmètre sécurité)."

echo
echo "==> 4/5  Suite de tests backend complète"
bash scripts/run_backend_tests.sh

echo
echo "==> 5/5  Smoke-test SSRF (hosts internes / IP privées refusés)"
docker compose exec -T web python manage.py shell <<'PY'
from core.security import DomainValidationError, resolve_public_ip, safe_webhook_request, validate_domain_for_scan
from advanced_security.scanners.port_scanner import scan_sensitive_ports

assertions = []

def blocked(label, fn):
    try:
        fn()
    except DomainValidationError:
        assertions.append((True, label))
    except Exception as exc:  # pragma: no cover - diagnostic
        assertions.append((False, f"{label} (exception inattendue: {exc!r})"))
    else:
        assertions.append((False, f"{label} (AUCUN blocage)"))

# IP littérales / internes
blocked("validate_domain_for_scan('127.0.0.1')", lambda: validate_domain_for_scan("127.0.0.1"))
blocked("validate_domain_for_scan('foo.internal')", lambda: validate_domain_for_scan("foo.internal"))
blocked("resolve_public_ip('127.0.0.1')", lambda: resolve_public_ip("127.0.0.1"))
blocked("resolve_public_ip('169.254.169.254')", lambda: resolve_public_ip("169.254.169.254"))
blocked("safe_webhook_request('http://127.0.0.1/hook')", lambda: safe_webhook_request("http://127.0.0.1/hook", json_payload={}))
blocked("safe_webhook_request('http://metadata.google.internal/')", lambda: safe_webhook_request("http://metadata.google.internal/", json_payload={}))

# Le port_scanner refuse les cibles internes
ports = scan_sensitive_ports("127.0.0.1")
assertions.append((ports == [], f"scan_sensitive_ports('127.0.0.1') == [] (obtenu: {ports})"))
ports = scan_sensitive_ports("localhost")
assertions.append((ports == [], f"scan_sensitive_ports('localhost') == [] (obtenu: {ports})"))

failed = [label for ok, label in assertions if not ok]
for ok, label in assertions:
    print(("  PASS  " if ok else "  FAIL  ") + label)
if failed:
    raise SystemExit(f"{len(failed)} assertion(s) SSRF en échec")
print(f"OK : {len(assertions)} assertions SSRF vérifiées.")
PY

echo
echo "RÉSULTAT: itération 2 validée (TLS + production + SSRF + tests)."
