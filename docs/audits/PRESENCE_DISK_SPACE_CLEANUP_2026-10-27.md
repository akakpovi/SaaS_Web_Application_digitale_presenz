# Présence — Remise à zéro Docker locale et libération d'espace disque

**Date** : 27 octobre 2026
**Hôte** : `elom-Latitude-E7470` — utilisateur `elom`
**Projet** : `/home/elom/Schreibtisch/SaaS_Web_Application_digitale_presenz` (branche `main`, 282 entrées modifiées/ajoutées non commitées — **conservées**)
**Objet** : remise à zéro contrôlée de l'environnement Docker local de développement de Presence, nettoyage des caches, puis reconstruction de la pile.

---

## 1. Périmètre Docker ciblé

Le démon Docker est **partagé** avec plusieurs autres projets. `docker compose ls -a` recensait cinq projets Compose :

| Projet Compose | Fichier de configuration | Statut initial | Décision |
|---|---|---|---|
| `saas_web_application_digitale_presenz` | `./docker-compose.yml` | 11 actifs + 2 sortis | **Périmètre autorisé — remis à zéro** |
| `backend` | `SaaS_..._v2/backend/docker-compose.yml` | 1 actif | **Périmètre autorisé** — pile marquée « DÉPRÉCIÉ — NE PAS DÉMARRER » dans le dépôt, volumes documentés comme jetables |
| `presence-validation` | `/tmp/presence-validation/docker-compose.yml` | 4 actifs + 1 sorti | **Préservé** (pile isolée de comparaison) |
| `ai-platform` | `~/Schreibtisch/ai-platform/docker-compose.yml` | 9 actifs | **Préservé** (autre projet) |
| `fingptfinrobot` | `~/Schreibtisch/FinGPTFinRobot/docker-compose.yml` | 1 redémarrant | **Préservé** (autre projet) |

Autres ressources détectées et **hors périmètre** : volumes `grid_trading_bot_*`, réseaux `freqtrade*`, `quant_lab_default`, `portfolio_elomai_network`, `docker-pentest-lab_pentest-net`, images tierces (librechat, jupyterlab, freqtrade, grafana, image ECR…).

Conteneur orphelin rattaché au périmètre : `presence-zap-debug` (ZAP, sorti code 3, 2 jours) — résidu des essais de scanner du projet.

## 2. Mesures avant nettoyage

```
/dev/nvme0n1p2  ext4  234G  216G utilisé  →  6,3G libres (98 %)
inodes : 3,9 M utilisés / 15 M (27 %)

docker system df
  Images       161   20,86 Go   (9,57 Go récupérables)
  Conteneurs    31    8,5 Mo    (0 récupérable)
  Volumes       23    2,415 Go  (1,22 Go récupérables)
  Cache build  294   11,76 Go   (9,00 Go récupérables)
```

Système : cache APT **1,1 Go** (dont 929 Mo de `.deb`, 28 paquets) ; `/var/log` **1,8 Go** (`syslog` 498 Mo, `syslog.1` 626 Mo, `syslog.2-4.gz` 162 Mo, `kern.log*` ~33 Mo, `atop` 466 Mo) ; journal systemd 146 Mo.

## 3. Sauvegarde vérifiée avant toute suppression

- `backups/postgres-20261026T165925Z.dump` — 2 478 365 octets.
- `backups/redis-20261026T165925Z.rdb.gz` — 24 Ko.
- `sha256sum -c SHA256SUMS-20261026T165925Z` → **OK pour les deux fichiers**.
- Lecture du dump sans restauration : `pg_restore --list` → archive personnalisée valide, base `presence`, **492 entrées TOC**, dumpée et relue par PostgreSQL 16.15.
- Inventaire préalable du volume d'archives : 16 fichiers (8 JSONL + 8 sidecars) pour les scans 1, 3578, 3579, 3580, 3581, 3582, 3585, 3595.
- Copie de préservation créée **avant** suppression : `backups/scanner-archives-20261026/` (244 Ko, 16 fichiers, `0600`, propriétaire `elom:elom`). `backups/` est ignoré par Git (`.gitignore:26`), aucune pollution du dépôt.

## 4. Suppression contrôlée (phase C)

