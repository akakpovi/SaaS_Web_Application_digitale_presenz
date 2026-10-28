# Presence — Lot 2 : migration vers des URLs anglaises dédiées `/en/...`

Date : 2026-10-28
Dépôt : `~/Schreibtisch/SaaS_Web_Application_digitale_presenz/SaaS_Web_Application_digitale_presenz_v2`
Frontend : `SaaS_Web_Application_UI_UX_frontendV2`
Branche : `main`
Statut global : **VALIDÉ TECHNIQUEMENT pour le lot 2**, avec les limites explicitement listées en §9.
Aucun commit, aucun push, aucun déploiement distant, aucune modification nginx.

---

## 1. Périmètre

Le lot 2 ajoute des URLs anglaises dédiées `/en/...` tout en conservant :

- les URLs allemandes nues, identiques et toujours canoniques ;
- l’alias historique `?lang=en`, fonctionnel ;
- le dossier interne `_i18n/`, toujours écrit et toujours `internal` dans nginx ;
- le routeur React, les pages et les composants existants.

Hors périmètre, non réalisé : redirections 301, modification de `nginx.conf`, suppression de `_i18n` ou de `?lang=en`, migration des liens internes, changement du sélecteur de langue.

---

## 2. Plan appliqué

1. **Routeur** — les 29 routes publiques indexables sont déclarées une seule fois (`PUBLIC_ROUTES` dans `src/App.tsx`) et montées deux fois : chemins nus (allemand) et `/en/...` (anglais). Les routes privées et d’authentification gardent leur URL unique et ne sont pas montées sous `/en`.
2. **Langue** — `localeFromPath()` lit `/en` ; `localizedPath()` produit l’URL d’une page dans une langue ; `RouteLocaleSync` aligne la langue de l’interface sur l’URL (le chemin gagne sur `?lang=`, qui reste le repli).
3. **Pré-rendu** — `prerender.mjs` écrit désormais, pour chaque route indexable :
   - `dist/<route>/index.html` (allemand, inchangé) ;
   - `dist/en/<route>/index.html` (anglais, **nouvelle URL canonique**) ;
   - `dist/_i18n/<route>/index.html` (alias `?lang=en`, conservé).
   Chaque fichier est rendu par le même `entry-server.tsx` avec un `StaticRouter` positionné sur l’URL exacte qu’il sert.
4. **Canonical / hreflang** — une seule fonction (`localizedPath`) alimente le canonical, les `hreflang`, le sitemap et le rendu React. `?lang=en` n’est plus une URL canonique : son canonical pointe vers `/en/...`.
5. **Sitemap** — 29 routes indexables × 2 langues + 8 articles = **66 URL** (voir §3).

### Pourquoi aucune modification nginx n’est nécessaire

La règle existante `location / { try_files $html_variant$uri/index.html $uri/index.html $uri =404; }` résout déjà `/en/pricing` vers `/en/pricing/index.html` : `$uri` vaut `/en/pricing`, donc `$uri/index.html` existe. `$html_variant` reste vide sans `?lang=en`. Aucun bloc, aucune redirection, aucun `map` n’a été ajouté. `nginx.conf` n’a pas été modifié (mtime `2026-10-27 22:24:21`, antérieur au lot).

---

## 3. Comptage exact du sitemap

| Élément | Nombre |
| --- | --- |
| Routes déclarées dans `src/seo/routes.json` | 34 |
| dont `noindex` (login, register, forgot-password, reset-password, onboarding) | 5 |
| Routes indexables | 29 |
| URLs allemandes (chemins nus) | 29 |
| URLs anglaises (`/en/...`, dont `/en` pour l’accueil) | 29 |
| Articles CMS pré-rendus (langue propre, slug propre, pas de doublon `/en/blog/...`) | 8 |
| **Total sitemap** | **66** |

Le chiffre de 66 est donc confirmé. Il n’inclut ni `_i18n`, ni `?lang=`, ni les routes privées.

---

## 4. Fichiers modifiés et mapping vers Docker Compose

Tous les fichiers sont dans `SaaS_Web_Application_UI_UX_frontendV2`. **Un seul service est concerné : `frontend`.** Aucun fichier backend, base de données, WordPress, nginx ou compose n’a été modifié dans ce lot.

