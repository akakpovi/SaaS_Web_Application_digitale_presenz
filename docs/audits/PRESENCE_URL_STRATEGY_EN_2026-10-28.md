# Presence — Stratégie d'URL bilingue `/en/` (2026-10-28)

**Statut : décision préparée, migration NON exécutée.**
Aucune URL, aucun routeur, aucun fichier nginx n'a été modifié dans ce lot. Ce document livre l'inventaire, la table de correspondance, la stratégie de redirection, les risques et le plan de livraison progressive demandés, puis s'arrête pour validation.

Dépôt réel : `~/Schreibtisch/SaaS_Web_Application_digitale_presenz/SaaS_Web_Application_digitale_presenz_v2`
Rapport précédent : [`PRESENCE_BILINGUAL_STATIC_SHELL_2026-10-27.md`](PRESENCE_BILINGUAL_STATIC_SHELL_2026-10-27.md)

---

## 1. Décision proposée

| Élément | Décision proposée |
| --- | --- |
| Allemand (défaut) | URL actuelles, sans préfixe : `/`, `/pricing`, `/features/…`, `/impressum`… |
| Anglais (indexable) | URL dédiées `/en/…` : `/en/`, `/en/pricing`, `/en/features/…`, `/en/impressum`… |
| Ancienne URL anglaise | `?lang=en` conservée **uniquement** comme redirection 301 vers `/en/…` |
| Canonical | Auto-canonique dans chaque langue ; jamais de canonical croisé |
| `hreflang` | `de` = URL nue, `en` = URL `/en/…`, `x-default` = URL nue (allemand) |
| Sitemap | Seulement les URL canoniques indexables, allemandes **et** anglaises, avec les paires `hreflang` |
| Authentification et application | Restent **sans préfixe** (`/login`, `/app/…`), `noindex`, langue par préférence |
| Articles de blog | Restent sur `/blog/<slug>` au lancement (voir §4.3, décision à valider) |
| Migration | Progressive, en 4 lots, avec garde-fous et retour arrière possible |

**Périmètre chiffré** : 29 routes marketing indexables (58 URL après migration), 5 routes `noindex` non préfixées, 8 articles CMS (2 DE, 6 EN), 14 routes applicatives privées.

---

## 2. État initial vérifié (2026-10-28)

### 2.1 Chiffres constatés dans le dépôt

| Élément | Valeur réelle | Preuve |
| --- | --- | --- |
| Routes déclarées dans `src/seo/routes.json` | **34** | lecture du fichier |
| Routes indexables | **29** | 34 − 5 `noindex` |
| Routes `noindex` | **5** : `/login`, `/register`, `/forgot-password`, `/reset-password`, `/onboarding` | `routes.json` |
| Coquilles allemandes pré-rendues | **34** (`dist/<route>/index.html`) | `check:seo` |
| Coquilles anglaises pré-rendues | **34** (`dist/_i18n/<route>/index.html`) | `find` |
| Articles CMS pré-rendus | **8** (`dist/blog/<slug>/index.html`) | build du 2026-10-27 |
| URL dans `dist/sitemap.xml` | **37** (29 routes + 8 articles) | comptage `<loc>` |
| Liens `xhtml:link` dans le sitemap | **0** | comptage |
| Existence de `dist/en/` | **non** | `fs.existsSync` |
| Route existante commençant par `/en` | **aucune** | `routes.json` + `App.tsx` |

### 2.2 Comportement actuel

* `nginx.conf` sélectionne la variante anglaise par `map $arg_lang $html_variant { en "/_i18n"; }` et `try_files $html_variant$uri/index.html …`.
* `/_i18n/**` est `internal` : le dossier n'est pas une URL publique.
* `hreflang="en"` pointe vers `…/pricing?lang=en`, qui sert bien un fichier HTML anglais.
* Le routeur React n'a **aucune notion de préfixe** : `BrowserRouter` sans `basename`, liens internes sans langue.
* `LanguageSwitcher` change la langue en mémoire et la persiste (`localStorage` + profil), **sans changer l'URL**.
* `i18n/index.tsx` donne la priorité à `?lang=` puis à la préférence stockée, puis au navigateur.
* `robots.txt` interdit `/app/`, `/login`, `/register`, `/forgot-password`, `/reset-password`, `/onboarding`, `/admin`, `/verify-email`, `/report/` ; `/scan/` est `noindex` via `SEO`, non interdit.

### 2.3 Défaut structurel découvert — le pré-rendu actuel n'est pas du contenu complet

Le pré-rendu actuel écrit, pour chaque route, un `<main>` de repli générique :

```html
<main data-prerender="true">
  <p>Presence</p>
  <h1>Website Monitoring Pricing</h1>
  <p>Free, Pro (€9/month)…</p>
  <p><a href="/">Home</a> · <a href="/pricing">Pricing</a> · <a href="/blog">Blog</a></p>
  <p>Path: /pricing</p>
</main>
```

