# Presence — SSG complet du site public (lot 1) — 2026-10-28

Statut global : **VALIDÉ TECHNIQUEMENT** pour l'implémentation SSG et les 36 tests
automatisés du lot 1 (URL existantes), **sous deux réserves explicitement non
automatisées** : revue visuelle pixel par pixel, et attribution Git impossible tant que
l'arbre de travail reste non commité. Le repli CMS indisponible a été reproduit sur le
code final le 2026-10-28 (§18). Aucune URL, règle nginx, donnée ou configuration de
déploiement n'a été modifiée pendant ce lot.

> **Consolidation 2026-10-28** — les sections 11 à 15 ajoutent les preuves brutes, les
> corrections B.1/B.2 et les résultats finaux. Deux chiffres de la première version étaient
> faux : il y a **8** tests SSG ajoutés (et non 7), donc **28** tests préexistants
> (et non 29) ; et les échecs de `verify-nginx.sh` n'étaient pas une course au démarrage
> mais un faux négatif `pipefail`/`SIGPIPE` sur les pages de ~60 Ko.

---

## 1. Périmètre et état initial

Le lot part du rapport [PRESENCE_URL_STRATEGY_EN_2026-10-28.md](./PRESENCE_URL_STRATEGY_EN_2026-10-28.md).
La SPA React rendait toutes les pages côté navigateur ; le pré-rendu précédent n'écrivait
qu'une coquille de secours (titre, description, H1, liens de pied de page). Le HTML brut
ne contenait donc ni les sections marketing, ni les tableaux de prix, ni les réponses FAQ,
ni le contenu juridique.

Contraintes respectées : URL inchangées, variante anglaise toujours `?lang=en`,
`dist/_i18n/` toujours `internal`, aucune redirection, aucun changement nginx, aucun commit,
aucun déploiement.

---

## 2. Architecture retenue

```
src/App.tsx                 AppRoutes (arbre de routes partagé) + App (navigateur)
src/AppProviders.tsx        pile de providers commune navigateur / build
src/entry-server.tsx        renderToPipeableStream + StaticRouter -> HTML complet
src/main.tsx                hydrateRoot si data-ssg="true", sinon createRoot
scripts/prerender.mjs       rend chaque route x langue, écrit dist/ + sitemap/robots
scripts/check-seo-build.mjs garde-fou sur les fichiers réellement produits
```

* **Un seul arbre de routes.** `AppRoutes` est exporté par `App.tsx` : le navigateur
  l'enveloppe dans `BrowserRouter`, le build dans `StaticRouter`. Une route ne peut pas
  exister d'un côté et manquer de l'autre.
* **Rendu complet au build.** `renderToPipeableStream(...)` avec `onAllReady` attend la
  résolution des routes `React.lazy` avant d'écrire le fichier : le HTML ne contient jamais
  le `<PageLoader />` à la place de la page.
* **Hydratation réelle.** `main.tsx` lit `data-ssg="true"` et `document.documentElement.lang`.
  Sur une page pré-rendue, `hydrateRoot` démarre dans la langue du document (aucune
  divergence `localStorage`/HTML). Les routes sans SSG (5 `noindex`, articles CMS) gardent
  `createRoot` et leur comportement antérieur.
* **Providers SSR-safe.**
  - `ThemeProvider` : `window`/`localStorage`/`matchMedia` protégés (`typeof window`),
    thème initial `light` côté serveur ; aucun composant public ne rend selon le thème.
  - `I18nProvider` : `initialLocale` explicite fourni par les deux entrées.
  - `SEO` : pas de `window.location` au rendu serveur (`VITE_BASE_URL` ou chaîne vide),
    tags émis après le montage, puis `dropPreRenderedDuplicates()` retire les copies
    pré-rendues qu'il remplace.
  - `AuthProvider` : aucune lecture de `localStorage` au rendu (uniquement `useEffect`),
    aucune session simulée côté serveur.
  - `BlogPage` : reçoit les articles du build via `BlogDataContext` + `#__blog-data`,
    aucune requête réseau pendant le rendu d'un composant.

---

## 3. Routes et variantes effectivement pré-rendues

`src/seo/routes.json` : **34 routes**, dont **5 `noindex`**
(`/login`, `/register`, `/forgot-password`, `/reset-password`, `/onboarding`).

* **29 routes indexables × 2 langues = 58 pages SSG** dans `dist/` :
  accueil, pricing, FAQ, blog, about, contact, 5 pages juridiques, 6 solutions,
  8 fonctionnalités, 4 outils.
* **Allemand** : `<route>/index.html` (`<html lang="de">`).
* **Anglais** : `_i18n/<route>/index.html` (`<html lang="en">`), servi par nginx
  uniquement pour `<route>?lang=en`.
* **8 articles WordPress** : `dist/blog/<slug>/index.html`, contenu réel du CMS,
  langue de l'article, `hreflang` par slug (jamais `?lang=`).
* **5 routes `noindex`** : coquille légère inchangée, `noindex,nofollow`, ni canonical
  ni alternates. Testé.
* **Routes privées/dynamiques non pré-rendues** (inchangé) : `/app/*`, `/admin`,
  `/scan/:id`, `/report/:id`, `/settings/integrations`, `/verify-email`.
* **Sitemap** : 37 URL (29 canoniques + 8 articles), aucune route privée, aucune
  entrée `_i18n` ou `?lang=`.

Fichiers produits (extrait mesuré sur le build validé) :

| Fichier | langue | SSG | `<h2>` | taille | H1 |
| --- | --- | --- | --- | --- | --- |
| `dist/index.html` | de | oui | 7 | 60 677 o | Ihre digitale Präsenz, jederzeit unter Kontrolle. |
| `dist/_i18n/index.html` | en | oui | 7 | 59 973 o | Your digital presence, always under control. |
| `dist/pricing/index.html` | de | oui | 1 | 21 215 o | Einfache, transparente Preise |
| `dist/_i18n/pricing/index.html` | en | oui | 1 | 20 873 o | Simple, transparent pricing |
| `dist/faq/index.html` | de | oui | 5 | 27 981 o | Häufig gestellte Fragen |
| `dist/features/ssl-monitoring/index.html` | de | oui | 8 | 23 607 o | SSL-Zertifikatsüberwachung |
| `dist/privacy/index.html` | de | oui | 12 | 20 183 o | Datenschutzerklärung |
| `dist/terms/index.html` | de | oui | 12 | 17 776 o | Allgemeine Geschäftsbedingungen |
| `dist/widerruf/index.html` | de | oui | 5 | 10 024 o | Widerrufsrecht |
| `dist/blog/index.html` | de | oui | 3 | 17 223 o | Leitfäden zur digitalen Präsenz für kleine Unternehmen |
| `dist/blog/de-was-ist-website-monitoring/index.html` | de | statique + `createRoot` | 5 | 8 326 o | Was ist Website-Monitoring? |

Les tailles incluent les balises et les styles inline ; le texte utile a été vérifié
séparément (voir §4).

---

## 4. Preuves de contenu dans le HTML brut

Contrôles automatisés (`scripts/check-seo-build.mjs`, `e2e/ssg-dist.spec.ts`) et lecture
directe des fichiers :

* **Accueil** : hero (`Ihre digitale Präsenz, jederzeit unter Kontrolle.` /
  `Your digital presence, always under control.`), 7 `<h2>` et 9 `<section>`, CTA
  `Kostenlos starten` / `Get started`, liens juridiques du footer. Pas de
  `data-prerender="true"`.
* **Pricing** : les 4 cartes (`Free`, `Pro`, `Business`, `Agency`), les 4 prix
  (`€0`, `€9`, `€29`, `€79`), la mention `/Monat` (DE) / `/month` (EN), la FAQ tarifs
  et la mention Paddle. La page allemande ne contient pas la copie anglaise et
  réciproquement.
* **FAQ** : questions **et réponses** réelles. Les panneaux sont repliés avec l'attribut
  `hidden` au lieu d'un rendu conditionnel (`{active === key && ...}` supprimait les
  réponses du HTML). On trouve par exemple la réponse complète
  « Website-Monitoring ist der automatische, kontinuierliche Prozess … » dans
  `dist/faq/index.html`, et plus de 10 panneaux `hidden` par langue.
  Même correction dans les FAQ de l'accueil, des pages fonctionnalités et des outils.
* **Fonctionnalités** : `/features/ssl-monitoring` contient les sections propres à la
  page (`Was Presence prüft`, `Häufige Fragen`, `Verwandte Funktionen`, 8 `<h2>`),
  pas seulement un H1 générique.
* **Pages juridiques** : contenu réel (12 sections pour Datenschutz et AGB), blocs
  d'identité centralisés (`config/operator.json`), avertissements de brouillon
  toujours visibles (`Diese Seite muss vor dem Livegang vervollständigt werden` /
  `This page must be completed before launch`). Aucun texte juridique n'a été
  supprimé ni présenté comme validé.
* **Blog** : `dist/blog/index.html` embarque `#__blog-data` avec les 8 articles du
  build ; chaque article pré-rendu contient son `<article>` WordPress réel
  (> 500 caractères de texte utile), son titre, sa catégorie et sa date.

---

## 5. Comportement si WordPress est indisponible au build

`scripts/prerender.mjs` :

* lit `.env` comme `vite build` (`loadEnv`) et non plus seulement `process.env` :
  `VITE_WP_API_URL` n'est plus silencieusement perdu lors d'un `pnpm run build` ;
* résout un CMS same-origin (`/cms`) contre l'origine du build **si elle est loopback**
  (`localhost`, `127.0.0.1`) ; pour cette origine locale uniquement, la vérification du
  certificat auto-signé est désactivée (aucun impact sur un CMS distant) ;
* timeout de 10 s, puis repli explicite ;
* ne génère **jamais** de faux article. Le blog reste alors une coquille servi par la
  SPA, marquée dans le HTML par `<!-- ssg:blog-fallback cms-unavailable -->`, et
  `check-seo-build.mjs` la signale en **warning** (pas en succès silencieux) ;
* si le CMS répond, le build produit 8 articles et la page blog en SSG complet.

Comportement observé le 2026-10-28 avec CMS injoignable :
`[prerender] WordPress unreachable (fetch failed) — blog articles will be client-rendered.`
puis `[check-seo] … ⚠️ dist/blog/index.html: CMS unreachable at build time — blog index is
a client-rendered fallback (not pre-rendered)` et **exit 0** (limitation documentée, build
non bloqué). Avec le CMS local joignable : `58 SSG pages + 8 articles`, `sitemap 37 URLs`.

---

## 6. Fichiers modifiés

