# Presence — Acceptation finale (master prompt du 27 octobre 2026)

**Périmètre :** pile locale Presence, environnement Docker partagé. **Aucun déploiement VPS, aucun paiement réel.**
**Rapports détaillés :**

- `PRESENCE_FINAL_SCANNER_UI_ACCEPTANCE_2026-10-27.md` — scanners et interface
- `PRESENCE_CONTINUOUS_MONITORING_NOTIFICATIONS.md` — surveillance, alertes, notifications
- `PRESENCE_BILLING_PAYMENTS_VALIDATION.md` — abonnements, paiements, quotas
- `PRESENCE_AKA_IA_FINAL_VALIDATION_2026-10-27.md` — AKA IA

---

## 1. Ce qui fonctionne réellement (preuves observées)

| Domaine | État | Preuve |
|---|---|---|
| API, auth, tenants | **Validé** | Recette 17/17 : création de site, scans, isolation 404 inter-tenant |
| Scan réel de bout en bout | **Validé** | Scan `health` `completed`, score 69, 7 `CheckResult`, 8 `ScannerRun`, 7 `Finding` persistés, API = base |
| Statuts honnêtes | **Validé** | `completed`/`partial`/`failed` agrégés par l'orchestrateur ; jamais de succès sur couverture incomplète (suites `scans`, `alerts`) |
| Six scanners avancés | **Installés** | `scanner-tools-check` : nmap 7.93, nikto 2.6.1, whatweb 0.5.5, dnsrecon 1.1.3, gobuster 3.6, testssl.sh présent ; Nuclei + ZAP conservés |
| Archives | **Validé** | `scanner_archive_data` monté sur `/app/scanner-archives` (volume conservé, permissions `0700`, propriétaire `app`) |
| Surveillance continue | **Validé** | Opt-in, planification respectant quota + intervalle minimum, pause qui vide la planification, vérification automatique réellement enchaînée par Celery Beat |
| Alertes | **Validé** | Création, déduplication, escalade des échecs répétés, résolution uniquement sur scan complet |
| Centre de notifications | **Validé** | Page Alerts (historique, filtres, acquittement, liens) ; cloche navigante ; canaux e-mail/Slack/Discord/webhook/SMS + préférences + push |
| Facturation serveur | **Validé (mocks)** | Signature webhook, idempotence, prix inconnu refusé, quotas serveur, expiration par période ; **paiement sandbox non exécuté** (clés absentes) |
| AKA IA | **Validé** | Passerelle réelle (`qwen/qwen3.8-27b`, 0,3–0,9 s), isolation 404/403, bloc de couverture dans le prompt, 503 propre en panne, plafond 60/h |
| Interface | **Validé (manuel)** | Parcours navigateur sur données réelles : site, monitoring, activation/pause, alertes, advisor ; aucune erreur console |

---

## 2. Ce qui a été corrigé dans cette mission

| Correction | Fichiers principaux |
|---|---|
| Surveillance opt-in (plus de scan automatique silencieux) | `monitoring/models.py`, `signals.py`, `serializers.py`, `views.py` |
| Retour des résultats de scan vers les compteurs de surveillance (échecs/escalade) | `scans/tasks.py`, `alerts/tasks.py` |
| Course « pause pendant un tick » qui laissait une planification fantôme | `monitoring/tasks.py` (+ test) |
| Escalade des exécutions partielles répétées | `alerts/tasks.py` |
| Droits payants après expiration (fuite de quotas `past_due` illimitée) + tâche d'expiration | `subscriptions/services/quotas.py`, `subscriptions/tasks.py`, `config/settings/base.py` |
| AKA IA : bloc de couverture du dernier scan dans le prompt | `advisory/services/security_advisor.py` (+ tests) |
| AKA IA : plafond de requêtes par utilisateur | `advisory/views.py`, `config/settings/base.py` (+ test) |
| UI : activation/pause de la surveillance, carte post-scan, cloche navigante, rafraîchissement du panneau sécurité | `Monitoring.tsx`, `WebsiteDetails.tsx`, `AppShell.tsx`, `api/types.ts` |
| Pile active remise à niveau (images reconstruites) | `docker compose build web celery-worker celery-beat frontend` |

