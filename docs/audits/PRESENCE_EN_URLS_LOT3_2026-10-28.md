# Presence — Lot 3 : liens conscients de la langue + 301 + nettoyage nginx

**Date :** 28 octobre 2026
**Dépôt :** `~/Schreibtisch/SaaS_Web_Application_digitale_presenz/SaaS_Web_Application_digitale_presenz_v2`
**Périmètre :** frontend uniquement (`SaaS_Web_Application_UI_UX_frontendV2`)
**Phases :** 3a (liens internes) puis 3b (redirections 301 + nettoyage nginx), séquentielles.

**Statut global : `VALIDÉ TECHNIQUEMENT`** pour les deux phases, avec les limites assumées de la section 8.
Aucun commit, aucun push, aucun déploiement distant, aucun autre service Docker touché.

---

## 1. Ce qui a changé, en une page

| Sujet | Avant (lot 2) | Après (lot 3) |
| --- | --- | --- |
| Liens internes sur une page anglaise | `<Link to="/pricing">` → URL allemande | `/en/pricing` (composant `LocaleLink`) |
| `?lang=en` sur une route publique | 200, HTML anglais servi depuis `dist/_i18n/` | **301** vers `/en/<route>` |
| `?lang=de` sur une route publique | 200, page allemande | **301** vers `/<route>` |
| Autres paramètres (`utm_*`, …) | perdus par le 301 | **conservés** (sauf `lang`), ordre d'origine |
| `_i18n` des 29 routes publiques | 29 fichiers générés | **0** (nginx redirige avant `try_files`) |
| `_i18n` des 5 routes noindex | 5 fichiers | **5** (inchangé, toujours servis en 200 direct) |
| Sitemap | 66 URLs | **66 URLs**, aucune entrée `?lang=` ni `_i18n` |
| `hreflang` / `canonical` | `/en/...` | inchangés |

La liste des 29 routes redirigées n'est **pas** recopiée à la main : elle est générée depuis
`src/seo/publicPaths.ts`, la même source que le routeur React, `LocaleLink` et `check-seo-build.mjs`.

---

## 2. Phase 3a — liens internes conscients de la langue

### 2.1 Fichiers

| Fichier | Rôle |
| --- | --- |
| `src/components/LocaleLink.tsx` (nouveau) | `<Link>` qui préfixe `/en` **uniquement** les routes de `PUBLIC_PATHS` quand `localeFromPath()` dit `en`. Exporte aussi `localizeTo()` (testable). |
| `src/pages/Landing.tsx`, `Pricing.tsx`, `FAQPage.tsx`, `AboutPage.tsx`, `ContactPage.tsx`, `FeaturePage.tsx`, `SolutionPage.tsx`, `ToolPage.tsx`, `BlogPage.tsx`, `BlogArticle.tsx`, `PrivacyPage.tsx`, `TermsPage.tsx`, `ImpressumPage.tsx`, `CookiesPage.tsx`, `WithdrawalPage.tsx`, `NotFound.tsx` | remplacent `Link` de `react-router-dom` par `LocaleLink` |
| `src/components/Breadcrumb.tsx`, `src/pages/PublicScanResult.tsx` | même remplacement |
| `src/seo/publicPaths.ts` | déjà la source unique (`PUBLIC_PATHS`, `isPublicRoutePath`) ; consommée par le routeur, `LocaleLink`, la carte nginx et le garde-fou SEO |
| `e2e/language-aware-links-dist.spec.ts` (nouveau) | 3 tests (HTML pré-rendu EN, HTML pré-rendu DE, clics réels) |

Règles appliquées (documentées dans le composant) :

- route publique + page `/en/...` → `/en/<route>` ; page allemande → `/<route>` ;
- `/login`, `/register`, `/forgot-password`, `/reset-password`, `/onboarding`, `/scan/…`, `/app/…`
  gardent **une seule URL** (aucun `/en/login`) ;
- `/blog/<slug>` garde son slug : la traduction d'un article a son propre slug, un préfixe `/en`
  pointerait sur un 404 ;
- liens externes, `#ancre`, `mailto:` non touchés.

### 2.2 Preuves (phase 3a)

```
$ pnpm exec tsc --noEmit
tsc exit=0

$ pnpm run build
[prerender] 34 routes × 2 languages (58 SSG pages + 29 ?lang=en aliases) + 8 articles, sitemap 66 URLs, base=https://localhost
[check-seo] routes=34 (5 noindex) · pre-rendered=58 · articles=8 · sitemap=66
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
build exit=0

$ pnpm exec playwright test --list
Total: 43 tests in 12 files

$ pnpm exec playwright test
43 passed (6.9m)
exit=0

$ bash scripts/verify-nginx.sh
28 lignes "ok"
✅ nginx.conf serves every advertised language variant (real nginx, real config).
verify-nginx exit=0
```

HTML servi après synchronisation de l'image de la phase 3a :

