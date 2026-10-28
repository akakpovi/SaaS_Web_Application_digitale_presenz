# Presence — Shell HTML bilingue pour `?lang=en` et SEO (2026-10-27)

**Périmètre :** frontend `SaaS_Web_Application_UI_UX_frontendV2`, pré-rendu, nginx, garde-fous SEO, tests E2E.
**Hors périmètre :** déploiement VPS, commit, modification des données ou volumes Docker (aucun n'a été touché).
**Question traitée :** une URL annoncée comme anglaise dans `hreflang` livrait un shell **allemand** ; un crawler sans JavaScript recevait donc la mauvaise langue.

---

## 1. État initial constaté

| Constat | Preuve |
| --- | --- |
| Une seule coquille statique, en allemand, pour toutes les URL | `dist/pricing/index.html` et `dist/pricing/index.html?lang=en` étaient servis par le **même** fichier |
| `hreflang="en"` annonçait pourtant une URL anglaise | `dist/pricing/index.html` publiait `<link rel="alternate" hreflang="en" href="…/pricing?lang=en">` |
| La langue anglaise n'existait qu'après exécution de React | `src/i18n/index.tsx` ne lisait `?lang=` que côté client (`localeFromSearch`) |
| Aucun garde-fou ne pouvait constater le défaut | `scripts/prerender.mjs` écrivait un fichier par route, `scripts/check-seo-build.mjs` ne vérifiait pas que l'URL annoncée par `hreflang` servait la langue déclarée |

Le rapport précédent (`PRESENCE_LEGAL_SEO_PRERENDER_2026-10-27.md`) avait déjà établi la couverture SEO des routes publiques ; le défaut restant était **la langue réellement servie**.

## 2. Stratégie retenue

**Variantes HTML par langue, sélectionnées par la query string, servies par nginx** :

* chaque route est écrite **deux fois** au build : `dist/<route>/index.html` (allemand, URL nue) et `dist/_i18n/<route>/index.html` (anglais) ;
* `nginx.conf` sélectionne la variante avec `map $arg_lang $html_variant { default ""; en "/_i18n"; }` puis `location / { try_files $html_variant$uri/index.html $uri/index.html $uri =404; }` ;
* `location /_i18n/ { internal; }` : le dossier de variantes **n'est pas une URL publique** (contenu dupliqué non adressable).

### Options écartées

| Option | Pourquoi écartée |
| --- | --- |
| Routes de langue `/en/…` | Crée de nouvelles URL, impose des redirections, un changement de routeur et invalide tous les `hreflang`/liens déjà annoncés : risque élevé pour un gain non démontré aujourd'hui |
| Sélection par `Accept-Language` | Réponse dépendante d'un en-tête : cache intermédiaire à gérer, et nginx statique ne peut pas la produire |
| Shell anglais « titre seulement » | Interdit explicitement par la demande, et trompeur pour les crawlers |
| Rendu serveur complet | Changement d'architecture (le pré-rendu au build suffit ici) |

**URLs préservées** : aucune URL nouvelle, aucune redirection, aucun alias ajouté. La variante anglaise reste `?lang=en`, exactement l'URL déjà annoncée par `hreflang` et déjà canonique de sa propre variante.

## 3. URLs réellement servies

| URL | Fichier servi | Langue du HTML |
| --- | --- | --- |
| `/pricing` | `dist/pricing/index.html` | `de` |
| `/pricing?lang=en` | `dist/_i18n/pricing/index.html` | `en` |
| `/pricing?lang=de` | `dist/pricing/index.html` (alias de la route nue) | `de` |
| `/_i18n/pricing/index.html` | — | **404** (bloc `internal`) |
| `/blog/<slug>` | `dist/blog/<slug>/index.html` | langue de l'article, `?lang=` sans effet |
| `/app/…`, `/settings/integrations`, `/verify-email`, `/admin` | `dist/index.html` (coquille SPA) | `de` (application privée, `noindex`) |

## 4. Fichiers modifiés

| Fichier | Rôle |
| --- | --- |
| `nginx.conf` | `map $arg_lang $html_variant`, `try_files $html_variant$uri/…` dans `location /`, `location /_i18n/ { internal; }` |
| `scripts/prerender.mjs` | écrit chaque route dans les deux langues, `_i18n` pour l'anglais, canonical/hreflang/`og:locale` par variante, articles jamais dans `_i18n`, sitemap/robots/404 |
| `scripts/check-seo-build.mjs` | garde-fou : rejoue la résolution nginx et exige que toute URL annoncée serve la langue annoncée |
| `scripts/verify-nginx.sh` | exécute le **vrai** nginx avec le **vrai** `nginx.conf` contre `dist/` |
| `src/i18n/index.tsx` | `localeFromSearch()` : le paramètre `?lang=` prime sur la préférence stockée et devient la langue persistée ; `canonicalPath()`/`alternateLinks()` par variante |
| `src/components/SEO.tsx` | tête runtime alignée sur la coquille : canonical de la variante, alternates par `hreflang`, `bilingual={false}` pour un article |
| `src/lib/prerenderedHead.ts` | supprime les balises pré-rendues **remplacées** par React (identité par `rel`/`hreflang`/`name`/`property`) |
| `src/components/AppShell.tsx` | appelle ce nettoyage dans l'espace privé (coquille publique + `noindex` applicatif) |
| `index.html` | commentaire de coquille (langue par défaut) |
| `Dockerfile` | `ARG VITE_BASE_URL` / `ARG VITE_WP_API_URL` transmis au build |
| `e2e/bilingual-shell-dist.spec.ts`, `e2e/legal-seo-dist.spec.ts`, `e2e/helpers/static-dist.ts`, `e2e/README.md` | tests de l'**artefact** : nginx modélisé depuis `dist/`, pas le serveur de dev |
| `package.json` | scripts `check:seo` et `check:nginx` |
| `.github/workflows/ci.yml` | `pnpm run build` (donc le garde-fou) avec `VITE_BASE_URL` |

## 5. Preuves sur le HTML brut généré

Build de référence (origine publique + CMS local, comme l'injection CI/Docker) :

```bash
cd SaaS_Web_Application_UI_UX_frontendV2
VITE_BASE_URL=https://presence.example VITE_WP_API_URL=http://127.0.0.1:8081/wp-json pnpm run build
# [prerender] 34 public routes × 2 languages + 8 articles, sitemap 37 URLs, base=https://presence.example
# [check-seo] routes=34 (5 noindex) · pre-rendered=34 · articles=8 · sitemap=37
# ✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.   → exit 0
```

`presence.example` est l'origine déjà utilisée par la CI : **aucun domaine de production n'a été inventé**.

### 5.1 Variante anglaise d'une route

`dist/_i18n/pricing/index.html` (sans JavaScript) :

```html
<html lang="en">
<title data-prerender-head="true">Simple Website Monitoring Pricing | Presence</title>
<link rel="canonical" href="https://presence.example/pricing?lang=en">
<link rel="alternate" hreflang="de" href="https://presence.example/pricing">
<link rel="alternate" hreflang="en" href="https://presence.example/pricing?lang=en">
<link rel="alternate" hreflang="x-default" href="https://presence.example/pricing">
<meta property="og:locale" content="en_GB">
<meta property="og:locale:alternate" content="de_DE">
<h1>Simple Website Monitoring Pricing | Presence</h1>
<p>Free, Pro (€9/month), Business (€29/month) and Agency (€79/month) plans. …</p>
<a href="/">Home</a> · <a href="/pricing">Pricing</a> · <a href="/blog">Blog</a>
```

La version allemande (`dist/pricing/index.html`) porte `lang="de"`, `og:locale=de_DE`, le titre et le résumé allemands, `hreflang x-default → /pricing` et le même jeu de liens en allemand.

### 5.2 Articles du CMS (branche séparée)

Un article vit sur une **seule** URL, dans sa langue ; ses traductions vivent sur leurs propres slugs.

| Fichier | `html lang` | Canonical | hreflang |
| --- | --- | --- | --- |
| `dist/blog/what-is-website-monitoring/index.html` | `en` | `/blog/what-is-website-monitoring` | `en` → propre slug, `de` → `/blog/de-was-ist-website-monitoring` |
| `dist/blog/de-was-ist-website-monitoring/index.html` | `de` | `/blog/de-was-ist-website-monitoring` | `de` → propre slug, `en` → `/blog/what-is-website-monitoring` |

* Réciprocité vérifiée dans les deux sens, et **aucun** `?lang=` sur un article (ni canonical, ni alternate).
* Les deux têtes annoncent `og:locale` (de_DE / en_GB) et `og:locale:alternate` pour la traduction publiée.
* 8 articles pré-rendus (`dist/blog/<slug>/index.html`), **0** article sous `dist/_i18n/blog/`.

### 5.3 Sitemap et robots

| Contrôle | Résultat |
| --- | --- |
| `<loc>` | 37 |
| URL `?lang=` dans le sitemap | 0 |
| `_i18n` dans le sitemap | 0 |
| Routes privées (`/app/`, `/admin`, `/settings`, `/login`, `/register`, `/report/`) | 0 |
| `localhost` dans `dist/**/*.{html,xml,txt}` | 0 fichier |
| `robots.txt` | `Disallow: /admin`, `Disallow: /report/`, `Sitemap: https://presence.example/sitemap.xml` |

## 6. Hydratation et changement de langue

* `index.html` est **hors** de l'arbre React (`#root`) : React recrée ses propres balises de tête et `dropPreRenderedDuplicates()` (appelé par `SEO`, qui possède ces balises, et par `AppShell`) retire **uniquement** les copies pré-rendues qu'il vient de remplacer. Un titre absent côté React laisse donc la balise de la coquille en place, et un article conserve les langues qu'il ne redéclare pas.
* Aucune duplication constatée : test `the hydrated head describes the requested variant, without duplicates`.
* `?lang=en` prime sur la préférence stockée (l'alternate ne serait sinon mort pour tout visiteur déjà venu), puis cette langue est persistée ; `?lang=de` est un alias de la route nue ; aucun boucle de redirection (le changement de langue dans l'appli ne réécrit pas l'URL).
* Routes privées : `/app/**?lang=en` continue de servir la coquille SPA (`200`), le `noindex` applicatif reste en place.

## 7. Ce que vérifie le garde-fou

`scripts/check-seo-build.mjs` (exécuté par `pnpm run build`, donc par la CI) :

1. chaque route de `routes.json` a ses **deux** fichiers ; toute route du sitemap en a un ;
2. titre, description, canonical, `og:locale`, `hreflang` et `noindex` de chaque variante sont exacts ;
3. chaque URL annoncée par `hreflang` est **résolue par les règles nginx rejouées** et le fichier obtenu doit déclarer `<html lang>` = langue annoncée (routes **et** articles) ;
4. `/_i18n/**` reste inadressable ; `/blog/` n'a pas de variante ;
5. sitemap : entrées attendues, ni URL `?lang=`, ni `_i18n`, ni route privée ; `robots.txt` interdit les routes privées.

L'origine du build est lue dans l'artefact (canonical de `dist/index.html`) quand `--base-url`/`VITE_BASE_URL`/`SITE_URL` ne sont pas fournis : `pnpm run check:seo` fonctionne donc sur un build public sans les variables de la CI.

### Preuves négatives (exécutées, puis restaurées)

**A — variante anglaise de `/impressum` retirée** (`mv dist/_i18n/impressum/index.html`) → `exit 1` :

```
❌ 3 SEO problem(s):
   - dist/_i18n/impressum/index.html: file missing (nginx would answer 404)
   - hreflang en on /impressum advertises /impressum?lang=en, which nginx resolves to "/impressum/index.html"
   - /impressum?lang=en advertises language en but serves <html lang="de">
```

Fichier restauré → `exit 0`.

**B — `location /` sans `$html_variant`** (le défaut d'origine, reproduit) → `exit 1` :

```
❌ 1 SEO problem(s):
   - nginx.conf: `location /` does not try $html_variant$uri/index.html, so ?lang=en would serve the default shell
```

`nginx.conf` restauré (sha256 identique), garde-fou → `exit 0`.

**C — défaut réel attrapé pendant ce travail.** Le premier build avec le CMS a échoué : les articles anglais étaient écrits dans `_i18n`, donc invisibles sur leur slug alors que le sitemap les annonçait.

```
- dist/sitemap.xml advertises an unexpected URL: https://presence.example/blog/how-to-monitor-website-uptime
```

Corrigé : `variantFile()` reçoit désormais un drapeau explicite (`inVariantFolder`) au lieu de déduire le dossier de la langue ; un article garde toujours son propre chemin.

## 8. Défauts trouvés et corrigés

| Défaut | Impact | Correction |
| --- | --- | --- |
| Article anglais écrit sous `_i18n` (§7-C) | Article absent de son URL, sitemap annonçant un 404 | Drapeau explicite `inVariantFolder` dans `scripts/prerender.mjs` |
| `check-seo-build.mjs` supposait `http://localhost:8443` quand aucune origine n'était passée (21 caractères) et tronquait les URL absolues du build public → **367 faux problèmes** | `pnpm check:seo` inutilisable sur un build public | Origine lue dans le canonical de l'artefact + message unique « outside the build origin » et sortie anticipée |
| `verify-nginx.sh` attendait `http://localhost:8443/…` en dur → 2 faux échecs | Le contrôle au vrai nginx échouait sur tout build public | Origine du build calculée (argument, environnement, canonical) |

## 9. Tests réellement exécutés

| Commande | Résultat | Code de sortie |
| --- | --- | --- |
| `VITE_BASE_URL=… VITE_WP_API_URL=… pnpm run build` (vite + pré-rendu + garde-fou) | 34 routes × 2 langues + 8 articles, 37 URL au sitemap, toutes les invariantes OK | **0** |
| `pnpm run check:seo` (seul, sur le build public) | `origin=https://presence.example`, `articles=8`, `sitemap=37`, ✅ | **0** |
| `node scripts/check-seo-build.mjs --base-url=https://other.example` | 12 messages « outside the build origin » (1 par traduction d'article), pas 367 troncatures | **1** (attendu) |
| Preuves négatives A, B puis restauration | voir §7 | **1**, **1**, puis **0** |
| `bash scripts/verify-nginx.sh` (nginx 1.27-alpine réel, `nginx.conf` réel, `dist/` monté) | 22 vérifications, 0 échec : variantes DE/EN servies, `/_i18n` en 404, 404 réels, en-têtes de sécurité | **0** |
| `pnpm exec tsc --noEmit` | aucune erreur | **0** |
| `node scripts/check-i18n.mjs` | 1858 clés dans `en.json` **et** `de.json`, interpolations identiques, parité exacte ; 43 littéraux visibles restants dans 24 fichiers (recensés) | **0** |
| `pnpm test:e2e` (suite complète, pile Docker réelle) | **28 réussis, 0 échec** (5 min 0 s) | **0** |
| `playwright test e2e/legal-seo-dist.spec.ts e2e/bilingual-shell-dist.spec.ts` | 11 réussis (dont `every public URL answers in the language its hreflang entry declares`, `each advertised hreflang URL opens the advertised language`, `the hydrated head describes the requested variant, without duplicates`, `the language variant folder is not a URL of its own`) | **0** |

Après ces exécutions, seuls `scripts/check-seo-build.mjs` et `scripts/verify-nginx.sh` (outils de contrôle, hors bundle et hors suites Playwright) ont changé : leurs propres contrôles ont été relancés et sont verts ci-dessus.

## 10. Limites et points ouverts

1. **Variante en query string.** `?lang=en` est servi comme vrai HTML, auto-canonique et annoncé par `hreflang`, mais rien ne garantit qu'un moteur traite un paramètre comme une page distincte ; le risque est une consolidation sur l'URL allemande. Si l'acquisition anglaise devient un objectif, la variante par chemin (`/en/…`) est la suite logique — elle demande routeur, redirections et sitemap, ce qui n'était pas nécessaire ici.
2. **Pas de test d'indexation réelle** : le travail porte sur le HTML et les métadonnées générés, pas sur le comportement de Google.
3. **Pré-rendu des articles dépendant du CMS au moment du build.** Sans `VITE_WP_API_URL` joignable, les articles sont rendus côté client et absents du sitemap (la liste `/blog` reste pré-rendue) ; le `docker-compose.yml` transmet `VITE_WP_API_URL` (`/cms` par défaut) et `VITE_BASE_URL`. Un CMS indisponible au build ne casse donc pas le site, mais dégrade le SEO des articles — à surveiller en production.
4. **Contenu de la coquille** : le corps pré-rendu contient le chrome localisé, le titre, le `h1` et le résumé de la route (identiques dans les deux langues), pas l'intégralité de la page React. Deux détails cosmétiques préexistants y subsistent et s'affichent brièvement avant hydratation / pour les crawlers : un `h1` suffixé « | Presence » et une ligne `Path: /pricing`. Aucun impact linguistique, symétrique DE/EN.
5. **`?lang=de`** est un alias non canonique de la route nue (documenté dans `nginx.conf` et dans le garde-fou) ; il n'a pas de canonical propre, volontairement.
6. **Aucun cache/CDN testé** : la sélection reposant uniquement sur la query string, aucune réponse ne dépend d'un en-tête, donc pas de `Vary` à gérer ; un cache d'edge reste à vérifier sur l'infrastructure réelle.
7. `scripts/verify-nginx.sh` **passe par `SKIP` (exit 0)** si Docker ou l'image `nginx:1.27-alpine` manque : lire sa sortie, un `SKIP` n'est pas un succès.

## 11. Classification

| Élément | Statut |
| --- | --- |
| Les 34 routes publiques × 2 langues : coquilles pré-rendues, `html lang`, titre, description, canonical, `hreflang`, `og:locale` | **VALIDÉ** (garde-fou + HTML brut + E2E) |
| `?lang=en` sert un HTML anglais sans JavaScript pour chaque route annoncée | **VALIDÉ** (garde-fou §3, vrai nginx, E2E dist) |
| Articles CMS : langue propre, traductions sur leurs slugs, réciprocité, jamais de `?lang=` | **VALIDÉ** (8 articles, garde-fou 3c) |
| Sitemap : 37 URL canoniques, aucune URL `?lang=`, `_i18n` ou privée ; `robots.txt` | **VALIDÉ** |
| `/_i18n/**` inadressable (404) | **VALIDÉ** (modèle + vrai nginx) |
| Hydratation React sans doublon de tête, sélecteur de langue, persistance, desktop/mobile | **VALIDÉ** (E2E 28/28, dont deux suites de pages publiques et une suite authentifiée) |
| TypeScript, parité i18n, build de production | **VALIDÉ** (exits 0) |
| Indexation effective par les moteurs de recherche | **À VÉRIFIER MANUELLEMENT** (hors de portée technique) |
| Comportement d'un cache/CDN devant nginx, en-têtes en production | **À VÉRIFIER MANUELLEMENT** |
| Pré-rendu des articles en production (CMS joignable au build) | **À VÉRIFIER MANUELLEMENT** (dépend de l'exploitation) |
| Choix définitif query string vs `/en/…` | **À VÉRIFIER MANUELLEMENT** (décision produit/SEO) |
| Déploiement VPS | **BLOQUÉ** (hors périmètre demandé) |

## 12. Prochaines priorités

1. Décider si la variante anglaise reste `?lang=en` ou passe à `/en/…` avant de communiquer sur le marché anglophone (impact : routeur, redirections, sitemap).
2. Ajouter `verify-nginx.sh` à la CI quand Docker y est disponible, et vérifier le CMS joignable au build en production (pré-rendu des articles).
3. Reprendre les 43 littéraux visibles restants (24 fichiers) recensés par `scripts/check-i18n.mjs`.
4. Nettoyer les deux détails cosmétiques de la coquille (§10.4) lors d'un prochain passage sur le pré-rendu.