Les tableaux de prix, les sections « fonctionnalités », la FAQ, les formulaires et le contenu juridique **ne sont pas** dans le HTML : ils n'existent qu'après exécution de React. C'est vrai pour l'allemand comme pour l'anglais.

Conséquences pour la demande actuelle :

1. Déplacer ces coquilles sous `/en/` ne produirait **pas** le « HTML anglais complet » exigé au §3 : ce serait toujours une coquille dont React remplace le contenu.
2. Un défaut supplémentaire apparaît dans les coquilles anglaises actuelles : leurs liens de repli pointent vers les URL allemandes (`href="/"`, `href="/pricing"`, `href="/blog"`) alors que le texte est anglais. Un crawler qui suit ces liens quitte la version anglaise.
3. La coquille allemande et la coquille anglaise partagent la même structure de repli : la différence se limite au titre, à la description, à `<html lang>` et aux métadonnées.

**Conclusion** : la migration `/en/` est réalisable, mais le critère « HTML complet sans JavaScript » nécessite un pré-requis d'architecture : un vrai rendu serveur/statique (SSG) des pages marketing. Le §5.1 décrit la plus petite modification cohérente. Sans ce pré-requis, le lot URL ne doit pas être déclaré accepté.

### 2.4 Blog : données réellement présentes

Interrogation du WordPress local (`/cms/wp-json/wp/v2/posts`) le 2026-10-28 :

| Langue | Slug | Traduction liée |
| --- | --- | --- |
| de | `de-was-ist-website-monitoring` | en `what-is-website-monitoring` |
| de | `de-ssl-zertifikat-pruefen` | en `how-to-check-ssl-certificate` |
| en | `what-is-website-monitoring` | de `de-was-ist-website-monitoring` |
| en | `how-to-check-ssl-certificate` | de `de-ssl-zertifikat-pruefen` |
| en | `digital-presence-checklist-small-business` | — |
| en | `website-security-checklist-small-business` | — |
| en | `what-is-dmarc` | — |
| en | `how-to-monitor-website-uptime` | — |

Total : **8 articles**, **2 paires DE/EN**, **4 articles anglais sans traduction allemande**, **0 article allemand sans traduction anglaise**. La langue vient de la taxonomie `language` et les liens de traduction du champ `presence_translations`, exposés par `wordpress/mu-plugins/presence-i18n.php`. Il n'existe donc **pas** de correspondance automatique par slug : toute URL anglaise d'article doit être dérivée de ces données, jamais devinée.

### 2.5 Contrôles techniques exécutés dans ce lot

| Commande | Résultat | Code de sortie |
| --- | --- | --- |
| `pnpm exec tsc --noEmit` | aucune erreur | **0** |
| `pnpm check:seo` | `routes=34 (5 noindex) · pre-rendered=34 · articles=8 · sitemap=37` ; « every SEO invariant » | **0** |
| Script d'inventaire (routes, sitemap, dossiers) | chiffres du §2.1 | **0** |
| `curl` WordPress local | 8 articles, 2 paires | **0** |
| `df -h /home/elom` | 14 G libres (94 % utilisés) | **0** |

Non réexécutés dans ce lot, car aucun code n'a changé depuis leur dernière exécution : build de production (code 0, 34 routes × 2 + 8 articles), 28 tests Playwright (28/28) et `verify-nginx.sh` (22 vérifications, 0 échec), exécutés le 2026-10-27 dans la même session. Ils devront être rejoués après chaque lot d'implémentation.

---

## 3. Inventaire exhaustif des routes

### 3.1 Pages publiques indexables (29)

Toutes ont une traduction anglaise réelle (catalogue `en.json` complet, coquille anglaise pré-rendue) et sont aujourd'hui `index,follow`.