```
served /en  → href="/en", /en/about, /en/blog, /en/contact, /en/cookies, /en/faq,
              /en/features/* (8), /en/impressum, /en/pricing, /en/privacy,
              /en/terms, /en/widerruf, href="/login", href="/register"
served /en  → aucun href="/(pricing|faq|about|features|tools)…"
served / (DE) → aucun href="/en…"
dist/index.html = served /  (SHA-256 identique : a52391c6…4b4912 à ce moment-là)
```

---

## 3. Phase 3b — redirections 301 et nettoyage nginx

### 3.1 Architecture retenue

1. **Carte générée** — `scripts/generate-nginx-locale-map.mjs` lit `src/seo/publicPaths.ts` et écrit
   `nginx.locale-map.conf` (gitignoré) :

   ```nginx
   map "$uri|$arg_lang" $presence_locale_redirect {
       default "";
       "/|en" "/en";
       "/|de" "/";
       "/pricing|en" "/en/pricing";
       "/pricing|de" "/pricing";
       … 58 règles (29 routes × 2 langues)
   }
   ```

   `--check` compare le fichier à la source sans écrire ; intégré à `pnpm check:seo`.

2. **nginx.conf** inclut la carte, puis, avant toute sélection de `location` :

   ```nginx
   if ($presence_locale_redirect != "") {
       return 301 $scheme://$http_host$presence_locale_redirect;
   }
   ```

   La cible est absolue et reprend `$http_host` (hôte + port réellement demandés). Un
   `return 301 /en/…` relatif aurait été absolutisé par nginx avec son **port d'écoute interne**
   (`:443`), ce qui casse la redirection dès que le conteneur est publié sur un autre port
   (vérification, préproduction) — mesuré : `Location: https://127.0.0.1/pricing` au lieu de
   `https://127.0.0.1:18443/pricing`.

   `map $arg_lang $html_variant` est conservé : il ne sert plus qu'aux 5 écrans noindex.

3. **Dockerfile** : `COPY --from=builder /app/nginx.locale-map.conf /etc/nginx/conf.d/presence-locale-map.conf`
   (le fichier est produit par `pnpm run build` dans l'étape builder ; sans lui, `include` échoue et
   nginx ne démarre pas).

4. **prerender.mjs** : plus aucune écriture `_i18n` pour une route publique ; `_i18n` reste écrit
   pour les 5 routes noindex (leur `?lang=en` doit continuer à répondre 200, `/en/login` n'existe pas).

### 3.2 Fichiers modifiés

| Fichier | Nature |
| --- | --- |
| `nginx.conf` | include de la carte + règle 301 + commentaires |
| `nginx.locale-map.conf` | **généré**, gitignoré |
| `scripts/generate-nginx-locale-map.mjs` | nouveau générateur (+ `--check`) |
| `Dockerfile` | copie de la carte depuis le builder |
| `package.json` | `build` lance le générateur avant `prerender.mjs` |
| `scripts/prerender.mjs` | suppression des alias publics, compteur `private ?lang=en shells` |
| `scripts/check-seo-build.mjs` | modèle nginx avec `=301`, assertions carte/alias/noindex |
| `scripts/verify-nginx.sh` | carte générée + montée, 301 exacts, suivi sans boucle, privées sans redirection |
| `e2e/helpers/static-dist.ts` | `nginxResolution()` (200/301/404), `Location` absolu |
| `e2e/bilingual-shell-dist.spec.ts` | test « alias 200 » → « 301 + Location + suivi » ; noindex = pas de redirection |
| `e2e/legal-seo-dist.spec.ts` | bloc alias → 301 + Location + URL finale |
| `e2e/ssg-dist.spec.ts` | URLs de contenu `?lang=en` → `/en/…` (assertions identiques) |
| `e2e/locale-redirects-dist.spec.ts` | nouveau, 6 tests |
| `.gitignore` | `nginx.locale-map.conf` |

### 3.3 Mapping fichiers → services Docker

| Fichier(s) | Service | Effet |
| --- | --- | --- |
| `nginx.conf`, `nginx.locale-map.conf`, `Dockerfile`, `dist/` | **`frontend` uniquement** | reconstruit et recréé |
| `src/**`, `scripts/**`, `e2e/**`, `package.json` | **`frontend` uniquement** (image, pas de service runtime) | aucun |
| `docker-compose.yml` | **non modifié** dans ce lot | aucun |
| backend Django, WordPress, base, Redis, Celery, Mailpit, scanner | **non touchés** | aucun |

Sauvegarde de `nginx.conf` avant modification :

```
f9537b73787cbcd8bb57eaf416d6223c662d1b9fd5600a8414c7c40b51953243  nginx.conf
f9537b73787cbcd8bb57eaf416d6223c662d1b9fd5600a8414c7c40b51953243  docs/audits/backups/nginx.conf.2026-10-28_113113
```

(chemin : `SaaS_Web_Application_UI_UX_frontendV2/docs/audits/backups/`, non suivi par Git)

---

## 4. Résultats réels des contrôles

### 4.1 `pnpm exec tsc --noEmit`

```
tsc exit=0
```

### 4.2 `pnpm run build`

```
[locale-map] wrote nginx.locale-map.conf: 29 public routes, 58 301 rules.
[prerender] Public origin is https://localhost — canonical/sitemap remain local. Set VITE_BASE_URL before a public deployment.
[prerender] TLS verification disabled for loopback CMS localhost -> 127.0.0.1 (self-signed local certificate).
[prerender] 34 routes × 2 languages (58 SSG pages + 5 private ?lang=en shells) + 8 articles, sitemap 66 URLs, base=https://localhost
[check-seo] origin=https://localhost (local preview — canonical/sitemap stay local)
[check-seo] routes=34 (5 noindex) · pre-rendered=58 · articles=8 · sitemap=66
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
build exit=0
```

Contenu de `dist/_i18n/` après build :

```
dist/_i18n/forgot-password/index.html
dist/_i18n/login/index.html
dist/_i18n/onboarding/index.html
dist/_i18n/register/index.html
dist/_i18n/reset-password/index.html
count: 5
```

### 4.3 `pnpm check:seo`

```
$ node scripts/generate-nginx-locale-map.mjs --check
[locale-map] nginx.locale-map.conf matches src/seo/publicPaths.ts (29 routes, 58 redirects).
map-check exit=0

$ pnpm check:seo
[check-seo] origin=https://localhost (local preview — canonical/sitemap stay local)
[check-seo] routes=34 (5 noindex) · pre-rendered=58 · articles=8 · sitemap=66
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
check:seo exit=0
```

Nouvelles assertions ajoutées au garde-fou :

- `nginx.conf` inclut la carte et contient la règle `return 301 $scheme://$http_host…` ;
- la carte contient exactement `29 × 2` règles, une par (route publique, langue) ;
- aucune route noindex n'apparaît dans la carte ;
- `dist/_i18n/<route>` **ne doit pas exister** pour une route publique ;
- `dist/_i18n/<route>` **doit exister**, être en anglais, `noindex`, sans canonical pour les 5 privées ;
- `?lang=en` d'une route publique se résout en `=301 /en/…`, `?lang=de` en `=301 /…` ;
- `?lang=en` d'une route noindex se résout vers la coquille `_i18n` (200).

### 4.4 `node scripts/check-i18n.mjs`

```
── Catalogue parity ──────────────────────────────────────────
en.json keys: 1858
de.json keys: 1858
✅ German catalogue matches the English reference exactly.
✅ Interpolations match in both languages.

── Hardcoded user-visible strings (JSX AST) ──────────────────
Files with remaining literals: 24
Total remaining literals: 43
check-i18n exit=0
```

Script **non modifié** dans ce lot ; **43** est la même valeur que l'audit du 27 octobre (référence
historique, pas un contrôle nouveau).

