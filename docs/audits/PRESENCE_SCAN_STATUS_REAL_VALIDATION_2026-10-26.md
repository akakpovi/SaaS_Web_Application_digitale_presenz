# Présence — Validation réelle des statuts de scan et des archives

**Date :** 2026-10-26
**Périmètre :** statuts agrégés `Scan`, `ScannerRun`, worker Celery, migration `0007`, archive des rapports Nuclei, API, interface
**Statut :** validé en conditions réelles sur un environnement isolé, avec une limite : le cas « scan complet + archive » a été exécuté via le runner contrôlé du worker et non via la file Celery.
**Référence :** `PRESENCE_SCAN_STATUS_INTEGRITY_2026-10-26.md`

---

## 1. Environnement utilisé

Aucun environnement de staging préexistant n'a été trouvé : le dépôt ne contient qu'une pile locale (`saas_web_application_digitale_presenz`) et une pile backend obsolète. La pile locale active n'a **pas** été utilisée comme environnement de test.

Un environnement isolé a été créé avec Compose, projet `presence-validation` :

| Élément | Valeur |
|---|---|
| Base de données | conteneur `presence-validation-validation-db-1`, base `presence_validation`, volume `presence-validation_postgres_data` |
| Redis | conteneur `presence-validation-validation-redis-1`, broker `/1`, result backend `/2` |
| Web | `presence-validation-validation-web-1`, port loopback `127.0.0.1:8090` |
| Worker | `presence-validation-validation-worker-1`, même image que le web |
| Archives | volume `presence-validation_scanner_archive_data`, monté sur `/app/scanner-archives` |
| Interface | nginx temporaire, `127.0.0.1:8088`, même origine API via proxy `/api/` |
| Réglages | `config.settings.development`, `AI_ADVISOR_ENABLED=false`, e-mail en mémoire |
| Réseau scanners | réseau partagé `presence_scanner_sandbox`, socket Docker monté uniquement sur le worker |

La cible des scans est `appchat.elomaiapp.com`, déjà autorisée et utilisée par les missions précédentes. Aucun test intrusif n'a été ajouté et le profil standard n'a pas été modifié.

### État de la pile principale

La pile principale n'a **pas** été migrée, redémarrée ni reconstruite :

- `scans` en est toujours à `0006_scannerrun_partial_status` ;
- le scan historique 3584 reste `completed` ;
- le worker principal ne monte toujours pas `/app/scanner-archives`.

Aucun déploiement en production n'a été effectué.

---

## 2. Images et versions réellement exécutées

| Composant | Identifiant / version |
|---|---|
| Image backend validée | `presence-validation-backend:2026-10-26`, digest `sha256:4f30b5f768e1251e237c0bba977f1f27e369cf82c4b4fd10517bf4703a932fdd` |
| Nuclei | `projectdiscovery/nuclei:latest`, digest `sha256:2eb4a29e8ee0359a6ea648bc376d4e5760701b752e1f99d2fcb0d8d1cd1a8466`, moteur **v3.11.1** |
| ZAP | `zaproxy/zap-stable:latest`, digest `sha256:4610c8ba23ed92d2edb2313a9b1554f769e6a04e99d32a1f50ae282a272a9185` |
| Templates Nuclei | **14 104 fichiers YAML** réellement présents sur le chemin monté ; le sidecar archive indique `templates_version = 14126`, valeur de déploiement configurée. L'écart est documenté, pas masqué. |
| Modèle Nuclei mesuré | profil standard du produit pour les scans API ; profil de validation informatif pour le scan complet 5 |

---

## 3. Validation du schéma et du worker

### Migration

Dans l'environnement isolé :

```
scans
 [X] 0001_initial
 ...
 [X] 0006_scannerrun_partial_status
 [X] 0007_scan_partial_status
```

La contrainte PostgreSQL `scan_status_valid` inclut bien `partial` :

```
CHECK (status IN ('pending','queued','running','completed','partial','failed','cancelled'))
```

