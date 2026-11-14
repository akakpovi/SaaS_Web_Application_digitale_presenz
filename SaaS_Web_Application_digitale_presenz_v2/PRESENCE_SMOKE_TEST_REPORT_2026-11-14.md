# Presence — Rapport de smoke test corrigé et répétition générale

**Date :** 2026-11-14
**Périmètre :** frontend v2, pile Docker Compose locale
**HEAD code validé :** `e9da5a0` (au-dessus de `58ee7f6`)

## Résultat final

| Mesure | Valeur |
|---|---|
| Scénarios applicables | **45/45 ✅** |
| Scénarios N/A | 6 (E4, E5, F2, G2, G3, M2) |
| A9 — blog FR | **✅ corrigé** : 0 article, message français, aucun contenu allemand |
| A7 — blog DE | **✅ fonctionnel**, réserve CMS : **2 articles DE** seulement |
| Tests E2E | **35/35 ✅** |
| Build | RC 0 — 87 pages SSG, 2 DE + 6 EN (8 au total), 95 URLs sitemap |
| Reconstruction propre | `down` + `build --no-cache web frontend` + `up` : RC 0 |
| Healthcheck | `GET /api/v1/health/` → **200** |
| CI `e9da5a0` | ✅ `43592091854` |
| Security `e9da5a0` | ✅ `43592091825` |
| TypeScript | RC 0 |
| Ruff | Non requis — aucun backend modifié |

> **Correction du rapport précédent :** A9 avait été marqué ✅ à tort. La page
> `/fr/blog/` affichait le catalogue complet (2 articles DE + 6 articles EN)
> après hydratation. A7 supposait à tort une couverture DE complète : le
> snapshot WordPress contient **2 articles DE et 6 articles EN**. Le filtrage
> par locale fonctionne : `/blog/` affiche 2 DE, `/en/blog/` affiche 6 EN et
> `/fr/blog/` affiche 0 article + le message FR.

## 1. Corrections

| Phase | Tâche | Itérations | Statut | Commit |
|---|---|---|---|---|
| 1 | Fix blog multilingue | 2 | ✅ | `8af1d5c` |
| 2 | Rapport corrigé | 1 | ✅ | `cee42b1` |
| 3 | Tests E2E | 2 | ✅ | `e9da5a0` |
| 4 | Push + CI | 1 | ✅ | `e9da5a0` |

Le commit `e9da5a0` inclut aussi le correctif Settings découvert par le test
français : le profil utilisateur ne doit plus écraser `<html lang>` lorsque
l’interface est dans une autre langue.

## 2. Correctif blog (phase 1)

| Fichier | Changement |
|---|---|
| `src/pages/BlogPage.tsx` | Le fetch hydraté transmet `locale` et ne remplace plus la liste localisée par le catalogue complet |
| `src/api/blog.ts` | Filtre client sur `post.lang` si WordPress ignore `presence_lang=fr` |
| `src/main.tsx` | L’hydratation accepte `locale: "fr"` |
| `src/pages/BlogArticle.tsx` | Langue d’article conservée pour DE/EN/FR |
| `src/i18n/fr.json` | « Aucun article disponible en français pour le moment. » |
| `src/i18n/en.json` | « No articles available in English yet. » |
| `scripts/prerender.mjs` | Conservation du code CMS au lieu de forcer `en` |

### Preuves avant / après

| Page | Avant | Après |
|---|---|---|
| `/blog/` | 8 cartes mixtes DE/EN | 2 cartes DE uniquement |
| `/fr/blog/` | 8 cartes DE/EN | 0 carte + message FR |
| `/en/blog/` | 8 cartes mixtes | 6 cartes EN uniquement |

La première itération corrigeait le prérendu mais pas l’hydratation ; la
deuxième ajoute le filtre client et passe la vérification.

## 3. Tests E2E

