# MISSION — Migration du backend Presence vers une architecture Scanner Engine

Tu travailles sur le backend Django/DRF du projet **Presence**, une plateforme SaaS B2B permettant aux petites entreprises de surveiller et améliorer la santé technique de leurs sites web.

## 1. OBJECTIF GLOBAL

Faire évoluer le backend existant vers une architecture **Scanner Engine modulaire, asynchrone et extensible**, capable d'utiliser progressivement les outils suivants :

- Nmap
- Nmap NSE
- Nikto
- OWASP ZAP
- Gobuster
- Feroxbuster
- testssl.sh
- Nuclei
- WhatWeb
- dnsrecon
- curl
- ApacheBench ou équivalent pour les mesures de performance

IMPORTANT :

Ne pas transformer Django en un simple wrapper de commandes shell.

Le backend doit avoir une architecture propre :

```text
Django REST API
      ↓
Scan Orchestrator
      ↓
Celery / Redis
      ↓
Scanner Engine
      ↓
Individual Scanners
      ↓
Parsers
      ↓
Normalized Findings
      ↓
CheckResults
      ↓
Health Score Engine
      ↓
Recommendations
```

Le système doit être conçu pour pouvoir ajouter ultérieurement d'autres scanners sans modifier le cœur de l'application.

---

# 2. CONTEXTE EXISTANT À PRÉSERVER

Le backend possède déjà notamment :

```text
accounts/
websites/
scans/
monitoring/
```

Il existe déjà :

- Django REST Framework
- PostgreSQL
- Redis
- Celery
- JWT authentication
- Website ownership
- Scan model
- CheckResult
- Monitoring
- scheduled scans
- health score
- OpenAPI / drf-spectacular
- Docker Compose

NE PAS réécrire inutilement les fonctionnalités existantes.

Avant toute modification :

1. inspecter le repository ;
2. lire `backend/backend-architecture.md` ;
3. inspecter les modèles actuels ;
4. inspecter les serializers ;
5. inspecter les views ;
6. inspecter les URLs ;
7. inspecter les Celery tasks ;
8. inspecter les tests existants ;
9. inspecter la logique actuelle de `public_checker` ;
10. comprendre exactement le fonctionnement actuel de `monitoring`.

Créer d'abord un court rapport :

```text
CURRENT ARCHITECTURE
CURRENT MODELS
CURRENT SCAN FLOW
CURRENT MONITORING FLOW
CURRENT CHECK SYSTEM
FILES TO MODIFY
FILES TO CREATE
RISKS
```

Puis implémenter.

---

# 3. RÈGLE CRITIQUE — SÉCURITÉ

Les outils de scan peuvent être dangereux s'ils sont exécutés directement avec des données utilisateur.

NE JAMAIS faire :

```python
os.system(user_input)
```

ou :

```python
subprocess.run(f"nmap {user_input}", shell=True)
```

Ne jamais utiliser `shell=True` pour construire des commandes à partir d'une cible utilisateur.

Utiliser uniquement des listes d'arguments :

```python
subprocess.run(
    [
        "nmap",
        "-sV",
        "--",
        hostname,
    ],
    capture_output=True,
    text=True,
    timeout=120,
    check=False,
)
```

La cible doit être validée avant exécution.

---

# 4. PROTECTION SSRF — OBLIGATOIRE

Presence est un SaaS où l'utilisateur peut enregistrer une URL.

Il faut empêcher les scans vers :

```text
localhost
127.0.0.0/8
0.0.0.0/8
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
169.254.0.0/16
::1
fc00::/7
fe80::/10
```

ainsi que les endpoints de metadata cloud connus.

Créer un service :

```text
scanners/security/target_validator.py
```

avec une API similaire :

```python
validate_target(url)
```

Il doit :

- accepter uniquement HTTP/HTTPS pour les scanners web ;
- normaliser hostname ;
- résoudre DNS ;
- vérifier les IP résolues ;
- refuser les IP privées ;
- refuser loopback ;
- refuser link-local ;
- refuser multicast ;
- refuser metadata endpoints ;
- gérer IPv4 et IPv6 ;
- empêcher les contournements basiques de validation ;
- vérifier la cible au moment du scan, pas seulement au moment de l'enregistrement.

