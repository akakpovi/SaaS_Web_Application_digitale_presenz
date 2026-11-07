# Rapport E2E — Lot F1 : Nuclei, rebuild et retest

- **Date** : 2026-11-07
- **Périmètre** : corrections F1, rebuild des services applicatifs, retest E2E du parcours progressif sur le stack réel.
- **Statut** : **VALIDÉ — 9 critères sur 9**.
- **Cible** : `https://appchat.elomaiapp.com/` (site 38, compte QA `qa-admin@presence.local`, user_id 139).
- **Stack** : compose canonique à la racine du dépôt (`docker-compose.yml`). `backend/docker-compose.yml` n'a pas été utilisé.

---

## 1. Synthèse

| Point F1 | État |
|---|---|
| Montage Nuclei | Corrigé par une **image dédiée** `presence-nuclei:2026-11-07` avec les templates `selected/` et `presence/` embarqués. Plus aucun bind mount de templates. |
| Faux `completed` | Corrigé : `nuclei.sandbox_unavailable` et `nuclei.unavailable` portent désormais `scan_complete=False`, donc l'orchestrateur produit `PARTIAL`. |
| Permissions du répertoire de travail | Corrigé : `/var/lib/presence-scanner-work`, créé en `1777` par le one-shot `scanner-work-init`, hors de `/tmp`. |
| Rebuild | `web`, `celery-worker`, `celery-beat` reconstruits et recréés ; image Nuclei construite. |
| Retest E2E | Parcours 6 exécuté de bout en bout : palier 1 terminé, palier 2 avec **9 findings Nuclei réels** et **9 chemins Gobuster**, parcours `completed`. |

Aucun conteneur `db`, `redis`, `frontend`, `scanner-egress-guard`, `scanner-sandbox-anchor`, `mailpit`, `umami`, `wordpress` ou `wordpress-db` n'a été arrêté ou recréé.

---

## 2. Diffs appliqués

### 2.1 `backend/scanners/implementations/nuclei.py`

Deux ajouts, dans `_unavailable_outcome()` et dans la branche `except SandboxError` :

```diff
+                scan_complete=False,
+                partial_reason="unavailable",
```

```diff
+                    scan_complete=False,
+                    partial_reason="sandbox_unavailable",
```

Sans ces clés, l'orchestrateur appliquait son repli historique `scan_complete = not (timed_out or memory_exceeded)` et classait le scan `COMPLETED`, ce qui propageait `COMPLETED` au parcours.

### 2.2 Tests

`backend/scanners/tests/test_advanced_security.py` :

- assertions ajoutées à `test_sandbox_failure_is_not_treated_as_a_clean_scan` ;
- nouveau test `test_unavailable_outcome_is_explicitly_incomplete`.

Nouveau fichier `backend/scans/tests/test_sandbox_unavailable_partial.py` :

- exécute le **vrai** `NucleiScanner` avec un exécuteur qui lève `SandboxError` ;
- vérifie `Scan.status == PARTIAL`, étape `partial`, `ScannerRun.status == PARTIAL`, `metadata["scan_complete"] is False`, puis `JourneyState.PARTIAL`.

### 2.3 Image Nuclei dédiée

Nouveau fichier `backend/scanners/docker/Dockerfile.nuclei` :

```dockerfile
FROM projectdiscovery/nuclei:latest
COPY scanners/templates/selected/ /opt/scanner-templates/selected/
COPY scanners/templates/presence/ /opt/scanner-templates/presence/
COPY scanners/templates/LICENSE /opt/scanner-templates/LICENSE
```

Le contexte de build est `backend/`, d'où les chemins `scanners/...`.

### 2.4 `docker-compose.yml`

