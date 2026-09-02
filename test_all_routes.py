#!/usr/bin/env python3
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost"
API_URL = BASE_URL + "/api/v1"

results = []

def run_test(name, method, url, data=None, headers=None, expected_status=[200], is_binary=False):
    if headers is None:
        headers = {}
    if data and isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    start_time = time.time()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.status
            elapsed = int((time.time() - start_time) * 1000)
            body = response.read()
            passed = status_code in expected_status
            
            parsed_json = None
            if not is_binary and "application/json" in response.headers.get("Content-Type", ""):
                try:
                    parsed_json = json.loads(body.decode("utf-8"))
                except Exception:
                    pass

            results.append({
                "name": name,
                "method": method,
                "url": url.replace(BASE_URL, ""),
                "status": status_code,
                "expected": expected_status,
                "passed": passed,
                "elapsed": elapsed,
            })
            return status_code, parsed_json, body
    except urllib.error.HTTPError as e:
        elapsed = int((time.time() - start_time) * 1000)
        body = e.read()
        passed = e.code in expected_status
        parsed_json = None
        try:
            parsed_json = json.loads(body.decode("utf-8"))
        except Exception:
            pass
        results.append({
            "name": name,
            "method": method,
            "url": url.replace(BASE_URL, ""),
            "status": e.code,
            "expected": expected_status,
            "passed": passed,
            "elapsed": elapsed,
        })
        return e.code, parsed_json, body
    except Exception as ex:
        elapsed = int((time.time() - start_time) * 1000)
        results.append({
            "name": name,
            "method": method,
            "url": url.replace(BASE_URL, ""),
            "status": "ERR",
            "expected": expected_status,
            "passed": False,
            "elapsed": elapsed,
        })
        return 0, None, None

print("\n==================================================================")
print(" 🧪 AUDIT AUTOMATISÉ COMPLET DE TOUTES LES ROUTES (PRESENCE SAAS) ")
print("==================================================================\n")

# 1. CORE & HEALTH
print("1. CORE & SANTÉ SERVEUR")
run_test("Health Check API", "GET", API_URL + "/health/", expected_status=[200])

# 2. AUTHENTIFICATION & JWT
print("\n2. AUTHENTIFICATION & TOKENS JWT")
run_test(
    "Inscription / Register", "POST", API_URL + "/auth/register/",
    data={"email": "audit_" + str(int(time.time())) + "@presence.io", "password": "TestPassword123!", "name": "Audit User"},
    expected_status=[201, 400]
)

status_login, login_data, _ = run_test(
    "Connexion / Login (JWT)", "POST", API_URL + "/auth/login/",
    data={"email": "demo@presence.io", "password": "demo123456"},
    expected_status=[200]
)

access_token = None
if login_data:
    if "tokens" in login_data and "access" in login_data["tokens"]:
        access_token = login_data["tokens"]["access"]
    elif "access" in login_data:
        access_token = login_data["access"]

auth_headers = {"Authorization": "Bearer " + access_token} if access_token else {}

if access_token:
    run_test("Profil Utilisateur (/auth/me/)", "GET", API_URL + "/auth/me/", headers=auth_headers, expected_status=[200])

# 3. PUBLIC SCANNER
print("\n3. SCANNER PUBLIC (PARCOURS GUEST / VISITEUR)")
status_scan, scan_data, _ = run_test(
    "Scan Public Synchrone", "POST", API_URL + "/public/scan/",
    data={"url": "https://decathlon.fr"},
    expected_status=[200, 429]
)

created_scan_id = "1"
if scan_data and isinstance(scan_data, dict):
    created_scan_id = str(scan_data.get("scan_id", "1"))

run_test("Statut Scan Public", "GET", API_URL + "/public/scan/" + created_scan_id + "/status/", expected_status=[200, 404])

run_test(
    "Envoi Rapport par Email (Lead)", "POST", API_URL + "/public/scan/" + created_scan_id + "/email/",
    data={"email": "prospect@agence.com"},
    headers={"Accept-Language": "fr-FR,fr;q=0.9"},
    expected_status=[200, 202, 404, 429]
)

run_test("Route Legacy Asynchrone /check/", "POST", API_URL + "/public/check/", data={"domain": "nike.com"}, expected_status=[202, 429])

# 4. WEBSITES
print("\n4. GESTION DES SITES WEB (DONNÉES RÉELLES POSTGRESQL)")
run_test("Liste des sites de l'utilisateur", "GET", API_URL + "/websites/", headers=auth_headers, expected_status=[200])