Prévoir également une protection contre le DNS rebinding.

---

# 5. NOUVELLE ARCHITECTURE DES SCANNERS

Créer :

```text
scanners/
├── __init__.py
├── base.py
├── registry.py
├── exceptions.py
├── security/
│   └── target_validator.py
├── executors/
│   └── command.py
├── parsers/
│   ├── __init__.py
│   ├── nmap.py
│   ├── nikto.py
│   ├── nuclei.py
│   ├── whatweb.py
│   ├── testssl.py
│   └── zap.py
└── implementations/
    ├── nmap.py
    ├── nikto.py
    ├── nuclei.py
    ├── whatweb.py
    ├── testssl.py
    ├── dnsrecon.py
    ├── gobuster.py
    ├── feroxbuster.py
    ├── zap.py
    └── performance.py
```

---

# 6. BASE SCANNER

Créer une abstraction commune.

Exemple conceptuel :

```python
class BaseScanner:

    name = None
    version = None
    scanner_type = None

    def validate_target(self, target):
        ...

    def build_command(self, target, options=None):
        ...

    def execute(self, target, options=None):
        ...

    def parse(self, output):
        ...

    def normalize(self, parsed_result):
        ...
```

Ne pas rendre cette classe inutilement complexe.

Chaque scanner doit respecter le même contrat.

---

# 7. SCANNER REGISTRY

Créer un registry central :

```text
ScannerRegistry
```

Exemple :

```python
ScannerRegistry.register(NmapScanner)
ScannerRegistry.register(NiktoScanner)
ScannerRegistry.register(NucleiScanner)
...
```

Puis :

```python
scanner = ScannerRegistry.get("nmap")
```

Le code métier ne doit jamais faire :

```python
if scanner == "nmap":
    ...
elif scanner == "nikto":
    ...
```

Le registry doit être extensible.

---

# 8. COMMAND EXECUTOR

Créer un composant sécurisé :

```text
scanners/executors/command.py
```

Responsabilités :

- subprocess ;
- timeout ;
- capture stdout ;
- capture stderr ;
- exit code ;
- durée d'exécution ;
- limite de sortie ;
- logging ;
- gestion des exceptions.

Retourner un objet normalisé :

```python
CommandResult(
    exit_code=0,
    stdout="...",
    stderr="...",
    duration_ms=1234,
)
```

Ne jamais laisser un scanner appeler `subprocess` directement si cela peut être centralisé dans cet executor.

---

# 9. MODÈLE ScannerRun

Créer un modèle permettant de suivre chaque outil individuellement.

```python
class ScannerRun(models.Model):

    scan = models.ForeignKey(
        Scan,
        on_delete=models.CASCADE,
        related_name="scanner_runs",
    )

    scanner = models.CharField(max_length=50)

    status = models.CharField(max_length=20)

    started_at = models.DateTimeField(null=True)

    finished_at = models.DateTimeField(null=True)

    duration_ms = models.PositiveIntegerField(null=True)

    exit_code = models.IntegerField(null=True)

    error_message = models.TextField(blank=True)

    raw_output = models.TextField(blank=True)

    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
```

Statuts :

```text
PENDING
RUNNING
COMPLETED
FAILED
TIMEOUT
CANCELLED
```

Ajouter les index nécessaires.

---

# 10. MODÈLE Finding

Créer un modèle normalisé indépendant du scanner.

```python
class Finding(models.Model):

    scanner_run = models.ForeignKey(
        ScannerRun,
        on_delete=models.CASCADE,
        related_name="findings",
    )

    category = models.CharField(max_length=50)

    check_code = models.CharField(max_length=100)

    title = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    severity = models.CharField(max_length=20)

    status = models.CharField(max_length=20)

    evidence = models.JSONField(default=dict)

    detected_value = models.JSONField(null=True, blank=True)

    expected_value = models.JSONField(null=True, blank=True)

    recommendation = models.TextField(blank=True)

    reference_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
```

Sévérités :