- nouveau one-shot `scanner-work-init` (`alpine:3.20`, `user: 0:0`, `install -d -m 1777 /work`) ;
- nouveau service de build `scanner-nuclei` (`profiles: ["tools"]`, image `presence-nuclei:2026-11-07`) ;
- `celery-worker` :
  - `TMPDIR` et `SCANNER_SANDBOX_SHARED_WORK_DIR` = `/var/lib/presence-scanner-work` ;
  - `SCANNER_NUCLEI_SCENARIO_TEMPLATES_PATH=""` et `SCANNER_NUCLEI_TEMPLATES_PATH=""` ;
  - `SCANNER_DOCKER_IMAGE_NUCLEI=presence-nuclei:2026-11-07` ;
  - volume `/var/lib/presence-scanner-work:/var/lib/presence-scanner-work` ;
  - `depends_on: scanner-work-init: service_completed_successfully`.

**Pourquoi un répertoire hôte et non un volume nommé** : le sandbox passe par le démon Docker de l'hôte (`/var/run/docker.sock`) et monte les répertoires de travail avec `--mount type=bind,src=…`. Un volume nommé ne serait visible que dans le worker ; le démon de l'hôte ne pourrait pas le monter. `testssl` et ZAP utilisent ce mécanisme. Le répertoire hôte, au même chemin absolu dans le worker et sur l'hôte, est la seule solution compatible sans modifier le sandbox.

**`.env` non modifié** : les valeurs ci-dessus sont des `environment` Compose, prioritaires sur `env_file`. Cela évite de toucher au fichier de secrets et rend le correctif visible dans Git.

---

## 3. Build et tests

| Étape | Résultat |
|---|---|
| `docker compose --profile tools build scanner-nuclei` | OK — image `presence-nuclei:2026-11-07`, 932 MB |
| `docker compose build web celery-worker celery-beat` | OK |
| Tests ciblés (`test_sandbox_unavailable_partial.py`, `test_journey_service.py`, `test_advanced_security.py`) | **105 passed, 7 subtests**, 79 s |
| Suite `scans/` complète avec `config.settings.test` | **387 passed, 23 subtests**, 413 s, `TEST_EXIT=0` |

Remarque : la même suite lancée avec `config.settings.production` produit des blocs d'échecs (redirections SSL, cookies sécurisés, cache Redis partagé). La configuration prévue est `config.settings.test`, qui désactive ces interrupteurs et utilise un cache local.

---

## 4. Vérifications après rebuild

| Contrôle | Résultat |
|---|---|
| `GET /api/v1/scan-journeys/` | **401** (plus 404) |
| `GET /api/v1/health/` | 200 |
| `scans.tasks.reap_stale_journeys` enregistré | oui |
| `NucleiScanner().is_available()` | **True** |
| `SCANNER_NUCLEI_SCENARIO_TEMPLATES_PATH` / `SCANNER_NUCLEI_TEMPLATES_PATH` | vides |
| `SCANNER_DOCKER_IMAGE_NUCLEI` | `presence-nuclei:2026-11-07` |
| `/var/lib/presence-scanner-work` | `drwxrwxrwt root:root`, écriture OK en `uid=100(app)` |
| Templates de l'image | `nuclei -validate` → *All templates validated successfully* |
| Services | 12 services actifs + `scanner-work-init` exited 0 |

---

## 5. Retest E2E

### 5.1 État initial du site 38

```json
{"health_score": 69, "health_status": "critical", "last_scan_id": 62,
 "scans_total": 25, "site_scans": 2, "site_findings": 55,
 "site_checkresults": 16, "site_runs": 24, "site_alerts": 3,
 "ai_runs": 0, "sec_total": 12, "monitoring_enabled": false,
 "monitoring_interval": "24h", "monitoring_last_scan_at": null}
```

Les 3 identifiants d'alerte et les 12 identifiants de `SecurityFinding` ont été relevés avant le test.

### 5.2 Parcours 6