| Fichier | Tests | Passés | Échecs |
|---|---:|---:|---:|
| `public-pages.spec.ts` | 10 | 10 | 0 |
| `auth.spec.ts` | 5 | 5 | 0 |
| `dashboard.spec.ts` | 3 | 3 | 0 |
| `websites.spec.ts` | 3 | 3 | 0 |
| `i18n-routing.spec.ts` | 4 | 4 | 0 |
| `admin.spec.ts` | 2 | 2 | 0 |
| `mobile.spec.ts` | 2 | 2 | 0 |
| `security.spec.ts` | 2 | 2 | 0 |
| `i18n-french.spec.ts` (existant) | 4 | 4 | 0 |
| **TOTAL** | **35** | **35** | **0** |

Exécution finale après reconstruction propre :

```text
35 passed (3.1m)
E2E_CLEAN_RC=0
```

Itération 1 : 34/35. Le test settings échouait car `Settings.tsx` réécrivait
`document.documentElement.lang` avec la langue du profil. Le provider i18n est
désormais seul propriétaire de cet attribut. Itération 2 : 35/35.

## 4. Répétition générale — 51 scénarios

Score initial : **45/45 avec A9 faux positif**.
Score après corrections : **45/45 applicables**, A9 réellement corrigé.
Itérations globales : **1** (les deux échecs du runner P8 étaient des erreurs
de script, pas de l’application).

| ID | Scénario | Statut | Snapshot | Note |
|---|---|---|---|---|
| A1 | Accueil DE | ✅ | `P8_A1_accueil_de.png` | |
| A2 | Accueil FR | ✅ | `P8_A2_accueil_fr.png` | |
| A3 | Accueil EN | ✅ | `P8_A3_accueil_en.png` | |
| A4 | `/de/` → 301 → `/` | ✅ | `P8_A4_redirect.png` | |
| A5 | Pricing public | ✅ | `P8_A5_pricing.png` | 4 plans, aucun QA |
| A6 | Pricing FR | ✅ | `P8_A6_pricing_fr.png` | 4 plans |
| A7 | Blog DE | ✅ | `P8_A7_blog_de.png` | 2 DE, aucun EN ; couverture DE complète non atteignable |
| A8 | Article DE | ✅ | `P8_A8_article.png` | |
| A9 | Blog FR | ✅ | `P8_A9_blog_fr.png` | 0 article, message FR, aucun allemand |
| A10 | Login DE | ✅ | `P8_A10_login_de.png` | |
| A11 | Login FR | ✅ | `P8_A11_login_fr.png` | |
| A12 | 404 | ✅ | `P8_A12_404.png` | |
| B1 | Inscription, 2 champs MDP | ✅ | `P8_B1_inscription.png` | erreur de confirmation |
| B2 | Doublon localisé | ✅ | `P8_B2_doublon.png` | |
| B3 | Connexion QA | ✅ | `P8_B3_login.png` | dashboard |
| B4 | Échec login localisé | ✅ | `P8_B4_echec.png` | |
| C1 | Dashboard DE + titre | ✅ | `P8_C1_dashboard.png` | |
| C2 | Sidebar complète | ✅ | `P8_C2_sidebar.png` | 9 liens + 3 actions |
| C3 | Dashboard FR | ✅ | `P8_C3_dashboard_fr.png` | |
| D1 | Liste des sites | ✅ | `P8_D1_sites.png` | |
| D2 | Ajout d’un site | ✅ | `P8_D2_ajout.png` | `.invalid`, pas de scan externe |
| D3 | Détail de site | ✅ | `P8_D3_detail.png` | détail du site de test P8 |
| D4 | Suppression | ✅ | `P8_D4_suppression.png` | site de test supprimé |
| E1 | Liste des scans | ✅ | `P8_E1_scans.png` | |
| E2 | Lancement d’un scan | ✅ | `P8_E2_lancement.png` | scan #1184 sur `.invalid` |
| E3 | Résultat de scan | ✅ | `P8_E3_resultat.png` | 7 scanners affichés ; score 0/100 |
| E4 | Journey avancé | N/A | — | |
| E5 | Exposition avancée | N/A | — | |
| F1 | Abonnement QA | ✅ | `P8_F1_subscription.png` | |
| F2 | Upgrade | N/A | — | |
| F3 | Pricing connecté QA | ✅ | `P8_F3_pricing_connecte.png` | QA Interne + Tarif actuel |
| G1 | Paramètres | ✅ | `P8_G1_settings.png` | |
| G2 | Profil | N/A | — | |
| G3 | Sécurité | N/A | — | |
| H1 | Switch FR | ✅ | `P8_H1_fr.png` | `/fr/` |
| H2 | Switch EN | ✅ | `P8_H2_en.png` | `/en/` |
| H3 | Switch DE | ✅ | `P8_H3_de.png` | `/` |
| H4 | Persistance locale | ✅ | `P8_H4_persistance.png` | reload `/fr/pricing/` |
| H5 | Dashboard FR | ✅ | `P8_H5_dashboard_fr.png` | |
| I1 | Login admin Django | ✅ | `P8_I1_admin.png` | |
| I2 | Modèles admin | ✅ | `P8_I2_modeles.png` | index admin |
| I3 | Scans admin | ✅ | `P8_I3_scans.png` | 47 scans |
| J1 | Hamburger mobile | ✅ | `P8_J1_mobile.png` | drawer plein écran |
| J2 | Dashboard mobile | ✅ | `P8_J2_mobile_dash.png` | |
| J3 | Login mobile | ✅ | `P8_J3_mobile_login.png` | |
| K1 | Anonyme → login | ✅ | `P8_K1_redirect.png` | |
| K2 | Admin anonyme → login | ✅ | `P8_K2_admin_anon.png` | |
| K3 | JWT → `/auth/me/` | ✅ | `P8_K3_jwt.png` | HTTP 200 |
| L1 | Déconnexion | ✅ | `P8_L1_logout.png` | tokens supprimés |
| M1 | Performance | ✅ | `P8_M1_perf.png` | LCP 2,55 s froid / 0,80 s chaud |
| M2 | Lazy loading | N/A | — | |