| Fichier | Rôle | Service(s) |
| --- | --- | --- |
| `src/App.tsx` | table `PUBLIC_ROUTES` montée en DE et sous `/en`, `RouteLocaleSync` | `frontend` |
| `src/components/RouteLocaleSync.tsx` (nouveau) | langue dérivée de l’URL après hydratation | `frontend` |
| `src/components/SEO.tsx` | canonical/hreflang/variant depuis le chemin puis `?lang=` | `frontend` |
| `src/i18n/index.tsx` | `EN_PREFIX`, `localeFromPath`, `localizedPath`, canonical/hreflang | `frontend` |
| `src/entry-server.tsx` | URL exacte du fichier rendu (`/en/...` ou alias) | `frontend` |
| `scripts/prerender.mjs` | troisième sortie `en/<route>/index.html`, sitemap 66 | `frontend` (build de l’image) |
| `scripts/check-seo-build.mjs` | garde-fou : canonical `/en`, alias, sitemap, résolution nginx | `frontend` (build) |
| `scripts/verify-nginx.sh` | vérifie `/en/...` et l’alias avec le vrai nginx | `frontend` (test) |
| `e2e/helpers/static-dist.ts` | documentation de la résolution `/en` | `frontend` (test) |
| `e2e/bilingual-shell-dist.spec.ts` | hreflang/canonical `/en`, test de l’alias | `frontend` (test) |
| `e2e/legal-seo-dist.spec.ts` | pages juridiques servies sous `/en` | `frontend` (test) |
| `e2e/public-pages-i18n.spec.ts` | alternates `/en`, navigation réelle `/en/features/...` | `frontend` (test) |
| `e2e/en-urls-dist.spec.ts` (nouveau) | contenu réel, sitemap 66, hydratation `/en` | `frontend` (test) |
| `docs/audits/PRESENCE_EN_URLS_MIGRATION_LOT2_2026-10-28.md` | ce rapport | aucun |

`Dockerfile` et `docker-compose.yml` n’ont **pas** été modifiés dans ce lot ; ils portent les modifications du lot précédent (override `PRERENDER_WP_API_URL` et `network: host`), réutilisées telles quelles.

---

## 5. Comportement des URL

| URL | Fichier servi | Langue | Canonical |
| --- | --- | --- | --- |
| `/pricing` | `dist/pricing/index.html` | de | `/pricing` |
| `/en/pricing` | `dist/en/pricing/index.html` | en | `/en/pricing` |
| `/pricing?lang=en` | `dist/_i18n/pricing/index.html` | en | `/en/pricing` |
| `/pricing?lang=de` | `dist/pricing/index.html` | de | `/pricing` |
| `/en` | `dist/en/index.html` | en | `/en` |
| `/_i18n/...` | — | — | 404 (`internal`) |
| `/en/inconnu` | — | — | 404 réel |

`hreflang` sur toutes les pages indexables : `de` → chemin nu, `en` → `/en...`, `x-default` → chemin nu.

---

## 6. Preuves d’exécution

### 6.1 Build hôte

```text
$ pnpm run build
[prerender] Public origin is https://localhost — canonical/sitemap remain local. Set VITE_BASE_URL before a public deployment.
[prerender] TLS verification disabled for loopback CMS localhost -> 127.0.0.1 (self-signed local certificate).
[prerender] 34 routes × 2 languages (58 SSG pages + 29 ?lang=en aliases) + 8 articles, sitemap 66 URLs, base=https://localhost
[check-seo] origin=https://localhost (local preview — canonical/sitemap stay local)
[check-seo] routes=34 (5 noindex) · pre-rendered=58 · articles=8 · sitemap=66
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
host_build_exit=0 duration=11s
```

### 6.2 Artefacts générés

```text
$ find dist/en -name index.html | wc -l
29

$ grep -o '<html lang="[a-z]*"' dist/en/pricing/index.html
<html lang="en"

$ grep -o '<link rel="canonical" href="[^"]*"' dist/en/pricing/index.html
<link rel="canonical" href="https://localhost/en/pricing"

$ grep -o '<link rel="alternate" hreflang="[^"]*" href="[^"]*"' dist/en/pricing/index.html
<link rel="alternate" hreflang="de" href="https://localhost/pricing"
<link rel="alternate" hreflang="en" href="https://localhost/en/pricing"
<link rel="alternate" hreflang="x-default" href="https://localhost/pricing"

$ grep -o '<link rel="canonical" href="[^"]*"' dist/_i18n/pricing/index.html
<link rel="canonical" href="https://localhost/en/pricing"

$ grep -o '<link rel="canonical" href="[^"]*"' dist/pricing/index.html
<link rel="canonical" href="https://localhost/pricing"

$ grep -c '<loc>' dist/sitemap.xml
66
<loc>https://localhost/</loc>
<loc>https://localhost/en</loc>
<loc>https://localhost/pricing</loc>
<loc>https://localhost/en/pricing</loc>
```