| Fichier | Raison |
| --- | --- |
| `src/App.tsx` | extrait `AppRoutes`, arbre partagé navigateur/build |
| `src/AppProviders.tsx` | pile de providers commune, contexte Helmet serveur |
| `src/entry-server.tsx` | rendu React complet (`renderToStream`, `StaticRouter`) |
| `src/main.tsx` | `hydrateRoot` sur `data-ssg`, langue initiale = langue du document, données blog |
| `src/contexts/BlogDataContext.tsx` | articles du build transmis à `BlogPage` |
| `src/pages/BlogPage.tsx` | démarre avec les articles du build, refetch au changement de langue |
| `src/i18n/index.tsx` | `initialLocale` déterministe ; `?lang=` prioritaire, détection inchangée hors SSG |
| `src/components/SEO.tsx` | origine configurée au build, tags émis après montage, dédoublonnage |
| `src/lib/prerenderedHead.ts` | suppression ciblée des balises pré-rendues remplacées |
| `src/components/AppShell.tsx` | `ThemeProvider` protégé pour le rendu serveur |
| `src/pages/FAQPage.tsx`, `Landing.tsx`, `ToolPage.tsx`, `FeaturePage.tsx` | réponses FAQ dans le HTML, repli visuel via `hidden` |
| `scripts/prerender.mjs` | rendu SSG, variantes, `.env`, CMS loopback, marqueur de repli |
| `scripts/check-seo-build.mjs` | garde-fous de contenu (prix, FAQ, sections, juridique, articles), warnings CMS |
| `e2e/ssg-dist.spec.ts` | **nouveau** : contenu brut, articles, hydratation, blog |
| `e2e/bilingual-shell-dist.spec.ts` | assertions de contenu adaptées au SSG, JSON-LD conservé autorisé |
| `package.json` | scripts `build` / `build:ssr` (SSR puis prerender puis check:seo) |

Aucun catalogue `de.json` / `en.json` n'a été modifié dans ce lot : les clés et la parité
restent celles du lot i18n précédent.

---

## 7. Tests réellement exécutés

| Commande | Résultat | Code de sortie |
| --- | --- | --- |
| `pnpm exec tsc --noEmit` | aucune erreur | **0** |
| `node /…/scripts/check-i18n.mjs` | catalogue 1858 clés DE/EN, parité et interpolations OK ; **43** littéraux JSX restants (inchangés) | **0** |
| `pnpm run build` (vite + SSR + prerender + check:seo) | 58 pages SSG, 8 articles, sitemap 37 | **0** |
| `pnpm check:seo` (inclus dans le build) | « ✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant. » | **0** |
| `pnpm exec playwright test` | **36 réussis / 36**, 6 min 30 s (dont 8 nouveaux tests SSG) | **0** |
| `bash scripts/verify-nginx.sh` | **22 vérifications `ok`**, vrai nginx + vrai `nginx.conf` | **0** |

Détail Playwright : **28 tests préexistants** (i18n public/authentifié, juridique, SEO dist,
scans, inscription, identité exploitant) + **8 tests `ssg-dist.spec.ts`** = 36. Le chiffre
« 28 » de la référence du 27 octobre est donc le bon ; la première version de ce rapport
comptait 7 tests SSG alors que le fichier en déclare 8 (voir §11.5 pour la liste brute).
Aucun test existant n'a été affaibli ; les deux adaptations portent sur le contenu des
coquilles devenues des pages complètes et sur le JSON-LD pré-rendu que l'application ne
remplace pas.

### Tests ajoutés (`e2e/ssg-dist.spec.ts`)

1. **Landing** : sections marketing, CTA, FAQ et liens juridiques dans le HTML brut, DE et EN.
2. **Pricing** : 4 plans, 4 prix, périodicité localisée, DE et EN.
3. **FAQ** : première réponse complète présente, panneaux repliés par `hidden` (> 10).
4. **Fonctionnalité** : sections propres (`what we check`, FAQ, related), ≥ 5 `<h2>`, pas de coquille.
5. **Juridique** : contenu propre à chaque page + avertissement de brouillon, DE et EN.
6. **Articles CMS** : `<article>` réel (> 500 caractères), titre présent, aucun article vide.
7. **Hydratation** : `html lang` = langue servie, H1 identique au HTML brut, aucun
   `data-prerender`, aucun message d'erreur d'hydratation (console + `pageerror`),
   sélecteur DE/EN fonctionnel sur 6 URL (accueil, pricing, FAQ × 2 langues).
8. **Blog** : les articles de `#__blog-data` sont visibles après hydratation.

---

## 8. Régressions et limites restantes

> Tableau historique du premier rapport. Les statuts consolidés, avec leurs réserves,
> sont au §15 ; les limites détaillées sont au §16.

