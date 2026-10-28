# Presence — Pré-rendu SEO des pages juridiques publiques

**Date :** 27 octobre 2026
**Périmètre :** `SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2`
**Nature :** correction de la couverture SEO des pages juridiques + porte de contrôle automatisée
**Aucun déploiement, aucun commit, aucune opération Docker, aucune donnée touchée.**

---

## 1. Statut en une phrase

`/impressum` et `/cookies` étaient **absents de `src/seo/routes.json`** : le build ne générait
aucun `dist/<route>/index.html` pour eux, et la règle nginx
`location / { try_files $uri/index.html $uri =404; }` renvoyait donc un **404 dur en production**
(le serveur de dev masquait le défaut par son repli SPA). Les deux routes sont désormais
pré-rendues, présentes dans le sitemap, et une **porte de contrôle du build** échoue si une route
publique n'est pas servie par son propre fichier pré-rendu.

---

## 2. État initial constaté (avant modification)

| Constat | Preuve |
| --- | --- |
| Routes publiques déclarées : **32** | `src/seo/routes.json` |
| `/impressum`, `/cookies` absentes de `routes.json` | `grep` sur le fichier |
| Fichiers pré-rendus manquants | `dist/impressum/index.html` → ABSENT, `dist/cookies/index.html` → ABSENT (privacy/terms/widerruf PRÉSENTS) |
| `sitemap.xml` généré : **27 `<loc>`**, sans impressum/cookies | `dist/sitemap.xml` |
| Règle nginx applicable | `nginx.conf` : `location / { try_files $uri/index.html $uri =404; }` → `=404` pour les deux routes |
| Métadonnées anglaises de `/widerruf` en allemand | `routes.json` : `title == titleDe`, `description == descriptionDe` |
| `og:locale` anglais incohérent | `SEO.tsx` : `en_US` (hydraté) vs `en_GB` (alternate du shell statique et `LOCALE_TAGS`) |
| Pré-rendu non idempotent | `cleanHead()` ne retirait pas les `rel="alternate"` : un second `prerender.mjs` produisait 6 alternates par page et les faisait fuiter sur les pages `noindex` |
| Routes juridiques réelles du routeur | `/privacy`, `/terms`, `/impressum`, `/cookies`, `/widerruf` — **aucun alias** `/datenschutz` ou `/agb` n'existe : rien de tel n'a été créé |

---

## 3. Fichiers modifiés

| Fichier | Nature |
| --- | --- |
| [src/seo/routes.json](../../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/seo/routes.json) | + `/impressum`, + `/cookies` (titres/descriptions DE **et** EN) ; métadonnées EN réelles pour `/widerruf` |
| [scripts/prerender.mjs](../../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/scripts/prerender.mjs) | `cleanHead()` retire aussi les `rel="alternate"` (idempotence) ; `robots.txt` interdit en plus `/verify-email` |
| [scripts/check-seo-build.mjs](../../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/scripts/check-seo-build.mjs) | **nouveau** — porte SEO du build (HTML généré, sitemap, robots, résolution nginx) |
| [package.json](../../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/package.json) | `build` exécute la porte ; nouveau script `check:seo` |
| [src/components/SEO.tsx](../../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/components/SEO.tsx) | `og:locale` anglais : `en_US` → `en_GB` (aligné sur `LOCALE_TAGS` et le shell) |
| [e2e/legal-seo-dist.spec.ts](../../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/e2e/legal-seo-dist.spec.ts) | **nouveau** — sert `dist/` avec les règles nginx et vérifie pages juridiques, sitemap, robots |
| [e2e/README.md](../../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/e2e/README.md) | documente la nouvelle suite et son prérequis `pnpm build` |

Aucun catalogue i18n, aucun composant métier, aucun contrôle d'accès, aucun prix, aucune logique
de scan et aucune traduction existante n'ont été modifiés.

---

## 4. Routes et langues pré-rendues

**34 routes** pré-rendues (32 avant), dont **5 `noindex`** (`/login`, `/register`,
`/forgot-password`, `/reset-password`, `/onboarding`) ; **sitemap : 29 URLs** (27 avant).