### 6.3 TypeScript

```text
$ pnpm exec tsc --noEmit
tsc_exit=0
```

### 6.4 Contrôle SEO du build

```text
$ pnpm check:seo
[check-seo] origin=https://localhost (local preview — canonical/sitemap stay local)
[check-seo] routes=34 (5 noindex) · pre-rendered=58 · articles=8 · sitemap=66
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
seo_exit=0
```

### 6.5 Contrôle i18n

```text
$ node scripts/check-i18n.mjs
en.json keys: 1858
de.json keys: 1858
✅ German catalogue matches the English reference exactly.
✅ Interpolations match in both languages.
Files with remaining literals: 24
Total remaining literals: 43
i18n_exit=0
```

Les 43 littéraux sont identiques au relevé historique du 27 octobre : ce lot n’en ajoute aucun.

### 6.6 Playwright — suite complète

```text
$ pnpm exec playwright test
Running 40 tests using 1 worker
...
  40 passed (6.5m)
[e2e] e2e accounts removed: 5 | e2e public leads removed: 1
pw_exit=0
```

Répartition : **36 tests préexistants** + **1 test d’alias ajouté** à `bilingual-shell-dist.spec.ts` + **3 tests** dans `en-urls-dist.spec.ts` = **40**. Aucune assertion existante n’a été supprimée ou affaiblie ; les assertions de canonical/hreflang anglaises ont été mises à jour vers la nouvelle URL canonique `/en/...`.

Tests spécifiquement liés au lot :

```text
✓ bilingual-shell-dist.spec.ts › every public URL answers in the language its hreflang entry declares
✓ bilingual-shell-dist.spec.ts › each advertised hreflang URL opens the advertised language
✓ bilingual-shell-dist.spec.ts › the historical ?lang=en URL still serves that English page
✓ bilingual-shell-dist.spec.ts › the hydrated head describes the requested variant, without duplicates
✓ en-urls-dist.spec.ts › the /en URLs ship the real English page, not a translated title
✓ en-urls-dist.spec.ts › the sitemap lists both languages and no alias
✓ en-urls-dist.spec.ts › a browser opening /en/... keeps the English URL and hydrates it
✓ legal-seo-dist.spec.ts › nginx-served legal pages carry their own pre-rendered head in both languages
✓ legal-seo-dist.spec.ts › the pre-rendered legal pages hydrate in German and in English
```

### 6.7 Vrai nginx, vrai `nginx.conf`

```text
$ bash scripts/verify-nginx.sh
[verify-nginx] build origin: https://localhost
— German (default) is the bare path
  ok    pricing DE — /pricing (200)
  ok    pricing DE via ?lang=de (alias) — /pricing?lang=de (200)
  ok    impressum DE — /impressum (200)
  ok    home DE via ?lang=de — /?lang=de (200)
— English lives at /en (its own canonical URL)
  ok    pricing EN lang — /en/pricing (200)
  ok    pricing EN title — /en/pricing (200)
  ok    pricing EN canonical — /en/pricing (200)
  ok    impressum EN title — /en/impressum (200)
  ok    home EN — /en (200)
  ok    blog listing EN — /en/blog (200)
— The historical ?lang=en URL still serves the same page
  ok    pricing EN alias lang — /pricing?lang=en (200)
  ok    pricing EN alias canonical — /pricing?lang=en (200)
  ok    impressum EN alias title — /impressum?lang=en (200)
  ok    home EN alias — /?lang=en (200)
  ok    login EN shell — /login?lang=en (200)
  ok    login EN stays noindex — /login?lang=en (200)
— The variant folder is internal, unknown URLs stay 404
  ok    variant folder not addressable — /_i18n/pricing/index.html (404)
  ok    variant home not addressable — /_i18n/index.html (404)
  ok    unknown URL is a real 404 — /definitely-not-a-page?lang=en (404)
  ok    unknown URL is a real 404 (DE) — /definitely-not-a-page (404)
  ok    unknown /en URL is a real 404 — /en/definitely-not-a-page (404)
— Non-HTML assets and client-rendered routes keep working
  ok    sitemap unaffected by ?lang=en — /sitemap.xml?lang=en (200)
  ok    sitemap lists the English URL — /sitemap.xml (200)
  ok    robots.txt — /robots.txt (200)
  ok    SPA shell for /app/ (unchanged) — /app/dashboard?lang=en (200)
— Security headers still applied by the real config
  ok    header Strict-Transport-Security
  ok    header X-Frame-Options: DENY
  ok    header X-Content-Type-Options: nosniff
✅ nginx.conf serves every advertised language variant (real nginx, real config).
nginx_exit=0
```

