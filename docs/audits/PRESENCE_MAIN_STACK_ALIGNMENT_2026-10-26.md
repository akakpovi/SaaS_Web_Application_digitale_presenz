# Presence — Alignement de la pile principale sur les statuts de scan et l'archivage

**Date :** 26 octobre 2026
**Pile :** `saas_web_application_digitale_presenz` (fichier Compose `docker-compose.yml` à la racine du dépôt)
**Environnement de comparaison :** pile isolée `presence-validation` (conservée intacte, non modifiée)
**Rapport de référence :** [`PRESENCE_SCAN_STATUS_REAL_VALIDATION_2026-10-26.md`](PRESENCE_SCAN_STATUS_REAL_VALIDATION_2026-10-26.md)

## 1. Statut final

**Validé en conditions réelles, avec une limite de couverture documentée.**

La pile principale exécute désormais le code validé (statuts agrégés `partial`, archivage des rapports, migration `0007`), son worker monte réellement le volume d'archives, et les comportements attendus ont été observés sur des scans réels : un scan santé complet reste `completed` malgré un scanner optionnel indisponible, un scan incomplet devient `partial` sans jamais résoudre de constat, les archives sont persistantes et les statuts sont cohérents dans la base, l'API et l'interface.

Limite : un scan `full`/`security` reste **`partial`** sur cette installation parce que six scanners avancés (`nmap`, `nikto`, `whatweb`, `testssl`, `dnsrecon`, `gobuster`) sont activés par la politique (`SCANNER_ADVANCED_SECURITY_ENABLED=true`) mais absents de l'image. Le pipeline signale désormais honnêtement cette couverture incomplète au lieu de la présenter comme un succès complet. Ce n'est pas une régression du code mais un écart d'installation préexistant, rendu visible par le correctif.

Aucune donnée historique n'a été modifiée, aucun volume n'a été supprimé, aucun code source n'a été modifié, aucun déploiement production n'a été effectué.

## 2. État initial (audit lecture seule)

### Conteneurs et images réellement exécutés

| Service | Image utilisée | Image ID | Observé |
|---|---|---|---|
| `web` | `saas_web_application_digitale_presenz-web` | `865710c9930f` | construite le 25/10 20:16 |
| `celery-worker` | image détaguée `77f253ffe7ea` | `77f253ffe7ea` | construite le 25/10 22:37 |
| `celery-beat` | `...-celery-beat` | `1f7218c16e12` | construite le 25/10 15:22 |
| `frontend` | `...-frontend` | `0f367c328f7f` | construite le 25/10 19:27 |

Un tag plus récent `saas_web_application_digitale_presenz-celery-worker:4d8e1adff3cb` (26/10 06:46) existait déjà mais **n'était pas utilisé par le conteneur actif** : il contenait `scanners/artifacts.py` sans `scans/services/status.py` ni la migration `0007`.

### Écart entre le code validé et le code réellement servi

Comparaison par empreinte SHA-256 entre l'arbre de travail et les images actives :

| Fichier | Arbre de travail | Image `web` active | État |
|---|---|---|---|
| `scans/services/orchestrator.py` | `8e97a4317d10` | `20648d7a4a95` | différent |
| `scans/services/steps_builder.py` | `3950e852eb17` | `d2d3c4449536` | différent |
| `scans/tasks.py` | `5fe5eb0aa562` | `3c9014618411` | différent |
| `scans/models.py` | `cd42e0caf3de` | `5de4db758eb7` | différent |
| `scanners/implementations/nuclei.py` | `a69c6286a9af` | `63ebcddad0c4` | différent |
| `scans/services/status.py` | `ee606dff4303` | absent | manquant |
| `scans/migrations/0007_scan_partial_status.py` | `3bc576b65e77` | absent | manquant |
| `scanners/artifacts.py` | `8b1dc8a742d8` | absent | manquant |

L'image du worker actif ne contenait **aucun** des modules de statut et d'archivage (`status.py`, `artifacts.py`, `0007`). L'écart était donc bien plus large qu'une simple migration manquante.

