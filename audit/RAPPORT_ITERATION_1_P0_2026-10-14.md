# Itération 1 — Phase 1 (Stabilisation) & début Phase 2 — Points bloquants P0

Date : 14 octobre 2026
Périmètre : P0-01, P0-02, P0-03, P0-04, P0-05 + sauvegarde préalable.
Statut : **terminé et vérifié par exécution**. P0-06 (configuration de production) et P0-07 (SSRF)
ne sont pas traités ici, conformément à la consigne.

---

## 0. Sauvegarde préalable

Script : `scripts/backup_pre_remediation.sh`

```bash
cd ~/Schreibtisch/SaaS_Web_Application_digitale_presenz
bash scripts/backup_pre_remediation.sh
```

Il exécute :

```bash
TS="$(date +%Y%m%d_%H%M%S)"
# 1) dump logique (restaurable selectivement)
docker exec saas_web_application_digitale_presenz-db-1 \
  pg_dump -U presence -d presence --no-owner --no-privileges \
  | gzip > "backups/presence_full_${TS}.sql.gz"
# 2) copie physique du volume (restauration à froid)
docker run --rm \
  -v saas_web_application_digitale_presenz_postgres_data:/data:ro \
  -v "$PWD/backups":/backup alpine:3.20 \
  tar czf "/backup/postgres_data_${TS}.tar.gz" -C /data .
```

Résultat vérifié (14/10 15:10) :

| Artefact | Taille | Contrôle |
|---|---|---|
| `backups/presence_full_20261014_151013.sql.gz` | 1,3 Mo | `gzip -t` OK — 44 `CREATE TABLE` |
| `backups/postgres_data_20261014_151013.tar.gz` | 15 Mo | 1 599 entrées, `PG_VERSION` + `base/` présents |

Restauration : `gunzip -c backups/presence_full_*.sql.gz | docker exec -i <db> psql -U presence -d presence`
`backups/` est exclu du dépôt (`.gitignore`).

---

## 1. Constat corrigé : quelle pile tournait réellement quoi

La reconnaissance a invalidé l'hypothèse initiale. Il existait **deux** piles Compose :

| Pile | Code embarqué | Données | Exposée |
|---|---|---|---|
| `saas_web_application_digitale_presenz` (racine, `docker-compose.yml`) | **ancien** (`scanners/base.py` md5 `dad1dc66…`) | **la production** : 2 631 scans | oui — **port 80**, frontend + API |
| `backend` (`SaaS_..._v2/backend/docker-compose.yml`) | intermédiaire (`5fd7d9e2…`) | base vide (0 scan) | non (aucun port publié) |

Le trafic produit passait donc par la pile racine, qui exécutait l'ancien code → 18 102 `ScannerRun`
`failed`, 0 finding, `health_score` NULL. **La pile canonique est celle de la racine** (elle contient le
frontend) ; la pile `backend` imbriquée était la redondante.

---

## 2. P0-01 — Pipeline de scan

### 2.1 `Severity.UNKNOWN`