---

## 7. Synchronisation locale (cycle validé)

Mapping : **tous les fichiers du lot → service `frontend` uniquement**. Aucun backend, base, CMS, nginx partagé ou volume n’est concerné.

Le bug Compose/BuildKit documenté au lot précédent est toujours présent : `docker compose build frontend` échoue sur l’entitlement `network.host`. Le contournement Bake équivalent a donc été réutilisé.

```text
previous_image=sha256:193c54d2da387a6363049040179b1e86b49da8369b02eb48a58cdfa00e9a1555
bake_json_exit=0
bake_build_exit=0 duration=38s
#18 writing image sha256:3df1a75a701374c4b78f6e3db960857686b6b97600fc3570bf64500138061b81 done

$ docker compose up -d --no-deps frontend
 Container ...-frontend-1 Recreate
 Container ...-frontend-1 Recreated
 Container ...-frontend-1 Started
up_exit=0
```

Conteneurs modifiés (diff avant/après) :

```text
9c9
< 9dd4094ff31c  ...-frontend-1  Up 55 minutes (healthy)
---
> a66a69fadcd1  ...-frontend-1  Up Less than a second (health: starting)
```

Aucun autre conteneur n’apparaît dans le diff.

Vérifications du contenu réellement servi :

```text
$ curl -skI https://127.0.0.1/en/pricing
HTTP/2 200
server: nginx/1.27.5
content-type: text/html

$ sha256sum dist/en/pricing/index.html /tmp/en-pricing-served.html
8724af76c0c78b363cdf42381cddf238226a8db7c733d4420c725ce58c513ebe  dist/en/pricing/index.html
8724af76c0c78b363cdf42381cddf238226a8db7c733d4420c725ce58c513ebe  /tmp/en-pricing-served.html

$ docker exec <frontend> sha256sum /usr/share/nginx/html/en/pricing/index.html /usr/share/nginx/html/index.html
8724af76c0c78b363cdf42381cddf238226a8db7c733d4420c725ce58c513ebe  /usr/share/nginx/html/en/pricing/index.html
b6b8192721f03504de535ee70b4e61850971692b69e14dec3efd27e2d110cd0b  /usr/share/nginx/html/index.html

$ sha256sum dist/index.html
b6b8192721f03504de535ee70b4e61850971692b69e14dec3efd27e2d110cd0b  dist/index.html

$ grep -oE "€[0-9]+" served
€0
€29
€79
€9

$ grep -oE ">Free<|>Pro<|>Business<|>Agency<" served
>Agency<
>Business<
>Free<
>Pro<

$ curl -sk https://127.0.0.1/en/pricing | grep canonical
<link rel="canonical" href="https://localhost/en/pricing"

$ curl -sk https://127.0.0.1/en/pricing | grep '<html lang'
<html lang="en"

$ curl -sk https://127.0.0.1/pricing?lang=en | grep canonical
<link rel="canonical" href="https://localhost/en/pricing"

$ curl -sk https://127.0.0.1/sitemap.xml | grep -c '<loc>'
66
$ ... | grep -c '/en'
29
```

Image en cours d’exécution : `sha256:3df1a75a701374c4b78f6e3db960857686b6b97600fc3570bf64500138061b81`. L’image précédente (`193c54d2…`) reste disponible localement pour un retour arrière.

---

## 8. Tests ajoutés ou adaptés

- `e2e/bilingual-shell-dist.spec.ts` : hreflang et canonical dérivés de `/en`, test **« the historical ?lang=en URL still serves that English page »** (statut 200, `lang=en`, canonical `/en`, alternates).
- `e2e/en-urls-dist.spec.ts` (nouveau) :
  1. contenu réel des pages `/en` (landing, pricing et ses prix, FAQ réponse, impressum + avertissement de brouillon, sections de la page fonctionnalité) ;
  2. sitemap : 66 URL, les deux langues, `/en` présent, aucun `?`, aucun `_i18n`, aucune duplication d’article sous `/en`, chaque URL résolue et servie ;
  3. navigateur : `/en/pricing` hydrate, conserve l’URL, publie un canonical unique `/en/pricing` ; `/en` est chargé par une seconde navigation réelle et publie `/en`.
- `e2e/legal-seo-dist.spec.ts` : les pages juridiques sont vérifiées sur `/en/...` et l’alias `?lang=en` est contrôlé séparément ; sitemap : entrées anglaises présentes, `_i18n` absent.
- `e2e/public-pages-i18n.spec.ts` : `hreflang="en"` pointe vers `/en/...`, le canonical anglais pointe vers `/en/...`, et `/en/features/ssl-monitoring` est ouvert dans le navigateur (langue, h1, URL, canonical).

