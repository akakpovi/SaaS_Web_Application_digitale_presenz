# Presence — Rapport de smoke test corrigé

**Date :** 2026-11-14  
**Périmètre :** frontend v2, pile Docker Compose locale  
**HEAD au moment du rapport :** `8af1d5c` (correctif blog au-dessus de `58ee7f6`)

## Résultat

| Mesure | Valeur |
|---|---|
| Scénarios applicables | **45/45 fonctionnels ✅** |
| Scénarios N/A | 6 (E4, E5, F2, G2, G3, M2) |
| A9 — blog FR | **✅ corrigé** : 0 article affiché, message français, aucun contenu allemand |
| A7 — blog DE | **✅ fonctionnel**, avec réserve de contenu CMS : **2 articles DE** disponibles, **6 articles EN** isolés sur `/en/blog/` |
| Build | RC 0 — 87 pages SSG, 8 articles, 95 URLs sitemap |
| TypeScript | RC 0 |

> **Correction du rapport précédent :** A9 avait été marqué ✅ à tort. La page
> `/fr/blog/` affichait en réalité le catalogue complet (2 articles DE +
> 6 articles EN) après hydratation. Le rapport initial comptait donc un faux
> positif. A7 était également basé sur une hypothèse erronée de « 8 articles
> allemands » : le snapshot WordPress contient 2 articles DE et 6 articles EN.

## Correctif blog (phase 1)

| Fichier | Changement |
|---|---|
| `src/pages/BlogPage.tsx` | Le fetch hydraté transmet désormais `locale` et ne remplace plus la liste localisée par le catalogue complet |
| `src/api/blog.ts` | Garde-fou côté client : `fetchPosts(..., locale)` filtre `post.lang`; WordPress ignore `presence_lang=fr` |
| `src/main.tsx` | L’hydratation accepte aussi le payload `locale: "fr"` |
| `src/pages/BlogArticle.tsx` | Langue d’article conservée pour `de`, `en` et `fr` |
| `src/i18n/fr.json` | Message vide : « Aucun article disponible en français pour le moment. » |
| `src/i18n/en.json` | Message vide : « No articles available in English yet. » |
| `scripts/prerender.mjs` | Conservation du code de langue CMS (`de`/`en`/`fr`) au lieu de forcer `en` |

### Preuves avant / après

| Page | Avant | Après |
|---|---|---|
| `/blog/` | `P7_blog_de_avant.png` — 8 cartes mixtes DE/EN | `P7_blog_de_apres_iter2.png` — 2 cartes DE uniquement |
| `/fr/blog/` | `P7_blog_fr_avant.png` — 8 cartes DE/EN | `P7_blog_fr_apres_iter2.png` — 0 carte, message FR |
| `/en/blog/` | `P7_blog_en_avant.png` — 8 cartes mixtes | `P7_blog_en_apres_iter2.png` — 6 cartes EN uniquement |

Itérations de la phase 1 : **2** (itération 1 : prérendu FR correct mais hydratation encore mélangée ; itération 2 : filtre client ajouté et vérifié).

## Les 51 scénarios