| Élément | Statut |
| --- | --- |
| URL publiques, canonical, hreflang, `x-default`, `og:locale`, `robots` | **VALIDÉ** — inchangés, vérifiés sur le HTML brut et après hydratation |
| Sitemap et `robots.txt` | **VALIDÉ** — 37 URL canoniques, aucune route privée, `_i18n` non adressable |
| Routes `noindex` | **VALIDÉ** — coquille légère conservée, aucun canonical/alternate |
| Hydratation (aucune erreur console, aucun remplacement de contenu) | **VALIDÉ** — 6 URL, 2 langues |
| Contenu complet des pages | **VALIDÉ** — contrôles par page, pas seulement un H1 |
| Articles CMS pré-rendus | **VALIDÉ TECHNIQUEMENT** (CMS joignable au build) |
| CMS injoignable au build | **LIMITE DOCUMENTÉE** — blog en coquille SPA, marqueur + warning, build non bloqué |
| Articles CMS | **LIMITE** — pages statiques (pas de SSG React) : `createRoot` remplace le contenu, comportement identique à la SPA précédente. Le HTML brut reste complet. |
| Variante anglaise | **INCHANGÉE** — toujours `?lang=en`, pas de `/en/`, pas de redirection |
| Sélecteur de langue public | **INCHANGÉ** — il ne réécrit pas l'URL (test existant conservé). Conséquence assumée : un rechargement de l'URL nue repart en allemand ; l'anglais durable passe par `?lang=en`. Les pages privées (`/app/*`) gardent la préférence `localStorage`. |
| Origine du build | **LOCAL** — `https://localhost` ; aucun domaine public inventé. `VITE_BASE_URL` doit être défini avant un build public. |
| Sitemap bilingue | **INCHANGÉ** — seules les URL canoniques allemandes y figurent (l'anglais est auto-canonique via `?lang=`). Décision du lot précédent, hors périmètre. |
| `scripts/verify-nginx.sh` | **VALIDÉ APRÈS CORRECTION** — la cause réelle des échecs n'était pas le démarrage : `printf '%s' "$body" \| grep -qF` sous `set -o pipefail` produit un `SIGPIPE` quand `grep -q` ferme le tube au premier match ; sur les pages de ~60 Ko (accueil), le pipeline est alors vu comme un échec. Le script écrit désormais le corps dans un fichier avant `grep`. Une attente de disponibilité sur le contenu exact (`/?lang=en`, statut 200 + `<html lang="en"`) a aussi été ajoutée. **3 exécutions à froid : 22/22 `ok`, exit 0** (voir §11.2 et §12). |
| Rendu visuel desktop/mobile | **À VÉRIFIER MANUELLEMENT** — les suites E2E couvrent les viewports mobile/desktop et l'absence de débordement sur les pages publiques et authentifiées, mais aucune revue visuelle pixel par pixel n'a été faite dans ce lot. |

### Décisions à prendre avant un build public

1. **CMS de build** : fournir une URL WordPress joignable depuis le runner (absolue ou
   same-origin loopback) pour pré-rendre les articles. Sinon le blog reste en coquille
   explicite et les articles ne sont pas dans le sitemap du build.
2. **Origine publique** : définir `VITE_BASE_URL` (canonical, hreflang, sitemap, OG).
3. **`/en/` et redirections** : hors lot 1, à planifier selon
   `PRESENCE_URL_STRATEGY_EN_2026-10-28.md`.

---

## 9. Confirmation de non-modification

* Aucun changement de `nginx.conf`, `Dockerfile` ni des règles de déploiement dans ce lot.
* Aucune URL publique créée, supprimée ou redirigée.
* Aucune base, aucun volume Docker, aucune donnée utilisateur supprimés ou migrés.
* Aucun commit, aucun push, aucun déploiement VPS.
* Les modifications locales préexistantes (i18n, juridique, SEO) ont été préservées.

---

## 10. Synthèse

Le site public est désormais **réellement généré au build** : chaque route indexable
existe en HTML complet, en allemand et en anglais, avec les sections marketing, les prix,
les réponses FAQ et les textes juridiques que le navigateur reçoit avant JavaScript.
`hydrateRoot` reprend ce HTML sans erreur, sans doublon de métadonnées et sans remplacer
la page. Les articles WordPress sont pré-rendus quand le CMS répond au build, avec un
repli explicite et testé sinon. Les URL, le sitemap, les routes `noindex` et nginx sont
inchangés, et l'ensemble des 36 tests Playwright ainsi que les 22 vérifications nginx
passent.

---

# Consolidation finale du 2026-10-28

Cette partie répond point par point à la demande de consolidation : preuves brutes,
correction TLS loopback, correction du harnais nginx, reruns et statuts honnêtes.

## 11. Preuves brutes

### 11.1 État Git réel

Le dépôt compte **29 commits**, mais l'arbre de travail contient un import massif non
commité : `git status --porcelain` renvoie **321 entrées**, dont de nombreux fichiers non
suivis (`scripts/`, `docs/audits/`, etc.), et `git diff --stat` porte sur **142 fichiers
suivis / 18 556 insertions / 7 738 suppressions**, mêlant backend, Docker, documentation
et frontend antérieurs à ce lot. Les fichiers non suivis n'apparaissent pas dans
`git diff`. Le lot SSG n'ayant pas été commité, il est **impossible d'isoler par Git** ses
seuls fichiers : toute affirmation contraire serait fausse. La liste du §6 est la liste des
fichiers effectivement édités pendant le lot SSG ; les preuves d'exécution ci-dessous
portent sur le build produit par ces fichiers.

<details>
<summary>Sortie brute complète — <code>git status --porcelain</code> (321 lignes)</summary>

```text
 M .github/workflows/ci.yml
 M .gitignore
 M "Bilan Complet du Projet.txt"
 M README.md
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/analyze-routes
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/deploy
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/deploy-preview
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/dev
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/dev.json
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/format
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/install
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/langserver
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.figma/make/site.json
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.gitattributes
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.gitignore
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/.mise.toml
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/AGENTS.md
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/CLAUDE.md
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/Dockerfile
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/index.html
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/nginx.conf
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/package.json
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/pnpm-lock.yaml
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/favicon.svg
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/icons/icon.svg
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/manifest.json
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/og-image.svg
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/robots.txt
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/sitemap.xml
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/App.tsx
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/api/authStorage.ts
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/api/client.ts
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/api/endpoints.ts
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/api/hooks/useAuth.ts
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/api/types.ts
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/AppShell.tsx
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/AuroraBackground.tsx
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/AuthGuard.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/Breadcrumb.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/CommandMenu.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/SEO.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/Toast.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/ui.tsx
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/contexts/AuthContext.tsx
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/imports/Presence___Master_Prompt_Frontend_Premium_V2.md
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/imports/pasted_text/seo-optimization-plan.md
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/index.css
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/main.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/AboutPage.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/AdminDashboard.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Alerts.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Auth.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Billing.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/BlogArticle.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/BlogPage.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/ContactPage.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Dashboard.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/FAQPage.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/FeaturePage.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Landing.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Monitoring.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/NotFound.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Onboarding.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Pricing.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/PrivacyPage.tsx
AD SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/PublicReport.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Reports.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Reviews.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Scans.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Settings.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/SolutionPage.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/TermsPage.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/ToolPage.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/WebsiteDetails.tsx
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Websites.tsx
A  SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/vite-env.d.ts
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/tsconfig.json
AM SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/vite.config.ts
 M SaaS_Web_Application_digitale_presenz_v2/backend/.dockerignore
 M SaaS_Web_Application_digitale_presenz_v2/backend/.env.example
 M SaaS_Web_Application_digitale_presenz_v2/backend/.gitignore
 M SaaS_Web_Application_digitale_presenz_v2/backend/Dockerfile
 M SaaS_Web_Application_digitale_presenz_v2/backend/accounts/models.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/accounts/serializers.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/accounts/services.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/accounts/tests/test_auth_api.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/accounts/urls.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/accounts/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/advanced_security/scanners/malware.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/advanced_security/scanners/port_scanner.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/advanced_security/tasks.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/advanced_security/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/alerts/tasks.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/analytics/middleware.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/analytics/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/config/asgi.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/config/settings/base.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/config/urls.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/config/wsgi.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/core/security.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/docker-compose.dev.yml
 M SaaS_Web_Application_digitale_presenz_v2/backend/docker-compose.yml
 M SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/models.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/serializers.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/signals.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/tasks.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/tests/test_models.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/urls.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/nginx/default.conf
 M SaaS_Web_Application_digitale_presenz_v2/backend/notifications/apps.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/notifications/providers.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/notifications/urls.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/notifications/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/public_checker/serializers.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/public_checker/tasks.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/public_checker/tests/test_email_language_detection.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/public_checker/tests/test_legacy_public_checker.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/public_checker/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/reports/serializers.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/reports/services.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/reports/urls.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/reports/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/reviews/serializers.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/reviews/services/bulk_import.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/reviews/urls.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/reviews/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/__init__.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/base.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/executors/__init__.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/executors/command.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/dnsrecon.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/feroxbuster.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/gobuster.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/nikto.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/nmap.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/nuclei.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/testssl.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/whatweb.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/zap.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/parsers/nikto.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/parsers/testssl.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/parsers/zap.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/reviews.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/__init__.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scans/models.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scans/services/orchestrator.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scans/services/scoring.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scans/services/steps_builder.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scans/tasks.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_scanner_engine.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/scans/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/seo/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/social/tasks.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/social/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/management/commands/create_plans.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/models.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/serializers.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/tests/test_subscriptions.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/urls.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/views.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/websites/models.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/websites/serializers.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/websites/tests/test_website_api.py
 M SaaS_Web_Application_digitale_presenz_v2/backend/websites/views.py
 M docker-compose.yml
?? "Presence \342\200\224 Master Prompt Frontend Premium V2.md"
?? "Presence \342\200\224 Master Prompt Frontend Premium.md"
?? "Prompt \342\200\224 Migration Backend Presence vers Scanner Engine.md"
?? "SaaS Web Application UI_UX_frontendV2.zip"
?? SaaS_Web_Application_UI_UX_frontendV2/
?? SaaS_Web_Application_digitale_presenz_v2/.~lock.Dokument_feuille_route_deployement.docx#
?? "SaaS_Web_Application_digitale_presenz_v2/Comptes existants ID E.txt"
?? SaaS_Web_Application_digitale_presenz_v2/Dokument_feuille_route_deployement.docx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/e2e/
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/playwright.config.ts
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/apple-touch-icon.png
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/icons/icon-192.png
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/icons/icon-512.png
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/icons/icon-maskable-512.png
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/og-image.png
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/public/sw.js
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/scripts/
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/AppProviders.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/api/blog.ts
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/api/errors.ts
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/api/hooks/useApiResource.ts
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/AssetSecurityPanel.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/BlogBody.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/LanguageSwitcher.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/LegalReviewNotice.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/OAuthReturnHandler.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/OperatorIdentityDetails.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/SecurityAdvisorChat.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/SocialAuditLog.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/UpgradePrompt.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/config/
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/contexts/BlogDataContext.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/contexts/PlanContext.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/data/
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/entry-server.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/i18n/
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/lib/
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/CookiesPage.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Growth.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/ImpressumPage.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Integrations.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/PublicScanResult.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/SecurityAdvisor.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/VerifyEmail.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/WithdrawalPage.tsx
?? SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/seo/
?? SaaS_Web_Application_digitale_presenz_v2/backend/accounts/emails.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/accounts/migrations/0002_user_profile.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/accounts/profile_urls.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/accounts/tests/test_email_i18n.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/accounts/tests/test_gdpr_api.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/accounts/tests/test_profile_api.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/advanced_security/migrations/0002_rename_advanced_se_website_caeec4_idx_advanced_se_website_ea2faa_idx.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/advanced_security/tests/test_malware.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/advisory/
?? SaaS_Web_Application_digitale_presenz_v2/backend/alerts/tests/test_alert_resolution.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/analytics/migrations/0002_alter_analyticsevent_event_type.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/analytics/tests/
?? SaaS_Web_Application_digitale_presenz_v2/backend/config/settings/test.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/docker/
?? SaaS_Web_Application_digitale_presenz_v2/backend/integrations/
?? SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/migrations/0002_monitoringconfig_scan_type.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/migrations/0003_alter_monitoringconfig_enabled.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/services.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/tests/test_overview_api.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/tests/test_scan_policy.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/monitoring/tests/test_scheduler.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/notifications/migrations/0002_webpushsubscription.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/notifications/migrations/0003_default_email_channel.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/notifications/signals.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/notifications/tests/test_alert_email_delivery.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/notifications/tests/test_push_api.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/organizations/
?? SaaS_Web_Application_digitale_presenz_v2/backend/public_checker/tests/test_scan_access_control.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/reports/tests/test_report_api.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/reviews/services/responses.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/reviews/tests/test_bulk_import.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/reviews/tests/test_review_api.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/artifacts.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/executors/sandbox.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/features.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/lighthouse.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/tool_run.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/parsers/lighthouse.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_advanced_security.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_advanced_tool_adapters.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_artifacts.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_lighthouse.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_reviews_scanner.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_sandbox.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/management/
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/migrations/0005_add_external_security_categories.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/migrations/0006_scannerrun_partial_status.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/migrations/0007_scan_partial_status.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/services/status.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_advanced_security_gate.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_alert_pipeline.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_monitoring_feedback.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_orchestrator_delegation.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_status_integrity.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/seo/migrations/0002_rename_seo_backlin_website_0f7bbd_idx_seo_backlin_website_34587d_idx_and_more.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/social/migrations/0002_rename_social_soci_website_058db5_idx_social_soci_website_9a3d13_idx.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/social/tests/test_social_tasks.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/api_views.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/authentication.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/management/commands/configure_billing.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/management/commands/create_paddle_sandbox.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/migrations/0002_billing_provider_fields.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/migrations/0003_api_key.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/migrations/0004_rename_billing_event_index.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/permissions.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/pricing.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/services/
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/tasks.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/tests/test_billing.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/tests/test_entitlement_expiry.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/tests/test_paddle_sandbox.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/tests/test_paid_plan_gates.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/websites/migrations/0004_scanner_engine.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/websites/migrations/0005_website_organization.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/websites/migrations/0006_website_websites_we_organiz_d596c4_idx_and_more.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/websites/permissions.py
?? SaaS_Web_Application_digitale_presenz_v2/backend/websites/tests/test_tenant_access.py
?? SaaS_Web_Application_digitale_presenz_v2/docs/
?? audit/AUDIT_PRESENCE_2026-10-14.md
?? audit/PRR_DIAGNOSTIC_2026-10-14.md
?? audit/RAPPORT_FINAL_PARITE_2026-10-23.md
?? audit/RAPPORT_ITERATION_1_P0_2026-10-14.md
?? audit/RAPPORT_ITERATION_2_P0_2026-10-14.md
?? audit/RAPPORT_ITERATION_4_2026-10-21.md
?? audit/RAPPORT_ITERATION_5_2026-10-23.md
?? audit/RAPPORT_PARITE_API_UI_2026-10-23.md
?? audit/RAPPORT_PRODUCTION_READINESS_2026-10-19.md
?? auditfrontendV2.txt
?? "compte de teste.docx"
?? docs/
?? frontend/src/App.tsx.bak
?? frontend/src/pages/Alerts.tsx.bak
?? frontend/src/pages/Alerts.tsx.bak2
?? frontend/src/pages/WebsiteDetails.tsx.bak
?? load/
?? logs/backend-rebuild.log
?? logs/backend-rebuild2.log
?? logs/scanner-tools-build.log
?? logs/testdb-cleanup.log
?? logs/tests_advisory.log
?? logs/tests_scanners.log
?? logs/tests_scans.log
?? logs/validation-run1.log
?? logs/validation-security.log
?? nginx/
?? omniroute_key.txt
?? presence_before_migration_repair_20260909_135204.sql
?? scripts/
?? wordpress/
```

</details>

<details>
<summary>Sortie brute complète — <code>git diff --stat</code> (142 fichiers)</summary>

```text
 .github/workflows/ci.yml                           |   81 +-
 .gitignore                                         |    6 +
 Bilan Complet du Projet.txt                        |  109 ++
 README.md                                          |  285 +++-
 .../.figma/make/site.json                          |    3 +-
 .../.gitignore                                     |    7 +
 .../Dockerfile                                     |   13 +-
 .../index.html                                     |   28 +-
 .../nginx.conf                                     |  203 ++-
 .../package.json                                   |    9 +-
 .../pnpm-lock.yaml                                 |   44 +
 .../public/manifest.json                           |   18 +-
 .../public/robots.txt                              |    4 +-
 .../public/sitemap.xml                             |   87 +-
 .../src/App.tsx                                    |  136 +-
 .../src/api/client.ts                              |  199 ++-
 .../src/api/endpoints.ts                           |  114 +-
 .../src/api/types.ts                               |  733 +++++++++-
 .../src/components/AppShell.tsx                    |  154 ++-
 .../src/components/Breadcrumb.tsx                  |    4 +-
 .../src/components/CommandMenu.tsx                 |  119 +-
 .../src/components/SEO.tsx                         |  147 +-
 .../src/components/Toast.tsx                       |    4 +-
 .../src/components/ui.tsx                          |  103 +-
 .../src/main.tsx                                   |   75 +-
 .../src/pages/AboutPage.tsx                        |  140 +-
 .../src/pages/AdminDashboard.tsx                   |  555 ++++----
 .../src/pages/Alerts.tsx                           |  652 +++++++--
 .../src/pages/Auth.tsx                             |  236 ++--
 .../src/pages/Billing.tsx                          |  520 ++++---
 .../src/pages/BlogArticle.tsx                      |  680 +++------
 .../src/pages/BlogPage.tsx                         |  212 +--
 .../src/pages/ContactPage.tsx                      |   76 +-
 .../src/pages/Dashboard.tsx                        |  714 ++++++----
 .../src/pages/FAQPage.tsx                          |  249 ++--
 .../src/pages/FeaturePage.tsx                      |  887 +++++-------
 .../src/pages/Landing.tsx                          |  771 +++++------
 .../src/pages/Monitoring.tsx                       |  824 ++++++++---
 .../src/pages/NotFound.tsx                         |   24 +-
 .../src/pages/Onboarding.tsx                       |  214 +--
 .../src/pages/Pricing.tsx                          |  359 +++--
 .../src/pages/PrivacyPage.tsx                      |  373 ++---
 .../src/pages/PublicReport.tsx                     |  347 -----
 .../src/pages/Reports.tsx                          |  673 ++++++---
 .../src/pages/Reviews.tsx                          |  951 ++++++++++---
 .../src/pages/Scans.tsx                            |  893 ++++++++----
 .../src/pages/Settings.tsx                         | 1438 ++++++++++++++++----
 .../src/pages/SolutionPage.tsx                     |  448 ++----
 .../src/pages/TermsPage.tsx                        |  332 ++---
 .../src/pages/ToolPage.tsx                         |  560 +++-----
 .../src/pages/WebsiteDetails.tsx                   |  540 +++++---
 .../src/pages/Websites.tsx                         |  361 +++--
 .../tsconfig.json                                  |    2 +-
 .../vite.config.ts                                 |   31 +-
 .../backend/.dockerignore                          |    1 +
 .../backend/.env.example                           |  198 ++-
 .../backend/.gitignore                             |    1 +
 .../backend/Dockerfile                             |   53 +-
 .../backend/accounts/models.py                     |   41 +
 .../backend/accounts/serializers.py                |   45 +-
 .../backend/accounts/services.py                   |  245 +++-
 .../backend/accounts/tests/test_auth_api.py        |   23 +-
 .../backend/accounts/urls.py                       |    2 +
 .../backend/accounts/views.py                      |  103 +-
 .../backend/advanced_security/scanners/malware.py  |  142 +-
 .../advanced_security/scanners/port_scanner.py     |   30 +-
 .../backend/advanced_security/tasks.py             |    3 +-
 .../backend/advanced_security/views.py             |    3 +
 .../backend/alerts/tasks.py                        |  154 ++-
 .../backend/analytics/middleware.py                |    6 +
 .../backend/analytics/views.py                     |   41 +
 .../backend/config/asgi.py                         |    6 +
 .../backend/config/settings/base.py                |  621 ++++++++-
 .../backend/config/urls.py                         |    4 +
 .../backend/config/wsgi.py                         |    6 +
 .../backend/core/security.py                       |  125 ++
 .../backend/docker-compose.dev.yml                 |    3 +
 .../backend/docker-compose.yml                     |   20 +-
 .../backend/monitoring/models.py                   |   25 +-
 .../backend/monitoring/serializers.py              |   38 +-
 .../backend/monitoring/signals.py                  |   11 +-
 .../backend/monitoring/tasks.py                    |  162 ++-
 .../backend/monitoring/tests/test_models.py        |    7 +-
 .../backend/monitoring/urls.py                     |    6 +
 .../backend/monitoring/views.py                    |  153 ++-
 .../backend/nginx/default.conf                     |    7 +
 .../backend/notifications/apps.py                  |    3 +
 .../backend/notifications/providers.py             |   51 +-
 .../backend/notifications/urls.py                  |    2 +
 .../backend/notifications/views.py                 |   73 +-
 .../backend/public_checker/serializers.py          |    1 +
 .../backend/public_checker/tasks.py                |    7 +-
 .../tests/test_email_language_detection.py         |   47 +-
 .../tests/test_legacy_public_checker.py            |  310 ++---
 .../backend/public_checker/views.py                |  188 ++-
 .../backend/reports/serializers.py                 |   18 +
 .../backend/reports/services.py                    |   79 ++
 .../backend/reports/urls.py                        |   17 +-
 .../backend/reports/views.py                       |  102 +-
 .../backend/reviews/serializers.py                 |   38 +
 .../backend/reviews/services/bulk_import.py        |   59 +-
 .../backend/reviews/urls.py                        |    4 +
 .../backend/reviews/views.py                       |   67 +
 .../backend/scanners/__init__.py                   |    3 +
 .../backend/scanners/base.py                       |  235 +++-
 .../backend/scanners/executors/__init__.py         |   27 +-
 .../backend/scanners/executors/command.py          |   24 +-
 .../backend/scanners/implementations/dnsrecon.py   |  235 ++--
 .../scanners/implementations/feroxbuster.py        |    6 +-
 .../backend/scanners/implementations/gobuster.py   |  288 ++--
 .../backend/scanners/implementations/nikto.py      |  198 ++-
 .../backend/scanners/implementations/nmap.py       |  278 ++--
 .../backend/scanners/implementations/nuclei.py     |  701 ++++++++--
 .../backend/scanners/implementations/testssl.py    |  327 ++++-
 .../backend/scanners/implementations/whatweb.py    |  207 +--
 .../backend/scanners/implementations/zap.py        |  648 +++++++--
 .../backend/scanners/parsers/nikto.py              |   76 +-
 .../backend/scanners/parsers/testssl.py            |   80 +-
 .../backend/scanners/parsers/zap.py                |  113 +-
 .../backend/scanners/reviews.py                    |  126 +-
 .../backend/scanners/tests/__init__.py             |  102 ++
 .../backend/scans/models.py                        |   38 +-
 .../backend/scans/services/orchestrator.py         |  690 +++++++++-
 .../backend/scans/services/scoring.py              |    3 +-
 .../backend/scans/services/steps_builder.py        |   21 +-
 .../backend/scans/tasks.py                         |  245 +++-
 .../backend/scans/tests/test_scanner_engine.py     |  159 ++-
 .../backend/scans/views.py                         |   41 +-
 .../backend/seo/views.py                           |    3 +
 .../backend/social/tasks.py                        |  203 ++-
 .../backend/social/views.py                        |    3 +
 .../management/commands/create_plans.py            |   69 +-
 .../backend/subscriptions/models.py                |  117 ++
 .../backend/subscriptions/serializers.py           |   16 +
 .../subscriptions/tests/test_subscriptions.py      |   40 +-
 .../backend/subscriptions/urls.py                  |   15 +-
 .../backend/subscriptions/views.py                 |  284 +++-
 .../backend/websites/models.py                     |   19 +-
 .../backend/websites/serializers.py                |   42 +-
 .../backend/websites/tests/test_website_api.py     |   27 +
 .../backend/websites/views.py                      |   98 +-
 docker-compose.yml                                 |  389 +++++-
 142 files changed, 18556 insertions(+), 7738 deletions(-)
```

</details>

### 11.2 Preuves HTML brutes (commandes demandées)

Les commandes sont exécutées telles quelles sur le build final. Deux limites de ces
commandes doivent être lues avec leur sortie :

* `grep -c 'hidden'` compte des **lignes**, pas des occurrences, et le HTML SSG est
  minifié sur une seule ligne : la sortie `1` ne signifie donc pas « un seul panneau ».
* `grep -o '<h2[^>]*>.*</h2>'` est **glouton** (`.*`) : sur une ligne unique, il ne
  capture que le dernier `<h2>` de la page.

```text
$ grep -o "<h2[^>]*>.*</h2>" dist/pricing/index.html | head -20
<h2 class="text-2xl font-bold text-slate-900 text-center mb-8">Häufige Fragen</h2>
$ grep -o "€[0-9]*" dist/pricing/index.html
€
€
€
€
€
€
€
€
€
€0
€9
€29
€79
$ grep -c "hidden" dist/faq/index.html
1
$ grep -o "<article[^>]*>" dist/blog/digital-presence-checklist-small-business/index.html
<article>
$ grep -o 'html lang="[a-z]*"' dist/index.html dist/_i18n/index.html
dist/index.html:html lang="de"
dist/_i18n/index.html:html lang="en"
```

Contrôles précis complémentaires (mêmes fichiers, expressions non gloutonnes) :

```text
FAQ answer panels (hidden=""): 21
FAQ <h2>: 5
FAQ first answer: Website-Monitoring ist der automatische, kontinuierliche Prozess, bei dem geprüft wird, ob Ihre Website erreichbar ist, gute Ladezeiten hat und korrekt konfiguriert ist. (phrase exacte, coupée après le premier point)
Pricing <h2> texts: Häufige Fragen (les plans sont des cartes <h3>)
Pricing prices: €0, €9, €29, €79 (plus 9 occurrences de « € » seules dans les libellés)
Pricing /Monat: 17 occurrences
Landing: 60 677 octets, 7 <h2>, 9 <section>
Article visible text: de-ssl-zertifikat-pruefen 2 136 caractères ; de-was-ist-website-monitoring 2 182
<html lang>: dist/index.html = de ; dist/_i18n/index.html = en
```

Le premier article choisi par `find` est
`digital-presence-checklist-small-business/index.html` ; il contient bien `<article>`.
Les tailles d'article ci-dessus sont le texte visible du `<body>` après retrait de
`<script>`, `<style>` et des balises (pas des octets de fichier).

### 11.3 Sortie complète de <code>pnpm check:seo</code>

```text
$ node scripts/check-seo-build.mjs
[check-seo] origin=https://localhost (local preview — canonical/sitemap stay local)
[check-seo] routes=34 (5 noindex) · pre-rendered=58 · articles=8 · sitemap=37
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
```

Aucun avertissement CMS dans ce build : le CMS loopback a répondu et les 8 articles ont
été pré-rendus. Le repli CMS indisponible a depuis été reproduit sur le code final, avec
un build séparé et le `dist/` validé sauvegardé puis restauré ; sortie brute et preuve au
§18.

### 11.4 Sortie complète de <code>check-i18n.mjs</code>

Le script n'a **pas été modifié dans ce lot**. Sortie brute :

```text
── Catalogue parity ──────────────────────────────────────────
en.json keys: 1858
de.json keys: 1858
✅ German catalogue matches the English reference exactly.
✅ Interpolations match in both languages.

── Hardcoded user-visible strings (JSX AST) ──────────────────
Files with remaining literals: 24
Total remaining literals: 43
      4  src/pages/Integrations.tsx
      4  src/pages/Landing.tsx
      3  src/pages/SolutionPage.tsx
      3  src/pages/ToolPage.tsx
      2  src/pages/AboutPage.tsx
      2  src/pages/Auth.tsx
      2  src/pages/ContactPage.tsx
      2  src/pages/FeaturePage.tsx
      2  src/pages/Onboarding.tsx
      2  src/pages/PrivacyPage.tsx
      2  src/pages/PublicScanResult.tsx
      2  src/pages/TermsPage.tsx
      2  src/components/CommandMenu.tsx
      1  src/pages/BlogArticle.tsx
      1  src/pages/BlogPage.tsx
      1  src/pages/CookiesPage.tsx
      1  src/pages/FAQPage.tsx
      1  src/pages/ImpressumPage.tsx
      1  src/pages/Settings.tsx
      1  src/pages/VerifyEmail.tsx
      1  src/pages/Websites.tsx
      1  src/pages/WithdrawalPage.tsx
      1  src/components/AppShell.tsx
      1  src/components/AssetSecurityPanel.tsx
   (run with --verbose for lines and text)
```

Le nombre de littéraux JSX reste **43** (identique à l'audit précédent) ; les catalogues
ont **1858 clés** chacune, avec parité et interpolations validées. Ce contrôle est une
référence historique réexécutée ici, pas une correction i18n de ce lot.

### 11.5 Liste brute des tests Playwright et comptage

```text
Listing tests:
  [chromium] › authenticated-i18n.spec.ts:201:1 › authenticated pages render in German and switch to English
  [chromium] › authenticated-i18n.spec.ts:242:1 › authenticated pages fit a mobile viewport in both languages
  [chromium] › bilingual-shell-dist.spec.ts:97:1 › every public URL answers in the language its hreflang entry declares
  [chromium] › bilingual-shell-dist.spec.ts:174:1 › each advertised hreflang URL opens the advertised language
  [chromium] › bilingual-shell-dist.spec.ts:232:1 › the hydrated head describes the requested variant, without duplicates
  [chromium] › bilingual-shell-dist.spec.ts:283:1 › a noindex route publishes no canonical and no alternates in either variant
  [chromium] › bilingual-shell-dist.spec.ts:306:1 › switching the language keeps the canonical on the requested URL
  [chromium] › launch-readiness.spec.ts:54:1 › public journey: German by default, English switch, legal pages
  [chromium] › launch-readiness.spec.ts:107:1 › mobile layout stays inside the viewport
  [chromium] › launch-readiness.spec.ts:121:1 › blog: German article, translated slug, published posts only
  [chromium] › launch-readiness.spec.ts:157:1 › free plan: first website is accepted, the second is refused
  [chromium] › launch-readiness.spec.ts:203:1 › admin surface is staff-only
  [chromium] › legal-pages-i18n.spec.ts:163:1 › legal pages render in German and in English
  [chromium] › legal-pages-i18n.spec.ts:196:1 › legal pages fit a mobile viewport in both languages
  [chromium] › legal-seo-dist.spec.ts:203:1 › nginx-served legal pages carry their own pre-rendered head in both languages
  [chromium] › legal-seo-dist.spec.ts:211:1 › the pre-rendered legal pages hydrate in German and in English
  [chromium] › legal-seo-dist.spec.ts:221:1 › sitemap.xml advertises the legal pages and no private route
  [chromium] › legal-seo-dist.spec.ts:259:1 › robots.txt protects the private routes and points at the sitemap
  [chromium] › legal-seo-dist.spec.ts:270:1 › client-rendered exceptions and the real 404 still behave
  [chromium] › legal-seo-dist.spec.ts:283:1 › the language variant folder is not a URL of its own
  [chromium] › operator-identity.spec.ts:126:1 › the imprint renders the configured identity and marks the rest
  [chromium] › operator-identity.spec.ts:179:1 › privacy, terms and withdrawal stay on the same source
  [chromium] › public-pages-i18n.spec.ts:208:1 › secondary public pages render in German and switch to English
  [chromium] › public-pages-i18n.spec.ts:239:1 › secondary public pages fit a mobile viewport in both languages
  [chromium] › public-pages-i18n.spec.ts:263:1 › ?lang= links open the advertised language and the hreflang alternates agree
  [chromium] › public-pages-i18n.spec.ts:317:1 › the tool funnel ends on a German report
  [chromium] › public-scan.spec.ts:8:1 › public scan → real report → shared link → lead capture
  [chromium] › registration-verification.spec.ts:9:1 › registration → e-mail link → verified account → login
  [chromium] › ssg-dist.spec.ts:44:1 › the landing page ships its marketing sections, not a shell
  [chromium] › ssg-dist.spec.ts:71:1 › pricing contains every plan and the real prices in both languages
  [chromium] › ssg-dist.spec.ts:91:1 › FAQ answers are in the HTML even while the accordion is closed
  [chromium] › ssg-dist.spec.ts:112:1 › feature pages contain their own sections, not the generic fallback
  [chromium] › ssg-dist.spec.ts:134:1 › legal pages carry their content and the draft warning
  [chromium] › ssg-dist.spec.ts:157:1 › CMS articles ship their real body and title
  [chromium] › ssg-dist.spec.ts:194:1 › the pre-rendered pages hydrate without errors or full replacement
  [chromium] › ssg-dist.spec.ts:246:1 › the blog index lists the build-time posts after hydration
Total: 36 tests in 10 files
```

Comptage par fichier : authenticated 2, bilingual 5, launch 5, legal-pages 2,
legal-seo 6, operator 2, public-pages 4, public-scan 1, registration 1, **ssg-dist 8**
= **36**. Il y a donc **8 nouveaux tests**, pas 7. L'écart se résout arithmétiquement :
36 − 8 = **28 tests préexistants**, exactement la référence du 27 octobre. Les 8 ajouts
sont tous dans le fichier neuf `e2e/ssg-dist.spec.ts` ; aucun test préexistant n'a été
scindé. La mention « 29 préexistants » de la première version était un comptage erroné,
pas une modification de la suite.

Les 8 tests ajoutés dans `e2e/ssg-dist.spec.ts` :

```text
1. the landing page ships its marketing sections, not a shell
2. pricing contains every plan and the real prices in both languages
3. FAQ answers are in the HTML even while the accordion is closed
4. feature pages contain their own sections, not the generic fallback
5. legal pages carry their content and the draft warning
6. CMS articles ship their real body and title
7. the pre-rendered pages hydrate without errors or full replacement
8. the blog index lists the build-time posts after hydration
```

## 12. Correction B.1 — TLS loopback du CMS

### Avant

```js
const loopback = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(parsed.hostname)
...
const request = client.get(
  parsed,
  { headers: { Accept: "application/json" }, rejectUnauthorized: !loopback },
  ...
)
```

Cette version ne vérifiait que la **chaîne** de l'URL, pas l'adresse réellement résolue,
et n'émettait aucun log.

### Après (fonctions exactes de `scripts/prerender.mjs`)

```js
/** `true` only for the two loopback addresses a local stack can publish. */
function isLoopbackAddress(address) {
  return address === "127.0.0.1" || address === "::1"
}

/**
 * Resolve the CMS host and return a loopback IP only when **every** address it
 * resolves to is loopback.
 *
 * Checking the URL string (`localhost`, `127.0.0.1`, `[::1]`) is not enough:
 * a hostname can resolve elsewhere through DNS or `/etc/hosts`, and the TLS
 * relaxation must never apply to a remote CMS. The caller connects to the
 * returned address (not to the hostname again), so the decision cannot change
 * between the check and the request.
 */
async function loopbackAddressFor(parsed) {
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "")
  if (net.isIP(hostname)) return isLoopbackAddress(hostname) ? hostname : null
  const addresses = await dns.lookup(hostname, {
    all: true,
    verbatim: true,
  })
  if (
    addresses.length === 0 ||
    !addresses.every(({ address }) => isLoopbackAddress(address))
  ) {
    return null
  }
  // Prefer IPv4: the local stack publishes its port on 127.0.0.1, while a
  // `localhost` entry may list `::1` first. Both are loopback and verified.
  const preferred = addresses.find(({ family }) => family === 4)
  return (preferred ?? addresses[0]).address
}

/**
 * Fetch JSON for the build.
 *
 * The local docker stack serves its CMS behind a self-signed certificate on
 * loopback; `fetch` refuses that certificate, so a developer build silently
 * lost every article. Verification is relaxed **only** when every resolved
 * address is loopback (where there is no remote peer to impersonate), and the
 * relaxation is logged so it can never pass unnoticed in CI. Any real CMS URL
 * keeps Node's default certificate verification.
 */
async function getJson(url, { timeoutMs = 10_000 } = {}) {
  const parsed = new URL(url)
  const loopback = await loopbackAddressFor(parsed)
  const client = parsed.protocol === "https:" ? https : http
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "")

  if (loopback) {
    console.warn(
      `[prerender] TLS verification disabled for loopback CMS ` +
        `${parsed.host} -> ${loopback} (self-signed local certificate).`,
    )
  }

  // Connect to the already-verified address; keep the original hostname for
  // SNI and the `Host` header. This prevents a second DNS answer from moving
  // the request to a non-loopback peer after the check.
  const options = loopback
    ? {
        host: loopback,
        port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
        path: `${parsed.pathname}${parsed.search}`,
        servername: hostname,
        headers: { Accept: "application/json", Host: parsed.host },
        rejectUnauthorized: false,
      }
    : parsed

  return new Promise((resolve, reject) => {
    const onResponse = (response) => {
      if (!response.statusCode || response.statusCode >= 400) {
        response.resume()
        reject(new Error(`HTTP ${response.statusCode}`))
        return
      }
      let body = ""
      response.setEncoding("utf8")
      response.on("data", (chunk) => {
        body += chunk
      })
      response.on("end", () => {
        try {
          resolve(JSON.parse(body))
        } catch (error) {
          reject(new Error(`invalid JSON (${error.message})`))
        }
      })
    }
    // `(url, options, callback)` for a normal remote CMS; a pre-connected
    // option object when the loopback address was already verified above.
    const request = loopback
      ? client.get(options, onResponse)
      : client.get(parsed, { headers: { Accept: "application/json" } }, onResponse)
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`timed out after ${timeoutMs}ms`))
    })
    request.on("error", reject)
  })
}
```

Points de sécurité :

* **Toutes** les adresses résolues doivent être **exactement** `127.0.0.1` ou `::1`.
  Un sous-domaine qui résout vers une IP publique, ou un `/etc/hosts` détourné vers une
  IP non loopback, désactive le relâchement ; `127.0.0.2` n'est pas accepté.
* La requête se connecte à **l'adresse déjà vérifiée** avec `servername`/`Host` conservés :
  une seconde résolution DNS ne peut pas déplacer la connexion après le contrôle.
* L'activation est **journalisée** à chaque build (observé :
  `TLS verification disabled for loopback CMS localhost -> 127.0.0.1`).

Pourquoi ne pas ajouter le certificat local au trust store du runner : cela exige des
droits administrateur et une modification système sur chaque machine/CI, rend le build
non portable, et élargit la confiance TLS à tout le processus. Le relâchement est ici
strictement limité à une connexion dont toutes les adresses résolues sont loopback.

## 13. Correction B.2 — `verify-nginx.sh`

### Cause réelle (et non « course au démarrage »)

La vérification échouait uniquement sur `/` (les deux variantes), pas sur `/pricing` :
l'accueil fait ~60 Ko, les pages de prix ~21 Ko. `request()` faisait :

```bash
if ! printf '%s' "$body" | grep -qF -- "$want_text"; then
```

Avec `set -o pipefail`, `grep -q` ferme le tube au premier match ; `printf` reçoit
`SIGPIPE` (141) et le pipeline est considéré comme en échec, même quand le texte est
présent. Un pipe buffer de 64 Ko explique la frontière entre les pages qui passaient et
celles qui échouaient. Un curl direct renvoyait bien `<html lang="en">`, ce qui a orienté
à tort vers un problème de démarrage.

### Après

* Le corps est écrit dans `$WORK/response.html` avant `grep`, ce qui supprime le
  `SIGPIPE` et le faux négatif.
* Une attente explicite (60 × 0,5 s) vérifie en plus que `/?lang=en` répond **200** et
  contient **`<html lang="en"`** avant la première assertion.
* Le conteneur reste jetable, démarré et supprimé par le script ; aucun autre conteneur,
  volume ou projet Docker n'est touché. Aucun conteneur applicatif n'a été redémarré :
  le script crée son propre nginx, et redémarrer la stack n'aurait pas corrigé le
  `SIGPIPE` tout en interrompant inutilement les services.

### Trois exécutions à froid consécutives

Chaque exécution précède d'un `docker rm -f presence-nginx-config-check` et le script
recrée son propre conteneur.

**Exécution 1**

```text
[verify-nginx] build origin: https://localhost
[verify-nginx] config=/home/elom/Schreibtisch/SaaS_Web_Application_digitale_presenz/SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/nginx.conf image=nginx:1.27-alpine port=18443
— German (default) is the bare path
  ok    pricing DE — /pricing (200)
  ok    pricing DE via ?lang=de (alias) — /pricing?lang=de (200)
  ok    impressum DE — /impressum (200)
  ok    home DE via ?lang=de — /?lang=de (200)
— English is the advertised ?lang=en URL
  ok    pricing EN lang — /pricing?lang=en (200)
  ok    pricing EN title — /pricing?lang=en (200)
  ok    pricing EN canonical — /pricing?lang=en (200)
  ok    impressum EN title — /impressum?lang=en (200)
  ok    home EN — /?lang=en (200)
  ok    blog listing EN — /blog?lang=en (200)
  ok    login EN shell — /login?lang=en (200)
  ok    login EN stays noindex — /login?lang=en (200)
— The variant folder is internal, unknown URLs stay 404
  ok    variant folder not addressable — /_i18n/pricing/index.html (404)
  ok    variant home not addressable — /_i18n/index.html (404)
  ok    unknown URL is a real 404 — /definitely-not-a-page?lang=en (404)
  ok    unknown URL is a real 404 (DE) — /definitely-not-a-page (404)
— Non-HTML assets and client-rendered routes keep working
  ok    sitemap unaffected by ?lang=en — /sitemap.xml?lang=en (200)
  ok    robots.txt — /robots.txt (200)
  ok    SPA shell for /app/ (unchanged) — /app/dashboard?lang=en (200)
— Security headers still applied by the real config
  ok    header Strict-Transport-Security
  ok    header X-Frame-Options: DENY
  ok    header X-Content-Type-Options: nosniff
✅ nginx.conf serves every advertised language variant (real nginx, real config).
```

**Exécution 2**

```text
[verify-nginx] build origin: https://localhost
[verify-nginx] config=/home/elom/Schreibtisch/SaaS_Web_Application_digitale_presenz/SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/nginx.conf image=nginx:1.27-alpine port=18443
— German (default) is the bare path
  ok    pricing DE — /pricing (200)
  ok    pricing DE via ?lang=de (alias) — /pricing?lang=de (200)
  ok    impressum DE — /impressum (200)
  ok    home DE via ?lang=de — /?lang=de (200)
— English is the advertised ?lang=en URL
  ok    pricing EN lang — /pricing?lang=en (200)
  ok    pricing EN title — /pricing?lang=en (200)
  ok    pricing EN canonical — /pricing?lang=en (200)
  ok    impressum EN title — /impressum?lang=en (200)
  ok    home EN — /?lang=en (200)
  ok    blog listing EN — /blog?lang=en (200)
  ok    login EN shell — /login?lang=en (200)
  ok    login EN stays noindex — /login?lang=en (200)
— The variant folder is internal, unknown URLs stay 404
  ok    variant folder not addressable — /_i18n/pricing/index.html (404)
  ok    variant home not addressable — /_i18n/index.html (404)
  ok    unknown URL is a real 404 — /definitely-not-a-page?lang=en (404)
  ok    unknown URL is a real 404 (DE) — /definitely-not-a-page (404)
— Non-HTML assets and client-rendered routes keep working
  ok    sitemap unaffected by ?lang=en — /sitemap.xml?lang=en (200)
  ok    robots.txt — /robots.txt (200)
  ok    SPA shell for /app/ (unchanged) — /app/dashboard?lang=en (200)
— Security headers still applied by the real config
  ok    header Strict-Transport-Security
  ok    header X-Frame-Options: DENY
  ok    header X-Content-Type-Options: nosniff
✅ nginx.conf serves every advertised language variant (real nginx, real config).
```

**Exécution 3**

```text
[verify-nginx] build origin: https://localhost
[verify-nginx] config=/home/elom/Schreibtisch/SaaS_Web_Application_digitale_presenz/SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/nginx.conf image=nginx:1.27-alpine port=18443
— German (default) is the bare path
  ok    pricing DE — /pricing (200)
  ok    pricing DE via ?lang=de (alias) — /pricing?lang=de (200)
  ok    impressum DE — /impressum (200)
  ok    home DE via ?lang=de — /?lang=de (200)
— English is the advertised ?lang=en URL
  ok    pricing EN lang — /pricing?lang=en (200)
  ok    pricing EN title — /pricing?lang=en (200)
  ok    pricing EN canonical — /pricing?lang=en (200)
  ok    impressum EN title — /impressum?lang=en (200)
  ok    home EN — /?lang=en (200)
  ok    blog listing EN — /blog?lang=en (200)
  ok    login EN shell — /login?lang=en (200)
  ok    login EN stays noindex — /login?lang=en (200)
— The variant folder is internal, unknown URLs stay 404
  ok    variant folder not addressable — /_i18n/pricing/index.html (404)
  ok    variant home not addressable — /_i18n/index.html (404)
  ok    unknown URL is a real 404 — /definitely-not-a-page?lang=en (404)
  ok    unknown URL is a real 404 (DE) — /definitely-not-a-page (404)
— Non-HTML assets and client-rendered routes keep working
  ok    sitemap unaffected by ?lang=en — /sitemap.xml?lang=en (200)
  ok    robots.txt — /robots.txt (200)
  ok    SPA shell for /app/ (unchanged) — /app/dashboard?lang=en (200)
— Security headers still applied by the real config
  ok    header Strict-Transport-Security
  ok    header X-Frame-Options: DENY
  ok    header X-Content-Type-Options: nosniff
✅ nginx.conf serves every advertised language variant (real nginx, real config).
```

Résultat : **3/3 exit 0, 22 vérifications `ok` à chaque fois**. Aucune relance manuelle.

## 14. Partie C — contrôles rejoués après corrections

| Commande | Code de sortie | Résultat |
| --- | --- | --- |
| `pnpm exec tsc --noEmit` | **0** | aucune erreur |
| `pnpm run build` | **0** | 58 pages SSG, 8 articles, sitemap 37 ; avertissement TLS loopback journalisé |
| `pnpm check:seo` | **0** | toutes les invariantes SEO |
| `pnpm exec playwright test` | **0** | **36/36 réussis**, 6 min 30 s |
| `bash scripts/verify-nginx.sh` | **0** | **22/22 `ok`**, vrai nginx |
| `node --check scripts/prerender.mjs` | **0** | syntaxe valide après resserrement TLS |

Après le resserrement final de `isLoopbackAddress` à `127.0.0.1`/`::1` (et non plus tout
`127.0.0.0/8`), le build a été **relancé** : `exit 0`, puis les sommes SHA-256 de **tous**
les fichiers de `dist/` ont été comparées avant/après — **aucune différence**. Les 36 E2E
et les 22 vérifications nginx, exécutés sur cet artefact, portent donc sur des octets
identiques. `check:seo` a également été relancé : `exit 0`.

Extrait du build final :

```text
dist-ssr/assets/Settings-DT-Dwx9E.js                  27.79 kB │ gzip:  7.04 kB
dist-ssr/assets/i18n--XKmSwFr.js                     268.33 kB │ gzip: 85.14 kB

✓ built in 431ms
[prerender] Public origin is https://localhost — canonical/sitemap remain local. Set VITE_BASE_URL before a public deployment.
[prerender] TLS verification disabled for loopback CMS localhost -> 127.0.0.1 (self-signed local certificate).
[prerender] 34 routes × 2 languages (58 SSG pages) + 8 articles, sitemap 37 URLs, base=https://localhost
[check-seo] origin=https://localhost (local preview — canonical/sitemap stay local)
[check-seo] routes=34 (5 noindex) · pre-rendered=58 · articles=8 · sitemap=37
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
```

Sortie finale Playwright :

```text
  ✓  36 [chromium] › e2e/ssg-dist.spec.ts:246:1 › the blog index lists the build-time posts after hydration (641ms)
[e2e] e2e accounts removed: 5 | e2e public leads removed: 1

  36 passed (6.5m)
```

Sortie finale nginx :

```text
  ok    header Strict-Transport-Security
  ok    header X-Frame-Options: DENY
  ok    header X-Content-Type-Options: nosniff
✅ nginx.conf serves every advertised language variant (real nginx, real config).
```

## 15. Statuts d'acceptation du lot 1

| Critère | Statut | Preuve / réserve |
| --- | --- | --- |
| A. Contenu HTML réel de l'accueil | **VALIDÉ TECHNIQUEMENT** | 60 677 o, 7 `<h2>`, 9 `<section>`, hero/CTA/FAQ/footer ; test E2E dédié |
| A. `/pricing` : plans, prix et détails | **VALIDÉ TECHNIQUEMENT** | Free/Pro/Business/Agency, €0/9/29/79, 17 mentions `/Monat` (DE) |
| A. `/faq` : questions **et réponses** | **VALIDÉ TECHNIQUEMENT** | 21 panneaux `hidden=""`, réponses réelles dans le HTML |
| A. Page fonctionnalité spécifique | **VALIDÉ TECHNIQUEMENT** | 8 `<h2>`, sections propres à SSL |
| A. Pages juridiques réelles + brouillon | **VALIDÉ TECHNIQUEMENT** | 12 `<h2>` privacy et terms ; `Arbeitsentwurf` sur privacy/terms, `vor dem Livegang` sur impressum/widerruf |
| A. Article de blog pré-rendu | **VALIDÉ TECHNIQUEMENT** | 8 articles ; deux mesurés : 2 136 et 2 182 caractères de texte visible (CMS joignable au build) |
| A. DE et EN cohérents avec leur langue | **VALIDÉ TECHNIQUEMENT** | `<html lang>`, titres, navigation, tests 2 langues |
| B. Aucune erreur/avertissement d'hydratation | **VALIDÉ TECHNIQUEMENT** | 6 URL × 2 langues, console + `pageerror` vides |
| B. Pas de remplacement complet inattendu | **VALIDÉ TECHNIQUEMENT** | H1 brut = H1 hydraté, aucun `data-prerender` |
| B. Langue HTML = langue initiale React | **VALIDÉ TECHNIQUEMENT** | `initialLocale` = `document.documentElement.lang` |
| B. Métadonnées sans doublons | **VALIDÉ TECHNIQUEMENT** | 1 canonical, 3 alternates, 1 description, 1 titre |
| B. Sélecteur de langue et navigation | **VALIDÉ TECHNIQUEMENT** | test E2E sur 6 URL ; comportement d'URL inchangé |
| C. URL allemandes inchangées | **VALIDÉ TECHNIQUEMENT** | routes.json + nginx, 58 pages mêmes chemins |
| C. Variante anglaise `?lang=en` | **VALIDÉ TECHNIQUEMENT** | 22 checks nginx, HTML EN réel |
| C. Aucun `/en/`, aucune redirection | **VALIDÉ TECHNIQUEMENT** | aucun ajout de route/redirection ; 404 inchangés |
| C. Canonical/hreflang/x-default/robots/sitemap | **VALIDÉ TECHNIQUEMENT** | `check:seo` + 5 tests dist |
| C. `pnpm check:seo` | **VALIDÉ TECHNIQUEMENT** | exit 0 |
| C. `dist/_i18n/` compatible nginx | **VALIDÉ TECHNIQUEMENT** | 22 checks, dossier toujours interne |
| D. TypeScript | **VALIDÉ TECHNIQUEMENT** | exit 0 |
| D. Build de production | **VALIDÉ TECHNIQUEMENT** | exit 0 |
| D. Tests unitaires/intégration pertinents | **VALIDÉ TECHNIQUEMENT** | aucune suite unitaire frontend n'existe (scripts `package.json`) ; couverture par les 36 E2E |
| D. 28 tests Playwright préexistants | **VALIDÉ TECHNIQUEMENT** | 28/28 préexistants + 8 nouveaux = 36/36 |
| D. `verify-nginx.sh` | **VALIDÉ TECHNIQUEMENT** | 3 cold runs + 1 final, 22/22, exit 0 |
| WordPress indisponible au build | **VALIDÉ TECHNIQUEMENT** | reproduit sur le code final le 2026-10-28 : build exit 0, 56 pages, 0 article, sitemap 29, fallback marqué ; voir §18 |
| Aucun commit / déploiement / changement nginx | **À VÉRIFIER MANUELLEMENT (Git)** | aucune commande d'écriture n'a touché nginx/URL ; l'import initial non commité empêche une preuve Git d'attribution |
| Revue visuelle pixel par pixel | **À VÉRIFIER MANUELLEMENT** | E2E viewports OK, aucune inspection visuelle humaine |

## 16. Limites restantes, sans reformulation atténuante

1. **Articles CMS non SSG React.** Le contenu est bien pré-rendu depuis WordPress
   (`<article>`, titre, date), mais l'hydratation de ces pages utilise `createRoot` : React
   remplace le document statique. Ce n'est pas une page SSG React hydratée comme les 58
   autres.
2. **Sélecteur de langue inchangé.** Il ne réécrit pas l'URL. Sur une page publique, un
   rechargement de l'URL nue repart en allemand ; l'anglais durable exige `?lang=en`.
   Les pages `/app/*` conservent la préférence `localStorage`.
3. **Dépendance au CMS au build.** Sans URL WordPress joignable (ou sans CMS loopback),
   le blog reste une coquille SPA explicitement marquée et les articles ne sont pas dans
   le sitemap de ce build.
4. **Origine locale.** `VITE_BASE_URL` n'est pas défini : canonical/sitemap utilisent
   `https://localhost`. Un build public doit fournir l'origine réelle.
5. **Sitemap bilingue inchangé.** Seules les URL canoniques allemandes y figurent ;
   l'anglais est auto-canonique via `?lang=en`. Aucune migration `/en/` n'a été faite.
6. **43 littéraux JSX restants** (24 fichiers) : préexistants, non introduits par ce lot,
   non corrigés ici.
7. **Preuve Git d'attribution impossible** : arbre non commité (321 entrées de status,
   dont des fichiers non suivis ; 142 fichiers suivis dans `git diff`). Aucun commit n'a
   été créé, conformément à la consigne.
