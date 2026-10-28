# Presence — Internationalisation DE/EN des pages publiques secondaires

**Date :** 27 octobre 2026
**Périmètre :** frontend `SaaS_Web_Application_UI_UX_frontendV2` (React/TypeScript), catalogues i18n, pages publiques secondaires (outils, fonctionnalités, solutions, à propos, contact, scan public), couche SEO statique (`scripts/prerender.mjs`, `src/seo/routes.json`), tests E2E.
**Hors périmètre de ce cycle :** backend Django, Paddle, WordPress, facturation, déploiement VPS. Aucune donnée, aucun volume Docker, aucun service d'un autre projet n'a été modifié, supprimé ou redémarré.

Le rapport du cycle précédent reste valable pour la coquille authentifiée : `docs/audits/PRESENCE_I18N_AUTHENTICATED_PAGES_2026-10-27.md`.

---

## 1. Résumé exécutif

Les **huit pages Fonctionnalités** — le dernier gros bloc public encore en anglais — sont désormais entièrement pilotées par les catalogues DE/EN, comme les pages Outils, Solutions, À propos, Contact et le scan public. Le parcours public allemand est cohérent de l'accueil jusqu'aux fonctionnalités, aux outils, aux solutions et au contact : plus aucune chaîne anglaise visible sur les 20 pages vérifiées en E2E, en allemand comme en anglais, sur desktop et en 390 px.

Trois défauts réels ont été trouvés **par les tests**, puis corrigés :

1. Les URL `?lang=de|en` émises par `alternateLinks()` (donc les balises `hreflang`) n'étaient **pas lues** par le runtime : un visiteur anglophone cliquant l'alternate allemand restait en anglais. Le paramètre est désormais prioritaire, sans casser la préférence enregistrée.
2. `index.html` déclarait `<html lang="en">` alors que l'allemand est la langue par défaut : le document statique annonçait la mauvaise langue. Le shell statique est passé en allemand (titre, description, Open Graph, Twitter), et la coquille `prerender` émet maintenant les `hreflang` `de`/`en`/`x-default` ainsi que `og:locale`.
3. Deux débordements horizontaux en 390 px, causés par des composés allemands longs (`Gesundheitsinfrastruktur`) et par le bouton d'en-tête trop large. Corrigés par `hyphens-auto`/`break-words`, une taille de `h1` responsive et une en-tête compacte sur mobile.

**Ce qui n'est pas terminé et ne doit pas être masqué :**

| Élément | État |
| --- | --- |
| Corps des pages juridiques (`/privacy`, `/terms`) encore en anglais | **traduit après ce rapport** (105 → 2 littéraux, voir `PRESENCE_LEGAL_PAGES_DE_2026-10-27.md`) ; validation juridique toujours **BLOQUÉE** |
| Données structurées (`softwareAppSchema`, `organizationSchema`) rédigées en anglais | P3, sans impact utilisateur, visible pour les moteurs |
| Articles de blog dans le shell statique | **bloqué** : `VITE_WP_API_URL` vide au build, les articles restent rendus côté client |

---

## 2. État initial constaté (avant modification)

Mesuré dans le dépôt, pas repris des rapports :

