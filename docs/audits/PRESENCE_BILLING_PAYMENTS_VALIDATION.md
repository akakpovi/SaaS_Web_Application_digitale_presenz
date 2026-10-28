# Presence — Abonnements, paiements et quotas

**Date :** 27 octobre 2026
**Périmètre :** environnement Docker local Presence. **Aucun paiement réel, aucun déploiement.**

---

## 1. Fournisseur et architecture constatés

- **Fournisseur unique : Paddle Billing**, intégré par API REST (`requests`), **sans SDK** — `backend/subscriptions/services/billing.py`.
- Aucun second système d'abonnement concurrent n'existe : les changements d'offre passent exclusivement par `POST /subscriptions/checkout/` puis par le **webhook** `POST /api/v1/webhooks/paddle/`.
- `POST /subscriptions/upgrade/` est explicitement **fermé** (409 `use_checkout`) : il ne peut plus octroyer une offre payante, que la facturation soit configurée ou non.
- Le client n'envoie jamais de montant : seulement `plan_tier` + `billing_cycle`. Le prix vient de `Plan.external_price_id_monthly/_yearly` (source unique partagée avec l'API publique de tarifs).
- Cartographie des statuts : `active`, `trialing`, `past_due`/`paused`, `canceled` → statuts locaux ; un prix inconnu **échoue bruyamment** (500 pour rejeu Paddle) au lieu d'appliquer un changement silencieux.

### Sécurité vérifiée dans le code

| Point | Implémentation |
|---|---|
| Signature webhook | `verify_paddle_signature` : HMAC-SHA256 sur `"{ts}:{raw_body}"`, support de plusieurs `h1` (rotation de clé), **tolérance de 5 minutes** contre le rejeu. |
| Corps non fiable | Le corps brut est relu tel quel (`request.body`), pas de re-sérialisation. |
| Idempotence | `BillingEvent` avec contrainte unique `(provider, event_id)` ; un événement déjà `processed` renvoie `duplicate` sans réappliquer. |
| Signatures refusées | Absence de signature, signature invalide, horodatage expiré → 400. Secret absent → **503 explicite** (jamais un succès silencieux). |
| Redirection navigateur | Jamais utilisée comme preuve de paiement : seule la confirmation webhook active une offre. |
| Données bancaires | Aucune donnée carte stockée ; le portail client Paddle héberge moyens de paiement et factures. |
| Annulation | `cancel_at_period_end` : l'abonnement reste `active` localement jusqu'au webhook `subscription.canceled` ; l'accès n'est pas coupé pendant une période déjà payée. |
| Isolation | Quotas calculés par utilisateur **ou** par organisation (payeur = `billing_owner`), jamais depuis un identifiant fourni par le client. |

---

## 2. Quotas réellement appliqués côté serveur

`backend/subscriptions/services/quotas.py` est l'unique point d'entrée (`assert_can_add_website`, `assert_can_scan`, `assert_can_add_team_member`, `assert_can_add_alert_channel`, `assert_paid_plan`, `assert_feature`), appelé par les vues et par le planificateur de surveillance. Un dépassement renvoie **403 structuré** (`code`, `limit`, `usage`, `plan`, `upgrade_url`).

Contrôles serveur confirmés par les tests : nombre de sites, scans/mois, canaux d'alerte, membres d'équipe (y compris invitations en attente), export PDF, clés API, suites payantes.

---

## 3. Corrections apportées

### 3.1 Fuite de droits après expiration (corrigée)

**Défaut réel :** `get_effective_plan` accordait l'offre payante à un abonnement `past_due` **sans limite de durée**, et `cancelled` perdait l'accès immédiatement même si la période était déjà payée. **Aucune tâche n'expirait jamais un abonnement** : un renouvellement refusé dont le webhook était perdu conservait les quotas payants indéfiniment.

Corrections :
- `subscriptions/services/quotas.py` — `_paid_period_has_ended()` : l'offre payante s'applique tant que `current_period_end` n'est pas dépassé (`active`, `trialing`, `past_due`, `cancelled`) ; `expired` retombe immédiatement sur Free ; `current_period_end` NULL conserve l'accès (comptes antérieurs à la facturation).
- `subscriptions/tasks.py` (nouveau) — `expire_subscriptions` : marque `expired` les abonnements dont la période est terminée, ce qui couvre les webhooks perdus.
- `config/settings/base.py` — planification quotidienne `expire-subscriptions-daily` (02:15) dans Celery Beat.

Ces tests ont été ajoutés et exécutés : `subscriptions/tests/test_entitlement_expiry.py` (8 tests) — `past_due` dans sa période garde Pro, après la période retombe Free, `cancelled` garde l'accès jusqu'à la fin de période, `expired` est immédiatement Free, la tâche ne touche pas les périodes en cours.

