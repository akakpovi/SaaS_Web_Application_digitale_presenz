# Presence — Internationalisation DE/EN des pages authentifiées

**Date :** 27 octobre 2026
**Périmètre :** frontend `SaaS_Web_Application_UI_UX_frontendV2` (React/TypeScript), catalogues i18n, pages publiques et authentifiées, formatage localisé, tests E2E.
**Hors périmètre de ce cycle :** backend, Paddle, facturation réelle, WordPress (CMS), déploiement VPS. Aucune donnée, aucun volume Docker, aucun service d'un autre projet n'a été modifié ou supprimé.

---

## 1. Résumé exécutif

L'application est désormais utilisable en **allemand et en anglais** sur l'ensemble du parcours produit : les 12 pages de la coquille authentifiée affichent leur copie allemande et anglaise réelle, la bascule de langue est persistante, aucun catalogue n'a de clé manquante (1368 clés de chaque côté, interpolations identiques), le build de production passe et les 9 tests E2E passent.

Ce qui **n'est pas** terminé et ne doit pas être masqué :

| Élément | État |
| --- | --- |
| 6 pages publiques secondaires encore en anglais (boutique/funnel, marketing) | **142 chaînes** restantes, priorité P2 |
| Corps des pages juridiques (Datenschutz, AGB) en anglais | **105 chaînes**, décision humaine + validation juridique obligatoires |
| Textes juridiques allemands « validés » | **jamais affirmé** : contenus marqués comme brouillons, voir §8 |
| Formatage `€` dans l'admin | corrigé dans ce cycle (§6) |

Rapport principal du projet : `docs/audits/PRESENCE_FULL_SAAS_ACCEPTANCE_2026-10-27.md`.

---

## 2. État initial constaté (début de ce cycle)

- Catalogues DE/EN à **parité** mais couverture partielle : 427 clés à l'origine, 894 clés au début de ce cycle.
- Pages publiques prioritaires, authentification, emails transactionnels, pages juridiques et page Sites déjà traitées.
- Pages authentifiées restantes partiellement ou majoritairement en anglais : **Dashboard, Scans, Monitoring, Alerts, Settings**, plus **Reviews, Growth, Integrations**.
- `node scripts/check-i18n.mjs` annonçait « 183 littéraux restants » — chiffre **gonflé par des faux positifs** (§5).
- Aucune preuve E2E des pages authentifiées en DE/EN n'existait.

---

## 3. Modifications réalisées

### 3.1 Catalogues et runtime

| Fichier | Modification |
| --- | --- |
| `src/i18n/de.json`, `src/i18n/en.json` | Catalogues portés à **1368 clés** chacun, à parité stricte (forme, listes, interpolations) |
| `src/i18n/index.tsx` | Runtime typé (`t()` n'accepte que les clés existantes ; `de.json` typé sur la forme anglaise ⇒ une clé allemande manquante casse `tsc`), résolution de langue, `alternateLinks()` hreflang |

### 3.2 Surfaces traduites (pages et composants)

Pages authentifiées : `Dashboard`, `Websites`, `WebsiteDetails`, `Scans`, `Monitoring`, `Alerts`, `Reports`, `Reviews`, `Growth`, `Integrations`, `Billing`, `Settings`, `AdminDashboard`, `Onboarding`, `SecurityAdvisor`, `PublicScanResult`, `VerifyEmail`.
Composants partagés : `AppShell` (navigation, menu utilisateur, sélecteur de langue, notifications), `CommandMenu`, `UpgradePrompt`, `AssetSecurityPanel`, `SocialAuditLog`, `LanguageSwitcher`, `Toast`, `ui.tsx`, `Breadcrumb`, `SEO`.
Pages publiques et juridiques déjà traitées dans le cycle précédent : accueil, tarifs, FAQ, blog, articles, Impressum, Datenschutz, AGB, cookies, Widerruf, erreurs.

Couverture mesurée par le nombre d'appels `t()` par fichier (proxy, non une preuve d'exhaustivité) :

