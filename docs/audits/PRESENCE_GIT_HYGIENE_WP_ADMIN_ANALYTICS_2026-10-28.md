# Presence — Assainissement Git, accès WordPress admin, plan analytics

**Date :** 2026-10-28
**Dépôt :** `SaaS_Web_Application_digitale_presenz` (remote `origin`, branche `main`)

---

## Partie 1 — Assainissement Git et publication

### 1.1 Statut initial des six fichiers

| Fichier | Index | Historique (`git log --all`) |
|---|---|---|
| `omniroute_key.txt` | non suivi | 0 commit |
| `presence_before_migration_repair_20260909_135204.sql` | non suivi | 0 commit |
| `SaaS_Web_Application_digitale_presenz_v2/Comptes existants ID E.txt` | non suivi | 0 commit |
| `compte de teste.docx` | non suivi | 0 commit |
| `nginx/ssl/presence.key` | non suivi (déjà couvert par `.gitignore:29 nginx/ssl/`) | 0 commit |
| `scripts/integrated_acceptance_recipe.py` | non suivi | 0 commit |

Aucun `git rm --cached` n'a donc été nécessaire : **aucun de ces fichiers n'a jamais été versionné**.

### 1.2 Déplacement hors dépôt

Quarantaine : `/home/elom/presence-secrets-quarantine-20261028` (droits `700`), arborescence conservée.
Les sept fichiers déplacés (les six + `presence.crt`, apparié à la clé) ont été vérifiés par empreinte avant/après :

```
omniroute_key.txt: OK
presence_before_migration_repair_20260909_135204.sql: OK
SaaS_Web_Application_digitale_presenz_v2/Comptes existants ID E.txt: OK
compte de teste.docx: OK
nginx/ssl/presence.key: OK
nginx/ssl/presence.crt: OK
scripts/integrated_acceptance_recipe.py: OK
exit=0
```

Une nouvelle paire TLS locale a été générée par `bash scripts/setup_local_tls.sh` (exit 0) pour que nginx continue de démarrer ; elle reste couverte par `nginx/ssl/` et n'est jamais versionnable.

### 1.3 `.gitignore`

Ajout à la racine :

```
omniroute_key.txt
presence_before_migration_repair_*.sql
SaaS_Web_Application_digitale_presenz_v2/Comptes existants ID E.txt
compte de teste.docx
scripts/integrated_acceptance_recipe.py   # recette avec mot de passe de fixture en dur
```

`nginx/ssl/` y figurait déjà.

### 1.4 Preuve d'absence

```
$ git status --porcelain | grep -E 'omniroute_key|migration_repair|Comptes existants|compte de teste|presence\.key|integrated_acceptance_recipe'
grep_exit=1        # aucun motif

$ union suivie + non suivie | grep -E '...|\.key$|\.crt$|...'
union_grep_exit=1  # aucun motif
```

Le statut est passé de 322 à 318 entrées : les quatre entrées visibles disparues sont les quatre fichiers non ignorés déplacés ; les deux autres étaient déjà masqués par `nginx/ssl/` et par le répertoire `scripts/` non suivi.

### 1.5 Commits (liste blanche explicite, jamais `git add -A`)

Chaque lot a été construit depuis `git status --porcelain -z --untracked-files=all`, contrôlé par grep anti-secrets, puis committé avec `--pathspec-from-file` :

| Hash | Message | Fichiers |
|---|---|---|
| `5f727f9` | `feat(ssg): prerender public pages with real content at build time` | 123 |
| `8a60a58` | `feat(i18n): publish English pages under /en with bilingual SEO` | 11 |
| `b9599dd` | `feat(nginx): redirect ?lang= to canonical URLs and keep tracking params` | 5 |
| `94377bc` | `feat(backend): land scanner, billing and i18n work in progress` | 352 |