| Contrôle | Valeur au début du cycle |
| --- | --- |
| `node ../../scripts/check-i18n.mjs` | **1608 clés** de chaque côté, parité stricte |
| `node scripts/scan-i18n-ast.mjs` | **148 littéraux** dans **16 fichiers** |
| Répartition | `PrivacyPage.tsx` 67, `TermsPage.tsx` 38, **`FeaturePage.tsx` 25**, 18 autres littéraux dispersés |
| Pages Outils / Solutions / À propos / Contact / Scan public | déjà traduites (seuls restaient marque, exemples d'URL et copyright) |
| `src/pages/FeaturePage.tsx` | 8 pages publiques en anglais, **entièrement codées en dur** (objet `configs`, ~300 chaînes) |
| `index.html` | `<html lang="en">`, titre/description/OG anglais |
| `scripts/prerender.mjs` | aucun `hreflang`, aucun `og:locale` dans les 32 fichiers pré-rendus |
| `src/i18n/index.tsx` | `alternateLinks()` émet `?lang=`, mais `detectLocale()` ignore ce paramètre |

Les 6 « pages publiques secondaires à 142 chaînes » du rapport précédent correspondent en réalité à **FeaturePage + les pages juridiques** : `A propos`, `Contact`, `Outils` et `Solutions` avaient déjà été traitées durant le cycle en cours.

---

## 3. Modifications réalisées

### 3.1 Pages publiques

| Fichier | Modification |
| --- | --- |
| `src/pages/FeaturePage.tsx` **(réécrit)** | Les 8 pages Fonctionnalités lisent toute leur copie dans `features.*` : titre, `metaTitle`, `metaDescription`, `h1`, intro, problème, solution, 5 bénéfices, étapes + descriptions, FAQ (questions/réponses), points contrôlés, libellés des liens connexes et CTA. La configuration ne garde que les slugs, chemins et clés typées (`MessageKey`/`ListKey`), donc une clé absente casse `tsc`. Sélecteur de langue ajouté dans l'en-tête. |
| `src/pages/FeaturePage.tsx` | Liens connexes désormais clés par `${path}-${label}` : deux liens pouvaient partager `/features/website-monitoring` (clé React dupliquée, avertissement de rendu). |
| `src/pages/AboutPage.tsx`, `ContactPage.tsx`, `SolutionPage.tsx`, `ToolPage.tsx`, `FeaturePage.tsx` | En-tête compacte (lien « Anmelden » masqué sous `sm`, CTA `whitespace-nowrap`), `h1` responsive avec `hyphens-auto break-words`. Aucun changement de contenu, de route ni de logique. |

### 3.2 Langue, SEO et coquille statique

| Fichier | Modification |
| --- | --- |
| `src/i18n/index.tsx` | `readUrlLocale()` : `?lang=de|en` est lu au démarrage et **prioritaire** sur la préférence stockée (sinon les alternates `hreflang` sont des liens morts pour un visiteur récurrent) ; la préférence est persistée par l'effet existant. |
| `index.html` | `<html lang="de">` (langue par défaut du lancement), titre, description, Open Graph et Twitter en allemand. La SPA substitue toujours la paire de la langue active. |
| `src/seo/routes.json` | `titleDe` + `descriptionDe` ajoutés aux **32 routes** publiques (27 indexables + 5 pages d'authentification `noindex`). |
| `scripts/prerender.mjs` | Le shell statique utilise la paire allemande (langue de lancement) ; `hreflang` `de`/`en`/`x-default` + `og:locale` + `og:locale:alternate` ajoutés à chaque page ; JSON-LD `WebSite` localisé ; page 404 et navigation de repli en allemand. Canonical inchangé (URL neutre, comme le runtime). |
| `e2e/public-pages-i18n.spec.ts` **(nouveau)** | 4 tests : balayage DE/EN des 20 pages (`h1`, `<html lang>`, `<title>`, aucune clé technique visible), responsive 390 px dans les deux langues, cohérence `?lang=`/`hreflang`/canonical, funnel Outil → scan réel en allemand. |

### 3.3 Catalogues

- Namespace `features.*` ajouté : **157 clés** (chrome partagé + 8 pages).
- `en.json` : 1608 → **1765 clés**. `de.json` : 1608 → **1765 clés**.

---

## 4. Qualité des contenus allemands

- Allemand professionnel B2B, phrases courtes, pas de superlatifs : « Wir prüfen … », « Sie erhalten … ».
- Acronymes conservés (`SSL`, `DNS`, `SPF`, `DKIM`, `DMARC`, `HSTS`, `CSP`, `MX`, `CNAME`, `TXT`, `NS`, `HTTP`, `PWA`) et expliqués à la première occurrence dans la FAQ.
- Aucune promesse ajoutée : les textes reprennent strictement les affirmations anglaises existantes (fréquence de contrôle selon le tarif, alerte 30 jours avant expiration, rapports PDF Pro/Business). Aucun prix, témoignage, certification ni résultat de scan n'a été inventé.
- Les affirmations « White-Label-Berichte » (page Agences) correspondent à une fonction réellement présente (`backend/reports/views.py: WhiteLabelPDFReportView`, `subscriptions/pricing.py`).
- Typographie allemande : guillemets „…“, tirets cadratins, `ß`/`ü`/`ö` corrects, `99,9 %` et `200 ms` formatés à l'allemande.

---

## 5. Parité et littéraux restants

### 5.1 Parité

```
$ node ../../scripts/check-i18n.mjs
en.json keys: 1765
de.json keys: 1765
✅ German catalogue matches the English reference exactly.
✅ Interpolations match in both languages.
exit 0
```

Le test de parité couvre la forme (chaînes vs listes), les clés et les interpolations `{…}`. `de.json` est typé sur la forme de `en.json` : une clé allemande manquante est une erreur de compilation, pas un repli silencieux.

### 5.2 Littéraux restants (scan AST)

```
$ node scripts/scan-i18n-ast.mjs
files with literals: 16   total literals: 124
    67  src/pages/PrivacyPage.tsx
    38  src/pages/TermsPage.tsx
     2  src/components/CommandMenu.tsx
     2  src/pages/Integrations.tsx
     2  src/pages/Landing.tsx
     2  src/pages/SolutionPage.tsx
     2  src/pages/ToolPage.tsx
     1  src/components/AppShell.tsx
     1  src/pages/AboutPage.tsx
     1  src/pages/Auth.tsx
     1  src/pages/BlogArticle.tsx
     1  src/pages/ContactPage.tsx
     1  src/pages/FeaturePage.tsx
     1  src/pages/Onboarding.tsx
     1  src/pages/PublicScanResult.tsx
     1  src/pages/Websites.tsx
```

`148 → 124` littéraux (`-24`, soit exactement `FeaturePage` 25 → 1).

Classement des 19 littéraux hors pages juridiques :

| Catégorie | Exemples | Décision |
| --- | --- | --- |
| Marque et copyright | `© 2026 Presence.` / `© 2026 Presence ·` (About, Contact, Feature, Solution, Tool) | **légitime** : nom propre + année, identique dans les deux langues |
| Exemples de saisie | `example.com`, `yourdomain.com`, `you@example.com`, `example-shop.de`, `app.presence.io/dashboard`, `Maria Schmidt` | **légitime** : exemples neutres ; les traduire nuirait au test E2E `public-scan.spec.ts` qui cible `you@example.com` |
| Identifiants techniques | `OAuth 2.0 · PKCE`, `esc` (raccourci clavier), `K` (initiale d'avatar) | **légitime** |
| Jeton de confirmation | `DISCONNECT` (saisie exigée avant déconnexion d'une intégration) | **doit rester littéral** : c'est un mot de confirmation, pas de la copie |
| Pages juridiques | 105 littéraux (`PrivacyPage` 67, `TermsPage` 38) au moment du scan | **traduites après ce cycle** (2 littéraux : mention ©) ; validation juridique **BLOQUÉE** — voir §8 |

Aucune chaîne n'a été supprimée ni reformulée pour faire baisser le compteur.

---

## 6. Resultats des tests (commandes et codes de sortie)

| # | Commande | Résultat | Statut |
| --- | --- | --- | --- |
| 1 | `npx tsc --noEmit` | exit **0**, aucun diagnostic | **VALIDÉ** |
| 2 | `node ../../scripts/check-i18n.mjs` | 1765/1765 clés, parité + interpolations, exit **0** | **VALIDÉ** |
| 3 | `node scripts/scan-i18n-ast.mjs` | 124 littéraux / 16 fichiers, exit **0** | **VALIDÉ** (inventaire §5) |
| 4 | `npm run build` | exit **0** — `vite build` + `prerender` : 32 routes publiques, sitemap 27 URL | **VALIDÉ** |
| 5 | `npx playwright test e2e/public-pages-i18n.spec.ts` | **4/4** (2,2 min) | **VALIDÉ** |
| 6 | `npx playwright test e2e/launch-readiness.spec.ts` | **5/5** (58,9 s) | **VALIDÉ** |
| 7 | `npx playwright test e2e/public-scan.spec.ts` | **1/1** (18,6 s) — scan réel `example.com`, rapport, partage, lead | **VALIDÉ** |
| 8 | `npx playwright test e2e/authenticated-i18n.spec.ts` | **2/2** (2,8 min) — non-régression de la coquille authentifiée | **VALIDÉ** |

Total : **12/12 tests E2E passés**, un seul worker, serveur de dev réutilisé (`http://localhost:5173`), pile Docker locale (API, base, Mailpit) en fonctionnement.

### 6.1 Détail du test de balayage DE/EN

20 routes × 2 langues, pour chacune :

- `h1` comparé à la valeur du catalogue de la langue active ;
- `<html lang>` vérifié ;
- `<title>` comparé à `metaTitle` (donc un titre resté anglais fait échouer le test) ;
- recherche des **1765 clés brutes** dans le texte visible (aucune clé technique affichée) ;
- erreurs JavaScript de page collectées et testées vides.

Routes couvertes : `/about`, `/contact`, 4 `/tools/*`, 8 `/features/*`, 6 `/solutions/*` ; `/pricing` est couvert par le test `?lang=` (les deux langues).

### 6.2 Tests d'intégration de la langue

- `/?lang=de` sur une préférence anglaise stockée → interface **et** `h1` allemands ; `?lang=en` → anglais.
- `hreflang` = exactement `de`, `en`, `x-default`, tous sur `/features/ssl-monitoring?lang=…` ; canonical sur `/features/ssl-monitoring` **sans** paramètre.
- Persistance : après bascule et `reload`, la langue choisie est conservée.

### 6.3 Tests non exécutés (et pourquoi)

| Test | Raison |
| --- | --- |
| Suites backend Django | aucun fichier backend modifié dans ce cycle |
| WordPress / blog éditorial | périmètre d'un autre cycle ; seul le parcours de lecture DE/EN est couvert (test 6, article allemand + slug traduit + brouillons masqués) |
| Paddle Sandbox | identifiants absents, hors périmètre ici |
| Lighthouse / Core Web Vitals | non demandé ; le build et le poids des bundles n'ont pas régressé de façon notable (`i18n` 286 kB non gzip, comme avant) |
| Accessibilité automatisée (axe) | non demandée dans ce cycle — le balayage vérifie seulement langue, titres et absence de clé brute |

---

## 7. Défauts détectés et corrigés

### 7.1 SEO

| Défaut | Preuve | Correction |
| --- | --- | --- |
| `?lang=` émis mais jamais lu : les alternates `hreflang` ne changeaient pas la langue | inspection `src/i18n/index.tsx` (`detectLocale` ne lit que `localStorage` + `navigator`) | `readUrlLocale()` prioritaire, test E2E dédié |
| `<html lang="en">` alors que l'allemand est la langue par défaut | `index.html` | `lang="de"` + titre/description/OG/Twitter allemands |
| Aucune balise `hreflang` dans les 32 pages pré-rendues, aucun `og:locale` | `head -20 dist/features/ssl-monitoring/index.html` avant correctif | `renderAlternates()` + `og:locale`/`og:locale:alternate` dans `prerender.mjs` |
| Titres/descriptions SEO statiques uniquement en anglais | `src/seo/routes.json` | `titleDe`/`descriptionDe` sur les 32 routes, utilisés pour le shell statique |
| 404 statique et navigation de repli en anglais | `prerender.mjs` | 404 et libellés de repli en allemand |
| Sitemap | `grep -c "features/" dist/sitemap.xml` → **8** | conforme, aucune action |

Vérification après build :

```
<title>SSL-Zertifikatsüberwachung | Presence</title>
<link rel="canonical" href="http://localhost:8443/features/ssl-monitoring" />
<link rel="alternate" hreflang="de" href="…/features/ssl-monitoring?lang=de" />
<link rel="alternate" hreflang="en" href="…/features/ssl-monitoring?lang=en" />
<link rel="alternate" hreflang="x-default" href="…/features/ssl-monitoring?lang=de" />
<meta property="og:locale" content="de_DE" />
<meta property="og:locale:alternate" content="en_GB" />
```

L'origine `localhost:8443` vient de l'absence de `VITE_BASE_URL` en local (le script l'annonce explicitement) : à définir avant tout déploiement public, sinon les canonicals restent locaux.

### 7.2 Mise en page mobile (défauts réels, trouvés par le test)

| Page | Défaut mesuré | Cause | Correction |
| --- | --- | --- | --- |
| `/about` (de, 390 px) | `+15 px` de débordement | `h1` « Digitale Gesundheitsinfrastruktur … » (`text-3xl` noir) + en-tête trop large (« Anmelden » + « Kostenlos starten ») | `text-2xl sm:text-4xl`, `hyphens-auto break-words`, lien de connexion masqué sous `sm`, CTA `nowrap` |
| `/features/website-monitoring` (de, 390 px) | `+4 px` | CTA d'en-tête « Website überwachen » (165 px) poussant la rangée au-delà de 390 px | CTA propre à la fonction masqué sous `sm` (le hero garde les deux actions), `h1` responsive + césure |

Après correction : **0 débordement** sur les 20 pages dans les deux langues.

### 7.3 Chaînes en dur

Aucun texte visible contrôlé par le frontend ne reste en dur sur les pages du périmètre (§5.2).

---

## 8. Checklist de sortie

| Élément | Statut |
| --- | --- |
| 8 pages Fonctionnalités en DE et EN | **VALIDÉ** |
| Outils, Solutions, À propos, Contact, scan public en DE et EN | **VALIDÉ** |
| Chrome partagé (en-tête, pied de page, fil d'Ariane, FAQ, CTA, 404 de la page Fonctionnalité) en DE et EN | **VALIDÉ** |
| Catalogues à parité (1765/1765) et interpolations cohérentes | **VALIDÉ** |
| Aucune clé technique visible sur les pages balayées | **VALIDÉ** |
| Langue du document (`<html lang>`) conforme à la langue active | **VALIDÉ** |
| Persistance de la langue après navigation et rechargement | **VALIDÉ** |
| `?lang=` et `hreflang` cohérents (de/en/x-default), canonical sans paramètre | **VALIDÉ** |
| Titre et meta description par page dans les deux langues | **VALIDÉ** (runtime) / **VALIDÉ** (shell statique en allemand) |
| Présence des pages Fonctionnalités dans le sitemap | **VALIDÉ** (8/8) |
| TypeScript | **VALIDÉ** |
| Build de production | **VALIDÉ** |
| E2E desktop DE/EN | **VALIDÉ** (20 pages) |
| E2E mobile DE/EN sans débordement horizontal | **VALIDÉ** |
| Funnel public réel (scan `example.com`) en allemand | **VALIDÉ** |
| Corps des pages juridiques en allemand | **VALIDÉ techniquement** (traduit après ce scan : 105 → 2 littéraux, spec `legal-pages-i18n` 2/2) |
| Validation juridique des textes allemands | **BLOQUÉ** — décision humaine (avocat / conseil) requise, jamais affirmée par ce rapport |
| Données structurées localisées (`softwareAppSchema`, `organizationSchema`) | **ÉCHEC** (P3, anglais) |
| Articles de blog pré-rendus (SEO statique) | **BLOQUÉ** — `VITE_WP_API_URL` absent au build ; les articles restent rendus côté client |
| `VITE_BASE_URL` renseigné (canonicals publics) | **À VÉRIFIER MANUELLEMENT** avant déploiement |
| Rendu visuel des deux langues (relecture humaine des textes allemands) | **À VÉRIFIER MANUELLEMENT** — aucune revue native allemande n'a été faite |
| Paddle Sandbox, backend, WordPress éditorial | non exécuté ici (autres cycles) |

---

## 9. Blocages et prochaines priorités

**P1 — avant lancement allemand**

1. Faire **valider par un juriste** les textes allemands de `/privacy` et `/terms` (traduits après ce rapport, voir `PRESENCE_LEGAL_PAGES_DE_2026-10-27.md`) : ce rapport ne certifie aucune conformité.
2. Renseigner `VITE_BASE_URL` (origine publique) pour que canonicals, `hreflang` et sitemap soient absolus et corrects.
3. Relecture des textes allemands par un locuteur natif, en particulier les pages Fonctionnalités (FAQ techniques) et la page Tarifs.

**P2**

4. Pré-rendre les articles de blog (`VITE_WP_API_URL` accessible au build) pour que les titres allemands existent dans le HTML statique.
5. Localiser les données structurées (`softwareAppSchema`, `organizationSchema`, `breadcrumbSchema`).

**P3**

6. Extraire un composant `<Wordmark />` pour les 8 littéraux « Presence » du pied de page.
7. Ajouter un contrôle automatique « aucune phrase anglaise sur une page allemande » (heuristique par mots vides) au scan i18n : détecterait une régression de copie avant la mise en production.

---

## 10. Fichiers touchés

```
src/pages/FeaturePage.tsx                     réécrit (8 pages, i18n, liens connexes uniques)
src/pages/AboutPage.tsx                       en-tête compacte, h1 responsive
src/pages/ContactPage.tsx                     en-tête compacte, h1 responsive
src/pages/SolutionPage.tsx                    en-tête compacte, h1 responsive
src/pages/ToolPage.tsx                        en-tête compacte, h1 responsive
src/i18n/index.tsx                            lecture de ?lang= (alternates fonctionnels)
src/i18n/de.json, src/i18n/en.json            +157 clés (namespace features.*), 1765/1765
index.html                                    lang=de + métadonnées allemandes par défaut
src/seo/routes.json                           titleDe/descriptionDe sur 32 routes
scripts/prerender.mjs                         hreflang, og:locale, shell statique allemand, 404
e2e/public-pages-i18n.spec.ts                 nouveau : 4 tests DE/EN (desktop, mobile, SEO, funnel)
docs/audits/PRESENCE_I18N_PUBLIC_PAGES_2026-10-27.md  ce rapport
```

Aucun fichier backend, aucun secret, aucune donnée, aucun volume Docker n'a été touché.