### Montage réel du volume d'archives

`docker inspect` sur le worker actif : seuls `media_data`, le bind `/tmp/presence-scanner` et `/var/run/docker.sock` étaient montés. **`scanner_archive_data` n'était pas monté sur `/app/scanner-archives`**, alors que le fichier Compose le déclarait depuis longtemps.

Le volume contenait néanmoins de vraies archives datées du 26/10 (05:38 → 06:32), écrites par des conteneurs ponctuels (`docker compose run`) construits après l'ajout du montage :

- `nuclei-scan3581-659bfa732c991f1f.jsonl` — 90 142 o — sha256 `659bfa73…7a2bd3`
- `nuclei-scan3585-54d6b74943c2c5a9.jsonl` — 90 232 o — sha256 `54d6b749…84c285`
- plus les sidecars et les archives vides des scans 3578, 3579, 3580, 3582.

Les empreintes de ces deux fichiers correspondent exactement aux `sha256` enregistrés dans `ScannerRun.metadata` en base : l'association archive ↔ run était déjà correcte.

### Base de données

- Total : 3 532 scans, 24 615 `scanner_run`, 6 253 findings, dernier `scan.id = 3594`.
- Répartition des scans : 3 531 `completed`, 1 `running`.
- Le scan 106 est en `running` depuis le **9 septembre 2026** (donnée historique préexistante, non touchée).
- Contrainte `scan_status_valid` : `pending, queued, running, completed, failed, cancelled` — **`partial` absent**.
- Migrations `scans` : `0001` → `0006` appliquées, `0007` non appliquée ; `0006_scannerrun_partial_status` déjà en place.
- Un seul `ScannerRun` en `timeout` : le run 24769 du scan 3584 (exit 137).

### File d'attente et tâches

- `redis -n 1 llen celery` = 0, aucune tâche active ni réservée (`celery inspect active|reserved` : `- empty -`).
- Beat actif : `run-due-monitors` toutes les 5 minutes, purge/retention la nuit, etc. Des scans santé réels s'exécutent donc régulièrement (~15–45 min d'intervalle observé).

### Espace disque

`/` à 97 % (6,9 Go libres) avant travaux — contrainte réelle prise en compte avant la reconstruction.

## 3. Prérequis de migration et retour arrière

### Sauvegarde vérifiée

- `scripts/backup.sh` exécuté : `backups/postgres-20261026T165925Z.dump` (2,4 Mo), `backups/redis-20261026T165925Z.rdb.gz`, `SHA256SUMS-20261026T165925Z`.
- SHA-256 du dump : `3070c047f9128b9b5d2798b59e2b402302691dc1c56250462ef8bbc859577cca`.
- `scripts/verify_backup_restore.sh` exécuté sur ce dump : restauration réelle dans une base jetable `presence_restore_check_…` sans erreur, avec **56 tables, 14 utilisateurs, 11 sites, 3 532 scans** puis suppression de la base de contrôle.
- Une sauvegarde antérieure (`postgres-20261021T172214Z.dump`) reste disponible.

### Compatibilité de `0007_scan_partial_status`

La migration supprime la contrainte `scan_status_valid`, modifie le champ `status` (ajout de la valeur `partial`) et recrée la contrainte. Elle ne contient **aucun `RunPython`** : aucune donnée n'est réécrite. Tous les statuts existants (`pending`, `queued`, `running`, `completed`, `failed`, `cancelled`) restent acceptés par la nouvelle contrainte, qui est un surensemble strict.

### Images de retour arrière

Avant reconstruction, les quatre images actives ont été retaguées (mêmes identifiants, aucun impact disque) :

| Tag de retour arrière | Image ID conservé |
|---|---|
| `...-web:pre-align-20261026` | `sha256:865710c9930f…f94736` |
| `...-celery-worker:pre-align-20261026` | `sha256:77f253ffe7ea…d8f0ed` |
| `...-celery-beat:pre-align-20261026` | `sha256:1f7218c16e12…4cff2` |
| `...-frontend:pre-align-20261026` | `sha256:0f367c328f7f…46acf` |

