# Presence — Surveillance continue, alertes et notifications

**Date :** 27 octobre 2026
**Périmètre :** environnement Docker local Presence (démon partagé), aucun déploiement.
**Méthode :** audit du code réellement exécuté, corrections minimales, tests Django ciblés sur le code de l'arbre de travail (`scripts/run_backend_tests.sh`).

---

## 1. État initial constaté

| Élément | État avant |
|---|---|
| Activation après le premier scan | Absente : `MonitoringConfig` était créée `enabled=True` avec `next_scan_at=now`, donc **tout site ajouté était scanné automatiquement** sans consentement, avec le type `health`. |
| Désactivation / réactivation | L'API permettait `DELETE` (mise en pause) mais **aucune UI ne permettait de réactiver** un site en pause. |
| Compteur d'échecs | `MonitoringConfig.record_failure()` / `record_success()` existaient mais **n'étaient appelés nulle part** : `consecutive_failures` restait à 0, la colonne « Fails » du tableau de bord restait vide et l'escalade de sévérité ne pouvait jamais se déclencher. |
| Alertes de scan incomplet | `alerts.tasks.report_scan_issue` existait (créée par la mission de statuts) et était bien appelée pour `failed`/`partial`. La sévérité restait `warning` pour toute exécution partielle, même répétée. |
| Résolution automatique d'alerte | Implémentée (`_auto_resolve`) : SSL, DNS, e-mail, en-têtes, performance, score, site hors ligne et `scan_failed`. Jamais déclenchée depuis un scan incomplet (garde `not_completed`). |
| Quotas dans le planificateur | Corrigés lors de la session précédente : `run_due_monitors` applique `max_scans_per_month` et `min_scan_interval`. |
| Centre de notifications | Page **Alerts** = historique, filtres (Tous / Critical / Warning / Resolved), acquittement et résolution. Le bouton cloche du header était **inerte** (aucun `onClick`, aucune navigation). |
| Préférences de notification | Écran Settings fonctionnel (`PATCH /alerts/preferences/`), canaux (e-mail/Slack/Discord/webhook/SMS), test de canal réel, web-push VAPID. |

---

## 2. Corrections apportées

### 2.1 Surveillance opt-in (backend)