### 4.5 `pnpm exec playwright test`

```
Running 49 tests using 1 worker
…
49 passed (5.9m)
exit=0
```

43 tests préexistants (40 hérités des lots 1–2 + les 3 de la phase 3a) + 6 nouveaux
(`locale-redirects-dist.spec.ts`).

### 4.6 `bash scripts/verify-nginx.sh` (vrai nginx, vrai `nginx.conf`)

```
92 lignes "ok"
✅ nginx.conf serves every advertised language variant (real nginx, real config).
verify-nginx exit=0
```

Extraits (29 routes publiques × `?lang=en`, suivies une seule fois) :

```
ok  /pricing?lang=en → 301 https://127.0.0.1:18443/en/pricing
ok  /pricing?lang=en → 301 → /en/pricing (200, en, 1 hop)
ok  /features/ssl-monitoring?lang=en → 301 → /en/features/ssl-monitoring (200, en, 1 hop)
ok  /tools/email-security-checker?lang=en → 301 → /en/tools/email-security-checker (200, en, 1 hop)
ok  home DE — /?lang=de → 301 → / (200, de, 1 hop)
ok  /login EN shell — /login?lang=en (200)
ok  /login DE — /login?lang=de (200)
ok  /register /forgot-password /reset-password /onboarding (200, aucune redirection)
ok  variant folder not addressable — /_i18n/pricing/index.html (404)
ok  unknown URL is a real 404 — /definitely-not-a-page?lang=en (404)
ok  sitemap unaffected by ?lang=en — /sitemap.xml?lang=en (200)
ok  SPA shell for /app/ (unchanged) — /app/dashboard?lang=en (200)
```

---

## 5. Synchronisation de l'image (local uniquement)

> Cette section décrit le cycle tel qu'il a été exécuté pour le lot 3. Depuis le correctif
> `scripts/build-frontend.sh` (voir §8.1 et §11), la commande unique est
> `bash scripts/build-frontend.sh` ; elle exécute le même build et le même `up -d --no-deps frontend`.