| Route juridique | Fichier généré | `<html lang>` | `robots` | Canonical | hreflang | Sitemap |
| --- | --- | --- | --- | --- | --- | --- |
| `/impressum` | `dist/impressum/index.html` **(nouveau)** | `de` | `index,follow` | `http://localhost:8443/impressum` | `de`, `en`, `x-default` | oui (0.3) |
| `/cookies` | `dist/cookies/index.html` **(nouveau)** | `de` | `index,follow` | `http://localhost:8443/cookies` | `de`, `en`, `x-default` | oui (0.3) |
| `/privacy` | `dist/privacy/index.html` | `de` | `index,follow` | oui | `de`, `en`, `x-default` | oui (0.3) |
| `/terms` | `dist/terms/index.html` | `de` | `index,follow` | oui | `de`, `en`, `x-default` | oui (0.3) |
| `/widerruf` | `dist/widerruf/index.html` | `de` | `index,follow` | oui | `de`, `en`, `x-default` | oui (0.2) |

Langues : l'allemand est la langue du shell statique (défaut de lancement, `DEFAULT_LOCALE` dans
`src/i18n`), l'anglais étant servi par la même URL avec `?lang=en` — c'est exactement la stratégie
des alternates (`alternateLinks()`), le canonical restant sans paramètre. `title`/`description`
anglais de `routes.json` documentent la copie anglaise ; **le build ne les consomme pas
aujourd'hui** (le shell est allemand par conception) — ce point est traité en § 8.

### Métadonnées vérifiées dans le HTML généré

```
<title>Impressum | Presence</title>
<meta name="description" content="Anbieterinformationen nach § 5 DDG für Presence, den Dienst zur Überwachung der digitalen Präsenz." />
<meta name="robots" content="index,follow" />
<link rel="canonical" href="http://localhost:8443/impressum" />
<link rel="alternate" hreflang="de" href="http://localhost:8443/impressum?lang=de" />
<link rel="alternate" hreflang="en" href="http://localhost:8443/impressum?lang=en" />
<link rel="alternate" hreflang="x-default" href="http://localhost:8443/impressum?lang=de" />
<meta property="og:locale" content="de_DE" />
<meta property="og:locale:alternate" content="en_GB" />
```

`/cookies` suit le même schéma (`<title>Cookies und Speicherung | Presence</title>`), et le repli
`<div id="root">` de ces pages ne contient **aucune donnée d'identité** ni placeholder : la porte
de contrôle refuse tout `[…] eintragen` / `[…] enter the …` dans le HTML généré.

### Build avec une origine publique (forme « déploiement », cf. CI et Docker)

`VITE_BASE_URL=https://presence.example pnpm run build` → porte verte, et :

```
<loc>https://presence.example/impressum</loc>                                  (sitemap)
Sitemap: https://presence.example/sitemap.xml                                  (robots.txt)
<link rel="canonical" href="https://presence.example/impressum" />             (HTML)
occurrences http(s)://localhost|127.0.0.1 dans dist/*.html|*.xml|*.txt : 0
```

---

## 5. Tests et contrôles réellement exécutés

| Commande | Code de sortie | Résultat observé |
| --- | --- | --- |
| `pnpm exec tsc --noEmit` | **0** | aucune erreur (inclut `src`, `e2e`, `vite.config.ts`, `playwright.config.ts`) |
| `node scripts/check-i18n.mjs` (racine) | **0** | parité **1858/1858**, interpolations identiques ; 43 littéraux résiduels dans 24 fichiers (inchangé par cette tâche) |
| `pnpm run build` (origine locale) | **0** | 34 routes + 0 article, sitemap 29 URLs, porte verte |
| `VITE_BASE_URL=https://presence.example pnpm run build` | **0** | porte verte, URLs absolues, aucun `localhost` |
| `pnpm exec playwright test e2e/legal-seo-dist.spec.ts` | **0** | **5/5** (2 exécutions, état livré) |
| `pnpm exec playwright test` (suite complète, 8 fichiers) | **1** | **21 réussis, 1 échec** — `authenticated-i18n.spec.ts` (voir § 8) |
| `pnpm exec playwright test e2e/authenticated-i18n.spec.ts -g "render in German and switch to English"` | **0** | **1/1** — le même test passe seul, sans changement de code |

Aucune de ces vérifications ne porte sur l'indexation réelle par un moteur de recherche : elles
prouvent la **génération** et la **servabilité** des fichiers, pas un classement Google.