### Montage réel du volume d'archives

Inspection du worker isolé :

```
Mounts=...volume:/var/lib/docker/volumes/presence-validation_scanner_archive_data/_data=>/app/scanner-archives ...
```

Test d'écriture/lecture exécuté sous l'utilisateur `app` (`uid=100`, `gid=101`) : succès.

Permissions observées :

- `/archives` et répertoires : `700 app:app` ;
- fichiers JSONL et sidecar : `600 app:app`.

### Persistance après redémarrage

Le worker isolé a été redémarré (`docker compose restart validation-worker`). Après redémarrage :

- le montage `/app/scanner-archives` est toujours présent ;
- le hash SHA-256 de l'archive du scan 5 est inchangé (`eadcc281e0f85d8bff6e5b6c8934608b935f90003f7f04cf0424a9b653970780`) ;
- un test d'écriture post-redémarrage réussit ;
- aucune archive n'a été perdue.

---

## 4. Scans réels exécutés

### Scan 2 — régression découverte puis corrigée

Premier scan santé réel, avant la correction finale : `partial` avec la raison `lighthouse unavailable`.

Cause : le calcul d'agrégation traitait un scanner **optionnel indisponible** comme une couverture incomplète. Lighthouse est explicitement optionnel lorsque la performance historique couvre déjà le besoin ; son absence ne doit pas déclasser un scan santé réussi.

Correction appliquée dans `scans/services/status.py` : un step non requis est ignoré, qu'il soit `skipped` ou `unavailable`. Un test de non-régression a été ajouté (`test_optional_unavailable_step_does_not_downgrade_success`).

C'est le principal apport de la validation réelle : ce comportement n'était pas visible dans les tests simulés précédents.

### Scan 3 — santé complet

| Élément | Valeur |
|---|---|
| Scan Presence | 3 |
| Statut agrégé | **completed** |
| Durée | 1 s |
| Score | 69 |
| Steps | website, ssl, dns, email_security, security_headers, performance, uptime : `completed` ; lighthouse : `unavailable` (`required=false`) |
| API | `GET /api/v1/scans/3/` → `status = completed` |
| Interface | badge **Completed** |

### Scan 4 — sécurité partiel réel

Lancé via l'API, `scan_type=security`, profil standard.

| Élément | Valeur |
|---|---|
| Scan Presence | 4 |
| Statut agrégé | **partial** |
| Durée | 151 s |
| Steps | nmap, nikto, whatweb, testssl, dnsrecon, gobuster : `unavailable` ; nuclei : `completed` (63,9 s) ; zap : `completed` (87,3 s) |
| Raison | couverture incomplète des scanners requis, pas un succès complet |
| Archive Nuclei | `nuclei/2026/10/26/nuclei-scan4-e3b0c44298fc1c14.jsonl`, 0 octet, sidecar 3 829 octets, `records = 0`, `complete = true` |
| Score | `—/100` dans l'interface, avec la mention « Score based on completed checks only — not a complete security assessment » |

Le rapport Nuclei est vide parce que le profil standard ne conserve que les sévérités high/critical et qu'aucun de ces constats n'était présent sur la cible. L'archive et son sidecar sont bien créés et persistés, mais ce scan ne démontre pas un rapport non vide.

### Scan 5 — Nuclei complet, archive réelle non vide

Scan contrôlé exécuté dans le conteneur worker de validation, avec un profil informatif non intrusif (`validation-info`, tags `misconfig`, sévérité `info`, `resolve_missing=false`, timeout 120 s). Ce profil n'est **pas** un profil de production et n'a pas été persisté dans les réglages.