---

## 4. Tests exécutés

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh subscriptions` | **55 tests, OK** (160 s) |
| `pnpm exec tsc --noEmit` / `pnpm run build` | OK (aucun changement frontend nécessaire sur la facturation) |

Couverture réelle des scénarios exigés par les tests existants (mocks provider, **aucun appel réel**) :

- paiement accepté : `test_checkout_returns_provider_url`, `test_subscription_created_activates_plan`, `test_transaction_completed_provisions_subscription` ;
- paiement refusé / indisponibilité fournisseur : `test_checkout_provider_failure_is_502`, `test_checkout_without_price_id_is_503`, `test_checkout_disabled` ;
- webhook invalide : `test_missing_signature_is_rejected`, `test_invalid_signature_is_rejected`, `test_expired_timestamp_is_rejected` ;
- webhook répété : `test_duplicate_event_is_idempotent` ;
- annulation : `test_cancelled_event_downgrades_status`, `test_cancel` ;
- expiration : nouveaux tests `test_entitlement_expiry` + tâche quotidienne ;
- changement d'offre : `test_upgrade_is_closed`, `test_upgrade_never_changes_the_plan` (l'endpoint ne peut pas octroyer d'offre) ;
- dépassement de quota : `test_free_plan_allows_only_one_website`, `test_pro_plan_raises_website_limit`, `test_scan_quota_is_enforced`, `test_scan_quota_allows_under_limit`, `test_alert_channel_quota_is_enforced`, `test_free_plan_cannot_export_pdf`, `test_free_plan_cannot_create_api_key` ;
- accès d'un autre tenant : couvert par les suites multi-tenant (`websites.tests.test_tenant_access`, `monitoring.tests.test_scan_policy.MonitoringAccessTests`) réexécutées dans la campagne.
- outillage sandbox : `subscriptions/tests/test_paddle_sandbox.py` (création des prix depuis le catalogue, refus sans clé, refus de l'API live sans drapeau explicite, secret webhook écrit mais **jamais affiché**).

---

## 5. Blocage réel : validation Paddle en mode test impossible en l'état

Constats mesurés dans l'environnement local (noms de variables uniquement, aucune valeur lue) :

| Élément | État constaté |
|---|---|
| `BILLING_ENABLED` | **désactivé** |
| `BILLING_PROVIDER` | `paddle` |
| `PADDLE_API_KEY` | **absent** |
| `PADDLE_WEBHOOK_SECRET` | **absent** |
| `PADDLE_ENVIRONMENT` | `sandbox` |
| `Plan.external_price_id_monthly/yearly` (4 offres) | **vides** |

Conséquence : `POST /subscriptions/checkout/` répond **503 `billing_not_configured`**, le webhook répond **503 `webhook_not_configured`**, et l'interface affiche correctement le bandeau « Payments are not enabled on this environment yet » avec les boutons d'achat désactivés.

**Aucun paiement de test, aucun webhook réel et aucun cycle renouvellement/annulation côté fournisseur n'ont donc pu être exécutés.** C'est un blocage de dépendance externe, pas un défaut du code : ce qui manque est un compte Paddle sandbox (clé API, secret webhook) et la création des prix sandbox — l'outillage existe déjà : `manage.py create_paddle_sandbox` (avec garde `--live` explicite) et `scripts/paddle_webhook_tunnel.sh`.

### Procédure de validation restante (à exécuter avec des identifiants sandbox)

1. `PADDLE_API_KEY` + `PADDLE_WEBHOOK_SECRET` sandbox dans l'environnement local, `BILLING_ENABLED=True` ;
2. `python manage.py create_paddle_sandbox` → renseigne `external_price_id_*` sur les 4 offres ;
3. tunnel webhook (`scripts/paddle_webhook_tunnel.sh`) puis paiement sandbox : vérifier l'activation par webhook, le rejeu (idempotence), le paiement refusé, l'annulation en fin de période, et la dégradation des droits ;
4. vérifier qu'aucun secret n'apparaît dans les logs.

---

## 6. Limites et risques résiduels

- `expire_subscriptions` n'a pas été observée sur Celery Beat réel : la tâche est enregistrée mais le conteneur `celery-beat` doit être recréé pour charger la nouvelle planification (prévu lors de la reconstruction contrôlée).
- Les périodes de grâce commerciales ne sont pas décidées : la règle actuelle est « accès payant jusqu'à `current_period_end`, puis Free », sans grâce supplémentaire. Toute période de grâce devrait être validée explicitement avant la mise en production.
- Les prix (9 € / 29 € / 79 €) sont ceux actuellement en base ; aucun prix n'a été inventé ni modifié dans cette session.
- Aucune donnée historique n'a été modifiée : les abonnements existants conservent leur statut, seule la lecture des droits change.