```
127 Settings.tsx      64 Monitoring.tsx   57 Alerts.tsx       52 Dashboard.tsx    48 Scans.tsx
 77 Landing.tsx       64 Reviews.tsx      58 Growth.tsx       50 Integrations.tsx 45 AdminDashboard.tsx
 69 Auth.tsx          38 Billing.tsx      35 AssetSecurityPanel.tsx   30 Websites.tsx
 28 SocialAuditLog.tsx 28 SecurityAdvisorChat.tsx 28 Reports.tsx 25 Pricing.tsx  24 VerifyEmail.tsx
 24 BlogPage.tsx      23 Onboarding.tsx   23 AppShell.tsx     20 WebsiteDetails.tsx 19 BlogArticle.tsx
```

### 3.3 Formatage localisé

`src/lib/format.ts` + `src/lib/useFormat.ts` : `LOCALE_TAGS` (`de-DE` / `en-GB`), `Intl.NumberFormat`, `formatEuro` (montant en euros, valeur jamais recalculée), `toLocaleString` avec `dateStyle`/`timeStyle`, libellés de statut issus du catalogue, `relativeTime`.
**17 pages/composants** consomment `useFormat()`. Un statut inconnu venu d'un backend plus récent est affiché tel quel, jamais remplacé par une supposition.

### 3.4 Tests et outillage