```text
INFO
LOW
MEDIUM
HIGH
CRITICAL
```

Statuts :

```text
PASS
FAIL
WARNING
NOT_APPLICABLE
UNKNOWN
```

---

# 11. ÉVOLUTION DU MODÈLE Scan

Conserver les champs existants compatibles.

Ajouter :

```text
progress
current_step
steps
scan_type
error_message
```

`progress` :

```text
0 → 100
```

`current_step` :

```text
dns
ssl
headers
email
performance
nmap
nikto
nuclei
...
```

`scan_type` :

```text
HEALTH
SECURITY
FULL
```

Ajouter éventuellement :

```text
queued_at
started_at
completed_at
failed_at
```

---

# 12. STRUCTURE DE `steps`

Utiliser temporairement un JSONField pour le feed temps réel.

Exemple :

```json
[
  {
    "key": "dns",
    "label": "Analyse DNS",
    "status": "done",
    "detail": "DNS resolution successful",
    "duration_ms": 342
  },
  {
    "key": "ssl",
    "label": "Analyse SSL/TLS",
    "status": "running",
    "detail": "Checking TLS configuration...",
    "duration_ms": null
  },
  {
    "key": "headers",
    "label": "Analyse des headers",
    "status": "pending",
    "detail": null,
    "duration_ms": null
  }
]
```

Statuts :

```text
pending
running
done
error
skipped
```

IMPORTANT :

Ce JSON est destiné au **feed temps réel**.

Les résultats persistants et analytiques doivent rester dans :

```text
ScannerRun
Finding
CheckResult
```

Ne pas mettre toutes les données métier dans `steps`.

---

# 13. SCAN ORCHESTRATOR

Créer :

```text
scans/services/orchestrator.py
```

Responsabilité :

- sélectionner les scanners ;
- ordonner les étapes ;
- lancer les scanners ;
- mettre à jour le progrès ;
- gérer les erreurs ;
- créer les ScannerRun ;
- créer les Findings ;
- déclencher le Score Engine.

API conceptuelle :

```python
ScanOrchestrator(scan).run()
```

---

# 14. HEALTH SCAN

Le Health Scan doit être rapide et déterministe.

Scanners/checkers initiaux :

```text
HTTP availability
HTTPS
HTTP → HTTPS
DNS
SSL/TLS
Security Headers
Email Security
Performance
WhatWeb
```

Il doit produire les catégories :

```text
Website
SSL
DNS
Email Security
Security Headers
Performance
```

---

# 15. SECURITY SCAN

Le Security Scan utilise :

```text
Nmap
Nmap NSE
Nikto
Nuclei
Gobuster
Feroxbuster
testssl.sh
WhatWeb
```

OWASP ZAP doit être traité comme un scanner lourd/asynchrone.

---

# 16. FULL SCAN

Le Full Scan combine :

```text
Health Scan
+
Security Scan
+
DAST
```

Mais éviter de lancer tous les outils simultanément sans contrôle.

Prévoir des limites de concurrence.

---

# 17. PREMIÈRES IMPLÉMENTATIONS

Implémenter réellement dans cette phase :

### 1. HTTP checker

Utiliser un client HTTP sécurisé.

Mesurer :

```text
status code
redirects
response time
content type
TLS availability
```

### 2. DNS checker

Utiliser un resolver DNS approprié.

Vérifier :

```text
A
AAAA
CNAME
MX
NS
DNSSEC
```

### 3. SSL checker

Utiliser OpenSSL / testssl.sh lorsque disponible.

Vérifier :

```text
certificate
expiration
hostname
chain
TLS versions
cipher strength
HSTS
```

### 4. Headers checker

Vérifier :

```text
HSTS
CSP
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Permissions-Policy
COOP
CORP
```

### 5. Email checker

Vérifier :

```text
MX
SPF
DMARC
DMARC policy
DKIM lorsque détectable
MTA-STS
TLS-RPT
```

### 6. Performance checker

Mesurer :

```text
DNS lookup
TCP connection
TLS handshake
TTFB
total response time
```

---

# 18. INTÉGRATION DES OUTILS EXTERNES

Créer les adapters suivants :