```
$ docker compose build frontend
 Image saas_web_application_digitale_presenz-frontend Building
additional privileges requested: pass "--allow=network.host" to grant requested privileges
build exit=1 duration=1s          ← bug Compose/BuildKit inchangé (voir §8.1)

$ docker buildx build --allow network.host --network host \
    --build-arg VITE_BASE_URL=https://localhost --build-arg VITE_WP_API_URL=/cms \
    --build-arg PRERENDER_WP_API_URL=http://127.0.0.1:8081 \
    -t saas_web_application_digitale_presenz-frontend <contexte>
#15 [locale-map] wrote nginx.locale-map.conf: 29 public routes, 58 301 rules.
#15 [prerender] 34 routes × 2 languages (58 SSG pages + 5 private ?lang=en shells) + 8 articles, sitemap 66 URLs
#15 ✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
#16 COPY --from=builder /app/nginx.locale-map.conf /etc/nginx/conf.d/presence-locale-map.conf
#18 naming to docker.io/library/saas_web_application_digitale_presenz-frontend
build exit=0 duration=57s

$ docker compose up -d --no-deps frontend
Container …-frontend-1 Recreated / Started
up exit=0
```

Conteneurs après l'opération (inchangés sauf `frontend`) :

```
presence-validation-frontend            Up 2 days
presence-validation-validation-web-1    Up 2 days (healthy)
presence-variant-check                  Up 14 hours
…-celery-beat-1                         Up 25 hours
…-celery-worker-1                       Up 25 hours
…-db-1                                  Up 31 hours (healthy)
…-frontend-1                            Up 6 seconds (healthy)
…-mailpit-1                             Up 31 hours (healthy)
…-redis-1                               Up 31 hours (healthy)
…-scanner-egress-guard-1                Up 31 hours (healthy)
…-web-1                                 Up 25 hours (healthy)
…-wordpress-1                           Up 22 hours (healthy)
…-wordpress-db-1                        Up 31 hours (healthy)
```

### Preuves sur le contenu réellement servi (`https://127.0.0.1`)

```
/pricing?lang=en                     301 → https://127.0.0.1/en/pricing
/?lang=en                            301 → https://127.0.0.1/en
/features/ssl-monitoring?lang=en     301 → https://127.0.0.1/en/features/ssl-monitoring
/pricing?lang=de                     301 → https://127.0.0.1/pricing

29 routes publiques : ok=29 bad=0
  (statut 301 + Location exact pour chaque route, sans exception)

/pricing?lang=en      200 hops=1 https://127.0.0.1/en/pricing    <html lang="en"
/?lang=en             200 hops=1 https://127.0.0.1/en            <html lang="en"
/impressum?lang=en    200 hops=1 https://127.0.0.1/en/impressum  <html lang="en"

/login?lang=en              200 loc=        /register?lang=en           200 loc=
/forgot-password?lang=en    200 loc=        /reset-password?lang=en     200 loc=
/onboarding?lang=en         200 loc=

dist/en/pricing   d09ad338d93e7ade60cea45b8909182c4724fe44c714c66c95f36886c8595c10
served /en/pricing d09ad338d93e7ade60cea45b8909182c4724fe44c714c66c95f36886c8595c10
dist/index.html   bc0d5ad2784ab0a1421bbf8ca6b48d10dba779262774a11dc59988ccdd98a6d7
served /          bc0d5ad2784ab0a1421bbf8ca6b48d10dba779262774a11dc59988ccdd98a6d7

sitemap : urls=66  ?lang=:0  _i18n:0
/_i18n/pricing/index.html 404 · /_i18n/index.html 404 · /en/pricing 200
```

---

## 6. Tests modifiés — ancienne vs nouvelle assertion

Aucune assertion supprimée sans remplacement au moins aussi strict. Chaque changement ci-dessous
est un **changement de comportement voulu** (le 200 direct était la conséquence de l'ancien
mécanisme, pas un contrat fonctionnel).

| Fichier / test | Ancienne assertion | Nouvelle assertion | Pourquoi |
| --- | --- | --- | --- |
| `bilingual-shell-dist.spec.ts` — « historical ?lang=en » (renommé « the historical ?lang= URL is a 301 to the canonical URL ») | `GET /pricing?lang=en` → **200**, `<html lang="en">`, canonical `/en/pricing`, 3 alternates | `GET` (sans suivi) → **301** + `Location` exact `http://127.0.0.1:PORT/en/pricing` ; puis `?lang=de` → 301 `…/pricing` ; puis suivi → **200**, URL finale `/en/pricing`, `<html lang="en">`, canonical `/en/…`, 3 alternates | la nouvelle forme est la redirection ; le contenu reste vérifié **après** le saut |
| `bilingual-shell-dist.spec.ts` — « noindex route… » | 200 direct sur `/login?lang=en` | 200 direct **+ absence d'en-tête `Location`** (explicite), puis mêmes vérifications de head | prouve qu'aucune redirection n'a été ajoutée sur une route privée |
| `legal-seo-dist.spec.ts` — `assertPrerenderedLegalRoute` | `?lang=en` → 200 + canonical | **301** + `Location` exact + URL finale `/en/…` + 200 + canonical | même raison |
| `ssg-dist.spec.ts` — landing, pricing, FAQ, feature, legal, hydratation | URLs de contenu `/?lang=en`, `/pricing?lang=en`, … | `/en`, `/en/pricing`, `/en/faq`, … (assertions de contenu inchangées) | le contenu anglais vit désormais sur son URL canonique ; les redirections sont couvertes par le nouveau spec |
| `e2e/helpers/static-dist.ts` | `resolveNginx()` retournait un fichier ou `null` | `nginxResolution()` → `{200,file}` / `{301,location}` / `{404}` ; `resolveNginx()` conservé comme raccourci ; le serveur émet un `Location` absolu comme nginx | le modèle doit refléter la redirection, sinon les specs mentent |
| `locale-redirects-dist.spec.ts` (nouveau) | — | 6 tests : 301 exact sur les 29 routes × 2 langues ; suivi `maxRedirects: 1` + 200 + URL finale ; paramètres supplémentaires supprimés ; 5 privées 200 sans `Location` ; `_i18n` public absent / privé présent ; sitemap 66 sans `?lang=`/`_i18n` | contrat complet de la phase 3b |