| ID | Scénario | Statut | Snapshot | Note |
|---|---|---|---|---|
| A1 | Accueil DE | ✅ | `P6_A1_accueil_de.png` | |
| A2 | Accueil FR | ✅ | `P6_A2_accueil_fr.png` | |
| A3 | Accueil EN | ✅ | `P6_A3_accueil_en.png` | |
| A4 | `/de/` → 301 → `/` | ✅ | `P6_A4_redirect_de.png` | |
| A5 | Pricing public | ✅ | `P6_A5_pricing.png` | 4 plans, aucun plan QA |
| A6 | Pricing FR | ✅ | `P6_A6_pricing_fr.png` | 4 plans |
| A7 | Blog DE | ✅ | `P7_blog_de_apres_iter2.png` | 2 DE, aucun EN ; objectif 8 non atteignable avec le snapshot |
| A8 | Article DE | ✅ | `P6_A8_article.png` | |
| A9 | Blog FR | ✅ corrigé | `P7_blog_fr_apres_iter2.png` | 0 article, message FR, aucun allemand |
| A10 | Login DE | ✅ | `P6_A10_login_de.png` | |
| A11 | Login FR | ✅ | `P6_A11_login_fr.png` | |
| A12 | 404 | ✅ | `P6_A12_404.png` | |
| B1 | Inscription, 2 champs MDP | ✅ | `P6_B1_inscription.png` | |
| B2 | Doublon localisé | ✅ | `P6_B2_doublon_erreur.png` | |
| B3 | Connexion QA | ✅ | `P6_B3_dashboard_apres.png` | |
| B4 | Échec login localisé | ✅ | `P6_B4_login_echec.png` | |
| C1 | Dashboard DE + titre | ✅ | `P6_C1_dashboard.png` | |
| C2 | Sidebar 12 liens | ✅ | `P6_C2_sidebar.png` | |
| C3 | Dashboard FR | ✅ | `P6_C3_dashboard_fr.png` | |
| D1 | Liste des sites | ✅ | `P6_D1_sites.png` | |
| D2 | Ajout d’un site | ✅ | `P6_D2_ajout.png` | |
| D3 | Détail site 38 | ✅ | `P6_D3_detail.png` | Score 69/100 |
| D4 | Suppression | ✅ | `P6_D4_apres.png` | Site de test nettoyé |
| E1 | Liste des scans | ✅ | `P6_E1_scans.png` | |
| E2 | Lancement d’un scan | ✅ | `P6_E2_lancement.png` | Scan de test #1183 |
| E3 | Résultat de scan | ✅ | `P6_E3_resultat.png` | 69/100 + checks |
| E4 | Journey avancé | N/A | — | |
| E5 | Exposition avancée | N/A | — | |
| F1 | Abonnement QA | ✅ | `P6_F1_subscription.png` | |
| F2 | Upgrade | N/A | — | |
| F3 | Pricing connecté QA | ✅ | `P6_F3_pricing_connecte.png` | QA Interne + « AKTUELLER TARIF » |
| G1 | Paramètres | ✅ | `P6_G1_settings.png` | |
| G2 | Profil | N/A | — | |
| G3 | Sécurité | N/A | — | |
| H1 | Switch FR | ✅ | `P6_H1_switch_fr.png` | `/fr/` |
| H2 | Switch EN | ✅ | `P6_H2_switch_en.png` | `/en/` |
| H3 | Switch DE | ✅ | `P6_H3_switch_de.png` | `/` |
| H4 | Persistance locale | ✅ | `P6_H4_persistance.png` | |
| H5 | Dashboard FR | ✅ | `P6_H5_dashboard_fr.png` | |
| I1 | Login admin Django | ✅ | `P6_I1_admin_login.png` | |
| I2 | Modèles admin | ✅ | `P6_I2_admin_modeles.png` | |
| I3 | Scans admin | ✅ | `P6_I3_admin_scans.png` | |
| J1 | Hamburger mobile | ✅ | `P6_J1_mobile_ouvert.png` | Drawer plein écran |
| J2 | Dashboard mobile | ✅ | `P6_J2_mobile_dashboard.png` | |
| J3 | Login mobile | ✅ | `P6_J3_mobile_login.png` | |
| K1 | Anonyme → login | ✅ | `P6_K1_redirect_login.png` | |
| K2 | Admin anonyme → login | ✅ | `P6_K2_admin_anonyme.png` | |
| K3 | JWT | ✅ | `P6_K3_auth.png` | |
| L1 | Déconnexion | ✅ | `P6_L1_apres.png` | Tokens supprimés |
| M1 | Performance | ✅ | `P6_M1_performance.png` | LCP 940 ms, 0 pageerror |
| M2 | Lazy loading | N/A | — | |

## Note A9 — faux positif initial

Le premier rapport indiquait A9 ✅ parce que la page contenait bien 8 cartes.
En réalité, elle affichait 2 articles allemands et 6 articles anglais après
hydratation. Le test de l’époque ne vérifiait pas la langue du contenu, seulement
la présence des cartes.

Après le correctif :

- `/fr/blog/` contient **0 carte** et le message
  « Aucun article disponible en français pour le moment. » ;
- aucun titre allemand (`Was ist Website-Monitoring?`,
  `So prüfen Sie Ihr SSL-Zertifikat`) n’est présent ;
- `/en/blog/` ne contient que les 6 articles anglais ;
- `/blog/` ne contient que les 2 articles allemands.

## Limite de contenu CMS

Le snapshot `src/seo/wordpress-posts.snapshot.json` contient **8 articles** :
2 avec `presence_lang.code = "de"`, 6 avec `presence_lang.code = "en"`, aucun
avec `fr`. Le scénario A7 ne peut donc pas afficher 8 articles allemands sans
créer ou traduire du contenu éditorial, ce qui sort du périmètre de ce correctif.
La page DE n’affiche désormais que le contenu réellement allemand.

## E2E

La suite Playwright complète est ajoutée en phase 3 et sera exécutée contre
`https://localhost` avec navigateur visible. Le tableau E2E final et les
snapshots `P8_*` sont ajoutés à l’issue de la répétition générale.