```text
NmapScanner
NiktoScanner
NucleiScanner
WhatWebScanner
TestSSLScanner
DnsreconScanner
GobusterScanner
FeroxbusterScanner
ZapScanner
PerformanceScanner
```

Chaque adapter doit :

1. valider la cible ;
2. construire ses arguments ;
3. exécuter l'outil ;
4. récupérer la sortie ;
5. parser la sortie ;
6. normaliser les résultats ;
7. créer les Findings.

---

# 19. FORMAT DE SORTIE NORMALISÉ

Tous les scanners doivent produire quelque chose de comparable :

```python
NormalizedFinding(
    check_code="ssl.expired",
    category="ssl",
    severity="critical",
    status="fail",
    title="SSL certificate expired",
    description="...",
    evidence={...},
    recommendation="Renew the certificate.",
)
```

Le Score Engine ne doit pas connaître les détails internes de Nmap/Nikto/Nuclei.

---

# 20. SCORE ENGINE

Créer :

```text
health/services/score_engine.py
```

Poids :

```text
Website             20
SSL/TLS             20
DNS                 15
Email Security      15
Security Headers    15
Performance         15
TOTAL              100
```

Le score doit être déterministe.

Le scanner ne calcule jamais directement le score.

Flux :

```text
Scanner
 ↓
Finding
 ↓
CheckResult
 ↓
ScoreEngine
 ↓
Category Score
 ↓
Global Score
```

---

# 21. SCORE PAR CHECK

Chaque check doit avoir :

```text
check_code
weight
severity
status
```

Exemple :

```text
ssl.certificate_valid
ssl.certificate_expiration
ssl.hostname_match
ssl.chain_valid
ssl.tls_version
ssl.weak_cipher
ssl.hsts
```

Le score doit pouvoir être recalculé sans relancer le scanner.

---

# 22. RECOMMENDATION ENGINE

Créer :

```text
health/services/recommendation_engine.py
```

Chaque Finding important doit pouvoir produire :

```text
title
impact
recommendation
priority
```

Exemple :

```text
Finding:
Missing HSTS

Priority:
HIGH

Recommendation:
Configure Strict-Transport-Security with an appropriate max-age.
```

---

# 23. CELERY

Le scan ne doit jamais bloquer une requête HTTP.

Créer des tasks :

```text
run_health_scan
run_security_scan
run_full_scan
run_scanner
```

Exemple :

```python
@shared_task
def run_health_scan(scan_id):
    ScanOrchestrator(scan_id).run()
```

Le endpoint API doit :

```text
create Scan
→ QUEUED
→ enqueue Celery task
→ return HTTP 202
```

---

# 24. ÉTAT DU SCAN

Lifecycle :

```text
PENDING
   ↓
QUEUED
   ↓
RUNNING
   ↓
COMPLETED
```

Alternative :

```text
RUNNING
   ↓
FAILED
```

ou :

```text
RUNNING
   ↓
CANCELLED
```

Le changement d'état doit être transactionnel lorsque nécessaire.

---

# 25. PROGRESSION

Pendant l'exécution :

```text
progress = 0
```

Puis :

```text
DNS       → 15%
SSL       → 30%
Headers   → 45%
Email     → 60%
Performance → 75%
Website   → 90%
Score     → 100%
```

Pour les Security Scans, calculer la progression à partir du nombre de scanners.

NE PAS hardcoder une progression incohérente.

---

# 26. LIVE SCAN FEED

Le backend doit préparer le frontend pour une interface ressemblant aux interfaces modernes de LLM lorsqu'ils "réfléchissent".

Le frontend doit pouvoir recevoir :

```json
{
  "scan_id": 123,
  "status": "running",
  "progress": 42,
  "current_step": "ssl",
  "steps": [
    {
      "key": "dns",
      "status": "done",
      "label": "Analyse DNS",
      "detail": "DNS resolution successful"
    },
    {
      "key": "ssl",
      "status": "running",
      "label": "Analyse SSL/TLS",
      "detail": "Checking certificate chain..."
    },
    {
      "key": "headers",
      "status": "pending",
      "label": "Analyse Security Headers"
    }
  ]
}
```

