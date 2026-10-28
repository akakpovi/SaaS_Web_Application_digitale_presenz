# Parité API ↔ UI — 2026-10-23

> **Mise à jour :** les écarts listés en § « Ce qui reste sans interface » ont
> depuis été traités et vérifiés. Voir
> [RAPPORT_FINAL_PARITE_2026-10-23.md](RAPPORT_FINAL_PARITE_2026-10-23.md).

Périmètre de cette itération : les trois missions restantes identifiées après
l'audit de parité (admin analytics, réglages monitoring/alertes/push, import
d'avis). Ce rapport distingue explicitement ce qui est **couvert et vérifié**
de ce qui **reste sans interface**.

## 1. Admin analytics — réel

- `GET /api/v1/analytics/admin/overview/` alimente `/admin` (aucune valeur
  codée en dur dans la page).
- Ajout au endpoint de métriques d'abonnement réelles :
  - `mrr_eur` = somme des abonnements `active` payants, un plan annuel étant
    ramené à son équivalent mensuel (`price_yearly / 12`) ;
  - `arr_eur`, `paying_users`, `trialing_users`, `by_plan[]` (tier, nom,
    nombre d'abonnements, MRR du plan) ;
  - les abonnements `free` et `trialing` sont exclus du MRR.
- Vérifié dans le navigateur : `MRR €53,17`, `€638 ARR · 2 paying · 0 trialing`,
  `Pro · 2 subs`, sans erreur console.
- Test : `analytics/tests/test_admin_overview.py` (403 non-staff, calcul
  mensuel + annuel, exclusion free/trial).

## 2. Monitoring, alertes et canaux

- `PATCH /monitoring/websites/:id/` : les six fréquences (5m, 15m, 30m, 1h,
  6h, 24h) sont proposées par site ; le changement est persisté puis relu.
  Vérifié via le DOM (24h → 6h) puis en base par l'API.
- `PATCH /alerts/preferences/` : les neuf interrupteurs de types d'alerte et
  la fréquence de digest lisent et écrivent les préférences réelles. Vérifié
  via le DOM (un interrupteur passe à `false` côté API puis revient).
- `POST /notifications/channels/:id/test/` : bouton « Test » sur chaque canal.
  Vérifié via l'UI : HTTP 200 et e-mail réellement remis (Mailpit).
- Web Push :
  - `GET /notifications/push/public-key/` (nouveau) expose la clé VAPID
    publique, indispensable à `pushManager.subscribe` ;
  - `public/sw.js` (nouveau) reçoit les pushs et ouvre l'URL cliquée ;
  - enregistrement du service worker dans `main.tsx` ;
  - `POST /notifications/push/subscribe/` crée l'abonnement du navigateur,
    `POST /notifications/push/test/` déclenche un envoi réel.
  - Tant que `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` sont vides, l'UI affiche
    un message explicite et n'invente pas de succès.
- Panneau PWA : l'état affiché est désormais lu dans le navigateur
  (`display-mode: standalone`, permission de notification). Le faux
  « installed · last synchronized today at 10:42 » et l'interrupteur
  « Offline data » (aucun cache hors-ligne implémenté) sont supprimés.
- Le composant `Toggle` est un vrai `role="switch"` (clavier + lecteur d'écran).

## 3. Import d'avis

- Bouton « Import CSV » + modal : choix/création de la source, fichier CSV ou
  JSON, suivi du job (`pending → processing → completed`), rafraîchissement
  automatique de la liste.
- Correctif backend indispensable : l'import calculait les avis mais **jamais
  leur sentiment**, la liste restait donc entièrement `neutral`. Le sentiment
  est maintenant calculé à l'import et stocké dans `ReviewSentiment`.
- Réimport idempotent : `(source, external_id)` fait un upsert au lieu de
  violer la contrainte d'unicité ; une note vide vaut 5 au lieu de faire
  échouer la ligne.
- Correctif déploiement : le volume `media_data` était créé `root:root`, donc
  tout upload renvoyait 500 (`PermissionError: /app/media/review_imports`).
  Le service `staticfiles` (déjà root) initialise et attribue le volume à
  `app` avant le démarrage de `web`.
- Vérifié : 2 lignes importées, `Ada` → `positive`, `Bob` → `negative`,
  réimport → toujours 2 avis. Tests : `reviews/tests/test_bulk_import.py`.

### Format CSV attendu

| Colonne | Obligatoire | Remarque |
| --- | --- | --- |
| `author` (ou `author_name`, `name`) | oui | ligne rejetée si absente |
| `rating` | non | 1–5, vide ⇒ 5 |
| `text` (ou `content`) | non | analysé pour le sentiment |
| `review_date` (ou `date`) | non | ISO 8601 ; défaut = maintenant |
| `external_id` | non | clé d'idempotence si fournie |

Une seconde ligne d'en-tête, un JSON (`[{...}]` ou `{"reviews": [...]}`) et
l'UTF-8 avec BOM sont acceptés.

## Vérifications exécutées

- `pnpm run build` : OK (tsc + vite + prerender).
- Suite backend complète : **432 tests, OK** (dont les nouveaux tests MRR,
  import CSV et push).
- Contrôles HTTP réels sur la pile Docker (`https://localhost/api/v1/`) :
  overview admin, PATCH préférences, PATCH monitoring, test de canal,
  clé publique push, 401 sur abonnement anonyme, import complet.
- Contrôles DOM : `/admin`, `/app/monitoring`, `/app/reviews`,
  `/app/settings` (alertes, PWA, compte).

## Ce qui reste sans interface (hors missions)

Ces routes ne sont pas couvertes à ce jour ; aucune n'a été modifiée.

| Route | État |
| --- | --- |
| `/auth/email/verify/` | **Couvert** : page `/verify-email` (voir rapport final). |
| `/public/scan/*` | **Couvert** : checker réel + page de résultats publique. |
| `/reviews/:id/approve/` | **Couvert** : action d'approbation dans `/app/reviews`. |
| `/scans/:id/results/` | **Couvert** : diagnostic consolidé dans le détail du scan. |
| `/monitoring/` (liste) | Remplacé par `/monitoring/overview/` dans l'UI. |
| `/analytics/events/track/` | Le trafic est enregistré côté serveur ; pas d'appel client. |
| `/subscriptions/upgrade/` | Volontairement fermé (legacy) : aucune UI attendue. |
| `admin/`, `webhooks/paddle/`, `api/docs|schema|redoc`, `health/` | Interne / machine, sans UI par conception. |

Réglages encore statiques (aucun endpoint de profil à ce jour) : section
« Business » et sélecteur de langue. La section « Compte » affiche désormais
l'utilisateur réel et signale que l'API est en lecture seule au lieu de
montrer une identité de démonstration.

**Conclusion (historique)** : les trois missions de cette itération étaient
couvertes et vérifiées. Les quatre écarts restants ont été fermés depuis ;
voir [RAPPORT_FINAL_PARITE_2026-10-23.md](RAPPORT_FINAL_PARITE_2026-10-23.md).