---

## 7. Ce qui n'a pas bougé

- `hreflang` (`de`, `en`, `x-default`) et canonical : inchangés, toujours `/en/…` pour l'anglais.
- Sitemap : **66** URLs (29 × 2 + 8 articles), aucune URL `?lang=`, aucun `_i18n`.
- Routes privées : mêmes URL, même comportement, `noindex` préservé.
- Page 404 réelle, `/app/`, `/report/`, `/scan/`, `/blog/<slug>`, `/verify-email`, `/admin`.
- Avertissements « Arbeitsentwurf » des pages juridiques et identité centralisée : inchangés.
- Aucun changement de schéma, de données, de backend, de CMS, ni de `docker-compose.yml`.

---

## 8. Limites et réserves

### 8.1 Compose/BuildKit — corrigé par `scripts/build-frontend.sh`

**Diagnostic (Docker Engine 29.9.1, Compose v5.6.0, buildx 0.38.0, BuildKit v0.34.0, builder par
défaut `docker`).** `docker compose build frontend` échoue avec :

```
additional privileges requested: pass "--allow=network.host" to grant requested privileges
```

Ce n'est ni une faute de syntaxe Compose (`build.network` et `build.entitlements` sont bien
transmis : `docker buildx bake --print` les affiche correctement), ni un bug de version : BuildKit
n'accorde `network.host` que si son propre allow-list le permet, et `docker compose build` n'expose
aucun `--allow` (`docker compose build --help` ne liste que `--builder`). Vérifié aussi **sans**
le bloc `entitlements` — `network: host` seul déclenche le même refus : retirer le bloc ne corrige
rien.

**Correctif retenu** : `scripts/build-frontend.sh`, commande unique documentée. Elle lit
`docker-compose.yml` via `docker buildx bake` (même définition, mêmes args, même `network: host`),
ajoute `--allow network.host`, tague l'image que Compose attend (nom lu dans
`docker compose config --images`, pas recopié), puis recrée **uniquement** le service `frontend`.
`NO_CACHE=1` force un build à froid. Le README et `docker-compose.yml` renvoient à ce script.

Il deviendra inutile dès que le builder Compose sera créé avec
`--buildkitd-flags '--allow-insecure-entitlement network.host'` (driver `docker-container`).

**Preuves du cycle complet par la commande unique** (build à froid, `NO_CACHE=1`) :

```
$ NO_CACHE=1 bash scripts/build-frontend.sh
#15 [prerender] 34 routes × 2 languages (58 SSG pages + 5 private ?lang=en shells) + 8 articles, sitemap 66 URLs
#15 ✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
#18 naming to docker.io/library/saas_web_application_digitale_presenz-frontend done
Container …-frontend-1 Recreated / Started
[build-frontend] done — https://127.0.0.1/ now serves saas_web_application_digitale_presenz-frontend
script exit=0 duration=58s

image : 76 index.html · sitemap 66 <loc> · presence-locale-map.conf présent
dist/index.html        bc0d5ad2784ab0a1421bbf8ca6b48d10dba779262774a11dc59988ccdd98a6d7
image/index.html       bc0d5ad2784ab0a1421bbf8ca6b48d10dba779262774a11dc59988ccdd98a6d7
dist/en/pricing        d09ad338d93e7ade60cea45b8909182c4724fe44c714c66c95f36886c8595c10
image/en/pricing       d09ad338d93e7ade60cea45b8909182c4724fe44c714c66c95f36886c8595c10
served /               bc0d5ad2…98a6d7 · served /en/pricing d09ad338…595c10
/pricing?lang=en → 301 https://127.0.0.1/en/pricing · /login?lang=en → 200 · sitemap 66
```