Une entrée `AD` périmée (`src/pages/PublicReport.tsx`, ajoutée à l'index puis absente du disque, non référencée par le routeur) a été retirée de l'index avec `git rm --cached` avant les commits.

**Non committés volontairement** (16 entrées) : le ZIP `SaaS Web Application UI_UX_frontendV2.zip`, le doublon `SaaS_Web_Application_UI_UX_frontendV2/`, `.figma/`, quatre `*.bak`, neuf journaux `logs/*.log`.

### 1.6 Push

```
$ git push origin main
To https://github.com/akakpovi/SaaS_Web_Application_digitale_presenz.git
   3b2206f..94377bc  main -> main
push_exit=0
```

Vérification distante :

```
$ git ls-remote origin refs/heads/main
94377bcced3eae9cefffeb7fa7209cdc4a06bb30  refs/heads/main
```

Remote unique `origin`, branche `main`, aucune ambiguïté.

---

## Partie 2 — WordPress admin en local

### 2.1 Diagnostic

```
$ curl -s -D - http://127.0.0.1:8081/wp-admin/
HTTP/1.1 302 Found
Location: http://localhost/cms/wp-login.php?redirect_to=http%3A%2F%2F127.0.0.1%3A8081%2Fwp-admin%2F&reauth=1

$ curl -sk -D - https://127.0.0.1/cms/wp-login.php
HTTP/2 404
```

`WP_HOME` valait `http://localhost/cms`, et `nginx.conf` renvoie délibérément `404` sur `/cms/` (l'admin n'est jamais proxifié). D'où une boucle fermée : `:8081` → `/cms/wp-login.php` → 404.

### 2.2 Correction retenue

Parmi les deux options, la **correction de `WP_HOME`** est la moins risquée : elle n'ouvre aucune route publique supplémentaire et ne touche ni `/cms/wp-json/` ni `/cms/wp-content/`.

`docker-compose.yml` : la valeur par défaut de `WORDPRESS_URL` passe de `http://localhost/cms` à `http://localhost:8081` (4 occurrences). L'admin est donc `http://localhost:8081/wp-admin/`, en loopback uniquement, comme le port publié l'impose déjà.

Un commentaire documente le piège et l'URL correcte. Sauvegardes horodatées hors Git : `/home/elom/presence-config-backups/{docker-compose.yml,nginx.conf}.20261028-131146`.

### 2.3 Vérification réelle (session authentifiée)

```
$ curl -s -D - http://localhost:8081/wp-admin/
HTTP/1.1 302 Found
Location: http://localhost:8081/wp-login.php?redirect_to=http%3A%2F%2Flocalhost%3A8081%2Fwp-admin%2F&reauth=1

$ curl -s http://localhost:8081/wp-login.php
http_code=200 size=4419
<title>Log In &lsaquo; Presence Blog &#8212; WordPress</title>

$ POST /wp-login.php
code=302 redirect=http://localhost:8081/wp-admin/

$ GET /wp-admin/ (avec session)
code=200 size=104140
<title>Dashboard &lsaquo; Presence Blog &#8212; WordPress</title>
id="dashboard-widgets" → 1
```

Le tableau de bord s'affiche réellement. Aucun mot de passe modifié.

### 2.4 Isolation des services

Seul `wordpress-1` a été recréé (`docker compose up -d --no-deps wordpress`, exit 0). `StartedAt` des autres conteneurs inchangés, y compris les projets voisins :

```
presence-validation-*            2026-10-26T08:40 → 09:10
presence-variant-check           2026-10-27T20:28
...-celery-beat-1                2026-10-27T09:58
...-frontend-1                   2026-10-28T11:27
...-web-1                        2026-10-27T09:58
...-wordpress-1                  2026-10-28T12:12  ← seul recréé
```

### 2.5 Cycle de synchronisation

`bash scripts/build-frontend.sh` → exit 0 (buildx bake + `up -d --no-deps frontend`). Premier cycle : image identique, conteneur laissé `Running`.

Empreintes avant/après ce cycle :

```
avant  /            bc0d5ad2784ab0a1421bbf8ca6b48d10dba779262774a11dc59988ccdd98a6d7
après  /            bc0d5ad2784ab0a1421bbf8ca6b48d10dba779262774a11dc59988ccdd98a6d7
avant  /en/pricing  d09ad338d93e7ade60cea45b8909182c4724fe44c714c66c95f36886c8595c10
après  /en/pricing  d09ad338d93e7ade60cea45b8909182c4724fe44c714c66c95f36886c8595c10
```

`GET https://127.0.0.1/` → `HTTP/2 200`, sitemap 66 `<loc>`, `/cms/wp-json/wp/v2/posts` → 200, `verify-nginx.sh` → exit 0.

---

## Partie 3 — Analytics : décision et scaffolding

Plan complet : [PRESENCE_ANALYTICS_PLAN_2026-10-28.md](PRESENCE_ANALYTICS_PLAN_2026-10-28.md).

**Décision : Umami auto-hébergé**, base dédiée dans le PostgreSQL 16 existant. Motifs : aucun transfert tiers, aucun cookie, une seule brique à exploiter, rapport Campagnes (UTM) natif, licence MIT. Plausible CE impose ClickHouse ; Matomo ajoute PHP + MySQL et son image « outil à consentement » dessert le positionnement du site.

### Scaffolding livré, inerte par construction

| Fichier | Contenu |
|---|---|
| `src/lib/analytics.ts` | `isAnalyticsEnabled()`, `trackEvent()`, `trackPageview()` — double garde (`VITE_ANALYTICS_ENABLED === "true"` **et** `window.umami` présent), no-op en SSR |
| `.env.example` | `VITE_ANALYTICS_ENABLED=false`, `VITE_ANALYTICS_WEBSITE_ID=`, `VITE_ANALYTICS_SCRIPT_URL=/stats/script.js` |
| `index.html` | marqueur `<!-- presence:analytics -->` dans `<head>`, aucun script |
| `.gitignore` (frontend) | `!.env.example` pour que le gabarit soit enfin versionnable |

### Preuves d'inertie

```
$ pnpm exec tsc --noEmit
tsc_exit=0

$ curl -sk https://127.0.0.1/ | grep -c 'presence:analytics'
1
$ curl -sk https://127.0.0.1/ | grep -c '/stats/script.js'
0
```

Le second build (avec marqueur) a recréé le conteneur : `dist/index.html` hôte et HTML servi sont identiques à l'octet —

```
cbb4729371ff65e584ddc79ea21c4e1e5c66d4f34051ce5d607242ae518304e7  dist/index.html
cbb4729371ff65e584ddc79ea21c4e1e5c66d4f34051ce5d607242ae518304e7  servi /
851b6dac74fe865171ee3de1cba684565fae939fa9bb2cd1e99738b6040df4bd  servi /en/pricing
```

Contrôles ciblés après rebuild : `verify-nginx.sh` exit 0 ; Playwright `ssg-dist` + `legal-seo-dist` + `bilingual-shell-dist` = **20 passed**, exit 0.

Aucun conteneur Umami n'existe, aucune requête n'est émise, aucun événement n'est instrumenté.

### Porte juridique (bloquante)

L'activation réelle est conditionnée à six points, détaillés dans le plan : finalisation des pages Datenschutz/Cookies (encore en brouillon), décision de base légale avec un juriste (§ 25 TDDDG, art. 6 RGPD), rétention et anonymisation, sous-traitants, mise à jour de la politique cookies, validation écrite. **Aucun test technique ne peut lever ce blocage.**

---

## Statut

| Élément | Statut |
|---|---|
| Secrets hors du dépôt, `.gitignore` en place | **VALIDÉ TECHNIQUEMENT** |
| Six fichiers absents de l'arbre suivi et de l'historique | **VALIDÉ TECHNIQUEMENT** |
| Quatre commits par lot | **VALIDÉ TECHNIQUEMENT** |
| Push `main` → `origin` | **VALIDÉ TECHNQUEMENT** (`3b2206f..94377bc`) |
| Admin WordPress accessible en local | **VALIDÉ TECHNIQUEMENT** (login réel, Dashboard 200) |
| Isolation des autres services | **VALIDÉ TECHNIQUEMENT** (`StartedAt` inchangés) |
| Scaffolding analytics inerte | **VALIDÉ TECHNIQUEMENT** |
| Activation analytics | **BLOQUÉ** — pages juridiques en brouillon |
| Conformité RGPD/TDDDG | **À VÉRIFIER PAR UN JURISTE** |

### Reste non committé (à la décision de l'utilisateur)

`docker-compose.yml` (WP_HOME), `index.html` (marqueur), `src/lib/analytics.ts`, `.env.example`, `.gitignore` frontend, ce rapport et le plan analytics — plus les 16 artefacts volontairement exclus.