8. **Revue visuelle** : les tests couvrent desktop/mobile et l'absence de débordement,
   mais aucune inspection pixel par pixel n'a été réalisée.

## 17. Confirmation de périmètre

* Aucun `git commit`, `git push`, déploiement ou migration de données.
* Aucune écriture dans `nginx.conf`, `docker-compose*`, `Dockerfile` ou les routes
  publiques pendant cette consolidation ; les seuls fichiers touchés sont
  `scripts/prerender.mjs`, `scripts/verify-nginx.sh` et ce rapport.
* Aucune suppression de données, volume ou conteneur hors le conteneur jetable
  `presence-nginx-config-check` créé/supprimé par son propre script.
* Aucune URL `/en/`, redirection 301 ou migration de sitemap n'a été ajoutée.

---

## 18. Vérifications finales du 2026-10-28 — repli CMS et prix

Exécution : **2026-10-28T09:12:01+01:00** (Europe/Berlin), sur le code final du lot 1. Aucun conteneur n'a été
arrêté : le CMS local a été rendu injoignable uniquement pour ce build via
`VITE_WP_API_URL=http://127.0.0.1:9/cms` (port loopback fermé). Le `dist/` validé a été
sauvegardé avant l'expérience, puis le build normal a été relancé après restauration.

### 18.1 Build avec CMS indisponible