### Preuves négatives (la porte n'est pas complaisante)

| Scénario | Résultat |
| --- | --- |
| A. `dist/impressum` + `dist/cookies` supprimés (état d'avant correction) | porte : **exit 1**, 6 problèmes dont `nginx resolves to "=404" instead of "/impressum/index.html"` ; spec E2E : **2 échecs** (`/impressum is not served by nginx — Received: 404`) |
| B. porte lancée avec `--base-url=https://presence.example` sur un `dist` construit pour localhost | **exit 1**, 237 problèmes (`canonical is http://localhost:8443/, expected https://presence.example/`) |
| C. assertion renforcée du test d'hydratation (statut HTTP de la navigation) | échoue bien en `404` dans l'état cassé — sans elle, la SPA rendait la page depuis la coquille 404 et masquait le défaut |
| D. `prerender.mjs` exécuté deux fois de suite | avant correction : 6 alternates par page et alternates **fuités sur les pages `noindex`** → porte **exit 1** ; après correction : 3 alternates par page publique, **0** sur `noindex`, porte **exit 0** |
| E. métadonnées anglaises de `/widerruf` remises provisoirement à l'identique de l'allemand | **exit 1** : `routes.json /widerruf: English and German titles are identical (untranslated?)` (+ description) ; fichier restauré **byte-identique** (`diff` vide) et porte revenue **exit 0** |
| F. `dist/` absent (build non lancé) | la spec E2E échoue avec l'instruction `run pnpm build` au lieu de « passer » en sautant |

---

## 6. Défauts détectés puis corrigés dans cette tâche

1. **404 dur sur les deux pages juridiques allemandes** (`/impressum`, `/cookies`) — P1 lancement.
2. **Absence des mêmes routes dans le sitemap** — P2.
3. **Métadonnées anglaises de `/widerruf` laissées en allemand** — P2 (invisible dans un build
   allemand, faux dès que la paire anglaise est utilisée).
4. **Pré-rendu non idempotent** (`cleanHead()` ne retirait pas les `rel="alternate"`) — P2, trouvé
   par la nouvelle porte.
5. **`og:locale` anglais incohérent** entre le shell statique (`en_GB`) et le head hydraté
   (`en_US`) — P3. Aucun test n'affirmait `en_US`.
6. **`robots.txt` généré n'interdisait pas `/verify-email`** (URL porteuse de jeton) — P2.

---

## 7. Checklist

| Élément | Statut |
| --- | --- |
| Audit initial du dépôt et de l'outillage SEO | **VALIDÉ TECHNQUEMENT** |
| `/impressum` pré-rendu, servi en 200 par les règles nginx | **VALIDÉ TECHNQUEMENT** |
| `/cookies` pré-rendu, servi en 200 par les règles nginx | **VALIDÉ TECHNQUEMENT** |
| `/privacy`, `/terms`, `/widerruf` toujours pré-rendus (non-régression) | **VALIDÉ TECHNQUEMENT** |
| `<html lang="de">`, titre, description DE, `og:locale`, `robots` dans le HTML généré | **VALIDÉ TECHNQUEMENT** |
| Canonical absolu, sans `?lang=`, et alternates `de`/`en`/`x-default` | **VALIDÉ TECHNQUEMENT** |
| Sitemap : 29 URLs, aucune route privée/`noindex`, aucun doublon, aucune query string | **VALIDÉ TECHNQUEMENT** |
| Chaque URL du sitemap est réellement servie (aucun 404 annoncé) | **VALIDÉ TECHNQUEMENT** |
| `robots.txt` : `Sitemap:` absolu, routes privées interdites | **VALIDÉ TECHNQUEMENT** |
| Aucune route alias inventée (chaque entrée de `routes.json` existe dans `src/App.tsx`) | **VALIDÉ TECHNQUEMENT** |
| Aucun `localhost` dans un build à origine publique | **VALIDÉ TECHNQUEMENT** |
| TypeScript, parity i18n, build local et build public | **VALIDÉ TECHNQUEMENT** |
| Suite E2E complète verte | **ÉCHEC PARTIEL** — 21/22 ; `authenticated-i18n` instable (§ 8) |
| Indexation effective (Google Search Console) | **À VÉRIFIER MANUELLEMENT** |
| Origine réelle de production (`VITE_BASE_URL`) | **BLOQUÉ** — domaine non fourni |
| Étape « Verify prerendered output » de la CI | **ÉCHEC (pré-existant)** — § 8 |
| Validité juridique des textes | **À VÉRIFIER PAR UN JURISTE** (inchangé, cf. `PRESENCE_LEGAL_PAGES_DE_2026-10-27.md`) |

---

## 8. Limitations, blocages et points à décider

1. **Instabilité du test `authenticated-i18n.spec.ts` (non modifié).** Trois exécutions dans la
   même session avec le même code : échec sur `pageErrors` (suite complète), échec sur
   `html[lang]` attendu `de` reçu `en` (exécution ciblée), puis **réussite** (exécution ciblée
   identique). Le fichier contient déjà des garde-fous explicites contre les ré-optimisations de
   dépendances Vite, ce qui confirme un environnement connu comme instable. Ce test parcourt 13
   pages authentifiées avec inscription + e-mail réel : aucune de ces surfaces n'est touchée par
   les fichiers modifiés ici. **Non corrigé** (le corriger supposerait de modifier un test existant
   sans diagnostic reproductible) ; à traiter comme P2.
2. **Étape CI `Verify prerendered output` probablement en échec avant cette tâche.** Elle exige
   `dist/blog/what-is-dmarc/index.html` (recherche de « BlogPosting ») alors que cet article n'est
   pré-rendu que si `VITE_WP_API_URL` est une URL absolue joignable au build ; la CI ne définit pas
   cette variable et le build local annonce `0 articles`. Constat, non corrigé : le corriger
   reviendrait à adapter une vérification CI à un CMS absent.
3. **Shell statique allemand pour `?lang=en`.** Un crawler sans JavaScript qui suit
   `hreflang="en"` reçoit le `<title>`/`<meta>` allemands (le contenu hydraté est bien anglais).
   C'est la conception actuelle (allemand = défaut de lancement, un fichier par chemin, nginx ne
   distingue pas la query string). Impact SEO réel, à trancher : accepter, ou générer un shell
   par langue avec des règles nginx dédiées. **À VÉRIFIER MANUELLEMENT.**