Ne jamais exposer de logs internes sensibles.

---

# 27. ENDPOINT ACTIVE SCAN

Ajouter :

```http
GET /api/v1/websites/{website_id}/active_scan/
```

Réponse sans scan :

```json
{
  "active": false,
  "scan": null
}
```

Avec scan :

```json
{
  "active": true,
  "scan": {
    "id": 123,
    "status": "running",
    "progress": 42,
    "current_step": "ssl",
    "steps": [...]
  }
}
```

Respecter les permissions d'ownership existantes.

Un utilisateur ne doit jamais pouvoir récupérer le scan d'un autre utilisateur.

---

# 28. SCANS FILTER

Faire évoluer :

```http
GET /api/v1/scans/
```

pour accepter :

```text
?website=<id>
?status=running
?status=queued
```

Supporter plusieurs statuts si l'architecture actuelle le permet.

Exemple :

```http
GET /api/v1/scans/?website=42&status=running
```

---

# 29. MONITORING ET PROCHAIN SCAN

Conserver :

```text
last_scan_at
next_scan_at
interval
enabled
```

Le backend doit garantir que :

```text
next_scan_at
```

est recalculé correctement lorsque :

- monitoring est activé ;
- monitoring est désactivé ;
- interval est modifié ;
- scan manuel terminé ;
- scan automatique terminé ;
- scan échoue.

---

# 30. COMPTE À REBOURS

Le backend n'a pas besoin d'envoyer un compte à rebours chaque seconde.

Le backend fournit :

```text
next_scan_at
server_now
```

Le frontend calcule :

```text
remaining = next_scan_at - client_now
```

Ajouter idéalement dans les réponses API :

```json
{
  "next_scan_at": "2026-09-09T12:30:00Z",
  "server_now": "2026-09-09T12:24:32Z"
}
```

Cela permet au frontend de corriger le décalage de l'horloge client.

---

# 31. GESTION DU SCAN AUTOMATIQUE

Si :

```text
next_scan_at <= now
```

mais que Celery n'a pas encore créé le Scan :

le frontend peut afficher :

```text
Scan imminent...
```

Le backend doit éviter de créer plusieurs scans simultanés pour le même Website.

Utiliser une protection transactionnelle / contrainte logique.

Un site ne doit pas avoir :

```text
3 RUNNING scans
```

simultanément.

---

# 32. MANUAL SCAN

Lorsqu'un utilisateur fait :

```http
POST /api/v1/websites/{id}/scan/
```

le backend doit :

1. vérifier ownership ;
2. vérifier target ;
3. vérifier qu'il n'existe pas déjà un scan actif ;
4. créer Scan ;
5. créer les étapes ;
6. mettre status = QUEUED ;
7. lancer Celery ;
8. retourner le Scan immédiatement.

Réponse :

```json
{
  "id": 123,
  "status": "queued",
  "progress": 0,
  "current_step": null,
  "steps": [...]
}
```

---

# 33. HTTP STATUS

Utiliser :

```text
201 Created
```

ou le statut déjà adopté par l'API pour la création.

Si un scan est déjà en cours :

```text
409 Conflict
```

Réponse :

```json
{
  "code": "scan_already_running",
  "scan_id": 123,
  "message": "A scan is already running for this website."
}
```

Le frontend pourra alors reprendre le feed du scan existant.

---

# 34. SERIALIZERS

Mettre à jour les serializers pour exposer :

```text
progress
current_step
steps
scan_type
scanner_runs
```

Ne pas exposer `raw_output` dans le serializer public par défaut.

Si nécessaire, créer un endpoint admin/debug séparé.

---

# 35. API SCANNER RUNS

Prévoir :

```http
GET /api/v1/scans/{scan_id}/scanner-runs/
```

Exemple :

```json
[
  {
    "scanner": "nmap",
    "status": "completed",
    "duration_ms": 2314
  },
  {
    "scanner": "nikto",
    "status": "running",
    "duration_ms": null
  }
]
```

Cela permettra plus tard d'afficher les détails avancés.

---

# 36. API FINDINGS