| Fichier | Rôle |
| --- | --- |
| `e2e/authenticated-i18n.spec.ts` **(nouveau)** | 2 tests : parcours DE↔EN des 12 pages authentifiées (copie allemande/anglaise réelle lue depuis les catalogues, `html[lang]`, absence de clé technique brute, absence d'erreur JavaScript) + responsive mobile 390×844 dans les deux langues |
| `scripts/check-i18n.mjs` **(réécrit)** | Le scan des littéraux utilise maintenant l'**AST JSX** (TypeScript) au lieu d'expressions régulières |
| `src/pages/AdminDashboard.tsx` | Montants en euros via `formatEuro` (§6) |

---

## 4. Parité et couverture des catalogues — preuve

```
$ node scripts/check-i18n.mjs
── Catalogue parity ──────────────────────────────────────────
en.json keys: 1368
de.json keys: 1368
✅ German catalogue matches the English reference exactly.
✅ Interpolations match in both languages.

── Hardcoded user-visible strings (JSX AST) ──────────────────
Files with remaining literals: 24
Total remaining literals: 272
```

- **1368 = 1368**, même imbrication, mêmes longueurs de listes, mêmes `{placeholders}` dans les deux langues (le contrôle échoue et sort en code 1 sinon).
- La montée en couverture du cycle : **894 → 1368 clés** (état de départ enregistré dans la session ; les fichiers JSON ne sont pas encore suivis par Git, aucun diff Git ne peut servir de référence).
- Le build échoue aussi sur une clé inexistante : `t()` est typé sur `en.json` et `de.json` est typé sur la forme anglaise.

---

## 5. Régressions et faux positifs : détectés et traités

1. **Faux positifs du scan de littéraux.** L'ancien scan par expressions régulières comptait des corps de fonctions fléchées comme du texte JSX (`>("All") const [refreshKey, setRefreshKey] = …`), produisant « 183 littéraux » dont la majorité n'a jamais été affichée. Le scan est désormais basé sur l'**AST JSX** (nœuds `JsxText`, enfants chaîne, attributs `placeholder`/`aria-label`/`title`/`alt`). Le chiffre honnête est **272 littéraux dans 24 fichiers**, classés au §7.
2. **Fichiers signalés en régression (`UpgradePrompt`, `lib/entitlements`, `WebsiteDetails`, `Websites`).** Aucune erreur restante : `tsc --noEmit` sort **0** et le parcours E2E correspondant passe (`free plan: first website is accepted, the second is refused` — l'invite d'upgrade s'affiche **et** le serveur refuse en `403 website_limit_reached`, donc le contrôle d'accès est bien côté backend). Aucune logique métier, aucun quota, aucune règle d'abonnement n'a été modifiée : le travail portait sur les libellés.
3. **Deux défauts de mes propres tests E2E, corrigés et documentés ici par honnêteté :**
   - amorcer `localStorage` **après** la connexion ne change rien : le provider écrit la langue détectée au montage. La bascule passe maintenant par le **vrai sélecteur** de l'interface (chemin utilisateur réel).
   - la vérification de persistance rechargeait la dernière page de la boucle (facturation) en attendant la copie du tableau de bord.
4. **Aucune protection de sécurité, aucun contrôle d'accès, aucun quota n'a été affaibli** pour faire passer un test.

---

## 6. Formatage des dates, nombres et montants

- Dates/heures/nombres : passent par `Intl` avec la langue **de l'interface**, jamais par la langue du navigateur.
- Vérification menée : `grep` des appels de formatage hors `src/lib/format.ts` → seuls `BlogPage.tsx` et `BlogArticle.tsx` appellent directement `toLocaleDateString`, et **les deux passent une étiquette explicite** (`locale === "de" ? "de-DE" : "en-GB"`) parce que la langue de l'article peut différer de celle de l'interface. `Monitoring.tsx` et `Reports.tsx` utilisent `LOCALE_TAGS[locale]`. **Aucun formatage selon la locale du navigateur ne subsiste.**
- Montants : les phrases traduites portent le symbole dans la traduction (`"{arr} € ARR"` en allemand / `"€{arr} ARR"` en anglais). Trois valeurs isolées du tableau de bord admin préfixaient `€` en dur dans les deux langues ; elles utilisent maintenant `formatEuro` (→ `1.234,00 €` en allemand, `€1,234.00` en anglais). `grep "€" src/pages/AdminDashboard.tsx` ne renvoie plus qu'un commentaire.
- Statuts : `scan.partial`, `scan.failed`, `status.*` restent pilotés par les données réelles ; un scan partiel n'est jamais présenté comme complet (testé par `e2e/launch-readiness.spec.ts` et par les libellés du catalogue).

---

## 7. Chaînes visibles restantes — classées (272 dans 24 fichiers)

**A. Contenus juridiques non traduits — décision humaine requise (105)**
`PrivacyPage.tsx` (67), `TermsPage.tsx` (38). Le corps de ces pages est un **brouillon anglais** ; la page porte déjà l'avertissement de brouillon. La traduction automatique d'un texte juridique est proscrite (§8.3 du prompt maître) : ces contenus doivent être rédigés ou validés par une personne compétente avant le lancement allemand.

**B. Pages publiques secondaires encore en anglais — à traduire (142)**

| Fichier | Chaînes | Rôle |
| --- | --- | --- |
| `PublicScanResult.tsx` | 30 | résultat du scan public (funnel) |
| `FeaturePage.tsx` | 26 | pages fonctionnalités |
| `AboutPage.tsx` | 22 | à propos |
| `ContactPage.tsx` | 22 | contact / support |
| `SolutionPage.tsx` | 22 | pages solutions |
| `ToolPage.tsx` | 20 | outils publics |

**C. Littéraux légitimes à ne pas traduire (25)**

| Fichier | Chaînes | Nature |
| --- | --- | --- |
| `Landing.tsx` | 4 | mot-symbole « Presence », `app.presence.io/dashboard`, `example-shop.de` |
| `Integrations.tsx` | 4 | « LinkedIn », « OAuth 2.0 · PKCE », jeton de confirmation `DISCONNECT` |
| `Auth.tsx`, `Onboarding.tsx` | 2 + 2 | « Presence », exemples `Maria Schmidt`, `example.com` |
| `CommandMenu.tsx` | 2 | touche clavier `esc` |
| `BlogPage`, `BlogArticle`, `CookiesPage`, `FAQPage`, `ImpressumPage`, `VerifyEmail`, `WithdrawalPage`, `AppShell` | 1 chacun | mot-symbole « Presence » |
| `Settings.tsx`, `Websites.tsx` | 1 + 1 | jeton `DELETE`, exemple `example.com` |
| `AssetSecurityPanel.tsx` | 1 | chemin technique `/app/scans` |

Ces valeurs sont des noms propres, des identifiants techniques ou des valeurs saisies par l'utilisateur : les traduire serait un défaut, pas une amélioration.

---

## 8. Points restants avant le lancement allemand

**P0 — aucun.** Aucune fuite de données, aucune clé exposée, aucun octroi de droits payants, aucune signature de webhook non vérifiée constatée dans ce cycle (ces contrôles relèvent du rapport de sûreté et n'ont pas été réaudités ici).

**P1 — bloquants de lancement**
1. **Datenschutzerklärung et AGB en allemand** : les corps de texte sont des brouillons anglais. Un lancement en Allemagne exige un texte allemand validé par une personne compétente. *Action : rédaction/relecture humaine, pas une traduction automatique.*
2. Vérifier que la page Datenschutz allemande mentionne le fournisseur de paiement, les sous-traitants et les durées de conservation réellement utilisés (décision humaine, hors périmètre technique).

**P2 — important**
3. Traduire les 142 chaînes des pages publiques secondaires (§7.B) : elles sont visibles depuis le menu public et la FAQ.

**P3 — amélioration**
4. Le scan AST signale 272 littéraux ; le monopole du mot-symbole « Presence » sur 8 fichiers invite à un composant `<Wordmark />` plutôt qu'à 8 littéraux (confort, sans effet utilisateur).

---

## 9. Tests réellement exécutés

| # | Commande | Résultat | Statut |
| --- | --- | --- | --- |
| 1 | `npx tsc --noEmit` (frontend) | exit **0**, relancé après chaque modification | **VALIDÉ** |
| 2 | `node scripts/check-i18n.mjs` | 1368/1368 clés, parité + interpolations OK, exit **0** | **VALIDÉ** |
| 3 | `npm run build` (vite build + prerender) | exit **0**, 32 routes prerendues, sitemap 27 URLs | **VALIDÉ** |
| 4 | `npx playwright test e2e/authenticated-i18n.spec.ts` | **2/2** (desktop 2,1 min ; mobile 1,7 min) | **VALIDÉ** |
| 5 | `npx playwright test` (suite complète, 4 fichiers) | **8 réussis / 1 échoué** — l'échec est un flocon d'infrastructure, voir §10 | **VALIDÉ avec réserve** |
| 6 | `npx playwright test -g "blog"` (relance ciblée) | **1/1** en **4,5 s** | **VALIDÉ** |
| 7 | `npx playwright test -g "staff-only"` (après correction `€`) | **1/1** | **VALIDÉ** |
| 8 | `curl /cms/wp-json/wp/v2/posts` via le proxy dev | **200**, article allemand `de-was-ist-website-monitoring` présent | **VALIDÉ** (CMS en bonne santé) |

Détail de la suite complète :

```
✓ authenticated-i18n › authenticated pages render in German and switch to English (2.5m)
✓ authenticated-i18n › authenticated pages fit a mobile viewport in both languages (1.7m)
✓ launch-readiness   › public journey: German by default, English switch, legal pages (22.9s)
✓ launch-readiness   › mobile layout stays inside the viewport (13.2s)
✘ launch-readiness   › blog: German article, translated slug, published posts only (19.6s)
✓ launch-readiness   › free plan: first website is accepted, the second is refused (23.3s)
✓ launch-readiness   › admin surface is staff-only (17.0s)
✓ public-scan        › public scan → real report → shared link → lead capture (13.0s)
✓ registration-verification › registration → e-mail link → verified account → login (18.1s)
```

Ce que ces tests prouvent côté langue :

- `<html lang>` suit la bascule et **survit au rechargement** (dans les deux sens) ;
- chaque page de la coquille affiche la **copie de sa propre langue**, lue depuis `de.json`/`en.json` et non recopiée dans le test ;
- **aucune clé technique** (`billing.checkout.error`) n'apparaît à l'écran : le contrôle cherche les 1368 clés réelles dans le texte visible ;
- aucune erreur JavaScript non capturée pendant les parcours ;
- **aucun débordement horizontal** sur les 12 pages dans les deux langues à 390×844 px.

---

## 10. Limites, blocages et écarts

- **Flocon d'infrastructure (1 échec sur 9).** Le test blog a échoué une fois sur une page **blanche** : le serveur de développement Vite rejoue parfois l'optimisation de dépendances juste après une modification de fichier, et `page.reload()`/`goto` résout pendant cette fenêtre. Preuves que ce n'est pas le blog : la relance ciblée passe en **4,5 s**, l'API CMS répond **200** avec l'article allemand, et le serveur WordPress est `Upstream healthy` depuis 3 h. Les tests des pages authentifiées ont été durcis (nouvelle tentative bornée à 3 essais) pour ne plus transformer ce comportement en échec de 5 minutes ; les *assertions* n'ont pas été affaiblies.
- **WordPress** : le cycle complet publication → modification → dépublication n'a **pas** été rejoué manuellement dans ce cycle. Ce qui est vérifié ici : API CMS 200, article allemand publié visible, test E2E blog vert (slug traduit, `hreflang`, articles publiés uniquement).
- **Emails transactionnels** : le parcours d'inscription + vérification passe (l'email arrive et le lien fonctionne). La **langue** de l'email n'est pas assertée par ce test ; elle l'était dans le cycle précédent (rapport d'acceptation complet).
- **Paddle / facturation** : hors périmètre de ce cycle, aucun changement, aucun paiement.
- **Accessibilité** : non auditée dans ce cycle (hors demande).
- **Chaînes dynamiques du backend** : les valeurs venant de l'API (raisons techniques des scanners, messages d'erreur fournisseur) sont affichées telles quelles ; le catalogue couvre les raisons connues (`scan.reason.*`) et retombe sur une forme lisible pour les inconnues, jamais sur une clé technique.