| Étape | Résultat |
|---|---|
| Création `POST /api/v1/scan-journeys/` | **201**, state `running`, stage 1, scan **1152**, `quota_charged=true` |
| Palier 1 (testssl) | **completed** en **80,7 s**, exit 0, **86 findings**, **0 CheckResult**, score santé nul |
| Parcours après palier 1 | `awaiting_confirmation`, `expires_at=2026-11-08T09:35:06Z` (+24 h) |
| `POST …/advance/` | **200**, stage 2, scan **1153**, `quota_charged=false` |
| Palier 2 | **completed** en **29,4 s** |
| Nuclei | **9 findings réels**, `scan_complete=true`, `percent=102`, **63 templates**, 193 requêtes, exit 0, 5,7 s, aucun code technique |
| Gobuster | **9 chemins** (`/cookies`, `/privacy`, `/robots.txt`, `/sitemap.xml`, `/stats`, `/terms`, `/tour`, `/wp-config.php.bak`, `/ws`), 23,1 s |
| CheckResult | 1 (catégorie `nuclei`) |
| Parcours final | **completed**, `expires_at=null` |
| Score santé du scan | **null** (aucun effet sur le score du site) |

Codes Nuclei observés (tous réels) : `http-missing-security-headers.*` pour CSP, COEP, COOP, CORP, Permissions-Policy, Referrer-Policy, X-Content-Type-Options, X-Frame-Options et X-Permitted-Cross-Domain-Policies.

### 5.3 Critères de succès

| # | Critère | Résultat |
|---|---|---|
| 1 | Rebuild 3 conteneurs + image Nuclei | ✅ |
| 2 | API parcours → 401 | ✅ |
| 3 | Reaper enregistré | ✅ |
| 4 | Palier 1 testssl, 80+ findings | ✅ (86) |
| 5 | Palier 2 Nuclei ≥ 1 finding réel | ✅ (9) |
| 6 | Palier 2 Gobuster ≥ 5 chemins | ✅ (9) |
| 7 | `sandbox_unavailable` → partial | ✅ (tests unitaires + intégration) |
| 8 | Cas d'erreur 400/400/404 | ✅ + 401 sans jeton |
| 9 | Effets de bord inchangés | ✅ |

---

## 6. Cas d'erreur

| Requête | Résultat |
|---|---|
| `POST /advance/` sur parcours `completed` | **400** — « aucun palier à confirmer » |
| `POST /cancel/` sur parcours `completed` | **400** — « annulation impossible » |
| `GET /scan-journeys/999999/` | **404** |
| `GET /scan-journeys/6/` sans jeton | **401** |

---

## 7. Reaper

Parcours synthétique **7** créé en `awaiting_confirmation` avec `expires_at` dans le passé, puis `reap_stale_journeys.apply()` :

```json
{"expired": 1, "reconciled": 0, "orphans": 0, "total": 1,
 "active": 0, "awaiting": 0, "coverage_alerts": 0,
 "reaper_inactive": false}
```

État après : `expired`. Métriques Redis observées :

```
presence:1:reaper:journeys_expired_total=1
presence:1:reaper:journeys_total=1
presence:1:reaper:journeys_active_count=0
presence:1:reaper:journeys_awaiting_count=0
presence:1:reaper:journeys_last_tick=2026-11-07T09:36:59.925824+00:00
```

Les compteurs sont laissés en place : ce sont des métriques opérationnelles cumulatives, pas des données de test.

---

## 8. Effets de bord et nettoyage

Après le test, avant nettoyage : santé **69/critical**, mêmes 3 alertes, **0 run IA**, monitoring inchangé, cible **200**. Les compteurs attendus avaient augmenté de 2 scans, 3 `ScannerRun`, 104 findings, 1 `CheckResult` et 1 `SecurityFinding`.

Suppressions effectuées :

- scans **1152** et **1153** (cascade `Finding`, `ScannerRun`, `CheckResult`, `AIRecommendationRun`) ;
- parcours **6** et **7** ;
- **1** `SecurityFinding` créé pendant le test (`309866c0-ed1b-491b-a299-90e1186ecf48`) ;
- **6** fichiers d'archive sous `scanner-archives/` (testssl, nuclei, gobuster pour les scans 1152/1153) ;
- jeton JWT temporaire.

État final, **identique à la baseline** :