4. **Divergence locale shell ↔ hydraté.** Avec `pnpm build` sans variable d'environnement exportée,
   le shell utilise le repli `http://localhost:8443` alors que le bundle utilise `VITE_BASE_URL`
   de `.env` (`https://localhost`). En Docker/CI la variable est exportée et les deux concordent.
   La porte affiche toujours l'origine qu'elle a contrôlée, donc une divergence devient visible.
   **À VÉRIFIER MANUELLEMENT** avant tout build manuel sur le serveur.
5. **Descriptions shell ↔ pages pour `/privacy` et `/terms`.** Le shell statique utilise la
   description de `routes.json`, la page hydratée utilise `legal.privacySubtitle` /
   `legal.termsSubtitle` (qui mentionnent « Arbeitsentwurf / working draft »). Les deux sont
   allemand/anglais corrects, mais non identiques. Décision produit : garder, ou aligner.
6. **`public/robots.txt` et `public/sitemap.xml` (replis de développement)** contiennent encore
   `https://localhost/...`. Ils sont écrasés dans `dist` par `scripts/prerender.mjs` (vérifié : le
   build public ne contient aucun `localhost`) ; ils ne concernent que `vite dev`/`vite preview`.
7. **Pages non pré-rendues, par conception** : `/blog/:slug` (dépend du CMS), `/scan/:id`,
   `/report/:id`, `/verify-email`, `/app/*`, `/admin` — servies par la coquille SPA par des règles
   nginx explicites, et absentes du sitemap.
8. **Non testé ici** : le rendu mobile des nouvelles pages (déjà couvert par
   `legal-pages-i18n.spec.ts`, qui passe : débordement horizontal ≤ 1 px à 390 px en DE et EN), et
   l'indexation réelle.

---

## 9. Comment relancer les preuves

```bash
cd SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2
pnpm run build                                  # vite build + prerender + porte SEO (exit 0 requis)
node scripts/check-seo-build.mjs --require-public-origin --base-url=https://<domaine>   # porte de lancement
pnpm exec playwright test e2e/legal-seo-dist.spec.ts
```