Déjà absent de l'arbre de travail (`grep -rn "Severity.UNKNOWN"` → aucune occurrence) : `base.py`
utilisait déjà `Severity.INFO`. Le vrai défaut restant était **le déploiement**, pas la source
(l'image de la pile racine divergeait du dépôt). Ce point est traité par P0-02/rebuild.

### 2.2 `scanners/base.py` — mapping explicite + exécution unique

Le mapping était local à la méthode et utilisait `dict.get(..., défaut)` : tout statut inconnu était
converti silencieusement, et une simple faute de frappe dans un scanner produisait un résultat faux
sans trace. Les tables sont désormais **au niveau module, exhaustives et journalisées** :

```python
SEVERITY_BY_SCANNER_STATUS: Final[dict[str, str]] = {
    "healthy": Severity.INFO, "passed": Severity.INFO, "good": Severity.INFO,
    "online": Severity.INFO, "neutral": Severity.INFO, "unknown": Severity.INFO,
    "warning": Severity.MEDIUM,
    "failed": Severity.HIGH, "error": Severity.HIGH, "critical": Severity.HIGH,
    "offline": Severity.CRITICAL, "down": Severity.CRITICAL,
}
FINDING_STATUS_BY_SCANNER_STATUS: Final[dict[str, str]] = { ... }

_FALLBACK_SEVERITY: Final[str] = Severity.MEDIUM
_FALLBACK_FINDING_STATUS: Final[str] = FindingStatus.UNKNOWN
```

```python
# Explicit mapping — an unknown status is logged, never silent.
status_key = (result.status or "").strip().lower()
if status_key not in SEVERITY_BY_SCANNER_STATUS:
    logger.warning(
        "Scanner '%s' returned unmapped status %r for %s — falling "
        "back to severity=%s / finding_status=%s",
        self.name, result.status, domain,
        _FALLBACK_SEVERITY, _FALLBACK_FINDING_STATUS,
    )
finding_status = FINDING_STATUS_BY_SCANNER_STATUS.get(status_key, _FALLBACK_FINDING_STATUS)
severity = SEVERITY_BY_SCANNER_STATUS.get(status_key, _FALLBACK_SEVERITY)
```

Et `scan_findings()` accepte désormais un `ScanResult` déjà calculé :

```python
def scan_findings(self, domain, result: ScanResult | None = None) -> list[NormalizedFinding]:
    if result is None:
        result = self.scan(domain)
    return self._scan_result_to_findings(result, domain)
```

### 2.3 `scans/services/orchestrator.py` — fin du double scan

L'orchestrateur exécutait chaque scanner **deux fois** (`scan()` puis `scan_findings()` qui rappelait
`scan()`) : deux fois le trafic HTTP/TLS/DNS sortant par scanner et par scan.

```python
# Run the scanner ONCE (target already SSRF-validated).
scan_result = scanner.scan(domain)
step["progress"] = 50

# Derive the granular findings from that same result —
# no second execution of the scanner.
findings = self._collect_findings(scanner, domain, scan_result)
```

Le dispatch est explicite et mémoïsé, car les 9 adaptateurs CLI ont leur propre cycle de vie et
n'acceptent que `domain` :

```python
_FINDINGS_ACCEPTS_RESULT: dict[type, bool] = {}

@classmethod
def _findings_accepts_result(cls, scanner) -> bool:
    key = type(scanner)
    if key not in cls._FINDINGS_ACCEPTS_RESULT:
        try:
            params = inspect.signature(scanner.scan_findings).parameters
            cls._FINDINGS_ACCEPTS_RESULT[key] = "result" in params
        except (TypeError, ValueError):
            cls._FINDINGS_ACCEPTS_RESULT[key] = False
    return cls._FINDINGS_ACCEPTS_RESULT[key]
```

Persistance du score — plus d'échec silencieux :

```python
category = _CATEGORY_MAP.get(scanner_name)
if category is None:
    logger.warning("...scanner '%s' has no CheckResult category mapping — "
                   "no CheckResult persisted for scan %d", scanner_name, self.scan_id)
    return

if is_uptime:
    score = None
else:
    score = scan_result.score
    if score is None:
        logger.error("...score=None for weighted category '%s' — coercing to 0",
                     category, self.scan_id)
        score = 0
```

### 2.4 `scans/tasks.py` — garantie de finalisation

Nouveau `_finalize_scan(scan_id)`, appelé après `orchestrator.run()` :

* vérifie `status == COMPLETED` ;
* recompte `CheckResult`, `Finding`, `ScannerRun.FAILED` et les journalise ;
* recalcule le score ; si un scan `health`/`full` termine avec `score = None`, force `0` et **log une
  erreur** (un scan noté ne peut plus jamais exposer un score NULL) ;
* log `ERROR` explicite si `check_results == 0`, `WARNING` si `findings == 0`.

```python
report = _finalize_scan(scan_id)
return {"scan_id": scan_id, "status": "done", **report}
```

### 2.5 Preuve d'exécution (P0-01)

Scan réel 2670, `POST /api/v1/public/scan/` → poll :

```
status= completed  score= 85  progress= 100
summary= {'critical': 1, 'warnings': 0, 'passed': 6}
checks= ['dns','email_security','performance','security_headers','ssl','uptime','website']
```