```json
{"health_score": 69, "health_status": "critical", "last_scan_id": 62,
 "scans_total": 25, "site_scans": 2, "journeys_total": 0,
 "site_findings": 55, "site_checkresults": 16, "site_runs": 24,
 "site_alerts": 3, "ai_runs": 0, "sec_total": 12,
 "monitoring_enabled": false, "monitoring_interval": "24h"}
```

Aucun volume, aucune base et aucune donnée préexistante n'a été supprimé.

---

## 9. Anomalies résiduelles et observations

1. **testssl produit 86 findings mais 0 `CheckResult`** : le mapping de catégorie manque toujours. C'est antérieur à F1 et n'empêche pas le parcours ; à traiter en F2 pour que le palier 1 alimente le score/les checks.
2. **Quota** : le palier 1 a consommé 1 scan du compte QA (`quota_charged=true`). Le palier 2 n'en consomme pas, conformément à la règle.
3. **Isolation inter-organisations** : le 404 a été vérifié sur un identifiant inexistant, pas avec un second compte réel. Un test à deux comptes reste à ajouter.
4. **Catalogue Nuclei classique** : `SCANNER_NUCLEI_TEMPLATES_PATH` est désormais vide. Les profils classiques (`standard`, `thorough`, `deep`) n'ont plus de catalogue embarqué ; seul `scenario_c` est couvert par l'image. À décider en F2 : embarquer le catalogue complet ou documenter la couverture.
5. **Image Nuclei** : 932 MB. Le tag doit être bumpé dans le compose lors d'un changement de sélection de templates.
6. **Archives** : la suppression d'un scan ne supprime pas ses archives ; le nettoyage a été manuel. Un job de purge serait utile.
7. **Tests** : `pytest` n'est pas dans l'image ; il a été installé dans un conteneur éphémère. Ajouter une cible de test dédiée éviterait cette dépendance réseau.

---

## 10. Recommandations F2

1. Mapper les findings testssl vers `CheckResult` (catégorie `ssl`) ou documenter l'exclusion.
2. Ajouter un test E2E à deux comptes pour l'isolation inter-organisations.
3. Trancher la couverture Nuclei des scans classiques (catalogue complet dans l'image ou profil dédié).
4. Exécuter la suite complète en CI avec `config.settings.test` et une image de test incluant pytest.
5. Ajouter la purge des archives lors de la suppression d'un scan.
6. Ajouter `SCANNER_DOCKER_IMAGE_NUCLEI` et le tag `presence-nuclei` dans `.env.example`.

---

## 11. Reproductibilité

```bash
cd ~/Schreibtisch/SaaS_Web_Application_digitale_presenz

# Build
docker compose --profile tools build scanner-nuclei
docker compose build web celery-worker celery-beat

# Recréation ciblée
docker compose up -d scanner-work-init web celery-worker celery-beat

# Tests
docker compose run --rm --no-deps --user app \
  -e DJANGO_SETTINGS_MODULE=config.settings.test \
  web sh -c "pip install --user -q pytest pytest-django && \
  python -m pytest scans/ -q --tb=short --create-db"

# Vérifications
curl -sk -o /dev/null -w '%{http_code}\n' https://localhost/api/v1/scan-journeys/   # 401
docker compose exec -T celery-worker celery -A config inspect registered | grep reap_stale_journeys
docker compose exec -T celery-worker python manage.py shell -c \
  "from scanners.implementations.nuclei import NucleiScanner; print(NucleiScanner().is_available())"
```

---

## 12. Fichiers touchés

| Fichier | Nature |
|---|---|
| `backend/scanners/implementations/nuclei.py` | modifié (+10 lignes) |
| `backend/scanners/tests/test_advanced_security.py` | modifié (+13 lignes) |
| `backend/scans/tests/test_sandbox_unavailable_partial.py` | nouveau (118 lignes) |
| `backend/scanners/docker/Dockerfile.nuclei` | nouveau |
| `docker-compose.yml` | modifié (+42/−8) |

Aucun commit n'a été créé.