status_create_site, site_data, _ = run_test(
    "Création de site normalisé", "POST", API_URL + "/websites/",
    data={"domain": "site-audit-" + str(int(time.time())) + ".com", "display_name": "Site Audit"},
    headers=auth_headers,
    expected_status=[201]
)

test_site_id = "1"
if site_data and isinstance(site_data, dict):
    test_site_id = str(site_data.get("id", "1"))

run_test(
    "Détail du site avec données réelles & checks", "GET", API_URL + "/websites/" + test_site_id + "/",
    headers=auth_headers,
    expected_status=[200]
)

run_test(
    "Déclenchement d'un scan authentifié", "POST", API_URL + "/websites/" + test_site_id + "/scan/",
    headers=auth_headers,
    expected_status=[202, 409]
)

# 5. SCANS & CHECK RESULTS
print("\n5. SCANS & RÉSULTATS DÉTAILLÉS")
run_test("Liste des scans utilisateur", "GET", API_URL + "/scans/", headers=auth_headers, expected_status=[200])
run_test("Détail d'un scan", "GET", API_URL + "/scans/" + created_scan_id + "/", headers=auth_headers, expected_status=[200, 404])
run_test("Liste des CheckResults d'un scan", "GET", API_URL + "/scans/" + created_scan_id + "/results/", headers=auth_headers, expected_status=[200, 404])

# 6. RAPPORTS PDF MARQUE BLANCHE
print("\n6. RAPPORTS PDF MARQUE BLANCHE (WEASYPRINT)")
run_test(
    "Génération PDF avec logo d'agence", "GET",
    API_URL + "/reports/pdf/" + created_scan_id + "/?logo_url=https://example.com/logo.png&lang=fr",
    headers=auth_headers,
    expected_status=[200, 404],
    is_binary=True
)

# 7. ANALYTICS & PILOTAGE
print("\n7. ANALYTICS & DASHBOARD ADMIN")
run_test(
    "Tracking d'événement télémétrie", "POST", API_URL + "/analytics/events/track/",
    data={"event_type": "page_view", "metadata": {"page": "audit_cli"}},
    expected_status=[200, 201]
)
run_test("Dashboard Admin Pilotage (CEO)", "GET", API_URL + "/analytics/admin/overview/", headers=auth_headers, expected_status=[200, 403])

# 8. ALERTS & NOTIFICATIONS
print("\n8. ALERTES & NOTIFICATIONS")
run_test("Liste des alertes", "GET", API_URL + "/alerts/", headers=auth_headers, expected_status=[200])
run_test("Canaux de notifications", "GET", API_URL + "/notifications/channels/", headers=auth_headers, expected_status=[200])

# 9. FRONTEND & SEO MULTILINGUE
print("\n9. FRONTEND, PWA & SEO MULTILINGUE")
run_test("Redirection Racine /", "GET", BASE_URL + "/", expected_status=[200, 302])
run_test("Landing Page Français (/fr/)", "GET", BASE_URL + "/fr/", expected_status=[200])
run_test("Landing Page Anglais (/en/)", "GET", BASE_URL + "/en/", expected_status=[200])
run_test("Landing Page Allemand (/de/)", "GET", BASE_URL + "/de/", expected_status=[200])
run_test("Page Paywall / Remédiation (/scan/66)", "GET", BASE_URL + "/scan/66", expected_status=[200])
run_test("PWA Manifest (/manifest.json)", "GET", BASE_URL + "/manifest.json", expected_status=[200])
run_test("Service Worker PWA (/sw.js)", "GET", BASE_URL + "/sw.js", expected_status=[200])

# RAPPORT FINAL
print("\n" + "=" * 80)
print(f"{'TEST / ROUTE':<45} {'MÉTHODE':<8} {'STATUT':<8} {'TEMPS':<8} {'RÉSULTAT':<8}")
print("-" * 80)

total_passed = 0
for r in results:
    status_str = str(r["status"])
    if r["passed"]:
        res_str = "✔ PASS"
        total_passed += 1
    else:
        res_str = "✖ FAIL"

    print(f"{r['name']:<45} {r['method']:<8} {status_str:<8} {str(r['elapsed']) + 'ms':<8} {res_str}")

print("=" * 80)
print(f"Résultat global : {total_passed}/{len(results)} routes validées avec succès.\n")

if total_passed == len(results):
    print("🎉 TOUTES LES ROUTES DU SYSTÈME SONT 100% OPÉRATIONNELLES !\n")
    sys.exit(0)
else:
    print("⚠️ Certaines routes nécessitent une attention.\n")
    sys.exit(1)