Seul `…-frontend-1` a été recréé ; les autres conteneurs conservent leur uptime
(`web` 25 h, `wordpress` 22 h, `db`/`redis` 31 h, `presence-validation-*` 2 jours).
`docker compose build frontend` échoue toujours (exit 1) : c'est précisément pourquoi le script
existe ; il ne remplace pas la commande standard par une astuce mentale, il l'encapsule.

### 8.2 Paramètres de requête supplémentaires — **résolus** (voir §12)

Un premier passage supprimait toute la query string. Depuis le correctif §12, seul `lang` est
retiré : `/pricing?lang=en&utm_source=newsletter&utm_medium=email` →
`301 /en/pricing?utm_source=newsletter&utm_medium=email`, dans l'ordre d'origine. Une campagne
conserve donc son attribution à travers la migration.

### 8.3 Variantes non normalisées

`?lang=en+` (encodage) et `/pricing/?lang=en` (slash final) ne correspondent pas à une clé de la
carte : 200 allemand, sans redirection, inchangé. En revanche `?lang=EN` **redirige** : `map`
compare ses clés sans tenir compte de la casse (constaté sur nginx réel, corrigé dans le modèle et
les tests au §12). Aucune boucle, aucun 404 dans ces cas.

### 8.4 `$http_host` dans le `Location`

La cible reprend l'hôte demandé par le client (comportement standard de nginx, qui utilise `$host`
de la même façon). Sans cache partagé, l'impact est limité à la requête de l'attaquant ; si un CDN
ou un cache est ajouté devant nginx, il faudra verrouiller `server_name`.

### 8.5 Cache navigateur des 301

Un 301 est mis en cache de façon agressive par les navigateurs. Le changement est voulu permanent,
mais revenir en arrière sur une route donnée demanderait un `Cache-Control` explicite — non ajouté.

### 8.6 `nginx.locale-map.conf` est un artefact de build

`nginx -t` sur le dépôt sans `pnpm build` échoue (include manquant). `verify-nginx.sh` et le build
Docker le génèrent ; le fichier est gitignoré. Un déploiement qui copierait `nginx.conf` sans la
carte ferait échouer nginx au démarrage (échec bruyant, pas silencieux).

### 8.7 Build local et origine

`VITE_BASE_URL` vaut `https://localhost` par défaut : canonical et sitemap restent locaux.
La production doit fournir l'origine publique, sinon les `301` restent corrects mais le sitemap
annonce `localhost`.

---

## 9. Checklist

### VALIDÉ TECHNIQUEMENT

- [x] `pnpm exec tsc --noEmit` → 0
- [x] `pnpm run build` → 0 (58 SSG + 5 coquilles privées + 8 articles, sitemap 66)
- [x] `pnpm check:seo` → 0 (avec carte à jour, alias publics absents, privées présentes)
- [x] `node scripts/check-i18n.mjs` → 0 (parité 1858/1858, 43 littéraux inchangés)
- [x] `pnpm exec playwright test` → 49/49, 0 échec
- [x] `bash scripts/verify-nginx.sh` → 0, 92 vérifications (29 × 301 exacts, suivi 1 saut, privées 200)
- [x] 29/29 routes publiques : `301` + `Location` exact sur le contenu réellement servi
- [x] `/en/…` : 200 direct, jamais de redirection (aucune boucle)
- [x] 5 routes noindex : 200 direct, aucun `Location`
- [x] `_i18n` : 0 copie publique, 5 coquilles privées
- [x] Sitemap : 66 URLs, 0 `?lang=`, 0 `_i18n`
- [x] SHA-256 servi = SHA-256 de `dist/` pour `/` et `/en/pricing`
- [x] Un seul conteneur recréé (`frontend`), autres services intacts
- [x] Sauvegarde horodatée de `nginx.conf` (SHA identique avant/après copie)
- [x] Aucun commit, aucun push, aucun déploiement distant

### ÉCHEC

- aucun.

### BLOQUÉ

- aucun blocage technique dans le périmètre du lot.
- *(hors périmètre)* `docker compose build frontend` reste inutilisable sans `--allow` (voir §8.1).

### À VÉRIFIER MANUELLEMENT

- [ ] Recharger `https://127.0.0.1/pricing?lang=en` dans un navigateur : adresse finale `/en/pricing`,
      contenu anglais, aucune boucle (vérifié en HTTP, pas en navigateur graphique).
- [x] Paramètres de campagne : conservés depuis le §12 (vérifié sur le contenu servi).
- [ ] Décider du sort des variantes non normalisées (§8.3).
- [ ] Prévoir la correction durable du builder Compose/BuildKit (§8.1).
- [ ] Re-crawl des anciennes URL `?lang=` par les moteurs : le 301 est en place, l'indexation
      effective ne peut pas être constatée ici.

---

## 10. Confirmations

- **Aucun commit, aucun push, aucun déploiement distant.** `git status --porcelain` reste à
  **322 entrées**, inchangé par rapport au début du lot 3 (décision de commit toujours en attente).
- **Aucune modification d'un autre service Docker** : seule l'image `…-frontend` a été reconstruite
  et seul le conteneur `…-frontend-1` recréé. Aucun volume supprimé, aucun `docker system prune`.