**Nuance importante :** si la migration est annulée (`manage.py migrate scans 0006`), la contrainte d'origine est recréée et **elle refuse la valeur `partial`**. Comme les scans 3595, 3597 et 3598 portent désormais ce statut, l'opération échouerait : un retour arrière du schéma exige de normaliser d'abord ces lignes (`failed` par exemple). Un simple retour à l'image précédente ne suffit donc **pas** après migration ; le schéma et le code doivent être ramenés ensemble, ou les nouvelles lignes normalisées. Le dump vérifié ci-dessus reste la voie sûre.

## 4. Vérifications préalables exécutées (sur le code de l'arbre de travail)

Toutes exécutées **avant** toute écriture, contre l'arbre de travail (le runner du dépôt monte `backend/` dans le conteneur, donc le code testé est bien celui qui a été cuit ensuite) :

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh scans scanners advisory monitoring` | **526 tests, OK**, 446,339 s |
| `python manage.py check` (`config.settings.production`) | « System check identified no issues (0 silenced). » |
| `python manage.py makemigrations --check --dry-run` | « No changes detected » |
| `docker compose config --quiet` | exit 0 |
| `pnpm exec tsc --noEmit` | exit 0 |
| `pnpm run build` | exit 0 (dont `Scripts/Scans-*.js` incluant l'UI « partial ») |

Le correctif « scanner optionnel indisponible » est présent dans `scans/services/status.py` (`_is_required` + étape `lighthouse` marquée `optional` par `steps_builder`) et couvert par `scans/tests/test_status_integrity.py`, inclus dans les 526 tests.

Le déclenchement de l'analyse IA et des alertes est réservé au statut `completed` (`scans/tasks.py`, l. 205-209 : `if report.get("status") == Scan.Status.COMPLETED`). Aucune modification n'a été apportée au module `advisory`.

## 5. Application du schéma et reconstruction

1. **Reconstruction** : `docker compose build web staticfiles celery-worker celery-beat frontend` → `BUILD_EXIT=0` (couches mises en cache pour `pip`, reconstruction rapide). Nouvelles images :

| Service | Nouvelle image ID |
|---|---|
| `web` | `sha256:ad272e6250751cdd591c891f4fa9e4774a5452614157ebba51398da50638ef47` |
| `celery-worker` | `sha256:d2d8555c64d16614d9dfec2f94f2810d0c1bfdde9d1eb17d1a2465efa1102665` |
| `celery-beat` | `sha256:442d290a4514c4e04af4f727da9fc5059dcd243a5fb45b1e52856d19a832016a` |
| `staticfiles` | `sha256:b7f8fc47b8d3f65b12adfb40ececa2f9872e562f3ef67bda866a8fbba66dfc95` |
| `frontend` | `sha256:3f2781e36dc5dbf618bb94b8b6570c0eac0a5ce72ebfc8838af960783c77c262` |

   Vérification d'identité arbre de travail ↔ image : `SAME` pour `status.py`, `orchestrator.py`, `tasks.py`, `models.py`, `0007_…`, `artifacts.py`, `nuclei.py` sur `web` **et** `celery-worker`. Le worker embarque `docker` 26.1.5 et `lighthouse` 12.8.2. Le bundle frontend servi contient bien la chaîne `Incomplete scan` (absente de l'image précédente).

2. **Migration** : `docker compose run --rm --no-deps web python manage.py migrate --noinput`
   → `Applying scans.0007_scan_partial_status... OK`

   | Contrôle | Avant | Après |
   |---|---|---|
   | `count(scans_scan)` | 3 532 | 3 532 |
   | `count(scans_scannerrun)` | 24 615 | 24 615 |
   | `count(scans_finding)` | 6 253 | 6 253 |
   | `max(scans_scan.id)` | 3 594 | 3 594 |
   | contrainte `scan_status_valid` | sans `partial` | avec `partial` |

   Aucune ligne réécrite, aucun identifiant modifié.

3. **Recréation contrôlée** : `staticfiles` (réinitialise propriété/permissions du volume, `exit 0`) puis `docker compose up -d web celery-worker celery-beat frontend`. Les services sans rapport (`db`, `redis`, `mailpit`, `wordpress`, `wordpress-db`, `scanner-sandbox-anchor`, `scanner-egress-guard`) n'ont **pas** été recréés.

4. **Images réellement actives après recréation** : `web` `ad272e625075`, `celery-worker` `d2d8555c64d1`, `celery-beat` `442d290a4514`, `frontend` `3f2781e36dc5` — identiques aux images construites. Logs de démarrage sans erreur ; le worker enregistre bien la nouvelle tâche `scans.tasks.prune_scanner_archives`.

## 6. Montage et persistance des archives

`docker inspect` sur le worker **réellement actif** :

```
volume saas_web_application_digitale_presenz_media_data -> /app/media (rw)
volume saas_web_application_digitale_presenz_scanner_archive_data -> /app/scanner-archives (rw)
bind /tmp/presence-scanner -> /tmp/presence-scanner (rw)
bind /var/run/docker.sock -> /var/run/docker.sock (rw)
```

- Identité effective : `uid=100(app) gid=101(app) groups=101(app),984` (984 = groupe du socket Docker).
- `/app/scanner-archives` : `700 app:app`.
- Test d'écriture/lecture contrôlé : création de `.align-check/probe.txt`, relecture correcte, fichier en `600 app:app` ; **artefact de test supprimé ensuite**.
- Archives préexistantes intactes : `nuclei-scan3581-…jsonl` → `659bfa73…7a2bd3` et `nuclei-scan3585-…jsonl` → `54d6b749…84c285`, conformes aux `sha256` en base.
- **Redémarrage contrôlé du worker** (`docker restart`, file vide, aucune tâche active au préalable) : empreinte agrégée de l'ensemble du répertoire `nuclei/2026/10/26` identique avant/après (`3121cac48de7a804c770ba86113d627a`), worker redevenu sain et re-enregistré ses tâches.
- Aucun conteneur de scan résiduel après les tests de timeout (seul subsiste `presence-zap-debug`, arrêté depuis 2 jours, sans rapport).

## 7. Validation fonctionnelle en conditions réelles

Cible unique : `appchat.elomaiapp.com`, déjà autorisée dans les missions précédentes. Aucun test intrusif, aucune modification du profil `standard`.

### A. Scan santé complet — `completed`

| Élément | Valeur |
|---|---|
| Scan Presence | **3596** (`health`, actif 24, déclenché via l'API autorisée) |
| Statut agrégé | **`completed`** |
| `health_score` | 69 |
| `failure_message` | vide |
| Durée | 1,4 s |
| Scanners | 7 `completed` (`website`, `ssl`, `dns`, `email_security`, `security_headers`, `performance`, `uptime`) |
| Scanner optionnel | `lighthouse` **`unavailable`** (8 ms) — sans effet sur le statut |

C'est exactement le cas « scanner optionnel indisponible » : l'indisponibilité de Lighthouse ne dégrade plus le scan, alors que sur l'image précédente le même constat était invisible puisqu'aucune agrégation n'existait.

### B. Scan complet `full` — archive persistante, statut `partial` justifié

| Élément | Valeur |
|---|---|
| Scan Presence | **3595** (`full`, actif 24, `scripts/live_scan_authorized_target.py --scan-type full`) |
| Statut agrégé | **`partial`** |
| Motif | « at least one required scanner did not complete a full run (nmap unavailable, nikto unavailable, whatweb unavailable, testssl unavailable, dnsrecon unavailable, gobuster unavailable) … the absent checks are not proof that a finding is resolved » |
| Durée | 143,6 s |
| `health_score` | 69 |
| ZAP | `completed`, 12 findings, 83,7 s |
| **Nuclei** | `completed`, exit 0, 58,2 s, **646 templates chargés**, 1 300 requêtes, 0 erreur réseau, `scan_complete = true` |

Archive Nuclei du scan 3595 (créée par le worker aligné) :

- `nuclei/2026/10/26/nuclei-scan3595-e3b0c44298fc1c14.jsonl` — 0 octet, sha256 `e3b0c442…b7852b855` (empreinte d'un fichier vide)
- sidecar `nuclei-scan3595-run24853-e3b0c44298fc1c14.meta.json` (`600 app:app`, 3 840 o) avec `scan_id=3595`, `complete=true`, `partial=false`, `records=0`, `profile=standard`, `profile_timeout_s=150`, `scanner_version v3.11.1`, `templates_loaded=646`, `requests=1300`, `retention_days=30`
- `ScannerRun.metadata.archive` en base : `status=stored`, `ref` identique au fichier, `sha256` identique, `truncated=false`, `retention_days=30`

Le rapport est vide parce que le profil `standard` (tags `exposure`, `misconfig`, sévérités `critical,high`) n'a produit **aucune correspondance** sur cette cible — ce n'est pas un scan non exécuté : 646 templates ont été chargés et 1 300 requêtes émises, et le fichier vide est explicitement accompagné de `complete=true`. Le contenu sensible a été vérifié : le sidecar ne contient que le bannière/statistiques Nuclei, aucune valeur d'authentification.

### C. Scans incomplets — jamais `completed`, aucune résolution

Deux exécutions contrôlées, dans le worker réel, sur l'actif isolé **32** (locataire de validation déjà existant, tenant de production non touché), avec un profil en mémoire non intrusif (`tags=misconfig`, `severity=info`, exclusions `dos/fuzz/intrusive/brute-force/…`, `resolve_missing=false`) et un budget volontairement court. Seule l'étape Nuclei est exécutée (périmètre volontairement limité, comme dans la validation isolée).

| Élément | Scan 3597 | Scan 3598 |
|---|---|---|
| Budget du profil | 1 s | 15 s |
| `ScannerRun` | 24867 | 24868 |
| Statut du run | `timeout`, exit **137** | `timeout`, exit **137** |
| Durée | 1 611 ms | 15 618 ms |
| **Statut agrégé** | **`partial`** | **`partial`** |
| Motif enregistré | « at least one required scanner did not complete a full run (nuclei timeout) … » | idem |
| Archive | `status=unavailable`, `detail=empty_report`, `partial=true` | idem |
| Findings du locataire | 1 avant → 1 après | 1 avant → 1 après |
| Constats résolus | 0 avant → 0 après | 0 avant → 0 après |

Points confirmés :

- un timeout n'est **jamais** converti en succès ; le statut agrégé reste non complet ;
- la complétude individuelle est conservée (`scan_complete=false`, `partial_reason='timeout'`) ;
- **aucune résolution de constat** n'est déclenchée par un scan incomplet ;
- le JSONL n'était **pas récupérable** (le sandbox tue le processus avant toute sortie exploitable) : le code l'enregistre explicitement (`unavailable` + `empty_report`) au lieu de fabriquer un rapport — comportement identique à celui observé dans l'environnement isolé ;
- aucun conteneur de scan ni processus résiduel après l'arrêt.

### D. API et isolation

| Contrôle | Résultat |
|---|---|
| `GET /api/v1/scans/?status=completed` | 200, 26 lignes (dont le scan 3596) |
| `GET /api/v1/scans/?status=partial` | 200, **1** ligne (scan 3595) |
| `GET /api/v1/scans/?status=failed` | 200, 0 ligne |
| `GET /api/v1/scans/3595/scanner-runs/` | 200, 16 lignes avec statut et durée par scanner (`nuclei completed 58198`, `zap completed 83736`, six `unavailable`) |
| `GET /api/v1/scans/3594/` (autre organisation) | **404** « No Scan matches the given query. » |
| `GET /api/v1/scans/3598/` (locataire de validation, autre organisation) | **404** |
| Scan 3594 / 3598 présents dans la liste du locataire ? | non / non |
| Accès anonyme `/scans/` et `/scans/3595/` | **401** |

### E. Interface (test navigateur réel)

Vérification Chromium (Playwright 1.64.1, `ignoreHTTPSErrors` pour le certificat local auto-signé) sur la pile réellement servie par nginx, session ouverte par jetons issus d'une vraie authentification API :

- filtre **`completed`** : 27 lignes, aucune occurrence d'« Incomplete scan » ;
- filtre **`partial`** : **1 seule ligne**, `appchat.elomaiapp.com`, libellé `Partial` ;
- ligne dépliée : bannière **« Incomplete scan. »** visible, avec le motif réel (« … nmap unavailable … ») et la présence de l'étape Nuclei.

Résultat : `UI_CHECK completed_rows=27 partial_rows=1`, test **passed**. Les captures et traces Playwright (`test-results/`) ont été supprimées après le test.

### F. Intégration IA et alertes

- `advisory.tasks.generate_scan_recommendations_task` a été déclenchée uniquement pour le scan **`completed`** 3596, et le worker a journalisé `AI advisor disabled for scan 3596` : l'intégration AKA IA est désactivée par la configuration de cette installation, **aucun appel externe n'a été généré** et le module `advisory` n'a pas été modifié.
- `advisory_airecommendation` : 0 ligne au total (avant et après).
- `detect_alerts` a été déclenchée pour le scan 3596 uniquement ; aucune alerte nouvelle n'en est issue (35 alertes au total, la plus récente datant du 25/10). Les scans 3595, 3597 et 3598 (non `completed`) n'ont déclenché ni analyse IA ni détection d'alertes.

### G. Historique préservé

- Scans `id < 3595` : **3 531 `completed` + 1 `running`**, identique à l'audit initial.
- Scan 3584 : toujours `completed`, avec son `ScannerRun` 24769 toujours `timeout` exit 137 (aucun statut réécrit).
- Scan 3594 : toujours `completed`, score 69.
- Scan 106 : toujours `running` (donnée préexistante, laissée telle quelle).

## 8. Fichiers modifiés

Aucun fichier source n'a été modifié par cette mission. `git status --short` compte **282 entrées avant et après** les travaux (toutes préexistantes : travail local sur le frontend, les scanners et les statuts). Les seules créations sont :

- `docs/audits/PRESENCE_MAIN_STACK_ALIGNMENT_2026-10-26.md` (ce rapport) ;
- `backups/postgres-20261026T165925Z.dump`, `backups/redis-20261026T165925Z.rdb.gz`, `backups/SHA256SUMS-20261026T165925Z` (sauvegarde, répertoire ignoré par Git) ;
- scripts de validation temporaires dans `/tmp/presence-align/` (hors dépôt) ;
- `dist/` du frontend régénéré par `pnpm run build` (répertoire ignoré par Git).

Aucun secret n'a été écrit dans un fichier, un log ou ce rapport.

## 9. Limites restantes et risques

1. **Scans `full`/`security` en `partial` sur cette installation.** `nmap`, `nikto`, `whatweb`, `testssl`, `dnsrecon` et `gobuster` sont activés par la politique mais absents de l'image : le statut agrégé est donc `partial` pour tous les scans de sécurité, y compris ceux dont ZAP/Nuclei ont parfaitement terminé. Deux options, décision produit/ops à prendre : installer ces binaires dans l'image du worker (couverture complète), ou désactiver explicitement le tier avancé concerné par la politique. Aucune des deux n'a été appliquée ici pour ne pas modifier silencieusement la couverture.
2. **Aucun rapport partiel récupérable observé.** Les deux timeouts réels ont tué le sandbox avant toute sortie JSONL ; le chemin « archive partielle non vide » n'est donc démontré que par les tests déterministes (`scanners/tests/test_artifacts.py`), pas en conditions réelles sur cette pile.
3. **Résolution réelle non démontrée.** Inchangé par rapport à la mission précédente : la cible autorisée conserve les mêmes constats, aucune correction réelle ne peut faire disparaître un constat. Aucun rapport n'a été fabriqué.
4. **Espace disque critique.** `/` était à 97 % (6,9 Go) avant, 98 % (6,5 Go) après reconstruction. Les anciennes images et le cache de build (~11 Go récupérables, plus ~9,5 Go d'images non utilisées) devraient être nettoyés lors d'une fenêtre dédiée. Aucun élagage n'a été exécuté ici.
5. **`scripts/live_scan_authorized_target.py` ne traite pas `partial` comme terminal** : il ne sort de sa boucle que sur `completed`/`failed`, donc sur un scan partiel il interroge l'API jusqu'à son propre délai d'expiration (observé : survivance de ~13 min après la fin réelle du scan). Le script n'a pas été modifié (outil de validation, hors périmètre des fichiers de la pile) ; correction recommandée pour les prochaines validations.
6. **Rollback du schéma non trivial.** Voir la section 3 : revenir à `0006` recrée une contrainte qui refuse `partial`, donc les nouvelles lignes doivent être normalisées au préalable.
7. **`lighthouse` reste `unavailable` dans le worker actif** malgré sa présence dans l'image (l'étape est optionnelle, donc sans impact fonctionnel). Cause non investiguée dans cette mission (`scanners/implementations/lighthouse.py` l. 162 : `shutil.which(self.binary)`), à examiner si l'audit performance/SEO par Lighthouse est attendu en production.
8. **Pile isolée conservée** (`presence-validation`) sur les ports 8090/8088, avec ses volumes intacts, comme environnement de comparaison.

## 10. Commandes de validation (récapitulatif)

```bash
# Audit et sauvegarde
git status --short ; docker ps -a ; docker inspect …            # lecture seule
bash scripts/backup.sh
bash scripts/verify_backup_restore.sh backups/postgres-20261026T165925Z.dump