| # | URL allemande | URL anglaise cible | Trad. EN | SEO | Dépendances |
| --- | --- | --- | --- | --- | --- |
| 1 | `/` | `/en/` | oui | indexable | `Landing`, tarifs statiques |
| 2 | `/pricing` | `/en/pricing` | oui | indexable | plans/prix, Paddle (checkout) |
| 3 | `/faq` | `/en/faq` | oui | indexable | FAQ + JSON-LD |
| 4 | `/blog` | `/en/blog` | oui | indexable | API WordPress, filtrage `presence_lang` |
| 5 | `/about` | `/en/about` | oui | indexable | contenu statique |
| 6 | `/contact` | `/en/contact` | oui | indexable | API contact |
| 7 | `/privacy` | `/en/privacy` | oui (brouillon) | indexable | identité opérateur, avertissement brouillon |
| 8 | `/terms` | `/en/terms` | oui (brouillon) | indexable | Paddle, décision B2B/B2C, brouillon |
| 9 | `/impressum` | `/en/impressum` | oui (brouillon) | indexable | identité opérateur, § 5 DDG |
| 10 | `/cookies` | `/en/cookies` | oui (brouillon) | indexable | stockage réel, brouillon |
| 11 | `/widerruf` | `/en/widerruf` | oui (brouillon) | indexable | droit de rétractation, Paddle |
| 12 | `/solutions/small-business` | `/en/solutions/small-business` | oui | indexable | i18n, CTA |
| 13 | `/solutions/freelancers` | `/en/solutions/freelancers` | oui | indexable | i18n, CTA |
| 14 | `/solutions/agencies` | `/en/solutions/agencies` | oui | indexable | i18n, CTA |
| 15 | `/solutions/restaurants` | `/en/solutions/restaurants` | oui | indexable | i18n, CTA |
| 16 | `/solutions/ecommerce` | `/en/solutions/ecommerce` | oui | indexable | i18n, CTA |
| 17 | `/solutions/local-business` | `/en/solutions/local-business` | oui | indexable | i18n, CTA |
| 18 | `/features/website-monitoring` | `/en/features/website-monitoring` | oui | indexable | i18n, JSON-LD |
| 19 | `/features/ssl-monitoring` | `/en/features/ssl-monitoring` | oui | indexable | i18n, JSON-LD |
| 20 | `/features/dns-monitoring` | `/en/features/dns-monitoring` | oui | indexable | i18n, JSON-LD |
| 21 | `/features/email-security` | `/en/features/email-security` | oui | indexable | i18n, JSON-LD |
| 22 | `/features/uptime-monitoring` | `/en/features/uptime-monitoring` | oui | indexable | i18n, JSON-LD |
| 23 | `/features/website-performance` | `/en/features/website-performance` | oui | indexable | i18n, JSON-LD |
| 24 | `/features/security-headers` | `/en/features/security-headers` | oui | indexable | i18n, JSON-LD |
| 25 | `/features/review-monitoring` | `/en/features/review-monitoring` | oui | indexable | i18n, JSON-LD |
| 26 | `/tools/website-checker` | `/en/tools/website-checker` | oui | indexable | API publique, quotas |
| 27 | `/tools/ssl-checker` | `/en/tools/ssl-checker` | oui | indexable | API publique |
| 28 | `/tools/dns-checker` | `/en/tools/dns-checker` | oui | indexable | API publique |
| 29 | `/tools/email-security-checker` | `/en/tools/email-security-checker` | oui | indexable | API publique |

Les routes canoniques juridiques sont **`/privacy`** et **`/terms`** : il n'existe ni `/datenschutz` ni `/agb` dans le routeur. Ne pas créer d'alias pour « remplir » le sitemap.

### 3.2 Routes `noindex` (5) — restent sans préfixe

| URL | Rôle | Cible `/en/…` | Raison |
| --- | --- | --- | --- |
| `/login` | connexion | **aucune** (301 depuis `/en/login`) | `noindex`, préférence de langue |
| `/register` | inscription | **aucune** | idem |
| `/forgot-password` | demande de réinitialisation | **aucune** | idem |
| `/reset-password` | nouveau mot de passe | **aucune** | idem |
| `/onboarding` | première configuration | **aucune** | idem |

L'anglais de ces écrans reste fonctionnel via la préférence persistée (et `?lang=en` pendant la transition). Aucune route privée n'est modifiée sans nécessité démontrée.

### 3.3 Routes dynamiques et privées (hors sitemap)

| Route | Nature | Langue | URL cible | Remarque |
| --- | --- | --- | --- | --- |
| `/blog/:slug` | article CMS | celle de l'article | inchangée au lancement | `hreflang` vers les slugs traduits |
| `/verify-email` | jeton de vérification | préférence | inchangée | `noindex`, jamais préfixée |
| `/scan/:scanId` | résultat de scan public | préférence | inchangée | `noindex`, contenu dynamique |
| `/report/:publicId` | ancien lien de partage | — | 301 vers `/scan/:id` | existant |
| `/admin` | administration | préférence | inchangée | privé, `noindex` |
| `/settings/integrations` | raccourci OAuth | — | redirection vers `/app/settings/integrations` | existant |
| `/app/*` | 14 routes authentifiées | préférence | inchangée | `noindex`, `AuthGuard` |
| `*` | page 404 | DE par défaut | inchangée | 404 réel nginx |

---

## 4. Table de correspondance et règles URL

### 4.1 Règle générale

```
URL_EN(path) = path === "/" ? "/en/" : "/en" + path
```