- `monitoring/models.py` : `enabled` passe à `default=False` avec commentaire explicite (aucun site n'est scanné en boucle sans consentement).
- `monitoring/signals.py` : la configuration créée à la création du site n'a **plus de `next_scan_at`** ; l'activation (API) programme la première vérification.
- `monitoring/serializers.py` : `update()` rend l'activation cohérente —
  - actif + activé ⇒ `next_scan_at = now` ;
  - désactivé ⇒ `next_scan_at = None` (plus aucune exécution après la pause) ;
  - changement d'intervalle pendant l'activité ⇒ re-planification depuis maintenant (jamais dans le passé, donc pas de rafale de rattrapage).
- `monitoring/views.py` : `get_or_create` ne force plus `enabled=True`.

### 2.2 Boucle de retour des résultats (backend)

- `scans/tasks.py` : nouveau `_record_monitoring_outcome(scan)` appelé par `_finalize_scan` et par le chemin d'exception du task —
  - `completed` ⇒ `record_success()` (remise à zéro des échecs) ;
  - `failed` / `partial` ⇒ `record_failure()` (incrément + niveau d'escalade).
- `alerts/tasks.py` : la sévérité de l'alerte de couverture tient compte de la répétition — 1ʳᵉ exécution partielle = `warning`, `partial` après ≥ 2 échecs consécutifs = `critical`. Une seule alerte `scan_failed` est maintenue en `firing` et rattachée à la dernière exécution (pas de doublon).

### 2.3 Interface (frontend)

- `src/pages/Monitoring.tsx` : bouton **Activate monitoring / Pause monitoring** sur chaque ligne ; badge « Monitoring off » en ton neutre ; le toast de pause précise qu'aucun scan programmé ne repartira.
- `src/pages/WebsiteDetails.tsx` : carte d'activation proposée **après le premier scan terminé** lorsque la surveillance est inactive. Elle explique ce qui est surveillé (uptime, certificat, score, alertes), la fréquence par défaut (24 h), l'impact sur le quota mensuel de scans et la possibilité de mettre en pause ou de changer la fréquence. Le bandeau d'en-tête ne confond plus l'état du site (`is_active`) avec l'état de surveillance.
- `src/components/AppShell.tsx` : la cloche de notifications navigue désormais vers `/app/alerts` (centre de notifications de l'application) ; le compteur reste basé sur les alertes `firing`.
- `src/api/types.ts` : type `MonitoringConfig` ajouté (aligné sur le sérialiseur réel).

### 2.4 Facturation — expiration liée au cycle (correction connexe)

Découverte pendant l'audit : aucune tâche n'expirait un abonnement et `get_effective_plan` accordait l'offre payante à un `past_due` **indéfiniment**.

- `subscriptions/services/quotas.py` : `_paid_period_has_ended()` ; `active`, `trialing`, `past_due` et `cancelled` conservent l'offre payante **jusqu'à `current_period_end`** puis retombent sur Free ; `expired` est immédiatement Free ; `current_period_end` NULL conserve l'accès (comptes historiques).
- `subscriptions/tasks.py` (nouveau) : `expire_subscriptions` marque `expired` les abonnements dont la période payée est terminée sans webhook reçu.
- `config/settings/base.py` : tâche planifiée quotidienne `expire-subscriptions-daily` (02:15).

---

## 3. Fichiers modifiés

| Fichier | Nature |
|---|---|
| `backend/monitoring/models.py` | opt-in par défaut |
| `backend/monitoring/signals.py` | plus de planification automatique |
| `backend/monitoring/serializers.py` | activation/pause/replanification |
| `backend/monitoring/views.py` | `get_or_create` sans activation implicite |
| `backend/scans/tasks.py` | retour des résultats vers `MonitoringConfig` |
| `backend/alerts/tasks.py` | escalade des exécutions partielles répétées |
| `backend/subscriptions/services/quotas.py` | expiration liée à la période |
| `backend/subscriptions/tasks.py` | nouvelle tâche d'expiration |
| `backend/config/settings/base.py` | entrée Celery Beat |
| `backend/monitoring/tests/test_models.py` | test d'opt-in |
| `backend/monitoring/tests/test_scan_policy.py` | planificateur avec config activée |
| `backend/monitoring/tests/test_scheduler.py` | quotas/intervalle + API d'activation (4 tests) |
| `backend/alerts/tests/test_alert_resolution.py` | **nouveau** — résolution automatique (6 tests) |
| `backend/scans/tests/test_monitoring_feedback.py` | **nouveau** — compteurs et escalade (6 tests) |
| `backend/subscriptions/tests/test_entitlement_expiry.py` | **nouveau** — expiration des droits (8 tests) |
| `frontend/src/pages/Monitoring.tsx` | activation/pause |
| `frontend/src/pages/WebsiteDetails.tsx` | proposition d'activation post-scan |
| `frontend/src/components/AppShell.tsx` | cloche → centre d'alertes |
| `frontend/src/api/types.ts` | type `MonitoringConfig` |

Aucune migration nouvelle n'est nécessaire : `MonitoringConfig.enabled` garde son schéma, seul le défaut applicatif change (les lignes existantes restent telles quelles).

---

## 4. Tests exécutés (arbre de travail monté dans le conteneur `web`)

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh monitoring` | **38 tests, OK** (138 s) |
| `bash scripts/run_backend_tests.sh monitoring.tests.test_scheduler monitoring.tests.test_models alerts.tests.test_alert_resolution alerts.tests.test_alerts scans.tests.test_alert_pipeline` | **45 tests, OK** (100 s) |
| `bash scripts/run_backend_tests.sh scans.tests.test_monitoring_feedback scans.tests.test_alert_pipeline alerts.tests.test_alert_resolution monitoring` | **60 tests, OK** (198 s) |
| `bash scripts/run_backend_tests.sh subscriptions` | **55 tests, OK** (160 s) — inclut les 8 nouveaux tests d'expiration |
| `pnpm exec tsc --noEmit` | OK |
| `pnpm run build` | OK (build + prérendu 31 routes publiques) |
| `docker compose config --quiet` | OK |

Couverture des points exigés :

- activation/désactivation/suspension/modification : tests API `MonitoringActivationApiTests` + UI ;
- quotas respectés par le planificateur : `MonitoringQuotaTests` (y compris deux sites dus partageant le quota) ;
- détection et déduplication : `DetectAlertsDeliveryTests`, `CoverageAlertEscalationTests` (2ᵉ exécution incomplète = 0 doublon, rattachement au dernier scan) ;
- reprise après échec : `_auto_resolve` ne s'exécute que sur un scan `completed`, testé dans `IncompleteScanAlertTests` ;
- absence de fausse résolution : un scan `partial`/`failed` ne peut ni créer ni résoudre (testé).

---

## 5. Décisions de conception à connaître

1. **Le centre de notifications in-app est la page Alerts.** « Lu » correspond à l'acquittement, l'historique et les filtres existent déjà, et chaque alerte porte le lien vers le site, le scan et le constat. Aucun second modèle de notification concurrent n'a été créé.
2. **La surveillance est désormais opt-in.** Les sites existants avec `enabled=True` en base continuent d'être scannés : la correction ne réécrit aucune donnée. Un site dont la surveillance était activée reste activé.
3. **La pause vide la planification.** Reprendre une surveillance ne rattrape pas les vérifications manquées.
4. **Une exécution partielle répétée devient critique** (≥ 2 échecs consécutifs) mais reste une alerte de couverture : elle ne résout jamais un constat.

---

## 6. Validation réelle sur la pile reconstruite (27/10, après 10:40)

Les images `web`, `celery-worker`, `celery-beat` et `frontend` ont été **reconstruites depuis l'arbre de travail puis recréées** (`docker compose build … && docker compose up -d --no-deps …`), sans toucher à `db`, `redis`, ni à aucun volume. Le worker recréé monte toujours `scanner_archive_data` sur `/app/scanner-archives` (volume `saas_web_application_digitale_presenz_scanner_archive_data`, propriétaire `app`, archives `dnsrecon` existantes conservées), et `manage.py check` ne signale aucun problème sur la nouvelle image.

> Découverte importante de cette vérification : avant reconstruction, la pile exécutait une **image antérieure** aux correctifs de la session (le conteneur `web` n'a aucun montage du code source). Toute validation fonctionnelle antérieure sur cette pile portait donc sur l'ancien code ; les preuves ci-dessous ont été produites après reconstruction.

### Anomalie supplémentaire trouvée et corrigée pendant la recette

Lors de la pause déclenchée pendant qu'un tick du planificateur s'exécutait, celui-ci réécrivait `next_scan_at` **sans condition** à la fin de son itération : une surveillance mise en pause pendant un tick gardait une « prochaine vérification » qui ne pouvait plus jamais tourner. `monitoring/tasks.py` utilise désormais `_reschedule()`, un `UPDATE` conditionnel (`enabled=True`) : si le site a été mis en pause entre-temps, aucune replanification n'est écrite. Test de régression : `test_pausing_during_a_tick_does_not_rearm_the_schedule`.

### Recette intégrée (`scripts/integrated_acceptance_recipe.py`)

Exécutée dans le conteneur `web` contre l'API réelle, avec deux comptes de test créés à la volée :

```
docker compose exec -T web python - < scripts/integrated_acceptance_recipe.py
```

Résultat : **17/17 contrôles réussis**, dont :

- création du site via `POST /api/v1/websites/` → 201 ;
- scan `health` réel accepté (202), terminé `completed`, score 69, 7 `CheckResult`, 8 `ScannerRun`, 7 `Finding` ;
- l'API renvoie le statut réellement persisté (`api=completed db=completed`) ;
- filtre `?status=completed` fonctionnel ;
- activation de la surveillance : `enabled=true` et première vérification planifiée ;
- pause : `enabled=false` **et** `next_scan_at=null` (l'anomalie ci-dessus est bien corrigée sur la pile reconstruite) ;
- isolation multi-tenant : site et scan d'un autre compte → 404 ;
- AKA IA : extérieur → 404 sans appel modèle ; propriétaire → 200 via la passerelle réelle (`qwen/qwen3.8-27b`, < 1 s).

Le planificateur Celery réel a par ailleurs enchaîné une **vérification de surveillance automatique** après l'activation (`Scan completed — 69/100`, « Monitoring scan », visible dans la timeline).

### Parcours navigateur réel (Vite dev server, session authentifiée)

| Étape | Résultat observé |
|---|---|
| Détail du site, surveillance en pause | Bandeau d'en-tête « Monitoring **paused** » + carte « Keep watching appchat.elomaiapp.com » avec explication (fréquence 24 h, quota, pause possible) et bouton « Activate monitoring » — capture `presence-website-monitoring-activation-2026-10-27.png` |
| Clic « Activate monitoring » | Bandeau passe à « active », carte disparaît, toast succès |
| Page Monitoring | Ligne du site avec badge d'état et bouton « Pause monitoring » ; résumé « 1 of 1 websites enabled », « Every 24 hours » ; timeline d'événements réels |
| Clic « Pause monitoring » | Badge « Monitoring off », bouton devient « Activate monitoring », résumé « 0 of 1 websites enabled », « No schedule » |
| Page Alerts (centre de notifications) | Filtres Tous/Critical/Warning/Resolved + alertes réelles issues du scan (en-têtes, e-mail) |
| Console / réseau | Aucune erreur console ; toutes les requêtes API en 200 |

Captures : `docs/audits/screenshots/presence-website-monitoring-activation-2026-10-27.png`, `docs/audits/screenshots/presence-monitoring-toggle-2026-10-27.png`.

### Correctif d'interface complémentaire

`AssetSecurityPanel` gardait sa propre copie de la politique : après activation, le panneau « Automated security » affichait encore « monitoring paused ». `WebsiteDetails` incrémente maintenant `refreshKey` après activation, ce qui rafraîchit les deux vues (vérifié : le texte obsolète a disparu, `Monitoring active` est affiché).

### Tests après ces correctifs

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh monitoring` (après le correctif de course) | **39 tests, OK** |
| `bash scripts/run_backend_tests.sh scans alerts websites notifications` | **285 tests, OK** (446 s) |
| `pnpm exec tsc --noEmit` / `pnpm run build` | OK |
| `docker compose config --quiet`, `manage.py check`, `makemigrations --check --dry-run` | OK, 78 migrations appliquées, aucune en attente |

## 7. Limites et éléments non vérifiés

- **Notification e-mail de bout en bout via Mailpit** : couverte par les tests backend (`locmem`) ; un envoi réel via Mailpit n'a pas été rejoué dans cette session.
- **Suite Playwright du projet** : non rejouée (le parcours a été validé manuellement dans le navigateur ; les specs E2E existantes portent sur l'inscription et le scan public).
- **Compteur `consecutive_failures` sur les données historiques** : il reste à 0 pour les scans passés ; il ne se remplit qu'à partir des prochains scans réels.
- **E-mail de scan incomplet au propriétaire** : la création d'alerte et l'envoi sont testés, mais le rendu final du courriel n'a pas été inspecté visuellement.
- Les scans créés par la recette (site `appchat.elomaiapp.com`, comptes `recipe.*@presence.local`) restent en base **comme données de test locales** ; ils n'ont pas été supprimés et aucun scan historique n'a été modifié.