| Élément | Valeur |
|---|---|
| Scan Presence | 5 |
| Statut agrégé | **completed** |
| Durée | 64 s |
| Step | nuclei : `completed`, `required=true` |
| ScannerRun | 25, `completed`, exit code 0, 63 963 ms |
| Complétude | `scan_complete = true` |
| Archive | `nuclei/2026/10/26/nuclei-scan5-eadcc281e0f85d8b.jsonl` |
| Taille / lignes | 89 873 octets, 9 lignes |
| SHA-256 | `eadcc281e0f85d8bff6e5b6c8934608b935f90003f7f04cf0424a9b653970780` |
| Sidecar | `nuclei-scan5-run25-eadcc281e0f85d8b.meta.json`, 3 821 octets |
| Association | `scan_id = 5`, `scanner_run_id = 25`, `complete = true`, `partial = false`, `records = 9` |
| Diagnostic | profil `validation-info`, templates chargés 115, requêtes 197, erreurs 4, `scanner_version = v3.11.1` |
| Secrets | aucun motif sensible détecté dans le JSONL (authorization, cookie, token=, password=, secret, bearer, API key, JWT) |

Cette exécution prouve que le code audité produit bien une archive persistante non vide, associée au bon `ScannerRun`, dans le volume monté du worker.

### Scan 6 — timeout réel, statut partiel et non-résolution

Scan contrôlé avec un scanner interne réussi (`website`) et Nuclei configuré avec un budget de 1 seconde.

| Élément | Valeur |
|---|---|
| Scan Presence | 6 |
| Statut agrégé | **partial** |
| Raison | `Partial scan: ... (nuclei timeout)` |
| Step website | `completed` |
| Step nuclei | `timeout`, exit code 137, 1 713 ms, `scan_complete = false` |
| Archive | non écrite, `status = unavailable`, `partial = true`, `detail = empty_report` |
| Findings | 13 constats avant et après, tous `open` ; le constat Nuclei reste `open` |
| Résolution abusive | aucune |

Le scan 6 a ensuite été rejoué : l'orchestrateur a détecté le statut terminal `partial`, n'a créé aucun nouveau `ScannerRun` et a conservé le statut et le score. Le timeout n'est jamais devenu un succès.

Aucun conteneur de scan ZAP/Nuclei ne subsistait après les essais.

---

## 5. API et interface

### API

| Vérification | Résultat |
|---|---|
| `GET /api/v1/scans/?status=completed` | 200, 2 scans (`3`, `5`) |
| `GET /api/v1/scans/?status=partial` | 200, 3 scans (`2`, `4`, `6`) |
| `GET /api/v1/scans/?status=failed` | 200, 1 scan (`1`, artefact d'initialisation de l'environnement) |
| `GET /api/v1/scans/5/` avec un autre tenant | **404** |
| `GET /api/v1/scans/5/` sans authentification | **401** |
| `GET /api/v1/scans/4/scanner-runs/` | expose `nuclei: completed`, `zap: completed`, les scanners indisponibles et le timeout du scan 6 |

### Interface navigateur

Interface réelle servie en même origine (`127.0.0.1:8088`) à partir du build courant, avec connexion du propriétaire de validation.

Vérifications observées :

- l'historique affiche 6 scans avec les badges **Completed**, **Partial** et **Failed** distincts ;
- le filtre **Completed** ne laisse que les 2 scans complets ;
- un scan partiel affiche « Incomplete scan. », la raison détaillée, la section **SCANNER RUNS** avec chaque scanner (`Unavailable`, `Completed`, durée, code de sortie) et l'avertissement explicite sur le score partiel ;
- un scan sans score affiche `—/100` et non une évaluation complète ;
- le scan partiel n'est jamais présenté comme un succès.

---

## 6. Fichiers modifiés pendant cette mission

| Fichier | Modification |
|---|---|
| `backend/scans/services/status.py` | correction : un step optionnel (`skipped` ou `unavailable`) n'est plus une couverture manquante |
| `backend/scans/tests/test_status_integrity.py` | nouveau test `test_optional_unavailable_step_does_not_downgrade_success` |
| `/tmp/presence-validation/docker-compose.yml` | pile de validation isolée (hors dépôt) |
| `/tmp/presence-validation/run_nuclei_complete.py` | runner contrôlé du scan complet 5 (hors dépôt) |
| `/tmp/presence-validation/run_nuclei_timeout.py` | runner contrôlé du scan timeout 6 (hors dépôt) |