Commande :

```text
VITE_WP_API_URL='http://127.0.0.1:9/cms' pnpm run build
```

Code de sortie : **0** (build non bloquant).

Effets observés : **56 pages SSG** au lieu de 58, **0 article**, sitemap **29 URL** au lieu
de 37, marqueur `ssg:blog-fallback cms-unavailable` dans les deux pages blog, et deux
avertissements `check-seo` explicitement acceptés.

Note : le log `TLS verification disabled` apparaît aussi pour cette URL de test en `http`,
car le message est émis dès que la cible est loopback, avant le choix du client HTTP/HTTPS ;
aucune vérification TLS n'est réellement désactivée pour `http`. Le mécanisme reste limité
aux adresses loopback et n'a pas été modifié dans cette vérification.

<details>
<summary>Sortie brute complète</summary>

```text
$ vite build && pnpm run build:ssr && node scripts/prerender.mjs && node scripts/check-seo-build.mjs
vite v8.0.3 building client environment for production...
[2K
transforming...✓ 2464 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                    3.34 kB │ gzip:   1.08 kB
dist/assets/index-Ccfmmdye.css                    64.61 kB │ gzip:  11.60 kB
dist/assets/check-COrqsU1_.js                      0.11 kB │ gzip:   0.12 kB
dist/assets/chevron-down-CWSZB2t2.js               0.11 kB │ gzip:   0.13 kB
dist/assets/chevron-right-QuW1pVpS.js              0.11 kB │ gzip:   0.13 kB
dist/assets/loader-circle-TQ7JpEl6.js              0.13 kB │ gzip:   0.14 kB
dist/assets/plus-CJh9tERh.js                       0.14 kB │ gzip:   0.14 kB
dist/assets/arrow-left-DizIuFGk.js                 0.15 kB │ gzip:   0.15 kB
dist/assets/clock-DMKBsjRq.js                      0.15 kB │ gzip:   0.15 kB
dist/assets/circle-check-big-DzsKWscJ.js           0.18 kB │ gzip:   0.17 kB
dist/assets/lock-D0VT-0-S.js                       0.19 kB │ gzip:   0.18 kB
dist/assets/mail-_f0Odg0R.js                       0.20 kB │ gzip:   0.19 kB
dist/assets/activity-DH1XTKi3.js                   0.22 kB │ gzip:   0.19 kB
dist/assets/copy-BybMT3VS.js                       0.22 kB │ gzip:   0.19 kB
dist/assets/circle-alert-dI1JMaHe.js               0.23 kB │ gzip:   0.17 kB
dist/assets/external-link-BLEgyKH_.js              0.23 kB │ gzip:   0.18 kB
dist/assets/eye-gMwbaar2.js                        0.24 kB │ gzip:   0.19 kB
dist/assets/triangle-alert-DUmHYZfk.js             0.25 kB │ gzip:   0.20 kB
dist/assets/shield-DfcrGUly.js                     0.26 kB │ gzip:   0.21 kB
dist/assets/bell-Cj2CtYo5.js                       0.27 kB │ gzip:   0.22 kB
dist/assets/shield-check-CXJQrla9.js               0.30 kB │ gzip:   0.24 kB
dist/assets/refresh-cw-CGsX3_a9.js                 0.30 kB │ gzip:   0.21 kB
dist/assets/bot-D-uCWHZ2.js                        0.31 kB │ gzip:   0.22 kB
dist/assets/trash-2-BEMDBw-q.js                    0.31 kB │ gzip:   0.20 kB
dist/assets/megaphone-Blg8QUYE.js                  0.33 kB │ gzip:   0.23 kB
dist/assets/shield-alert-BTkahLj7.js               0.34 kB │ gzip:   0.25 kB
dist/assets/loader-XhdColKa.js                     0.39 kB │ gzip:   0.23 kB
dist/assets/star-BJFMGiFm.js                       0.46 kB │ gzip:   0.28 kB
dist/assets/prerenderedHead-DxZWmPMA.js            0.51 kB │ gzip:   0.35 kB
dist/assets/usePricingPlans-CQe5CD8y.js            0.69 kB │ gzip:   0.41 kB
dist/assets/Breadcrumb-CHUjgFCl.js                 0.91 kB │ gzip:   0.51 kB
dist/assets/LegalReviewNotice-CeDc1fuA.js          0.99 kB │ gzip:   0.46 kB
dist/assets/useAuth-BGX6EXMK.js                    1.13 kB │ gzip:   0.58 kB
dist/assets/OperatorIdentityDetails-DofICbUF.js    1.28 kB │ gzip:   0.62 kB
dist/assets/NotFound-CXnmAXbz.js                   1.78 kB │ gzip:   0.72 kB
dist/assets/blog-CvAeL32I.js                       2.08 kB │ gzip:   1.04 kB
dist/assets/pricing-CEtOpt6T.js                    2.27 kB │ gzip:   0.85 kB
dist/assets/CookiesPage-BwNpUd37.js                3.03 kB │ gzip:   1.09 kB
dist/assets/ImpressumPage-DVvbxzUz.js              3.05 kB │ gzip:   1.16 kB
dist/assets/WithdrawalPage-Czh2tvXH.js             3.42 kB │ gzip:   1.12 kB
dist/assets/TermsPage-IJLey5-w.js                  3.80 kB │ gzip:   1.22 kB
dist/assets/PrivacyPage-BlY7UReO.js                3.97 kB │ gzip:   1.24 kB
dist/assets/SEO-DCQ0Fs_l.js                        3.98 kB │ gzip:   1.63 kB
dist/assets/useFormat-CxAlvfLb.js                  4.52 kB │ gzip:   1.65 kB
dist/assets/operator-Cg64XYw-.js                   4.68 kB │ gzip:   1.44 kB
dist/assets/AboutPage-CeT-vkJz.js                  5.09 kB │ gzip:   1.57 kB
dist/assets/VerifyEmail-DIOaOn8j.js                5.14 kB │ gzip:   1.60 kB
dist/assets/Pricing-CZxf9gQI.js                    5.76 kB │ gzip:   2.05 kB
dist/assets/BlogPage-BulNeAGY.js                   5.79 kB │ gzip:   1.94 kB
dist/assets/FAQPage-sajjbQj6.js                    6.20 kB │ gzip:   1.88 kB
dist/assets/ContactPage-5cS-L9d1.js                6.67 kB │ gzip:   2.05 kB
dist/assets/Websites-DjeCPkF7.js                   6.79 kB │ gzip:   2.14 kB
dist/assets/BlogArticle-Da01h4wh.js                8.36 kB │ gzip:   2.72 kB
dist/assets/ui-RZMTuJRB.js                         8.46 kB │ gzip:   2.79 kB
dist/assets/SolutionPage-hKY1RZUi.js               8.49 kB │ gzip:   2.43 kB
dist/assets/Billing-CAtvfTc0.js                    8.70 kB │ gzip:   2.72 kB
dist/assets/Onboarding-Cw0tRZcm.js                 9.20 kB │ gzip:   2.39 kB
dist/assets/client-DKVOCXUf.js                     9.24 kB │ gzip:   3.08 kB
dist/assets/AdminDashboard-DNCI-5_e.js            10.30 kB │ gzip:   2.77 kB
dist/assets/Reports-ZPUE-hWs.js                   10.60 kB │ gzip:   3.56 kB
dist/assets/ToolPage-Bjlnt2dg.js                  12.00 kB │ gzip:   3.28 kB
dist/assets/Growth-CYCOIeCN.js                    12.24 kB │ gzip:   3.37 kB
dist/assets/Alerts-B6whr4SM.js                    12.86 kB │ gzip:   3.55 kB
dist/assets/Dashboard-CBpJHs_-.js                 13.52 kB │ gzip:   3.49 kB
dist/assets/Auth-BxgQhXyZ.js                      13.56 kB │ gzip:   3.55 kB
dist/assets/SecurityAdvisor-C_1hALxl.js           13.67 kB │ gzip:   4.49 kB
dist/assets/PublicScanResult-D-3HP0FM.js          14.93 kB │ gzip:   4.20 kB
dist/assets/Monitoring-DylxRdDa.js                15.38 kB │ gzip:   4.04 kB
dist/assets/Scans-B_tBiUtu.js                     16.03 kB │ gzip:   4.35 kB
dist/assets/index.esm-C6wN_h6T.js                 16.41 kB │ gzip:   5.87 kB
dist/assets/Reviews-BptxGxAX.js                   17.58 kB │ gzip:   5.16 kB
dist/assets/FeaturePage-DeX0aQrl.js               17.73 kB │ gzip:   3.22 kB
dist/assets/Integrations-LChhLXpW.js              18.47 kB │ gzip:   4.99 kB
dist/assets/WebsiteDetails-D87bzHpb.js            19.78 kB │ gzip:   5.32 kB
dist/assets/Landing-Ck4qHPoc.js                   26.84 kB │ gzip:   6.35 kB
dist/assets/purify.es-CBD8qKwf.js                 29.08 kB │ gzip:  11.46 kB
dist/assets/Settings-BfeLMLVd.js                  30.04 kB │ gzip:   7.23 kB
dist/assets/index-Dk76yUbR.js                    228.19 kB │ gzip:  70.32 kB
dist/assets/i18n-DUhhrlDG.js                     320.74 kB │ gzip: 103.79 kB
dist/assets/BarChart-CPBQKB0m.js                 356.86 kB │ gzip: 103.27 kB

✓ built in 2.50s
$ vite build --ssr src/entry-server.tsx --outDir dist-ssr --emptyOutDir
vite v8.0.3 building ssr environment for production...
[2K
transforming...✓ 78 modules transformed.
rendering chunks...
computing gzip size...
dist-ssr/assets/prerenderedHead-DpyYUUUP.js            0.51 kB │ gzip:  0.35 kB
dist-ssr/assets/usePricingPlans-Ci6EYIRH.js            0.68 kB │ gzip:  0.40 kB
dist-ssr/assets/Breadcrumb-Bq5wGl0u.js                 0.91 kB │ gzip:  0.52 kB
dist-ssr/assets/useApiResource-CLZC0NYh.js             0.93 kB │ gzip:  0.49 kB
dist-ssr/assets/LegalReviewNotice-C4ii1XqD.js          0.93 kB │ gzip:  0.46 kB
dist-ssr/assets/LanguageSwitcher-DczRNGXJ.js           0.99 kB │ gzip:  0.60 kB
dist-ssr/assets/useAuth-6DGdsFHI.js                    1.11 kB │ gzip:  0.57 kB
dist-ssr/assets/OperatorIdentityDetails-B3vmBP2V.js    1.22 kB │ gzip:  0.62 kB
dist-ssr/assets/NotFound-DFZ1FZMv.js                   1.69 kB │ gzip:  0.72 kB
dist-ssr/assets/blog-DipTe_pd.js                       2.08 kB │ gzip:  1.04 kB
dist-ssr/assets/pricing-DiLeJyzj.js                    2.27 kB │ gzip:  0.85 kB
dist-ssr/assets/CookiesPage-j9zSvlu9.js                2.60 kB │ gzip:  0.99 kB
dist-ssr/assets/ImpressumPage-c_hFIVed.js              2.64 kB │ gzip:  1.05 kB
dist-ssr/assets/WithdrawalPage-BEERyI7Z.js             3.06 kB │ gzip:  1.06 kB
dist-ssr/assets/TermsPage-BzR8C73y.js                  3.62 kB │ gzip:  1.24 kB
dist-ssr/assets/PrivacyPage-CXPRzsSF.js                3.77 kB │ gzip:  1.26 kB
dist-ssr/assets/SEO-BP1wyUrR.js                        3.86 kB │ gzip:  1.65 kB
dist-ssr/assets/useFormat-DVdyO0ME.js                  4.51 kB │ gzip:  1.64 kB
dist-ssr/assets/operator-COXffeLz.js                   4.68 kB │ gzip:  1.44 kB
dist-ssr/assets/AboutPage-BnRnaXS5.js                  4.72 kB │ gzip:  1.58 kB
dist-ssr/assets/VerifyEmail-UUoa2vBs.js                4.77 kB │ gzip:  1.59 kB
dist-ssr/assets/BlogPage-Cz6hqhYZ.js                   5.35 kB │ gzip:  1.93 kB
dist-ssr/assets/Pricing-BWE5mS3a.js                    5.45 kB │ gzip:  2.05 kB
dist-ssr/assets/FAQPage-CgrqASKI.js                    5.85 kB │ gzip:  1.89 kB
dist-ssr/assets/ContactPage-DaYKZNyT.js                6.05 kB │ gzip:  1.94 kB
dist-ssr/assets/UpgradePrompt-DeT_93Rv.js              6.11 kB │ gzip:  2.20 kB
dist-ssr/assets/Websites-DzQmYl7T.js                   6.27 kB │ gzip:  2.13 kB
dist-ssr/assets/BlogArticle-C0OXvGx-.js                7.41 kB │ gzip:  2.54 kB
dist-ssr/assets/SolutionPage-CpneETv2.js               7.86 kB │ gzip:  2.41 kB
dist-ssr/assets/ui-CP-ZkeTd.js                         7.86 kB │ gzip:  2.66 kB
dist-ssr/assets/Billing-BpM_0B9H.js                    8.04 kB │ gzip:  2.67 kB
dist-ssr/assets/Onboarding-D0VyFT9W.js                 8.59 kB │ gzip:  2.37 kB
dist-ssr/assets/AdminDashboard-dlUv2KFx.js             9.06 kB │ gzip:  2.52 kB
dist-ssr/assets/client-DmdTI4Wd.js                     9.24 kB │ gzip:  3.08 kB
dist-ssr/assets/Reports-3thmqcgI.js                    9.74 kB │ gzip:  3.47 kB
dist-ssr/assets/Alerts-D02zAzB8.js                    11.01 kB │ gzip:  3.12 kB
dist-ssr/assets/Growth-D1ZwumVl.js                    11.28 kB │ gzip:  3.37 kB
dist-ssr/assets/ToolPage-CGHFkRtm.js                  11.31 kB │ gzip:  3.29 kB
dist-ssr/assets/Auth-Cvy1HKBQ.js                      12.00 kB │ gzip:  3.34 kB
dist-ssr/assets/SecurityAdvisor-BGJjfEhc.js           12.40 kB │ gzip:  4.23 kB
dist-ssr/assets/Dashboard-DZO3JDVe.js                 12.44 kB │ gzip:  3.46 kB
dist-ssr/assets/PublicScanResult-IWnNQKW0.js          13.70 kB │ gzip:  4.14 kB
dist-ssr/assets/Monitoring-DwkCOvev.js                14.22 kB │ gzip:  3.98 kB
dist-ssr/assets/Scans-DbAj0ryh.js                     14.87 kB │ gzip:  4.31 kB
dist-ssr/assets/Reviews-DsPGGq2u.js                   15.62 kB │ gzip:  4.83 kB
dist-ssr/assets/Integrations-BnorvjcZ.js              16.41 kB │ gzip:  4.64 kB
dist-ssr/assets/FeaturePage-jIPaRKAn.js               16.98 kB │ gzip:  3.21 kB
dist-ssr/assets/WebsiteDetails-UD3y2YmR.js            17.85 kB │ gzip:  5.12 kB
dist-ssr/assets/Landing-Y9X3c0Qc.js                   24.55 kB │ gzip:  6.21 kB
dist-ssr/entry-server.js                              24.63 kB │ gzip:  6.99 kB
dist-ssr/assets/Settings-DT-Dwx9E.js                  27.79 kB │ gzip:  7.04 kB
dist-ssr/assets/i18n--XKmSwFr.js                     268.33 kB │ gzip: 85.14 kB

✓ built in 556ms
[prerender] Public origin is https://localhost — canonical/sitemap remain local. Set VITE_BASE_URL before a public deployment.
[prerender] TLS verification disabled for loopback CMS 127.0.0.1:9 -> 127.0.0.1 (self-signed local certificate).
[prerender] WordPress unreachable (connect ECONNREFUSED 127.0.0.1:9) — blog articles will be client-rendered.
[prerender] 34 routes × 2 languages (56 SSG pages) + 0 articles, sitemap 29 URLs, base=https://localhost — CMS unreachable: blog articles are served by the SPA at build time. Blog index keeps its fallback shell.
[check-seo] origin=https://localhost (local preview — canonical/sitemap stay local)
[check-seo] routes=34 (5 noindex) · pre-rendered=56 · articles=0 · sitemap=29
⚠️  dist/blog/index.html: CMS unreachable at build time — blog index is a client-rendered fallback (not pre-rendered)
⚠️  dist/_i18n/blog/index.html: CMS unreachable at build time — blog index is a client-rendered fallback (not pre-rendered)
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
```