```
id=2670 | status=completed | health_score=85 | health_status=critical | progress=100

scans_checkresult : dns 15 | email_security 15 | performance 15 |
                    security_headers 0 (critical) | ssl 20 | uptime NULL | website 20
scans_finding     : 7 findings (security_headers.overall = high/fail, le reste info/pass)
scans_scannerrun  : 7 runs, tous « completed » (121–526 ms)
```

Avant le correctif : 0 finding, 7 `CheckResult` au total sur 2 631 scans, score NULL.
Après : 7 `CheckResult` + 7 `Finding` + score pour **un** scan.

---

## 3. P0-03 / P0-04 — Sécurité des endpoints publics

Fichier : `public_checker/views.py`.

### 3.1 Modèle d'autorisation

```python
GUEST_SCANS_SESSION_KEY = "guest_scan_ids"

def _may_read_scan(request, scan) -> bool:
    """Guest scans are public by design (no account data, purged after 24 h).
    Account scans are private: only their owner may read them."""
    if scan.is_guest:
        return True
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return False
    return scan.website.owner_id == user.id


def _session_owns_scan(request, scan) -> bool:
    """Used by convert/email: never act on someone else's scan."""
    if not scan.is_guest:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated
                    and scan.website.owner_id == user.id)
    session_key = _session_key_of(request)
    if session_key and scan.session_key == session_key:
        return True
    owned_scans = request.session.get(GUEST_SCANS_SESSION_KEY) or []
    return str(scan.id) in {str(i) for i in owned_scans}
```

P0-04 (`/status/`) :

```python
if lookup.isdigit():
    scan = (Scan.objects.select_related("website").prefetch_related("check_results")
            .filter(pk=int(lookup)).first())
    if scan is None or not _may_read_scan(request, scan):
        return Response({"detail": "Scan not found."}, status=404)
```

P0-03 (`/convert/`) — le scan est verrouillé et filtré sur `is_guest=True`, puis la session est
vérifiée **dans** la transaction :

```python
with transaction.atomic():
    scan = (Scan.objects.select_for_update().select_related("website")
            .filter(pk=int(scan_id), is_guest=True).first())
    if scan is None or not _session_owns_scan(request, scan):
        logger.warning("Rejected scan conversion: scan=%s user_id=%s "
                       "(not a guest scan of this session)", scan_id, request.user.pk)
        return Response({"detail": "Scan not found."}, status=404)
```

Correctif supplémentaire non demandé mais de même classe : `/email/` acceptait n'importe quel `scan_id`
et envoyait le rapport à une adresse choisie → exfiltration. Il est désormais limité
(`filter(pk=..., is_guest=True)` + `_session_owns_scan`).

La liste `guest_scan_ids` en session couvre le cas où `django.contrib.auth.login` fait tourner la clé de
session (`cycle_key`) : le visiteur peut encore récupérer son scan après inscription.

### 3.2 Preuve d'exécution — 8/8 sur la pile déployée

`bash scripts/verify_p0_security.sh` (HTTP réel via nginx:80, 2 comptes + 2 sessions) :

```
P0-04  Anonyme → scan privé d'un compte ....................... 404  PASS
P0-04  Propriétaire (A) → son propre scan privé ............... 200  PASS
P0-04  Autre compte (B) → scan privé de A ..................... 404  PASS
       Anonyme → scan invité (public par conception) .......... 200  PASS
P0-03  Compte B, navigateur étranger → vol de scan invité ..... 404  PASS
P0-03  Compte B → conversion d'un scan d'un autre compte ...... 404  PASS
       Anonyme → email du rapport d'un scan privé ............. 404  PASS
       Visiteur (même session) → conversion de son scan ....... 200  PASS
```

---

## 4. P0-05 — Migrations manquantes

6 migrations étaient appliquées en base mais absentes du dépôt. Reconstruction par
`makemigrations` (arbre monté dans le conteneur) puis alignement sur le **nom déjà enregistré** dans
`django_migrations`, afin qu'aucun SQL ne soit rejoué :