Aucune modification de l'intégration AKA IA, des scanners, des règles d'ingestion ou des données de la pile principale.

---

## 7. Tests exécutés

```
bash scripts/run_backend_tests.sh \
  scans.tests.test_status_integrity \
  scans.tests.test_orchestrator_delegation \
  scans.tests.test_scanner_engine \
  scans.tests.test_advanced_security_gate \
  scans.tests.test_scans \
  scans.tests.test_alert_pipeline \
  advisory.tests.test_scan_ingestion \
  advisory.tests.test_nuclei_lifecycle \
  scanners.tests.test_artifacts \
  monitoring \
  public_checker.tests.test_legacy_public_checker
```

**Résultat : 270 tests exécutés, `OK`, 204,286 s.**

Autres contrôles :

| Commande | Résultat |
|---|---|
| `python manage.py check` | aucune erreur |
| `python manage.py makemigrations --check --dry-run` | aucune migration manquante |
| `docker compose config --quiet` | configuration valide |
| `pnpm exec tsc --noEmit` | aucune erreur |
| `pnpm run build` | build Vite réussi |

Ces commandes ont été exécutées après la correction du statut optionnel.

---

## 8. Limites et éléments non vérifiés

- **Le cas complet + archive Nuclei (scan 5) n'a pas été exécuté via la file Celery.** Il a utilisé `run_authenticated_scan.apply` dans le conteneur worker de validation, qui exécute le même code, le même sandbox Docker et le même volume d'archives, mais pas via le processus Celery de longue durée. Le chemin Celery standard a été validé par les scans 2, 3 et 4 via l'API.
- **Le profil informatique du scan 5 est un profil de validation local**, non persisté dans les réglages de production. Le profil standard du produit ne détecte actuellement aucun constat high/critical sur cette cible, d'où l'archive vide du scan 4.
- **La cible `appchat.elomaiapp.com` n'a pas été modifiée** ; la résolution réelle d'un constat après correction n'est pas démontrée ici, seulement l'absence de résolution abusive sur un scan partiel.
- **La pile principale reste sur l'ancien code.** La migration `0007` n'y est pas appliquée et son worker ne monte pas le volume d'archives. Toute mise en service doit appliquer la migration, reconstruire l'image et recréer le worker.
- Le nombre réel de templates présents (14 104) diffère de la valeur de déploiement configurée (14 126) ; le sidecar conserve la valeur configurée, ce qui peut induire un léger écart de traçabilité.
- Les scans de validation utilisent des identifiants et un mot de passe locaux ; aucun secret n'est reporté ici et l'environnement n'est pas exposé au-delà de la loopback.

---

## 9. Conclusion

La validation réelle est réussie sur l'essentiel :

- l'environnement isolé applique la migration `0007` et la contrainte PostgreSQL accepte `partial` ;
- le worker monte réellement le volume d'archives, écrit et relit les rapports, et les conserve après redémarrage ;
- un scan santé réel devient `completed` ;
- un scan sécurité réel avec scanners indisponibles devient `partial`, jamais `completed`, avec le détail par scanner ;
- un timeout réel devient `partial`, ne résout aucun constat et reste terminal lors d'un rejeu ;
- un scan Nuclei réel complet produit une archive non vide, persistante et associée au bon `ScannerRun` ;
- l'API et l'interface distinguent complètement les statuts `completed`, `partial` et `failed` ;
- l'isolation inter-locataires et l'authentification restent appliquées.

La correction du statut optionnel indisponible a été découverte précisément grâce à cette validation réelle et est désormais couverte par un test.

**Statut final : validé sur un environnement isolé et réel, avec une réserve documentée sur le mode d'exécution du cas « archive complète » et sur la pile principale, qui reste à migrer et à reconstruire avant déploiement.**