* Pas de double slash, pas de slash final sur les pages intérieures (comme aujourd'hui).
* La page d'accueil anglaise est **`/en/`** (canonical avec slash final) ; `/en` redirige en 301 vers `/en/`.
* Aucune autre racine de langue (`/de/…`) n'est créée : l'allemand garde les URL existantes.
* Aucune URL `/en/...` n'est créée pour une page sans contenu anglais réel. Les 29 pages ci-dessus ont toutes un contenu anglais ; les 5 routes `noindex` n'en reçoivent pas.

### 4.2 Canonical, `hreflang`, `x-default`

Pour une page marketing :

| Balise | Allemand | Anglais |
| --- | --- | --- |
| `canonical` | `https://<domaine>/pricing` | `https://<domaine>/en/pricing` |
| `hreflang="de"` | URL nue | URL nue |
| `hreflang="en"` | `/en/pricing` | `/en/pricing` |
| `hreflang="x-default"` | URL nue | URL nue |
| `og:locale` | `de_DE` | `en_GB` |

Chaque variante est auto-canonique : aucune ne canonicalise vers l'autre. `x-default` pointe vers l'allemand, langue par défaut et destination pour une langue non servie.

### 4.3 Articles de blog

Les articles ont un slug propre par langue ; ce ne sont pas deux variantes d'une même URL.

| Article DE | Article EN | URL DE | URL EN | `hreflang` |
| --- | --- | --- | --- | --- |
| `de-was-ist-website-monitoring` | `what-is-website-monitoring` | `/blog/de-was-ist-website-monitoring` | `/blog/what-is-website-monitoring` | paire réciproque |
| `de-ssl-zertifikat-pruefen` | `how-to-check-ssl-certificate` | `/blog/de-ssl-zertifikat-pruefen` | `/blog/how-to-check-ssl-certificate` | paire réciproque |
| — | `digital-presence-checklist-small-business` | — | `/blog/digital-presence-checklist-small-business` | auto |
| — | `website-security-checklist-small-business` | — | `/blog/website-security-checklist-small-business` | auto |
| — | `what-is-dmarc` | — | `/blog/what-is-dmarc` | auto |
| — | `how-to-monitor-website-uptime` | — | `/blog/how-to-monitor-website-uptime` | auto |

**Recommandation au lancement** : conserver ces URL, y compris pour les articles anglais, et ne pas créer `/en/blog/<slug>`.

Justification :

1. Un article est un contenu, pas une déclinaison de page : son URL identifie le contenu, sa langue est déclarée par `<html lang>` et `hreflang`.
2. Les 6 articles anglais existent déjà et seraient déplacés sans bénéfice démontré, avec 301 et perte temporaire de signal.
3. `/en/blog/<de-slug>` serait un faux URL anglais pointant vers un contenu allemand — interdit par la demande.
4. Le blog allemand (`/blog`) liste les 2 articles allemands, le blog anglais (`/en/blog`) les 6 articles anglais ; le filtrage existe déjà (`fetchPosts(…, locale)`).

**Exception assumée** : les articles anglais ne sont pas sous `/en/`. Le `hreflang` reste correct et le HTML de l'article est déjà complet (le pré-rendu injecte le contenu WordPress).

**Variante stricte (phase ultérieure)** : déplacer les 6 articles anglais vers `/en/blog/<slug>` avec 301 depuis `/blog/<slug>`, map générée au build à partir de `presence_lang` et `presence_translations`. Coût : 6 redirections, mise à jour des liens éditoriaux et du sitemap. À ne faire qu'après décision explicite et analyse des liens entrants.

### 4.4 Changement de langue dans l'interface

| Contexte | Comportement cible |
| --- | --- |
| Page marketing `/pricing` → EN | navigation vers `/en/pricing` (rechargement complet, pas de routeur croisé) |
| Page marketing `/en/pricing` → DE | navigation vers `/pricing` |
| Article avec traduction | lien vers le slug traduit |
| Article sans traduction | pas de navigation ; message explicite « cet article n'existe qu'en … » ; jamais de faux URL |
| `/login`, `/app/…` | préférence seulement, pas de changement d'URL |
| Préférence | persistée (`localStorage` + profil), comme aujourd'hui |

Le sélecteur ne doit jamais produire `/en/login` ou `/en/app/…`.

---

## 5. Architecture cible

### 5.1 Pré-requis : rendu statique du contenu (SSG)

**Constat** : le pré-rendu actuel est un injecteur de métadonnées + repli, pas un rendu des composants. Pour tenir « HTML anglais complet », il faut rendre les pages React côté build.

**Plus petite modification cohérente** :

1. Extraire un manifeste de routes publiques partagé (`path`, composant, métadonnées) utilisé par `App.tsx` et par une nouvelle entrée serveur.
2. Ajouter `src/entry-server.tsx` :
   `<HelmetProvider><AuthProvider><I18nProvider initialLocale={…}><ToastProvider><StaticRouter location={path}><PublicRoutes/></StaticRouter></ToastProvider></I18nProvider></AuthProvider></HelmetProvider>`
   rendu avec `renderToString` (ou `renderToPipeableStream` si les imports `lazy` sont conservés).
3. Build en deux temps : `vite build` (client) puis `vite build --ssr src/entry-server.tsx --outDir dist-ssr`, puis `scripts/prerender.mjs` qui importe le bundle serveur, rend chaque route dans chaque langue et injecte le HTML dans `<div id="root">`.
4. `main.tsx` : `hydrateRoot` lorsque `#root` contient `data-prerender`, sinon `createRoot`.
5. Garde-fous navigateur : `ThemeProvider` (`localStorage`, `matchMedia`), `I18nProvider` (`navigator`), `SEO` (`window.location.origin`) doivent accepter un rendu sans `window`. Les pages marketing vérifiées (`Landing`, `Pricing`, `FAQ`, `About`, `Contact`, `Feature`, `Solution`, `Tool`, pages juridiques) n'utilisent **aucune** API navigateur ni requête **pendant le rendu** (vérifié par recherche ; `Pricing` n'utilise `window.location.assign` que dans un gestionnaire de clic) ; `BlogPage` reçoit ses articles initiaux du build.
6. Locale **imposée par l'URL** au rendu et à l'hydratation : `de` pour une URL nue, `en` pour `/en/…`. La préférence stockée ne doit pas changer la langue du HTML d'une URL publique, sinon divergence d'hydratation et contenu incohérent avec le canonical.