---

## 9. Limites et réserves (assumées, non corrigées dans ce lot)

1. **Liens internes des pages `/en`** — les composants publics rendent encore des liens vers les chemins nus (`/pricing`, `/features/...`, `/register`). Une navigation *cliquée* depuis `/en` quitte donc le préfixe anglais, même si la page de destination reste traduite par l’état i18n. Ce point relève du lot 3 (liens conscients de la langue, ou redirections).
2. **Sélecteur de langue** — il change la langue sur place sans réécrire l’URL, comportement préexistant conservé (test `switching the language keeps the canonical on the requested URL`). Il ne bascule pas encore `/en/pricing` ↔ `/pricing`.
3. **`/en` et nginx** — aucune règle dédiée : le fonctionnement repose sur la règle générique `try_files` existante. C’est volontaire (contrainte du lot), mais une revue nginx restera nécessaire si le lot 3 introduit des redirections.
4. **Articles CMS** — pas de `/en/blog/<slug>` : chaque traduction possède son propre slug, comme avant. Les articles restent hors du préfixe `/en`.
5. **Origine locale** — le build courant utilise `https://localhost` (canonical et sitemap locaux). Une mise en production exige `VITE_BASE_URL` ; le contrôle `--require-public-origin` n’a pas été exécuté.
6. **Compose/BuildKit** — `docker compose build frontend` échoue toujours sur `network.host` ; le cycle a été exécuté via `docker compose build --print` + `docker buildx bake --allow network.host`. Le contournement est documenté, pas corrigé dans le dépôt.
7. **Pas de revue juridique** — ce lot ne touche pas au contenu juridique et ne vaut pas validation des mentions, AGB, Datenschutz ou Widerruf.

---

## 10. Statuts

### VALIDÉ TECHNIQUEMENT

- `tsc --noEmit` : exit 0.
- `pnpm run build` : exit 0 ; 58 pages SSG + 29 alias + 8 articles ; sitemap 66.
- `pnpm check:seo` : exit 0.
- `node scripts/check-i18n.mjs` : exit 0, parité 1858/1858, 43 littéraux inchangés.
- `pnpm exec playwright test` : 40/40, exit 0 (dont 36 préexistants).
- `bash scripts/verify-nginx.sh` : exit 0, vrai nginx.
- Synchronisation Docker : build exit 0, `up` exit 0, SHA-256 identiques hôte / servi / conteneur, seuls les prix et plans attendus, canonical `/en/pricing`, sitemap 66 dont 29 `/en`.
- Aucun autre conteneur recréé ou arrêté.

### ÉCHEC

- Aucun.

### BLOQUÉ

- Aucun pour ce lot.

### À VÉRIFIER MANUELLEMENT

- Rendu visuel de `/en`, `/en/pricing`, `/en/faq`, `/en/impressum` sur mobile et desktop (les tests couvrent le HTML et l’hydratation, pas une revue visuelle).
- Comportement attendu des liens internes depuis `/en` (limite §9.1) : décision produit à prendre pour le lot 3.
- Validation juridique des pages : hors périmètre, toujours en brouillon.

---

## 11. Confirmations

- **Aucun commit, aucun push, aucun déploiement distant.**
- **Aucune modification de `nginx.conf`** : mtime `2026-10-27 22:24:21`, antérieur au lot ; `verify-nginx.sh` lit ce fichier tel quel.
- **Aucune redirection 301**, aucun début de lot 3.
- **`_i18n` et `?lang=en` toujours présents et fonctionnels** ; leur canonical pointe désormais vers `/en/...` pour éviter deux canoniques concurrentes.
- **URLs allemandes inchangées** : `/pricing`, `/impressum`, `/faq`, etc. servent toujours le même fichier et le même canonical.
- **Aucun autre service Docker touché** : seul `frontend` a été recréé ; producteurs, base, Redis, WordPress, Mailpit et scanners sont restés intacts.
- **Aucun fichier hors périmètre modifié dans ce lot** : la liste des fichiers modifiés depuis le début du lot (mtime < 150 min, hors `Dockerfile` du lot précédent) correspond exactement aux 13 fichiers listés en §4.
- L’état Git reste à **321 entrées non commitées**, identique à l’état initial ; les nouveaux fichiers du lot sont dans des sous-arbres déjà non suivis (`e2e/`, `scripts/`, `src/`), ce qui explique que le compteur global ne change pas.