- **Aucune modification fonctionnelle de `docker-compose.yml`, du backend, du CMS ou de la base.**
  (Un commentaire explicatif a été ajouté à `docker-compose.yml` dans l'addendum §11 ; ni `network`,
  ni `entitlements`, ni les args de build n'ont changé.)
- **Aucune donnée utilisateur, aucun secret** copié dans ce rapport.
- **`nginx.conf` sauvegardé** avant modification, copie horodatée hors Git.
- Le lot s'arrête ici : pas de début de lot 4, pas de migration supplémentaire.

---

## 11. Addendum — fin du contournement manuel du build (28 octobre 2026)

**Demande :** le cycle « `docker compose build` → échec → `docker buildx build --allow` » se répétait
depuis le lot 1 ; il doit tenir en une commande documentée.

### Diagnostic (lecture seule)

| Composant | Version |
| --- | --- |
| Docker Engine (client + serveur) | 29.9.1 (API 1.56) |
| Docker Compose | v5.6.0 |
| buildx | v0.38.0 |
| BuildKit | v0.34.0, builder `default`, driver `docker` |

- `docker compose build --help` n'expose **aucun** `--allow` / `--entitlement` (seul `--builder`).
- `docker buildx bake --print frontend` montre que Compose transmet bien `network: host` **et**
  `entitlements: ["network.host"]` : la syntaxe est correcte, le refus vient du allow-list BuildKit.
- Sonde `network: host` **sans** `entitlements` : même échec
  (`additional privileges requested: pass "--allow=network.host"`).
  → ce n'est ni la syntaxe, ni le bloc `entitlements` ; c'est une limite de `docker compose build`,
  qui ne peut pas accorder l'entitlement au builder par défaut.

### Correctif

| Fichier | Changement |
| --- | --- |
| `scripts/build-frontend.sh` (nouveau) | `docker buildx bake -f docker-compose.yml --allow network.host --set frontend.tags=<image Compose> frontend`, puis `docker compose up -d --no-deps frontend`. Nom d'image lu dans `docker compose config --images`. `NO_CACHE=1` pour un build à froid. Commentaire d'en-tête expliquant quand le script disparaîtra. |
| `docker-compose.yml` | commentaire seul : pourquoi `docker compose build` échoue ici et quelle commande utiliser. Aucun changement fonctionnel (mêmes `network`, `entitlements`, args). |
| `README.md` | les deux exemples de build utilisent `bash scripts/build-frontend.sh` (+ explication courte). |

`chmod +x scripts/build-frontend.sh` appliqué.

### Vérification

- `NO_CACHE=1 bash scripts/build-frontend.sh` → **exit 0, 58 s**, build réel (pas de cache),
  58 pages SSG + 5 coquilles privées + 8 articles, sitemap 66, `check-seo` ✅.
- Image : 76 `index.html`, 66 `<loc>`, `presence-locale-map.conf` présent.
- SHA-256 identiques entre l'image reconstruite à froid et `dist/` hôte :
  `index.html` `bc0d5ad2…98a6d7`, `en/pricing/index.html` `d09ad338…595c10`.
- Servi : `/` et `/en/pricing` même SHA-256 ; `/pricing?lang=en` → 301 `/en/pricing` ;
  `/login?lang=en` → 200 ; sitemap 66.
- Seul `…-frontend-1` recréé ; tous les autres conteneurs (dont `presence-validation-*`,
  `wordpress`, `web`, `db`, `redis`, `celery-*`, `mailpit`, `scanner-*`) conservent leur uptime.
- `docker compose build frontend` échoue toujours (exit 1) — comportement documenté, contourné par
  le script, pas par une manipulation manuelle.

### Réserves

- Le script dépend de `docker buildx` (livré avec Docker) et de `docker compose config`.
- Durablement, un builder `docker-container` créé avec
  `--buildkitd-flags '--allow-insecure-entitlement network.host'`, ou un WordPress build-time
  joignable sans `network: host`, permettrait de supprimer le script.
- Aucun commit, aucun push, aucun déploiement ; aucun autre service Docker touché.

---

## 12. Correctif — les paramètres UTM survivent au 301 (28 octobre 2026)

**Constat.** La §8.2 décrivait bien un comportement non résolu : le 301 supprimait **toute** la
query string. Avant/après exact sur le même exemple :

```
AVANT : GET /pricing?lang=en&utm_source=newsletter&utm_medium=email
        301  Location: https://127.0.0.1/en/pricing
        (utm_source et utm_medium perdus → attribution de campagne cassée)

APRÈS : GET /pricing?lang=en&utm_source=newsletter&utm_medium=email
        301  Location: https://127.0.0.1/en/pricing?utm_source=newsletter&utm_medium=email
        puis 200, <html lang="en">, 1 seul saut
```

### Mécanisme

`nginx.locale-map.conf` (généré) contient un second `map` qui retire uniquement le jeton `lang` et
recopie le reste dans l'ordre d'origine :

```nginx
map $args $presence_locale_query {
    default "";
    "~*^lang=(?:en|de)$"           "";
    "~*^lang=(?:en|de)&(.+)$"      "?$1";
    "~*^(.+)&lang=(?:en|de)&(.+)$" "?$1&$2";
    "~*^(.+)&lang=(?:en|de)$"      "?$1";
}
```

et `nginx.conf` l'ajoute à la cible :

```nginx
return 301 $scheme://$http_host$presence_locale_redirect$presence_locale_query;
```

`~*` est nécessaire : `map` compare ses clés **sans tenir compte de la casse**, donc `?lang=EN`
redirige déjà ; sans ce drapeau la query serait perdue dans ce cas précis.

**Correction de la §8.3 au passage** : `?lang=EN` ne renvoie pas 200 — il redirige (comportement
antérieur au correctif, que le modèle de test ne reflétait pas). Seuls `?lang=en+` et le slash final
restent hors carte.

### Vérifications (nginx réel, port 18443)

```
ok  UTM after lang — /pricing?lang=en&utm_source=newsletter&utm_medium=email&utm_campaign=launch
      → 301 https://127.0.0.1:18443/en/pricing?utm_source=newsletter&utm_medium=email&utm_campaign=launch
ok  UTM around lang — /pricing?utm_source=newsletter&lang=en&utm_medium=email
      → 301 …/en/pricing?utm_source=newsletter&utm_medium=email
ok  UTM before lang — /pricing?utm_source=newsletter&lang=en
      → 301 …/en/pricing?utm_source=newsletter
ok  lang alone keeps no query — /pricing?lang=en → 301 …/en/pricing
ok  params after lang (DE) — /pricing?lang=de&a=1&b=2 → 301 …/pricing?a=1&b=2
ok  UTM end-to-end — → 301 → /en/pricing?utm_source=newsletter&utm_medium=email (200, en, 1 hop)
ok  ?lang=EN (map casse-insensible) — /pricing?lang=EN → 301 …/en/pricing
ok  ?lang=EN + UTM — /pricing?lang=EN&utm_source=x → 301 …/en/pricing?utm_source=x
ok  ?lang=en+ (encodage) — 200, aucune redirection
ok  trailing slash + ?lang=en — 200, aucune redirection
```

### Contenu réellement servi (après `bash scripts/build-frontend.sh`, exit 0, 38 s)

```
/pricing?lang=en&utm_source=newsletter&utm_medium=email&utm_campaign=launch
  301 → https://127.0.0.1/en/pricing?utm_source=newsletter&utm_medium=email&utm_campaign=launch
/pricing?utm_source=newsletter&lang=en&utm_medium=email
  301 → https://127.0.0.1/en/pricing?utm_source=newsletter&utm_medium=email
/pricing?utm_source=newsletter&lang=en
  301 → https://127.0.0.1/en/pricing?utm_source=newsletter
/pricing?lang=en
  301 → https://127.0.0.1/en/pricing            (aucun « ? » résiduel)
/pricing?lang=de&a=1&b=2
  301 → https://127.0.0.1/pricing?a=1&b=2
/pricing?lang=EN&utm_source=x
  301 → https://127.0.0.1/en/pricing?utm_source=x

suivi : 200, hops=1, https://127.0.0.1/en/pricing?utm_source=newsletter&utm_medium=email, lang=en
hors carte : /pricing?lang=en+ → 200 sans Location · /pricing/?lang=en → 200 sans Location

SHA-256 inchangés : dist/index.html = servi / (bc0d5ad2…98a6d7),
                    dist/en/pricing    = servi /en/pricing (d09ad338…595c10)
```

### Fichiers modifiés par ce correctif

| Fichier | Changement |
| --- | --- |
| `scripts/generate-nginx-locale-map.mjs` | émet `map $args $presence_locale_query` (`~*`) |
| `nginx.conf` | `return 301 …$presence_locale_redirect$presence_locale_query` |
| `scripts/check-seo-build.mjs` | modèle `localeRedirectQuery()` (identique à nginx), assertions UTM/casse |
| `e2e/helpers/static-dist.ts` | même transformation, `$arg_lang` insensible à la casse |
| `e2e/locale-redirects-dist.spec.ts` | test « drops » → « keeps », 8 cas exacts, nouveau test hors-carte |
| `scripts/verify-nginx.sh` | 8 vérifications 301/UTM + 2 hors-carte |

### Contrôles

```
pnpm exec tsc --noEmit ............... exit 0
pnpm run build ....................... exit 0 (58 SSG + 5 coquilles privées + 8 articles, sitemap 66)
pnpm check:seo ....................... exit 0
pnpm exec playwright test ............ 50/50 passed (49 existants + 1 nouveau), exit 0
bash scripts/verify-nginx.sh ......... exit 0, 102 vérifications (0 échec)
bash scripts/build-frontend.sh ....... exit 0, 38 s, seul …-frontend-1 recréé
```

Aucun commit, aucun push, aucun autre service Docker touché.