Prévoir :

```http
GET /api/v1/scans/{scan_id}/findings/
```

Avec filtres :

```text
?severity=critical
?category=ssl
?status=fail
```

---

# 37. OPENAPI

Mettre à jour drf-spectacular pour documenter :

```text
POST /websites/{id}/scan/
GET /websites/{id}/active_scan/
GET /scans/
GET /scans/{id}/
GET /scans/{id}/scanner-runs/
GET /scans/{id}/findings/
```

Documenter :

```text
200
201
202
400
401
403
404
409
```

selon les endpoints.

---

# 38. LOGGING

Ajouter un logging structuré.

Exemple :

```text
scan_id=123
website_id=42
scanner=nmap
status=running
```

Ne jamais logger :

- JWT ;
- mots de passe ;
- tokens ;
- secrets ;
- credentials ;
- données privées inutiles.

---

# 39. TIMEOUTS

Chaque scanner doit avoir un timeout.

Exemple conceptuel :

```text
curl          15s
DNS           10s
testssl       60s
WhatWeb       30s
Nmap          120s
Nikto         180s
Nuclei        180s
Gobuster      120s
Feroxbuster   120s
ZAP           300s+
```

Les valeurs doivent être configurables via settings/env.

Ne pas hardcoder les timeouts partout.

---

# 40. LIMITES DE RESSOURCES

Prévoir :

```text
max concurrent scans
max concurrent scanner runs
max output size
max scan duration
```

Configuration via environment variables :

```text
MAX_CONCURRENT_SCANS
MAX_SCAN_DURATION
MAX_SCANNER_OUTPUT
```

---

# 41. DOCKER

Créer une architecture permettant aux scanners externes d'être isolés.

Ne pas installer aveuglément tous les outils Kali dans le conteneur Django.

Préférer :

```text
backend container
        │
        └── Celery
              │
              └── Scanner execution layer
```

avec des images dédiées lorsque nécessaire.

Créer par exemple :

```text
docker/scanners/
├── Dockerfile.security
├── Dockerfile.network
└── Dockerfile.web
```

Les scanners doivent fonctionner sans privilèges root lorsque possible.

Ne pas utiliser :

```yaml
privileged: true
```

sauf nécessité technique documentée.

---

# 42. CONFIGURATION DES SCANNERS

Ajouter une configuration centralisée :

```python
SCANNER_CONFIG = {
    "nmap": {
        "enabled": True,
        "timeout": 120,
    },
    "nikto": {
        "enabled": True,
        "timeout": 180,
    },
    "nuclei": {
        "enabled": True,
        "timeout": 180,
    },
}
```

Permettre de désactiver un outil s'il n'est pas installé.

Le Health Scan ne doit pas planter entièrement parce qu'un scanner optionnel est absent.

---

# 43. GRACEFUL DEGRADATION

Si :

```text
nuclei unavailable
```

ne pas faire :

```text
FULL SCAN = FAILED
```

si les autres scanners fonctionnent.

Créer :

```text
scanner status = unavailable
```

et éventuellement :

```text
finding/status = UNKNOWN
```

Le système doit clairement indiquer qu'une partie du scan n'a pas été exécutée.

---

# 44. TESTS BACKEND

Ajouter des tests unitaires et d'intégration.

Minimum :

### Target validation

Tester :

```text
https://example.com
```

et refuser :

```text
http://127.0.0.1
http://localhost
http://169.254.169.254
10.x.x.x
192.168.x.x
```

### Scan lifecycle

Tester :

```text
PENDING
→ QUEUED
→ RUNNING
→ COMPLETED
```

et :

```text
RUNNING
→ FAILED
```

### Progress

Tester :

```text
0 → 25 → 50 → 75 → 100
```

### Steps

Tester :

```text
pending
→ running
→ done
```

### Active scan

Tester :

```http
GET /websites/{id}/active_scan/
```

avec :

```text
no scan
running
queued
completed
```

### Ownership

Un utilisateur A ne doit jamais voir les scans du site de l'utilisateur B.

### Duplicate scan

Deux requêtes simultanées ne doivent pas créer deux scans actifs pour le même site.