### Conteneurs (15)
- 13 conteneurs du projet principal (web, staticfiles, celery-worker, celery-beat, db, redis, mailpit, wordpress, wordpress-db, wordpress-init, scanner-sandbox-anchor, scanner-egress-guard, frontend) — arrêt propre puis `down --remove-orphans`.
- 1 conteneur de la pile dépréciée (`backend-db-1`).
- 1 conteneur orphelin (`presence-zap-debug`).

### Volumes (10, ≈ 543 Mo)
| Volume | Taille mesurée |
|---|---|
| `saas_..._wordpress_db_data` | 170,2 Mo |
| `saas_..._postgres_data` | 127,7 Mo |
| `saas_..._wordpress_data` | 74,3 Mo |
| `saas_..._redis_data` | 57,4 Mo |
| `saas_..._static_data` | 3,45 Mo |
| `saas_..._scanner_archive_data` | 209 ko (16 fichiers inventoriés) |
| `saas_..._media_data` | 0 |
| `backend_postgres_data` (dépréciée) | 77,2 Mo |
| `backend_redis_data` (dépréciée) | 29,7 Mo |
| `backend_static_data` (dépréciée) | 3,45 Mo |

### Réseaux (3)
`saas_web_application_digitale_presenz_default`, `presence_scanner_sandbox` (créé par Compose, sous-réseau 172.31.240.0/24), `backend_default`. Aucun réseau d'un autre projet n'a été touché.