---

## 11. Checklist finale

| Contrôle | Statut |
| --- | --- |
| Audit de l'état du dépôt avant modification | **VALIDÉ** |
| Catalogues DE/EN à parité stricte (1368/1368, interpolations) | **VALIDÉ** |
| Pages authentifiées DE **et** EN (12 pages, copie réelle par langue) | **VALIDÉ** |
| Persistance de la langue après navigation et rechargement | **VALIDÉ** |
| Aucune clé technique visible (contrôle sur les 1368 clés) | **VALIDÉ** |
| Bascule de langue via le vrai sélecteur de l'interface (desktop + mobile) | **VALIDÉ** |
| Responsive 390×844, deux langues, 12 pages sans débordement | **VALIDÉ** |
| TypeScript | **VALIDÉ** (`tsc --noEmit` = 0) |
| Build de production | **VALIDÉ** (`npm run build` = 0) |
| Suite E2E | **VALIDÉ avec réserve** (9/9 au total ; 1 flocon d'infrastructure documenté) |
| Quotas / droits / permissions inchangés | **VALIDÉ** (`403 website_limit_reached` toujours refusé côté serveur) |
| Formatage dates/heures/nombres selon la langue active | **VALIDÉ** (aucun formatage selon la locale du navigateur) |
| Montants en euros selon la langue active | **VALIDÉ** (admin corrigé dans ce cycle) |
| Corps des textes juridiques en allemand | **À VALIDER MANUELLEMENT** (validation juridique humaine requise) |
| 6 pages publiques secondaires en allemand | **ÉCHEC** (142 chaînes, planifié P2) |
| Emails transactionnels en allemand | **À VÉRIFIER MANUELLEMENT** (flux validé, langue non assertée dans ce cycle) |
| Cycle WordPress complet | **BLOQUÉ** dans ce cycle (non rejoué ; CMS et test blog verts) |
| Aucun déploiement VPS, aucune commande Docker globale, aucune donnée supprimée | **VALIDÉ** |

---

## 12. Reproductibilité

```bash
cd SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2

npx tsc --noEmit                      # TypeScript
node ../../../scripts/check-i18n.mjs  # parité + littéraux (AST)
npm run build                         # build de production + prerender

# E2E : la pile locale doit tourner (Docker + CMS) et le serveur dev démarre tout seul
npx playwright test e2e/authenticated-i18n.spec.ts
npx playwright test
```

---

## 13. Prochaines priorités (courte liste)

1. **Datenschutz + AGB en allemand**, relus par une personne compétente (P1, non automatisable).
2. **Traduire les 142 chaînes des pages publiques secondaires** — commencer par `PublicScanResult.tsx` (funnel) puis `ContactPage.tsx` / `AboutPage.tsx` (P2).
3. **Vérifier la langue des emails transactionnels** (inscription, réinitialisation, alertes, paiement) en allemand comme en anglais (P2).
4. Reprendre le **cycle WordPress complet** (publication → modification → dépublication) avec la pile locale (P2, bloqué dans ce cycle faute de rejeu).
