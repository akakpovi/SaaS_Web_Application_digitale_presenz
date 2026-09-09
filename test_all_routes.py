#!/usr/bin/env python3
import json, sys, time, urllib.request, urllib.error

BASE = "http://localhost"
API = BASE + "/api/v1"
tests = []

def run(name, method, url, data=None, headers=None, ok=[200]):
    hdrs = dict(headers or {})
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=hdrs, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.status
            dt = int((time.time() - t0) * 1000)
            body = r.read()
            try:
                js = json.loads(body.decode("utf-8"))
            except Exception:
                js = None
            passed = code in ok
            tests.append((name, method, code, ok, passed, dt))
            return code, js
    except urllib.error.HTTPError as e:
        code = e.code
        dt = int((time.time() - t0) * 1000)
        body = e.read()
        try:
            js = json.loads(body.decode("utf-8"))
        except Exception:
            js = None
        passed = code in ok
        tests.append((name, method, code, ok, passed, dt))
        return code, js
    except Exception as ex:
        dt = int((time.time() - t0) * 1000)
        tests.append((name, method, "ERR", ok, False, dt))
        return 0, None

print("\n" + "="*65)
print(" 🧪 AUDIT DE TOUTES LES ROUTES (PRESENCE SAAS) ")
print("="*65 + "\n")

# Core
run("Health Check API", "GET", API + "/health/", ok=[200])

# Auth
run("Inscription / Register", "POST", API + "/auth/register/", {"email": f"t_{int(time.time())}@presence.io", "password": "Password123!", "name": "User"}, ok=[201, 400])
_, lg = run("Connexion / Login (JWT)", "POST", API + "/auth/login/", {"email": "demo@presence.io", "password": "demo123456"}, ok=[200])
tok = (lg or {}).get("tokens", {}).get("access") or (lg or {}).get("access", "")
auth = {"Authorization": f"Bearer {tok}"} if tok else {}

if tok:
    run("Profil Utilisateur (/auth/me/)", "GET", API + "/auth/me/", headers=auth, ok=[200])

# Public Scan
_, sc = run("Scan Public Synchrone", "POST", API + "/public/scan/", {"url": "https://decathlon.fr"}, ok=[200, 429])
sid = str((sc or {}).get("scan_id", "1"))
run("Statut Scan Public", "GET", API + f"/public/scan/{sid}/status/", ok=[200, 404])
run("Envoi Rapport par Email", "POST", API + f"/public/scan/{sid}/email/", {"email": "client@agence.com"}, headers={"Accept-Language": "fr-FR"}, ok=[200, 202, 404, 429])
run("Route Legacy /check/", "POST", API + "/public/check/", {"domain": "nike.com"}, ok=[202, 429])

# Websites
run("Liste des sites", "GET", API + "/websites/", headers=auth, ok=[200])
_, st = run("Création de site", "POST", API + "/websites/", {"domain": f"site-{int(time.time())}.com", "display_name": "Audit Site"}, headers=auth, ok=[201, 400])
site_id = str((st or {}).get("id", "1"))
run("Détail du site & checks", "GET", API + f"/websites/{site_id}/", headers=auth, ok=[200])
run("Déclenchement scan auth", "POST", API + f"/websites/{site_id}/scan/", headers=auth, ok=[202, 409])

# Scans & Reports
run("Liste des scans", "GET", API + "/scans/", headers=auth, ok=[200])
run("Détail d'un scan", "GET", API + f"/scans/{sid}/", headers=auth, ok=[200, 404])
run("CheckResults détaillés", "GET", API + f"/scans/{sid}/results/", headers=auth, ok=[200, 404])
run("Rapport PDF Marque Blanche", "GET", API + f"/reports/pdf/{sid}/?lang=fr", headers=auth, ok=[200, 404])

# Analytics & Admin
run("Tracking événement", "POST", API + "/analytics/events/track/", {"event_type": "page_view", "metadata": {"page": "cli"}}, ok=[200, 201])
run("Dashboard Admin (CEO)", "GET", API + "/analytics/admin/overview/", headers=auth, ok=[200, 403])

# Alerts
run("Liste des alertes", "GET", API + "/alerts/", headers=auth, ok=[200])
run("Canaux notifications", "GET", API + "/notifications/channels/", headers=auth, ok=[200])

# Frontend Nginx & SEO
run("Redirection Racine /", "GET", BASE + "/", ok=[200, 302])
run("Landing Page (FR)", "GET", BASE + "/fr/", ok=[200])
run("Landing Page (EN)", "GET", BASE + "/en/", ok=[200])
run("Landing Page (DE)", "GET", BASE + "/de/", ok=[200])
run("Page Scan & Paywall", "GET", BASE + "/scan/66", ok=[200])
run("PWA Manifest", "GET", BASE + "/manifest.json", ok=[200])
run("Service Worker", "GET", BASE + "/sw.js", ok=[200])

print("\n" + "="*75)
print(f"{'TEST / ROUTE':<35} {'MÉTHODE':<8} {'STATUT':<8} {'TEMPS':<8} {'RÉSULTAT':<8}")
print("-" * 75)

passed = 0
for name, meth, code, ok, ok_bool, dt in tests:
    res = "✔ PASS" if ok_bool else "✖ FAIL"
    if ok_bool: passed += 1
    print(f"{name:<35} {meth:<8} {str(code):<8} {str(dt)+'ms':<8} {res}")

print("="*75)
print(f"Résultat : {passed}/{len(tests)} routes validées avec succès.\n")