---

## 3. Tests exécutés (résultats réels)

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh advisory` | **181 tests, OK** |
| `bash scripts/run_backend_tests.sh scans alerts websites notifications` | **285 tests, OK** |
| `bash scripts/run_backend_tests.sh subscriptions` | **55 tests, OK** |
| `bash scripts/run_backend_tests.sh monitoring` | **39 tests, OK** |
| Suites ciblées (statuts, ingestion, orchestration, alertes) | OK |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | aucune migration manquante (78 appliquées) |
| `pnpm exec tsc --noEmit`, `pnpm run build` | OK |
| `docker compose config --quiet` | OK |
| Recette intégrée réelle (`scripts/integrated_acceptance_recipe.py`) | **17/17** |
| Parcours navigateur | Validé (captures dans `docs/audits/screenshots/`) |

Échecs à signaler : **aucun test en échec** après corrections. Les seuls « échecs » rencontrés étaient des contrôles de la recette, corrigés (planification à la pause) puis vérifiés.

---

## 4. Non fait / partiellement fait

1. **Paiement Paddle sandbox** : impossible sans `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET` et les price IDs. Procédure prête (`manage.py create_paddle_sandbox`, `scripts/paddle_webhook_tunnel.sh`).
2. **Scans `security`/`full`** : non rejoués dans cette session (installation et validation antérieures, cf. rapport scanners) ; la chaîne health + UI + ingestion a été réexécutée.
3. **Recommandations IA automatiques** : `AI_ADVISOR_ENABLED=false` en local ; logique couverte par tests, exécution réelle désactivée.
4. **Quota IA par forfait** : décision produit non prise (plafond horaire global en place).
5. **Suite Playwright** du projet : non rejouée (parcours manuel effectué).
6. **E-mail réel via Mailpit** : non rejoué manuellement (tests `locmem`).
7. **VPS** : aucun accès, aucune ressource mesurée ; plan de release et préconditions documentés dans `PRESENCE_VPS_RELEASE_READINESS_2026-10-27.md`.
8. **Espace disque local** : `/` à 93 % utilisé (≈17 Go libres), images Docker 21 Go dont ≈12 Go récupérables et ≈3,8 Go de cache de build. Nettoyage non exécuté sans autorisation (le nettoyage du 27/10 reste valide, cf. son rapport).

---

## 5. Risques bloquants avant première mise en production

| Risque | Gravité | Traitement |
|---|---|---|
| Aucun paiement réel validé (activation réelle d'offre non observée) | **Bloquant commercial** | Obtenir les identifiants sandbox puis exécuter la procédure du rapport facturation |
| Période de grâce / politique d'expiration non décidée | Moyen | Décision produit ; l'implémentation actuelle coupe à `current_period_end` |
| Secrets de production absents (clés Paddle, éventuels mail) | **Bloquant** | Renseigner les secrets sur le VPS (hors dépôt) |
| Disk du VPS inconnu face à 21 Go d'images + archives | Moyen | Mesurer avant build, prévoir rotation des archives et des logs |
| Quota IA par offre non appliqué | Moyen | Décision produit + brancher `assert_*` sur l'usage AKA IA |
| Cible externe autorisée unique pour les tests `security` | Faible | Documenter les cibles autorisées et les limites de débit |

---

## 6. Étapes restantes avant première mise en production

1. Décider et configurer la facturation (clés sandbox → recette paiement → clés live).
2. Décider la politique d'expiration/grâce et le quota IA par forfait.
3. Exécuter un scan `security` complet sur la cible autorisée avec les six scanners, vérifier `partial`/`completed` et l'archivage.
4. Rejouer la suite Playwright et le test de charge `load/k6/presence_load_test.js` sur un environnement isolé.
5. Libérer l'espace Docker (≈12 Go récupérables) avant toute nouvelle reconstruction lourde.
6. Appliquer le plan de release VPS (sauvegarde vérifiée → migrations → services → contrôles de fumée) sans l'exécuter maintenant.