### Scanner registry

Tester :

```text
get("nmap")
get("nikto")
unknown scanner
```

### Parser

Tester chaque parser avec fixtures.

---

# 45. TESTS AVEC DE VRAIS OUTILS

Créer un environnement de test séparé.

NE PAS lancer automatiquement Nmap/Nikto/ZAP sur des domaines publics arbitraires pendant les tests.

Utiliser :

```text
local test container
```

avec une application volontairement simple.

Par exemple :

```text
test-target
```

dans Docker Compose.

Les tests d'intégration doivent scanner uniquement cette cible contrôlée.

---

# 46. MIGRATIONS

Créer les migrations Django propres.

Avant migration :

```bash
python manage.py makemigrations
```

puis :

```bash
python manage.py migrate
```

Vérifier que les anciennes données restent compatibles.

NE PAS supprimer les données historiques existantes.

---

# 47. COMPATIBILITÉ AVEC LE FRONTEND EXISTANT

Ne casser aucun endpoint existant sans nécessité.

Si un champ change :

```text
deprecated
```

préférer une transition compatible.

Les nouveaux champs peuvent être ajoutés sans supprimer immédiatement les anciens.

---

# 48. PERFORMANCE

Ne pas exécuter :

```text
Nmap + Nikto + ZAP + Nuclei + Gobuster
```

dans la requête HTTP.

Tout doit être asynchrone.

Architecture :

```text
HTTP request
    ↓
create Scan
    ↓
Celery
    ↓
Scanner
    ↓
Database
```

---

# 49. FRONTEND CONTRACT

Le backend doit fournir toutes les informations nécessaires pour construire plus tard cette UI :

```text
┌──────────────────────────────────────┐
│ 🔍 Analyse du site en cours...      │
│                                      │
│ ████████████░░░░░░░░ 58%             │
│                                      │
│ ✓ Analyse DNS                        │
│   DNS resolution successful          │
│                                      │
│ ✓ Analyse SSL/TLS                    │
│   Certificate valid                  │
│                                      │
│ ◉ Analyse Security Headers           │
│   Checking CSP...                    │
│                                      │
│ ○ Analyse Email Security             │
│                                      │
│ ○ Performance                        │
│                                      │
└──────────────────────────────────────┘
```

Le backend doit donc exposer :

```text
progress
current_step
steps
step status
step label
step detail
duration
scan status
```

---

# 50. PRÉPARATION FUTURE SSE / WEBSOCKET

Pour cette version :

```text
POLLING
```

est acceptable.

Le frontend pourra faire :

```text
GET /scans/{id}/
```

toutes les 2 secondes pendant le scan.

Mais structurer le backend de façon à pouvoir remplacer plus tard :

```text
Polling
```

par :

```text
SSE
```

ou :

```text
WebSocket / Django Channels
```

sans modifier les modèles métier.

Ne pas implémenter WebSocket dans cette phase sauf si l'infrastructure actuelle le rend trivial.

---

# 51. PRIORITÉ D'IMPLÉMENTATION

Implémenter dans cet ordre :

## Phase A — Foundation

```text
BaseScanner
ScannerRegistry
CommandExecutor
TargetValidator
ScannerRun
Finding
```

## Phase B — Scan lifecycle

```text
Scan fields
ScanOrchestrator
Celery tasks
progress
steps
```

## Phase C — Core checks

```text
HTTP
DNS
SSL
Headers
Email
Performance
```

## Phase D — External scanners

```text
Nmap
WhatWeb
testssl
Nikto
Nuclei
Gobuster
Feroxbuster
```

## Phase E — ZAP

```text
OWASP ZAP
```

comme tâche lourde séparée.

## Phase F — Score

```text
CheckResult
ScoreEngine
RecommendationEngine
```

## Phase G — API

```text
active_scan
scanner-runs
findings
filters
OpenAPI
```

## Phase H — Tests

```text
unit
integration
security
scanner fixtures
```

---

# 52. IMPORTANT — NE PAS SUR-ENGINEER

Pour cette migration, ne créer pas immédiatement :