**Pourquoi c'est indispensable** : sans SSG, `/en/pricing` resterait une coquille de 4 paragraphes. Le lot URL seul ne satisfait pas le critère d'acceptation.

**Risques SSG** : divergences d'hydratation (dates `Intl`, `useId`, contenu dépendant du navigateur) ; composants `lazy` ; contexte d'authentification ; taille et temps de build. Atténuation : locale URL-first, formatage déterministe, tests de console après hydratation, rendu limité aux 29 pages publiques.

### 5.2 Routeur

* `basename` calculé au chargement : `/en` si `pathname` commence par `/en/` ou vaut `/en`, sinon `/`.
* Les liens publics internes (`Link to="/pricing"`) deviennent automatiquement `/en/pricing` sous le basename.
* **28 liens** des pages publiques pointent vers l'application ou l'authentification (25 vers `/login|/register|/onboarding|…`, 3 vers `/app/…`). Ils doivent sortir du basename (ancre `<a href>` ou helper dédié) pour ne jamais produire `/en/login` ou `/en/app/…`.
* `/en/app/…`, `/en/admin`, `/en/login`, etc. : 301 vers l'URL nue, jamais rendues.
* La bascule de langue est une navigation complète : le basename est recalculé au chargement, ce qui évite un routeur à deux arbres.

**Alternative écartée** : dupliquer l'arbre de routes sous `/en/*` avec des liens préfixés manuellement. Plus de surface d'erreur pour 29 pages, et les liens existants devraient tous être réécrits.

### 5.3 i18n et hydratation

Nouvelle précédence :

1. préfixe d'URL (`/en/…`) sur les pages publiques ;
2. `?lang=` **uniquement** pendant la transition (puis redirigé) ;
3. préférence stockée / navigateur **uniquement** sur les routes sans préfixe (auth, app, pages dynamiques).

`canonicalPath()` et `alternateLinks()` deviennent des fonctions de chemin (`/pricing` ↔ `/en/pricing`) et non de query string. `SEO.tsx` reçoit toujours le chemin sans préfixe et ajoute `/en` selon la variante d'URL. Les articles conservent leurs alternates par slug.

**Changement de comportement à valider** : un visiteur anglophone qui revient sur `/` verra l'allemand (URL par défaut) et devra cliquer sur EN, ou être redirigé s'il choisit `/en/`. C'est le prix d'un HTML cohérent et hydratable. La préférence reste utilisée dans l'application et les emails.

### 5.4 nginx