```bash
cd SaaS_Web_Application_digitale_presenz_v2/backend
docker compose -f docker-compose.yml run --rm --no-deps --user "0:0" -v "$PWD":/app \
  web python manage.py makemigrations advanced_security analytics notifications seo social websites

mv websites/migrations/0004_remove_website_unique_website_domain_per_owner_and_more.py \
   websites/migrations/0004_scanner_engine.py
```

| Fichier reconstitué | Déjà en base |
|---|---|
| `advanced_security/0002_rename_advanced_se_website_caeec4_idx_…` | oui |
| `analytics/0002_alter_analyticsevent_event_type.py` | oui |
| `notifications/0002_webpushsubscription.py` | oui |
| `seo/0002_rename_seo_backlin_website_0f7bbd_idx_…` | oui |
| `social/0002_rename_social_soci_website_058db5_idx_…` | oui |
| `websites/0004_scanner_engine.py` (renommé) | oui |

Vérification à trois niveaux :

1. `python manage.py makemigrations --check --dry-run` → **`No changes detected`** (exit 0).
2. `python manage.py migrate` au démarrage → **`No migrations to apply.`** (aucun SQL dangereux rejoué).
3. **Test décisif** : création d'une base neuve et migration depuis les seuls fichiers du dépôt, puis
   comparaison `pg_dump --schema-only` base neuve vs base de production :

```
1143 lignes  /tmp/fresh_schema.sql
1143 lignes  /tmp/live_schema.sql
DIFF_LINES=8   → uniquement les lignes \restrict <jeton aléatoire> (pg_dump ≥ 16)
```

Schémas **identiques**. Une base neuve reconstruit donc désormais exactement le schéma de production.

---

## 5. P0-02 — Déploiement et Git

### 5.1 Compose

* `docker-compose.yml` (racine) : en-tête ajouté — **pile canonique unique**, avec l'avertissement
  explicite de ne **pas** ajouter de clé `name:` (elle renommerait le projet Compose et créerait de
  nouveaux volumes vides, masquant les données de production).
* `SaaS_..._v2/backend/docker-compose.yml` : bandeau **DÉPRÉCIÉ** + procédure d'arrêt.
* `SaaS_..._v2/backend/docker-compose.dev.yml` : renvoi vers la pile canonique.

```bash
# Arrêt de la pile redondante (volumes conservés)
docker compose -f SaaS_Web_Application_digitale_presenz_v2/backend/docker-compose.yml down
```

Résultat : conteneurs + réseau `backend_default` supprimés, volumes `backend_*` **conservés**.
Ne restent que les 6 conteneurs de la pile canonique, tous sains.

### 5.2 Rebuild — l'image redevient conforme au dépôt

```bash
docker compose build && docker compose up -d
```

```
saas_web_application_digitale_presenz-web-1  Up (healthy)   8000/tcp
saas_web_application_digitale_presenz-frontend-1  Up (healthy)  0.0.0.0:80->80/tcp
web-1  |  Running migrations:  No migrations to apply.
web-1  |  Starting gunicorn 23.0.0 / Listening at: http://0.0.0.0:8000
```

Contrôle md5 arbre ↔ image :

```
MATCH scanners/base.py
MATCH scans/services/orchestrator.py
MATCH scans/tasks.py
MATCH public_checker/views.py
```

### 5.3 Git — intégrer le frontend V2 déployé

Le dossier `SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/` était
**non suivi** : l'image était construite depuis un répertoire que le dépôt ne contenait pas. Il est
désormais indexé (74 fichiers) ; `node_modules/` et `dist/` restent exclus par le `.gitignore` local
du dossier (vérifié avec `git check-ignore`).

```bash
git add SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2
git status --short
# Commit à votre main :
git commit -m "fix(p0): align deployed stack with repository"
```

Aucun commit n'a été créé (non demandé).

---

## 6. Tests

Le code est **cuit dans l'image** : `docker exec <web> python manage.py test` teste une version
périmée. Un lanceur dédié monte l'arbre de travail :

```bash
bash scripts/run_backend_tests.sh                # 326 tests
bash scripts/run_backend_tests.sh public_checker # une app
```