> **A7 / contenu CMS :** le snapshot contient **2 articles DE et 6 articles EN**
> (8 au total). Aucun article FR n’existe. `/blog/` affiche 2 DE, `/en/blog/`
> affiche 6 EN et `/fr/blog/` affiche 0 article + le message FR. La réserve
> porte uniquement sur le volume de contenu DE : l’ajouter exigerait de créer
> ou traduire des articles dans WordPress, hors périmètre de ce correctif.
> La page DE n’affiche désormais que le contenu réellement allemand.

> **D3/E3 :** le détail et le résultat portent sur le site de test P8
> `e2e-p8-….invalid`, supprimé après D4. Le scan #1184 a été exécuté sur ce
> domaine invalide pour ne jamais scanner un vrai domaine de production.

## 5. Notes A9 — faux positif initial

Le premier rapport indiquait A9 ✅ parce que la page contenait 8 cartes. En
réalité, elle affichait 2 articles allemands et 6 articles anglais après
hydratation. Le test ne vérifiait pas la langue du contenu.

Après le correctif :

- `/fr/blog/` contient 0 carte et le message
  « Aucun article disponible en français pour le moment. » ;
- aucun titre allemand (`Was ist Website-Monitoring?`,
  `So prüfen Sie Ihr SSL-Zertifikat`) n’est présent ;
- `/en/blog/` ne contient que les 6 articles anglais ;
- `/blog/` ne contient que les 2 articles allemands.

## 6. HEAD, CI et snapshots

| Élément | Valeur |
|---|---|
| HEAD code | `e9da5a0` |
| Base demandée | `58ee7f6` |
| Commits | `8af1d5c`, `cee42b1`, `e9da5a0` |
| CI | ✅ `43592091854` |
| Security | ✅ `43592091825` |
| Scan anti-secrets du diff | ✅ aucune valeur de secret |
| `.env` | inchangé |

Snapshots P8 : **46 fichiers** dans `screenshots/` (45 scénarios applicables +
la confirmation D4). Les 6 scénarios N/A ne produisent pas de snapshot.
Les preuves E2E sont également dans `screenshots/E2E_*.png`, et les logs
d’exécution dans `/tmp/p7-e2e-run*.log`.