### Images
- 13 images taguées du projet : `saas_...-{web,staticfiles,celery-beat,celery-worker,frontend,scanner-egress-guard}` (`latest` + étiquettes `pre-align-20261026`), plus `presence-backend:lighthouse-test`, `presence-egress-guard:test`, `presence-frontend:latest`.
- Images *dangling* portant le label `com.docker.compose.project=saas_web_application_digitale_presenz` (`docker image prune -a --filter label=…` → 218,6 Mo annoncés, le reste étant libéré par la suppression des étiquettes).
- 7 images *dangling* non labellisées, attribuées **par inspection** avant suppression : `workdir=/app` avec `gunicorn config.wsgi:application` (images backend) et `entrypoint=/usr/local/bin/egress-guard` (images egress-guard). Aucune image d'un autre projet n'a été supprimée.
- `projectdiscovery/nuclei:latest` : voir §7 (supprimée puis **restaurée à l'identique**).

### Cache de build
`docker builder prune -a -f` → **11,76 Go récupérés** (poste le plus important). Cache de build ramené à 0.

### Nettoyage système (élévation demandée et approuvée une seule fois)
`apt-get clean` + suppression des journaux déjà tournés (`syslog.1`, `syslog.2-4.gz`, `kern.log.1/.2.gz/.3.gz`) + `journalctl --vacuum-size=100M`.
Mesure en octets avant/après : `20 414 771 200 → 22 353 567 744` soit **+1,94 Go**. `/var/cache/apt` : 1,1 Go → 80 ko. `/var/log` : 1,8 Go → 977 Mo.

## 5. Espace disque récupéré

| Étape | `df -hT /` — libre | Occupation |
|---|---|---|
| Avant | 6,3 G | 98 % |
| Après conteneurs + volumes + images | 7,1 G | 97 % |
| Après purge du cache de build | 20 G | 92 % |
| Après nettoyage système | **20,8 G** (22,35 Go mesurés) | 91 % |
| Après reconstruction des images + restauration nuclei | **19 G** | 92 % |

**Gain net final : ≈ +12,7 G** (6,3 G → 19 G), avec un pic de ≈ 20,8 G libres pendant la fenêtre nettoyée. Inodes : 3,9 M → 3,2 M utilisés (22 %).

## 6. Données de test perdues

- **PostgreSQL principale** : 14 utilisateurs, 11 sites, 3 532 scans, 24 615 `ScannerRun`, 6 253 constats (inventaire de la mission `PRESENCE_MAIN_STACK_ALIGNMENT_2026-10-26`). Conservés dans `backups/postgres-20261026T165925Z.dump`.
- **Redis** : 57,4 Mo (files et cache).
- **Archives scanner** : 16 fichiers — copie conservée dans `backups/scanner-archives-20261026/`.
- **WordPress local** : 74,3 Mo de contenu + 170,2 Mo de base MariaDB.
- **Base de la pile dépréciée `backend`** : 43 tables publiques, 50 migrations, 3 utilisateurs, **0 scan, 0 site** (le dépôt documentait ces volumes comme jetables).

## 7. Correction d'une erreur de périmètre (à connaître)

`projectdiscovery/nuclei:latest` (932 Mo, aucun conteneur associé) a d'abord été classée « image d'audit orpheline » et supprimée. Vérification faite ensuite dans le code :

```
SCANNER_SANDBOX['docker']['images'] = {"nuclei": "projectdiscovery/nuclei:latest", "zap": "zaproxy/zap-stable:latest", …}
SCANNER_SANDBOX['docker']['pull_policy'] = "never"
```

et `NucleiScanner` exécute bien le binaire **dans ce conteneur** (`docker_entrypoint=""`, templates montés sur `/nuclei-templates`). La suppression était donc une régression réelle du chemin de scan (avec `--pull never`, l'étape Nuclei aurait échoué faute d'image).

Correction appliquée : `docker pull projectdiscovery/nuclei:latest` → digest **identique** à l'image supprimée (`sha256:582d5546…`), et `nuclei -version` renvoie **v3.11.1**, exactement la version enregistrée dans `NUCLEI_RELIABILITY_2026-10-25.md`. Aucune dérive de version.

Même vérification faite pour `zaproxy/zap-stable:latest` (2,44 Go, `images.zap`) : **conservée** volontairement.

## 8. Éléments conservés

- Dépôt Git intact : code source, fichiers Compose, scripts, migrations, `.env` (`SaaS_..._v2/backend/.env`, 2 860 octets, `0600` — contenu jamais affiché).
- `backups/` : dump PostgreSQL + empreintes SHA256, dump Redis, jeux antérieurs, copie des archives scanner.
- `docs/audits/` : `PRESENCE_MAIN_STACK_ALIGNMENT_2026-10-26.md`, `PRESENCE_SCAN_STATUS_INTEGRITY_2026-10-26.md`, `NUCLEI_*` — intacts.
- Pile isolée `presence-validation` : 4 conteneurs actifs + 1 init sorti 0, volumes `presence-validation_*`, image `presence-validation-backend:2026-10-26`, réseau `presence-validation_default`.
- Autres projets : `ai-platform` (9 conteneurs, 5 volumes, 4 réseaux), `fingptfinrobot`/goldbot, volumes `grid_trading_bot_*`, réseaux freqtrade/quant_lab/portfolio_elomai/docker-pentest-lab.
- Images de base nécessaires à la reconstruction : `python:3.12-slim`, `node:20-alpine`, `postgres:16-alpine`, `redis:7-alpine`, `nginx:1.27-alpine`, `alpine:3.20`, `mariadb:11`, `wordpress:6.7-php8.3-apache`, `wordpress:cli-php8.3`, `axllent/mailpit:v1.21`.
- `/tmp/.mount_FreebuKgTCwH` (464 Mo) : point de montage de l'application en cours — non touché.

## 9. Reconstruction et contrôles effectués

**Image** — `docker compose build` (cache vide, compilation complète) : **EXIT_CODE=0**, aucune erreur.

| Image | Taille |
|---|---|
| `saas_...-celery-worker` | 1,47 Go (CLI Docker + toolchain scanners) |
| `saas_...-web` / `-staticfiles` / `-celery-beat` | 347 Mo |
| `saas_...-frontend` | 49,6 Mo |
| `saas_...-scanner-egress-guard` | 12,7 Mo |

**Services** — `docker compose up -d` : 11 conteneurs actifs + `staticfiles` et `wordpress-init` sortis avec code 0 ; 7 volumes neufs ; `presence_scanner_sandbox` et le réseau par défaut recréés par Compose.

**Contrôles réussis**
- `python manage.py check` → aucun problème ; `makemigrations --check --dry-run` → aucun changement.
- **78 migrations appliquées, 0 en attente** ; `scans.0007_scan_partial_status` appliquée ; contrainte `scan_status_valid` accepte `partial`.
- `GET https://localhost/api/v1/health/` → **200** `{"status":"ok","service":"presence-api","dependencies":{"database":true,"redis":true}}`.
- Redis `PING` → `PONG` ; `celery -A config inspect ping` → 1 nœud, `pong`.
- `https://localhost/` → 200 ; `http://localhost/` → 301 (`SECURE_SSL_REDIRECT`) ; `/api/v1/health/` via nginx → 200.
- Volume d'archives monté sur le worker (`scanner_archive_data → /app/scanner-archives`), répertoire `drwx------ app:app` (0700), écriture puis relecture OK, fichier de test supprimé.
- Base neuve et propre : 0 utilisateur, 0 site, 0 scan, 0 run, 0 constat ; procédure documentée du `README` appliquée → `manage.py create_plans` → 4 plans (Free, Pro, Business, Agency).
- Aucun conteneur de scan résiduel ; logs web/worker/frontend sans erreur.

**Contrôles non effectués / limites**
- **Aucun scan n'a été relancé** (hors périmètre de cette mission) : la pile est vérifiée sur la santé, l'API, les migrations et les montages, **pas** par un cycle de scan réel.
- Les six scanners avancés (nmap, nikto, whatweb, testssl, dnsrecon, gobuster) restent absents de l'image du worker : les scans `full`/`security` resteront `partial` (mission suivante, à traiter séparément).
- Pas de superutilisateur (identifiants non inventés) : `docker compose exec web python manage.py createsuperuser` à lancer.
- Validation navigateur non refaite (contrôles HTTP uniquement).
- `GET /static/admin/css/base.css` → **404, comportement préexistant** : la configuration nginx du frontend (`nginx.conf`, non modifié par cette mission) ne contient aucune `location /static/`. Ce n'est pas une régression liée à la remise à zéro.

## 10. Erreurs rencontrées et actions restantes

**Erreurs**
1. Suppression involontaire de l'image de sandbox `projectdiscovery/nuclei:latest` → restaurée à l'identique (digest et version `v3.11.1` vérifiés).
2. `sudo` indisponible dans l'environnement : le nettoyage système a nécessité **une** demande d'élévation (approuvée) ; aucune autre opération privilégiée n'a été exécutée.
3. La copie des archives était initialement en `root:root 0600` (illisible pour vous) → propriété réattribuée à `elom:elom`.

**Reste récupérable mais volontairement préservé**
- Cache de build reconstitué après reconstruction : 2,2 Go (842 Mo récupérables).
- Images non liées à Presence : ≈ 10,8 Go récupérables (librechat-dev 2,63 Go, jupyterlab 1,33 Go, freqtrade, quant_lab, grafana, image ECR…).
- `/var/log/atop` 466 Mo ; journaux `syslog` courant 498 Mo.
- Anciens jeux de sauvegarde (`postgres_data_20261014_151013.tar.gz` 15 Mo, `presence_full_20261014_151013.sql.gz` 1,3 Mo, jeux du 21/10).
- Caches utilisateur hors périmètre Docker : `~/.cache/ms-playwright` 2,0 Go, navigateurs 1,9 Go, `pip`+`pnpm` 255 Mo.
- Disque : 19 G libres, 92 % — la marge est confortable mais pas illimitée.

**Cause de la croissance des journaux identifiée** : `csc_vpnagent` journalise toutes les 30 secondes (`syslog` ≈ 0,5 Go par rotation) et s'y ajoutent les messages `apparmor`/`bwrap`. Recommandation : filtrer ce flux (rsyslog) ou réduire la rétention, sinon `/var/log` regagnera plusieurs centaines de Mo par jour.

## 11. Statut final

- Ressources Docker locales autorisées supprimées : **oui** (15 conteneurs, 10 volumes, 3 réseaux, images du projet et caches).
- Volumes hors périmètre préservés : **oui** (ai-platform, grid_trading_bot, presence-validation).
- Caches inutiles nettoyés : **oui** (cache de build 11,76 Go, APT 1,1 Go, journaux tournés).
- Gain d'espace mesuré : **oui** — 6,3 G → 19 G libres (pic 20,8 G).
- Code source, configurations, sauvegarde PostgreSQL et rapports protégés conservés : **oui**.
- Pile `presence-validation` préservée : **oui**.
- Environnement local Presence reconstruit et testé : **oui** — migrations appliquées, API/DB/Redis sains, volume d'archives opérationnel ; **aucun scan de bout en bout relancé**, donc non revalidé fonctionnellement sur le chemin de scan.

**Conclusion** : remise à zéro et nettoyage **réalisés et vérifiés** ; environnement reconstruit et sain au niveau infrastructure, API, base et migrations. La validation par un scan réel reste à faire, et l'installation des scanners avancés reste un travail séparé.