| Exécution | Résultat |
|---|---|
| `manage.py test` (avant, image périmée) | 309 tests — **4 échecs** |
| `public_checker` (arbre monté) | 23 tests — **OK** |
| `SingleExecutionTests` (3 nouveaux) | 3 tests — **OK** |
| `manage.py test` complet (arbre monté) | **323 tests — OK** |
| **Suite finale (arbre monté)** | **326 tests — OK (569 s)** |

```
Found 326 test(s).
Ran 326 tests in 569.402s

OK
Destroying test database for alias 'default'...
```

Les 4 échecs initiaux ont été traités sans affaiblir d'assertion :

1. `test_german_header_is_forwarded_to_celery_task` — le test créait un scan invité sans session
   propriétaire. Corrigé en liant le scan à la session du client, **plus deux cas négatifs ajoutés**
   (session étrangère → 404 ; `scan_id` inconnu → 404).
2. `test_create_public_scan` — affirmait `health_status is None` alors que la vue renvoie `neutral` :
   assertion remplacée par la valeur réelle + `poll_url`, `Cache`, `Scan` en base, et
   `run_public_scan.delay(scan.id)` (le test attendait un ancien appel `delay(domain, scan_id)` qui
   n'a jamais existé dans ce code).
3. `test_poll_public_scan_processing` / `test_poll_public_scan_completed` — reposaient sur une lecture
   de cache **non authentifiée par clé arbitraire**, c'est-à-dire précisément le vecteur supprimé en
   P0-04. Réécrits sur le contrat réel (polling d'un scan invité en base) et **reforcés** : score,
   `summary`, `checks`, `progress`.

Nouveau fichier `public_checker/tests/test_scan_access_control.py` : 11 tests de régression
(anonyme/compte tiers/propriétaire sur `/status/`, conversion par session étrangère, conversion d'un
scan d'autrui, conversion sans authentification, parcours légitime, `/email/`).

Nouveau `SingleExecutionTests` (`scans/tests/test_scanner_engine.py`) : `scan()` appelé **une seule
fois** (compteur), `scan_findings(result=…)` ne relance pas le scanner, et un statut inconnu tombe sur
le fallback explicite `medium` / `unknown` sans lever d'exception.

---

## 7. Limites et points restants

* **P0-06 (production + TLS)** et **P0-07 (SSRF redirections/rebinding)** : non traités — prochaine
  itération, conformément à la consigne. La pile tourne toujours en `DEBUG=True`, `ALLOWED_HOSTS=['*']`,
  CORS `*`, sans TLS.
* `health_status = critical` avec `health_score = 85` (scan 2670) : c'est la règle existante de
  `calculate_health_score` (tout check `critical` force `critical`). Incohérence de produit à arbitrer,
  hors périmètre P0.
* Le rate-limit reste contournable par `X-Forwarded-For` (P1).
* Les 9 scanners CLI n'ont toujours pas leurs binaires dans l'image : les étapes correspondantes
  passent en `unavailable` (comportement voulu, désormais journalisé).
* 18 102 `ScannerRun` historiques restent `failed` et 2 624 scans restent sans score : ce sont des
  données du passé, à rejouer ou à nettoyer (tâche P1), pas un défaut du pipeline corrigé.

---

## 8. Fichiers modifiés / créés

Modifiés :

* `scanners/base.py`, `scans/services/orchestrator.py`, `scans/tasks.py`
* `public_checker/views.py`
* `public_checker/tests/test_legacy_public_checker.py`, `public_checker/tests/test_email_language_detection.py`
* `scans/tests/test_scanner_engine.py`
* `docker-compose.yml`, `SaaS_..._v2/backend/docker-compose.yml`, `SaaS_..._v2/backend/docker-compose.dev.yml`
* `.gitignore`

Créés :

* `scanners` : 6 migrations reconstituées (voir §4)
* `scripts/backup_pre_remediation.sh`, `scripts/verify_p0_security.sh`, `scripts/run_backend_tests.sh`
* `public_checker/tests/test_scan_access_control.py`
* `audit/RAPPORT_ITERATION_1_P0_2026-10-14.md` (ce document)