</details>

### 18.2 Restauration et rebuild de référence

Le CMS n'avait pas été arrêté ; la variable d'environnement a simplement été retirée.
`dist/` a été supprimé puis reconstruit avec `pnpm run build` :

```text

✓ built in 590ms
[prerender] Public origin is https://localhost — canonical/sitemap remain local. Set VITE_BASE_URL before a public deployment.
[prerender] TLS verification disabled for loopback CMS localhost -> 127.0.0.1 (self-signed local certificate).
[prerender] 34 routes × 2 languages (58 SSG pages) + 8 articles, sitemap 37 URLs, base=https://localhost
[check-seo] origin=https://localhost (local preview — canonical/sitemap stay local)
[check-seo] routes=34 (5 noindex) · pre-rendered=58 · articles=8 · sitemap=37
✅ pre-rendered HTML, sitemap and robots.txt satisfy every SEO invariant.
```

Code de sortie : **0**. Le build restauré contient bien **58 pages SSG**, **8 articles** et
**37 URL** de sitemap. Les sommes SHA-256 de **tous** les fichiers de `dist/` sont
**identiques** au `dist/` validé sauvegardé avant le test : `RESTORED_DIST_IDENTICAL=yes`.
L'état final du dépôt correspond donc au build de référence du rapport.

### 18.3 Prix allemands et anglais

Sorties brutes, sans reformatage ni résumé :

```text
$ grep -oE "€[0-9]+" dist/pricing/index.html
€0
€9
€29
€79

$ grep -oE "€[0-9]+" dist/_i18n/pricing/index.html
€9
€29
€79
€9
€29
€79
€9
€29
€79
€0
€9
€29
€79
```

Les valeurs **uniques** sont exactement `€0`, `€9`, `€29`, `€79` dans les deux langues.
Les répétitions anglaises de `€9`, `€29` et `€79` correspondent aux plusieurs emplacements
de prix de la page (cartes et FAQ) ; aucun prix n'est tronqué, fusionné ou mal capturé. La
page allemande affiche les quatre prix une fois chacun.

Statut : **VALIDÉ TECHNIQUEMENT** pour les deux vérifications.