* Supprimer `map $arg_lang $html_variant` et `location /_i18n/`.
* `location /` conserve `try_files $uri/index.html $uri =404` ; `/en/...` est servi naturellement par `dist/en/.../index.html`.
* `location = /en { return 301 /en/; }`.
* Redirections `?lang=` : `map` sur `$args` pour retirer **uniquement** `lang` et préserver `utm_*`, `gclid`, `fbclid` ; `return 301` vers `/en$uri` (ou `$uri` pour `lang=de`). Aucune règle ne s'applique à `/api/`, `/cms/`, `/assets/`.
* 301 des préfixes privés : `/en/app/*` → `/app/*`, `/en/admin` → `/admin`, `/en/(login|register|forgot-password|reset-password|onboarding|verify-email)` → URL nue.
* `/blog/<slug>?lang=…` → 301 vers le slug sans `lang` (la langue de l'article ne change pas).
* `/en/blog/...` (hors `/en/blog`) → **404**, pas de redirection vers un article allemand.
* Page 404 : décider si `/en/...` inconnu doit servir un 404 anglais (`dist/en/404.html`) ; sinon le 404 reste allemand, ce qui est acceptable mais à documenter.
* Cache : fichiers statiques, aucun `Vary` nécessaire (la langue n'est plus dans un en-tête ni une query).

### 5.5 SEO et sitemap

* Sitemap cible : **66 URL** (29 × 2 + 8 articles), avec `xmlns:xhtml` et, pour chaque URL, les liens `hreflang` réciproques (`de`, `en`, `x-default`). Les articles non traduits n'ont qu'une entrée auto.
* Aucune URL `?lang=`, aucune URL `_i18n`, aucune route privée ou `noindex`.
* `robots.txt` inchangé, sauf ajout défensif de `/en/app/` si des URL préfixées pouvaient être indexées (elles redirigent déjà).
* `VITE_BASE_URL` doit être absolu et public au build ; le garde-fou échoue si une origine locale fuit dans le sitemap de production.
* Les avertissements « brouillon » des pages juridiques sont conservés ; les versions anglaises ne doivent pas être présentées comme juridiquement contraignantes (décision à valider, §8).

### 5.6 Blog WordPress

* Le build lit `presence_lang` et `presence_translations` ; il ne déduit jamais une traduction par slug.
* `/en/blog` : articles `en` uniquement ; `/blog` : articles `de` uniquement.
* Les liens depuis `/en/blog` vers `/blog/<slug>` sont des ancres complètes (hors basename).
* Si le CMS est injoignable au build : les coquilles d'articles ne sont pas générées ; `/blog/` continue de servir la SPA ; `/en/blog` doit afficher un état explicite (pas de liste vide silencieuse).
* Aucune URL `/en/blog/<slug>` au lancement ; toute URL `/en/blog/<de-slug>` répond 404.

---

## 6. Stratégie de redirection

### 6.1 Matrice

| Source | Cible | Code | Remarque |
| --- | --- | --- | --- |
| `/en` | `/en/` | 301 | une seule URL canonique pour l'accueil anglais |
| `/?lang=en` | `/en/` | 301 | ancienne URL annoncée par `hreflang` |
| `/pricing?lang=en` | `/en/pricing` | 301 | idem |
| `/pricing?lang=de` | `/pricing` | 301 | alias vers l'URL nue |
| `/en/pricing?lang=en` | `/en/pricing` | 301 | supprime le paramètre, évite un doublon |
| `/en/pricing?lang=de` | `/pricing` | 301 | bascule de langue par URL |
| `/en/login` (idem register, forgot, reset, onboarding, verify-email) | `/login` | 301 | routes privées non préfixées |
| `/en/admin` | `/admin` | 301 | idem |
| `/en/app/…` | `/app/…` | 301 | idem |
| `/blog/<slug>?lang=en` (ou `de`) | `/blog/<slug>` | 301 | la langue de l'article ne change pas |
| `/en/blog/<slug>` | — | **404** | jamais de redirection d'une URL EN vers un article DE |
| `/en/<inconnue>` | — | **404** | pas de repli SPA sous `/en` |

### 6.2 Conservation des paramètres

Les campagnes (`utm_*`, `gclid`, `fbclid`) doivent survivre à la redirection. La règle retire **uniquement** `lang` :

* `?lang=en` → aucun paramètre ;
* `?lang=en&utm_source=x` → `?utm_source=x` ;
* `?utm_source=x&lang=en` → `?utm_source=x` ;
* `?utm_source=x&lang=en&gclid=y` → `?utm_source=x&gclid=y`.

À tester sur les quatre formes ; si `lang` apparaît deux fois, le comportement (suppression de toutes les occurrences) doit être documenté.

### 6.3 Absence de boucle

Invariants à tester :

1. la cible d'une redirection ne contient jamais `lang` ;
2. une URL `/en/…` n'est redirigée que si elle porte `lang=de` (bascule) ou appartient à une racine privée ;
3. une URL nue n'est jamais redirigée vers `/en/…` sans `lang=en` ;
4. chaque chaîne se termine en **un seul** saut, code final 200 (ou 404 pour `/en/blog/<slug>`) ;
5. les redirections ne s'appliquent pas à `/api/`, `/cms/`, `/assets/`.

---

## 7. Fichiers impactés et effort

| Fichier | Changement | Taille |
| --- | --- | --- |
| `src/App.tsx` | manifeste de routes partagé, `basename`, garde des liens privés | M |
| `src/main.tsx` | `hydrateRoot` conditionnel | S |
| `src/entry-server.tsx` (nouveau) | rendu serveur des pages publiques | M |
| `src/i18n/index.tsx` | locale par chemin, précédence, canonical/alternates | M |
| `src/components/SEO.tsx` | canonical/hreflang par chemin | S |
| `src/components/LanguageSwitcher.tsx` | navigation vers l'URL équivalente, cas article/privé | M |
| `src/components/AppShell.tsx` | garde `window` pour le SSG | S |
| 12 fichiers publics (hors `Auth`, `VerifyEmail`, `AuthGuard`) | 25 liens auth + 3 liens app hors basename | M |
| `scripts/prerender.mjs` | rendu SSG, arborescence `/en`, sitemap 66 URL + `xhtml:link` | L |
| `nginx.conf` | suppression `_i18n`, 301 `?lang`, 301 préfixes privés, `/en` | M |
| `scripts/check-seo-build.mjs` | invariants 66 URL, paires, articles, absence de query | M |
| `vite.config.ts`, `package.json` | build SSR + script de build | S |
| `e2e/bilingual-shell-dist.spec.ts` + nouveau spec redirections | HTML brut `/en`, hydratation, 301, switcher | M |

Aucune dépendance nouvelle : `react-dom/server`, `StaticRouter` et `hydrateRoot` sont déjà disponibles.

**Ordre de grandeur** : deux lots de développement (SSG, puis URL) + un lot de redirections, chacun avec ses tests. Ne pas annoncer de date sans validation du périmètre.

---

## 8. Risques et décisions

| Risque | Gravité | Atténuation |
| --- | --- | --- |
| Coquille vide sous `/en` si le SSG n'est pas fait | **Élevée** | faire du SSG le lot 1 et un critère de sortie |
| Divergence d'hydratation | **Élevée** | locale imposée par l'URL, formatage déterministe, test console |
| Fuite de liens vers `/en/login` ou `/en/app` | **Élevée** | helper de sortie de basename, 301 défensifs, test de parcours |
| Boucles de redirection `?lang` | Moyenne | matrice §6, test d'un seul saut |
| `hreflang`/canonical incohérents | **Élevée** | garde-fou de build, réciprocité, `x-default` |
| Perte de signal sur les articles anglais (variante stricte) | Moyenne | conserver les URL au lancement, 301 si migration ultérieure |
| Langue juridique de référence | **Élevée (juridique)** | décision explicite : l'allemand fait foi, l'anglais est informatif |
| Attribution analytics | Moyenne | préserver `utm_*`, mettre à jour les rapports |
| WordPress injoignable au build | Moyenne | SPA pour les articles, état explicite pour `/en/blog` |
| Domaine/CDN inconnus | Moyenne | `VITE_BASE_URL` fourni, règles de cache à vérifier en production |

**Décisions à valider avant tout code** :

1. **SSG obligatoire** avant la bascule `/en`, ou acceptation explicite d'un HTML de repli (contraire au §3 de la demande).
2. **Articles** : exception au lancement (recommandée) ou migration stricte `/en/blog/<slug>`.
3. **Auth/app** : restent sans préfixe (recommandé) ou passent aussi sous `/en`.
4. **`?lang=en`** : 301 immédiat (recommandé) ou alias 200 temporaire.
5. **Langue juridique** : l'allemand est-il la version faisant foi pour Impressum, AGB, Datenschutz et Widerruf ?

---

## 9. Livraison progressive

### Lot 0 — Validation (ce document)

Livrables : inventaire, table de correspondance, matrice de redirection, risques, plan. Aucun changement de code.

### Lot 1 — SSG sur les URL actuelles

Objectif : rendre le contenu complet sans changer aucune URL.
Contenu : entrée serveur, manifeste de routes, gardes navigateur, hydratation, blog index initial.
Critères de sortie :

* le HTML brut de `/pricing` contient le tableau des prix, pas seulement le titre ;
* `/` contient les sections principales ;
* hydratation sans erreur console ;
* 28 E2E existants verts ;
* aucune URL modifiée.

### Lot 2 — URL `/en/…` pour les 29 pages

Objectif : publier les URL anglaises, canonicals, `hreflang`, sitemap, switcher.
Contenu : arborescence `dist/en`, suppression logique de `_i18n` côté serveur (les fichiers peuvent rester jusqu'au lot 3), basename, 28 liens, sitemap 66 URL.
Critères de sortie :

* `/en/pricing` sert un HTML anglais complet avec `<html lang="en">` ;
* canonical et `hreflang` réciproques ;
* switcher `/pricing` ↔ `/en/pricing` ;
* `/en/login`, `/en/app` inexistants ou 301 ;
* tests de parité et de liens internes verts.

### Lot 3 — Redirections et nettoyage

Objectif : basculer les anciennes URL et retirer le mécanisme `_i18n`.
Contenu : 301 `?lang`, 301 préfixes privés, suppression `map`/`_i18n`, sitemap final, mise à jour du garde-fou.
Critères de sortie :

* matrice §6 vérifiée en un seul saut ;
* paramètres de campagne conservés ;
* aucun `_i18n` ni `?lang` dans le sitemap ;
* `verify-nginx.sh` et E2E verts.

### Lot 4 — Optionnel : articles sous `/en/blog/<slug>`

Uniquement si la décision 2 va dans ce sens, après analyse des liens entrants et validation. 301 par slug, map générée au build, mise à jour des liens éditoriaux.

**Retour arrière** : les lots 2–3 ne touchent que des artefacts de build et la configuration nginx. Un redéploiement de l'image précédente restaure l'état antérieur ; aucune donnée, aucun volume, aucune base n'est modifié.

---

## 10. Tests

### 10.1 Déjà exécutés (référence)

Voir §2.5 : `tsc` 0, `check:seo` 0, inventaire, WordPress, disque. Build et E2E du 2026-10-27 : build 0, 28/28 Playwright, 22 vérifications nginx.

### 10.2 À ajouter par lot

| # | Test | Assertion |
| --- | --- | --- |
| 1 | HTML brut `/en/pricing` | `lang="en"`, titre/description EN, canonical `/en/pricing`, `hreflang` réciproques, `og:locale=en_GB` |
| 2 | Contenu complet sans JS | présence du tableau de prix et des sections, pas seulement le `<h1>` |
| 3 | `/` vs `/en/` | contenus allemand/anglais, aucun mélange, liens de repli corrects |
| 4 | Redirections | matrice §6, un seul saut, paramètres conservés |
| 5 | Sitemap | 66 `<loc>`, paires réciproques, zéro `?lang`, zéro `_i18n`, zéro route privée |
| 6 | Hydratation | aucun message React, langue initiale = langue du HTML |
| 7 | Switcher | `/pricing` ↔ `/en/pricing`, article sans traduction, pages privées |
| 8 | Liens internes | aucun `/en/login`, `/en/app`, `/en/blog/<slug>` ; tous les liens publics répondent 200 |
| 9 | Auth/app | connexion, redirection, `noindex`, URL non préfixées |
| 10 | Blog | liste DE/EN, article EN sans `/en/`, `/en/blog/<de-slug>` 404 |
| 11 | Juridique | brouillons visibles, identité centralisée, mobile |
| 12 | Mobile | 390 px, pas de débordement horizontal |
| 13 | nginx réel | `verify-nginx.sh` étendu aux 301 et à `/en` |
| 14 | CMS indisponible | build sans articles : pas de 500, état explicite |

---

## 11. Blocages et vérifications manuelles

| Élément | Statut | Responsable |
| --- | --- | --- |
| Décision SSG vs repli | **bloquant** | produit/technique |
| Décision articles `/en/blog` | **bloquant** pour le lot 4 | produit/SEO |
| Langue juridique de référence | **bloquant** pour `/en/impressum|terms|widerruf` | juriste |
| Domaine public définitif | **bloquant** pour canonical/sitemap | ops |
| Accès Search Console / analytics | requis après déploiement | ops |
| Liens entrants vers les 6 articles anglais | requis si lot 4 | SEO |
| WordPress joignable au build en production | à vérifier | ops |
| Règles CDN/cache pour `/en` et 301 | à vérifier | ops |
| 404 anglais sous `/en` | décision mineure | produit |

---

## 12. Classification

### VALIDÉ TECHNIQUEMENT

* Inventaire réel : 34 routes, 29 indexables, 5 `noindex`, 8 articles, 2 paires DE/EN.
* Aucune collision de route avec `/en` ; `location /` peut servir `dist/en/...` sans conflit.
* Le pré-rendu actuel produit bien un fichier par route et par langue, mais **pas** le contenu complet.
* Les 29 pages marketing n'utilisent ni `window`, ni `document`, ni requête au rendu : le SSG est réalisable sans réécrire les pages.
* Les défauts identifiés sont reproductibles : coquille de repli, liens de repli anglais vers l'allemand, absence de `hreflang` dans le sitemap.
* La matrice de redirection proposée est sans boucle par construction (cibles sans `lang`, préfixes privés séparés).
* `tsc` et `check:seo` passent sur l'état actuel.

### À IMPLÉMENTER

* Entrée serveur + hydratation (lot 1).
* Arborescence `/en`, basename, switcher, canonical/`hreflang`, sitemap (lot 2).
* 301 `?lang`, 301 préfixes privés, suppression `_i18n` (lot 3).
* Tests §10.2 et mise à jour du garde-fou.

### BLOQUÉ

* Acceptation du critère « HTML complet » tant que le SSG n'est pas livré.
* `/en/impressum`, `/en/terms`, `/en/widerruf` tant que la langue juridique de référence n'est pas décidée.
* Sitemap/canonical de production tant que le domaine définitif n'est pas fourni.
* Lot 4 tant que la décision articles n'est pas prise.

### À VÉRIFIER MANUELLEMENT

* Rendu mobile et longueur des libellés allemands dans la navigation `/en`.
* Comportement du sélecteur sur un article sans traduction.
* Absence de flash de langue à l'hydratation.
* Search Console après bascule (couverture, 404, redirections).
* Attribution des campagnes `utm_*` après 301.
* Langue réelle de la page 404 sous `/en`.

---

## 13. Validation demandée

Le plan démontre que la migration est réalisable **sans perdre de route** : toutes les URL allemandes restent identiques, les URL anglaises deviennent des 301 vers `/en/…`, et les routes privées ne changent pas. Il démontre aussi que le critère « HTML complet » **n'est pas atteint** par l'architecture actuelle : le SSG est un pré-requis, pas une option.

Avant d'implémenter, valider :

1. **SSG d'abord** (lot 1), puis bascule `/en` (lot 2) et redirections (lot 3) ?
2. **Articles** : exception au lancement (recommandée) ou migration stricte `/en/blog/<slug>` ?
3. **Auth/app** : restent sans préfixe (recommandé) ?
4. **`?lang=en`** : 301 immédiat (recommandé) ou alias 200 temporaire ?
5. **Juridique** : l'allemand est-il la version faisant foi ?

Tant que ces points ne sont pas tranchés, aucune URL n'est modifiée et aucun déploiement n'est effectué.