# Prérequis (arbre de travail)
bash scripts/run_backend_tests.sh scans scanners advisory monitoring   # 526 tests OK
docker compose run --rm --no-deps --user 0:0 web python manage.py check
docker compose run --rm --no-deps --user 0:0 web python manage.py makemigrations --check --dry-run
docker compose config --quiet ; pnpm exec tsc --noEmit ; pnpm run build

# Alignement
docker compose build web staticfiles celery-worker celery-beat frontend
docker compose run --rm --no-deps web python manage.py migrate --noinput
docker compose up -d web celery-worker celery-beat frontend

# Validation réelle
python3 scripts/live_scan_authorized_target.py --base-url https://localhost/api/v1 --scan-type full   # scan 3595
# scan santé 3596 via POST /api/v1/websites/24/scan/ {"scan_type":"health"}
# scans 3597/3598 : timeouts contrôlés 1 s et 15 s sur l'actif isolé 32, dans le worker
docker restart saas_web_application_digitale_presenz-celery-worker-1   # persistance des archives
pnpm exec playwright test --config /tmp/presence-align/playwright-ui.config.ts   # interface : 1 passed
```

## 11. Conclusion

**Validé en conditions réelles.** La pile principale exécute le code audité et l'a démontré sur des scans réels : migration `0007` appliquée sans perte (3 532 scans, 24 615 runs, 6 253 findings inchangés), worker reconstruit et monté sur le volume d'archives, scan santé `completed` malgré un scanner optionnel indisponible, scan complet archivé et persistant après redémarrage, scans incomplets en `partial` sans aucune résolution de constat, API et interface cohérentes, isolation inter-locataires respectée, historique intact.

La limite qui subsiste n'est pas un défaut de code mais un écart d'installation : sans les six binaires de scanners avancés, les scans de sécurité sont désormais correctement étiquetés `partial` au lieu d'être faussement déclarés `completed`. La décision d'installer ces scanners ou d'ajuster la politique de couverture reste à prendre explicitement.