```text
microservices
Kubernetes
Kafka
RabbitMQ supplémentaire
event sourcing
complex distributed architecture
```

Le projet est encore en phase MVP.

La bonne architecture actuelle est :

```text
Django
+
PostgreSQL
+
Redis
+
Celery
+
isolated scanner execution
```

Elle doit rester simple.

---

# 53. CRITÈRES D'ACCEPTATION

La migration est considérée comme réussie uniquement si :

### Architecture

- [ ] Scanner Engine existe
- [ ] BaseScanner existe
- [ ] Scanner Registry existe
- [ ] Command Executor sécurisé existe
- [ ] Target Validator existe
- [ ] ScannerRun existe
- [ ] Finding existe

### Scan

- [ ] Scan n'est plus un stub
- [ ] Celery exécute réellement les étapes
- [ ] progress est mis à jour
- [ ] current_step est mis à jour
- [ ] steps sont mises à jour
- [ ] CheckResult est créé
- [ ] Score est calculé

### Tools

- [ ] HTTP checker
- [ ] DNS checker
- [ ] SSL checker
- [ ] Headers checker
- [ ] Email checker
- [ ] Performance checker
- [ ] Nmap adapter
- [ ] Nikto adapter
- [ ] Nuclei adapter
- [ ] WhatWeb adapter
- [ ] testssl adapter
- [ ] dnsrecon adapter
- [ ] Gobuster adapter
- [ ] Feroxbuster adapter
- [ ] ZAP adapter

Les outils externes doivent être gérés proprement lorsqu'ils ne sont pas disponibles.

### API

- [ ] active_scan endpoint
- [ ] scan filtering
- [ ] scanner runs endpoint
- [ ] findings endpoint
- [ ] OpenAPI mis à jour

### Monitoring

- [ ] next_scan_at continue de fonctionner
- [ ] scan automatique fonctionne
- [ ] pas de scans simultanés pour le même site
- [ ] scan manuel fonctionne
- [ ] 409 si scan déjà actif

### Security

- [ ] SSRF protection
- [ ] IP private blocking
- [ ] metadata endpoint blocking
- [ ] subprocess sans shell=True
- [ ] timeout
- [ ] output limits
- [ ] concurrency limits
- [ ] scanner isolation

### Tests

- [ ] tests unitaires passent
- [ ] tests API passent
- [ ] tests ownership passent
- [ ] tests scan lifecycle passent
- [ ] tests SSRF passent
- [ ] tests parser passent
- [ ] tests existants passent

---

# 54. LIVRABLE FINAL

À la fin de l'implémentation, fournir un rapport :

```text
================================================
PRESENCE SCANNER ENGINE MIGRATION
================================================

Architecture:
...

Files created:
...

Files modified:
...

Database migrations:
...

Scanners implemented:
...

Scanners unavailable:
...

API changes:
...

Security protections:
...

Tests:
X passed
X failed

Remaining TODO:
...

How to run:
...

How to test:
...
```

Ne pas simplement dire "implementation completed".

Donner les commandes exactes permettant de vérifier :

```bash
docker compose up -d

docker compose exec backend python manage.py migrate

docker compose exec backend python manage.py check

docker compose exec backend pytest
```

et les commandes permettant de vérifier la disponibilité des scanners.

IMPORTANT :

Avant de modifier le code, inspecter réellement le repository et adapter cette architecture aux fichiers/modèles déjà présents.

Ne jamais supposer qu'un fichier ou une classe existe sans l'avoir vérifié.

Ne pas supprimer de fonctionnalités existantes.

Ne pas modifier le frontend dans cette phase sauf si une modification minimale est absolument nécessaire pour maintenir la compatibilité API.

OBJECTIF FINAL :

Transformer le backend Presence d'un système de scan actuellement stub/simple en un véritable :

```text
MODULAR SCANNER ENGINE
        +
ASYNC SCAN ORCHESTRATION
        +
NORMALIZED FINDINGS
        +
HEALTH SCORE ENGINE
        +
LIVE SCAN PROGRESS API
        +
MONITORING
```

tout en gardant l'architecture suffisamment simple pour un MVP SaaS.