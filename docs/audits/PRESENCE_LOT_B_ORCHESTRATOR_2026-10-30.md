# Presence — Lot B : orchestrateur de parcours, admission, verrouillage et quotas atomiques

**Version du lot :** 2026-10-30
**Validation d'exécution :** 2026-11-04
**Périmètre :** backend uniquement — logique d'orchestration des parcours progressifs.
**Statut final :** **VALIDÉ TECHNIQUEMENT** — 1 102 tests verts, concurrence vérifiée sur PostgreSQL, rétrocompatibilité des scans classiques confirmée.

---

## 1. Synthèse exécutive

Le Lot B rend le parcours progressif fonctionnel au niveau backend. Il ajoute :

- un **service d'admission et de cycle de vie** (`JourneyService`) : création, attente de confirmation, avancement, finalisation, annulation ;
- un **verrouillage PostgreSQL** par site puis par parcours (`select_for_update`) qui sérialise deux créations ou deux avancements simultanés ;
- une **admission de quota atomique** : le verrou sur l'organisation est pris avant le comptage, et le scan palier 1 facturé (`quota_charged=True`) est lui-même la réservation ;
- un **claim atomique** `QUEUED → RUNNING` par un seul `UPDATE` conditionnel, exécuté par la tâche Celery avant l'orchestrateur ;
- le **filtrage des étapes et du budget par palier** : palier 1 = testssl seul / 150 s, palier 2 = scénario C / 360 s, scan classique inchangé / 540 s ;
- le **conditionnement de tous les effets de bord classiques** : un scan enfant de parcours ne touche ni le score de santé, ni le monitoring, ni les alertes, ni l'IA.

Aucun endpoint, sérialiseur, URL, migration, vue, worker ou profil Nuclei n'a été créé ou modifié. Aucun déploiement n'a été effectué.

### Résultats vérifiés

| Contrôle | Résultat |
|---|---|
| Suite backend complète (`bash scripts/run_backend_tests.sh`) | **1 102 tests OK**, exit 0, 1 281,045 s |
| Tests dédiés au Lot B | **65 tests OK**, exit 0, 78,690 s |
| Migrations | `makemigrations --check --dry-run` → **No changes detected** |
| Endpoints / sérialiseurs / URLs | aucun diff sur `scans/api`, `views.py`, `serializers.py`, `urls.py` |
| Frontend / Docker / workers / profils Nuclei | aucun diff |
| Scan anti-secrets | aucun secret ; seuls les mots de passe factices de test (`CorrectHorseBattery1!`) apparaissent, comme dans le reste de la suite |

### Rétrocompatibilité

Les scans classiques (`journey_stage=NULL`) conservent :

- leur pipeline d'étapes (`_HEALTH_STEPS`, `_SECURITY_STEPS`, `_FULL_STEPS`, Nikto inclus) ;
- leur budget de 540 s ;
- leur recalcul de score de santé ;
- leurs effets de bord : `detect_alerts`, `report_scan_issue`, conseiller IA, `MonitoringConfig.record_success/failure`.

Le claim atomique s'applique aussi aux scans classiques créés en `QUEUED` (tous les chemins produit le font), mais un scan déjà terminal garde le chemin de ré-entrée historique (finalisation et relance du conseiller IA). Aucun test existant n'a été modifié.

---

## 2. Fichiers créés et modifiés

### 2.1 Fichiers créés

| Fichier | Contenu |
|---|---|
| `SaaS_Web_Application_digitale_presenz_v2/backend/scans/services/exceptions.py` | `JourneyError`, `JourneyConflictError`, `JourneyStateError`, `JourneyExpiredError`, `QuotaExceededError` |
| `SaaS_Web_Application_digitale_presenz_v2/backend/scans/services/journey_service.py` | `JourneyService` et `check_write_permission` |
| `SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_journey_service.py` | 65 tests unitaires, d'intégration et de concurrence |
| `docs/audits/PRESENCE_LOT_B_ORCHESTRATOR_2026-10-30.md` | ce rapport |

### 2.2 Fichiers modifiés

| Fichier | Modification |
|---|---|
| `.../backend/scans/services/orchestrator.py` | `claim_scan()` ; budget palier 1 (150 s) ; score de santé non recalculé pour un scan enfant |
| `.../backend/scans/services/steps_builder.py` | `_JOURNEY_STAGE1_STEPS` (testssl seul) et sélection `journey_stage=1` |
| `.../backend/scans/tasks.py` | claim au démarrage ; `_finalize_scan(update_monitoring=…, update_health=…)` ; délégation `JourneyService.on_stage_completed()` ; aucun effet de bord classique pour un parcours |
| `.../backend/subscriptions/services/quotas.py` | `scans_used_this_month()` filtre `quota_charged=True` |

### 2.3 Fichiers explicitement non modifiés

`scans/models.py`, `scans/migrations/*`, `config/settings/*`, `scanners/implementations/*`, `scans/api/*`, `scans/serializers.py`, `scans/urls.py`, frontend, Docker Compose, Dockerfile, tâches de monitoring, reaper, alertes, scoring, profil Nuclei.

Aucune migration n'a été générée.

---

## 3. Architecture `JourneyService`

### 3.1 Flux complet

```text
create_journey(website, user)
  │  transaction.atomic
  │  1. SELECT Website FOR UPDATE            (verrou d'admission)
  │  2. check_write_permission(owner/admin/analyst)
  │  3. SELECT ScanJourney actif FOR UPDATE → JourneyConflictError
  │  4. SELECT Organization FOR UPDATE → comptage quota → QuotaExceededError
  │  5. INSERT ScanJourney(state=running, current_stage=1)
  │  6. INSERT Scan(stage=1, status=queued, quota_charged=True)
  │  7. transaction.on_commit → run_authenticated_scan.delay(scan.id)
  ▼
Palier 1 exécuté par Celery (claim atomique, testssl, budget 150 s)
  ▼
on_stage_completed(scan.id)
  │  · stage 1 completed/partial → awaiting_confirmation + expires_at = now + 24 h
  │  · stage 1 failed/cancelled → failed
  │  · stage 2 completed → completed ; partial → partial ; failed → failed
  ▼
advance_journey(journey.id, user)
  │  transaction.atomic
  │  1. SELECT Website FOR UPDATE → SELECT Journey FOR UPDATE
  │  2. permission + état awaiting_confirmation + TTL
  │  3. aucun scan classique actif (pending/queued/running)
  │  4. Nuclei disponible (SCANNER_ADVANCED_SECURITY_ENABLED)
  │  5. state=running, current_stage=2, expires_at=NULL
  │  6. INSERT Scan(stage=2, quota_charged=False)
  │  7. transaction.on_commit → run_authenticated_scan.delay(scan.id)
  ▼
Palier 2 exécuté par Celery (nuclei scénario C + gobuster, budget 360 s)
  ▼
on_stage_completed(scan.id) → completed / partial / failed
```

### 3.2 Méthodes

| Méthode | Rôle | Erreurs |
|---|---|---|
| `create_journey(website, requested_by, trigger_source)` | Admission + création du palier 1 | `JourneyConflictError`, `QuotaExceededError`, `PermissionError` |
| `on_stage_completed(scan_id)` | Transition après un scan enfant terminal | aucune (idempotente, retourne le parcours) |
| `advance_journey(journey_id, requested_by)` | Confirmation explicite → palier 2 | `JourneyStateError`, `JourneyExpiredError`, `JourneyConflictError`, `PermissionError` |
| `cancel_journey(journey_id, requested_by)` | Annulation terminale | `JourneyStateError`, `PermissionError` |
| `check_and_reserve_quota(organization)` | Comptage sous verrou d'organisation | `QuotaExceededError` |
| `journey_ttl_hours()` | TTL configurable (`SCAN_JOURNEY_TTL_HOURS`, défaut 24 h) | — |
| `check_write_permission(user, website)` | Rôles owner/admin/analyst ; superuser autorisé | `PermissionError` |

### 3.3 État des scans enfants

| Palier | `scan_type` | Étapes | Budget | `quota_charged` | Déclencheur |
|---|---|---|---:|---|---|
| 1 | `security` | `testssl` | 150 s | `True` | `trigger_source` demandé |
| 2 | `security` | `nuclei` (scénario C) + `gobuster` | 360 s | `False` | `manual` |

`Scan` n'a pas de colonne `requested_by` : l'utilisateur demandeur reste porté par `ScanJourney.requested_by`. Le scan enfant ne porte que son `trigger`.

---

## 4. Verrouillage et atomicité

### 4.1 Ordre de verrouillage constant

| Ordre | Objet | Pris par |
|---|---|---|
| 1 | `Website` | `create_journey`, `advance_journey` |
| 2 | `Organization` | `check_and_reserve_quota` (appelé dans la transaction de création) |
| 3 | `ScanJourney` | `create_journey` (lecture du parcours actif), `advance_journey`, `cancel_journey`, `on_stage_completed` |
| 4 | `Scan` enfant | `cancel_journey`, `on_stage_completed` |

Aucun chemin ne verrouille ces objets dans l'ordre inverse. `on_stage_completed` verrouille le parcours **avant** le scan enfant, comme `cancel_journey`.

### 4.2 Scénarios de concurrence

| Scénario | Comportement obtenu |
|---|---|
| Double clic « lancer un parcours » | Un seul parcours ; le second appel lève `JourneyConflictError`, aucun second scan |
| Deux créations simultanées sur le même site | Verrou `Website` : une réussite, un conflit, 1 parcours / 1 scan |
| Deux créations simultanées, deux sites, quota = 1 | Verrou `Organization` : une réussite, un `QuotaExceededError`, 1 scan facturé |
| Deux avancements simultanés | Verrou `Website` puis `Journey` : un seul palier 2, le second lève `JourneyStateError` |
| Parcours en attente + scan classique | Le monitoring continue ; `advance` refuse en `JourneyConflictError`, le parcours reste `awaiting_confirmation` |
| Deux workers claim le même scan | Un seul `UPDATE` conditionnel réussit ; le second sort silencieusement |
| Claim sur scan `RUNNING`/`CANCELLED`/terminal | `False` |
| Avancement après TTL | `JourneyExpiredError` |
| Avancement sur parcours `completed` | `JourneyStateError` |
| Annulation d'un parcours terminal | `JourneyStateError` |

### 4.3 Preuves de concurrence

Trois classes `TransactionTestCase` exécutent de vrais threads avec des connexions PostgreSQL indépendantes (barrière de départ commune, `connection.close()` en fin de thread) :

| Test | Attendu | Résultat |
|---|---|---|
| `test_two_simultaneous_journeys_on_one_site` | `["conflict", "success"]`, 1 parcours, 1 scan | OK |
| `test_quota_race_across_two_sites_of_one_organization` | `["quota", "success"]`, 1 scan facturé | OK |
| `test_two_simultaneous_advances_create_one_stage_two` | `["state_error", "success"]`, 1 scan palier 2 | OK |
| `test_two_simultaneous_claims_only_one_wins` | `[False, True]`, scan `RUNNING` | OK |

Ces tests utilisent PostgreSQL (le backend de la suite), pas SQLite : `select_for_update()` y est réellement bloquant.

### 4.4 Idempotence des callbacks

`on_stage_completed` est idempotente : si le parcours n'est plus `running` (déjà `awaiting_confirmation`, terminal, expiré ou annulé), elle retourne l'état courant sans le modifier et sans repousser `expires_at`. Un callback de palier 1 arrivé après le passage au palier 2 est ignoré (`journey_stage_mismatch`).

---

## 5. Quotas atomiques

### 5.1 Implémentation

`JourneyService.check_and_reserve_quota(organization)` :

1. `Organization.objects.select_for_update().get(pk=…)` ;
2. plan effectif via `get_effective_plan_for_organization()` (propriétaire payeur, repli Free, même sémantique que l'API) ;
3. `scans_used_this_month(organization=…)` ;
4. `QuotaExceededError` si `used >= plan.max_scans_per_month`.

Le verrou est conservé jusqu'au commit par `create_journey` (`transaction.atomic`). Le compteur n'est pas un champ dénormalisé : le `Scan` palier 1 créé avec `quota_charged=True` **est** la réservation. Il n'existe donc ni double incrément ni compteur faux au changement de mois.

### 5.2 Option A

| Palier | `quota_charged` | Compté par `scans_used_this_month()` |
|---|---|---|
| 1 | `True` | oui |
| 2 | `False` | non |

`scans_used_this_month()` filtre désormais `quota_charged=True`. Les scans existants et classiques ont la valeur par défaut `True` : leur comptage est inchangé. Le comptage du monitoring, de l'API et de la page facturation reste cohérent.

### 5.3 Tests

- quota dépassé → aucun parcours créé ;
- scans `quota_charged=False` → ne consomment pas le quota ;
- palier 1 facturé, palier 2 gratuit, total mensuel = 1 ;
- course de quota sur deux sites d'une même organisation → un seul succès ;
- annulation → pas de remboursement ;
- absence de plan → aucun plafond inventé.

---

## 6. Claim atomique

```python
def claim_scan(scan_id: int) -> bool:
    now = timezone.now()
    updated = Scan.objects.filter(
        id=scan_id,
        status=Scan.Status.QUEUED,
    ).update(
        status=Scan.Status.RUNNING,
        started_at=now,
        updated_at=now,
    )
    return updated == 1
```

- un seul `UPDATE … WHERE status='queued'`, donc atomique au niveau PostgreSQL ;
- `started_at` et `updated_at` sont écrits explicitement (`auto_now` est contourné par `QuerySet.update`) ;
- aucun `select_for_update()` + `save()` : pas d'écrasement d'une transition concurrente par une instance périmée ;
- retourne `False` si le scan est `RUNNING`, terminal ou annulé.

Dans `run_authenticated_scan`, le claim est exécuté avant l'orchestrateur. Un scan déjà terminal conserve le chemin historique (finalisation, relance du conseiller IA) ; un scan `QUEUED` est réclamé exactement une fois. Le gagnant exécute les scanners ; le perdant retourne `{"status": "skipped", "reason": "claim_lost"}` sans créer de `ScannerRun` ni de `Finding`.

Tests : claim `QUEUED → RUNNING` (started_at renseigné), claim sur `RUNNING` → `False`, sur `CANCELLED` → `False`, sur scan absent → `False`, deux threads simultanés → un seul `True`.

---

## 7. Conditionnement des effets de bord

| Effet de bord | Scan classique | Scan enfant de parcours |
|---|---|---|
| Recalcul du score du scan (`recalculate_scan_health`) | oui | **non** — `health_score` reste `NULL` |
| `_record_monitoring_outcome` | oui | **non** |
| `detect_alerts` (findings) | oui si `COMPLETED` | **non** |
| `report_scan_issue` (couverture) | oui si `FAILED`/`PARTIAL` | **non** |
| `generate_scan_recommendations_task` (IA) | oui si `COMPLETED` et flag actif | **non** |
| Notification de findings | via alertes classiques | **non** |
| Passage d'état du parcours | — | `JourneyService.on_stage_completed()` |

Le conditionnement est explicite dans `tasks.py` :

```python
report = _finalize_scan(
    scan_id,
    update_monitoring=not is_journey,
    update_health=not is_journey,
)
if is_journey:
    JourneyService.on_stage_completed(scan_id)
    return …
# chemin classique inchangé : alertes, conseiller, alerte de couverture
```

L'orchestrateur ne recalcule le score que si `scan.journey_id is None`. Un crash de l'orchestrateur marque le scan enfant `FAILED` puis appelle `on_stage_completed` : le parcours échoue au lieu de rester bloqué en `running`.

Tests : un scan enfant `COMPLETED` ne déclenche aucun des trois envois, laisse `health_score=NULL` et ne modifie pas `MonitoringConfig` (3 échecs conservés) ; un scan classique `COMPLETED` déclenche toujours alertes + IA et remet `consecutive_failures` à 0.

---

## 8. Disponibilité de Nuclei

Le palier 2 dépend de Nuclei (`requires_advanced_security = True`). `advance_journey` vérifie `advanced_security_enabled()` **après** le contrôle de conflit de scan classique et **avant** toute création de scan :

- si le flag est actif → palier 2 créé et publié ;
- sinon → `state=failed`, `expires_at=NULL`, aucun scan palier 2, log `journey_stage_unavailable reason=advanced_security_disabled`.

Aucun `COMPLETED` mensonger n'est produit : l'orchestrateur marquerait Nuclei `SKIPPED` et le parcours pourrait paraître complet, ce que l'admission interdit en amont.

Le test correspondant force `SCANNER_ADVANCED_SECURITY_ENABLED=False` et vérifie `state=failed` + absence de scan palier 2.

---

## 9. Permissions

`check_write_permission(user, website)` s'appuie sur la matrice existante `organizations.access` :

| Rôle | Autorisation |
|---|---|
| superuser | oui |
| owner | oui |
| admin | oui |
| analyst | oui |
| viewer | `PermissionError` |
| aucun rôle / hors organisation | `PermissionError` |
| utilisateur absent ou anonyme | `PermissionError` |

Aucun modèle `WebsiteRolePermission` n'existe dans le dépôt : les rôles sont portés par `Membership` (organisation) et `Website.owner` pour les sites historiques sans organisation. Le service fournit la fonction ; le Lot D l'appellera avant `create_journey` (elle est aussi appelée en défense en profondeur dans `create_journey`, `advance_journey` et `cancel_journey`).

---

## 10. Tests unitaires

Fichier : `backend/scans/tests/test_journey_service.py` — **65 tests, 78,690 s, exit 0**.

| Classe | Nb | Objet |
|---|---:|---|
| `JourneyStageProfileTests` | 6 | palier 1 = testssl seul, palier 2 inchangé, pipeline classique inchangé, budgets 150/360/540 |
| `WritePermissionTests` | 6 | owner, analyst, viewer, hors organisation, anonyme, superuser |
| `CreateJourneyTests` | 9 | création, `on_commit`, trigger, conflit, double clic, parcours en attente, parcours terminé, viewer, utilisateur absent |
| `JourneyQuotaTests` | 5 | quota dépassé, scans non facturés, palier 1/2, compteur mensuel, absence de plan |
| `StageCompletionTests` | 12 | stage 1 completed/partial/failed/cancelled, stage 2 completed/partial/failed/cancelled, idempotence, scan classique, scan non terminal, callback périmé |
| `AdvanceJourneyTests` | 10 | avancement, publication après commit, état incorrect, expiration, conflit classique, scan classique terminé, viewer, Nuclei absent, double avancement, parcours inconnu |
| `CancelJourneyTests` | 5 | attente, exécution, parcours terminal, viewer, quota non remboursé |
| `ClaimScanTests` | 4 | claim réussi, `RUNNING`, `CANCELLED`, scan absent |
| `JourneyTaskSideEffectTests` | 4 | aucun effet de bord palier 1/palier 2, effets classiques conservés, claim avant orchestration |
| `ConcurrentJourneyCreationTests` | 2 | même site, course de quota inter-sites |
| `ConcurrentAdvanceTests` | 1 | deux avancements simultanés |
| `ConcurrentClaimTests` | 1 | deux claims simultanés |

---

## 11. Non-régression

Commande exécutée depuis la racine du dépôt :

```bash
bash scripts/run_backend_tests.sh
```

Résultat :

```text
Ran 1102 tests in 1281.045s

OK
```

- 1 037 tests existants (1 016 + 21 du Lot C2) : **tous verts** ;
- 65 nouveaux tests : **tous verts** ;
- aucun test existant modifié ;
- exit code : **0**.

`makemigrations --check --dry-run` : `No changes detected`.

Le diff ne touche ni `scans/api`, ni `views.py`, ni `serializers.py`, ni `urls.py`, ni le frontend, ni Docker, ni les profils Nuclei, ni les migrations.

---

## 12. Limites connues

1. **Admission partagée avec les scans classiques non branchée.** `create_journey` verrouille le site, mais `trigger_scan` (`websites/views.py`), `run_due_monitors` (`monitoring/tasks.py`) et `public_checker` ne prennent pas ce verrou. Un scan classique peut donc démarrer pendant l'exécution du palier 1. `advance_journey`, lui, refuse un palier 2 si un scan classique est actif. Le service d'admission commun décrit au §3.1 du rapport de conception reste à brancher dans un lot dédié ; le faire ici aurait imposé de modifier le monitoring planifié et les vues, hors périmètre du Lot B.
2. **Pas de réglage `base.py` pour le budget du palier 1.** `_budget_settings_for_scan` lit `SCAN_JOURNEY_STAGE1_TIME_BUDGET_SECONDS` avec un défaut de 150 s ; la variable n'a pas été ajoutée à `base.py` (fichier explicitement hors périmètre). Le timeout testssl reste celui de `SCANNER_CONFIG` (120 s), ce qui laisse 30 s de marge dans l'enveloppe de 150 s. Un opérateur ne peut pas surcharger le budget par environnement tant que la variable n'est pas déclarée.
3. **Expiration non persistée par `advance_journey`.** Le dépassement du TTL lève `JourneyExpiredError` sans écrire `state=expired` (l'exception annulerait la transaction). La transition `expired` appartient au reaper du Lot E, conformément au rapport de conception (§4.2).
4. **Reprise après worker mort non automatique.** Si un worker meurt pendant un palier, le reaper des scans marque le scan `FAILED`, mais aucun callback ne met le parcours à jour ; il reste `running` jusqu'à la réconciliation du reaper de parcours (Lot E). Aucun parcours n'est supprimé et aucun scan classique n'est affecté.
5. **Pas de champ de motif sur `ScanJourney`.** L'indisponibilité de Nuclei est journalisée (`journey_stage_unavailable`) et le parcours passe à `failed`, mais le motif n'est pas persisté en base : le schéma du Lot A ne prévoit pas de colonne `failure_message` sur `ScanJourney`.
6. **Double clic = conflit, pas 200 idempotent.** `create_journey` lève `JourneyConflictError` sur un parcours actif, conformément au contrat `Raises` du Lot B et au test de concurrence attendu (`["conflict","success"]`). Le Lot D pourra mapper ce cas en 409, ou en 200 avec le parcours existant s'il le souhaite, sans changer le service.
7. **Trigger du palier 2 fixé à `manual`.** `ScanJourney` ne stocke pas la source de déclenchement ; seul le palier 1 reçoit le `trigger_source` demandé. Le palier 2 est toujours `Scan.Trigger.MANUAL`.
8. **Pas de contrainte globale d'unicité des scans actifs.** Le verrou d'admission du parcours est applicatif (verrou de ligne), pas une contrainte PostgreSQL globale ; les chemins classiques conservent leur contrôle 409 historique.

---

## 13. Prochaines étapes

| Lot | Contenu | Dépendance |
|---|---|---|
| Lot D | API du parcours : `POST /scan-journeys/`, `GET /{id}/`, `POST /{id}/advance/`, `POST /{id}/cancel/`, mapping des exceptions (`409`, `410`, `403`, `429`) | Lot B |
| Lot E | `reap_stale_journeys` : expiration, réconciliation `running` sans scan actif, métriques `journeys` | Lot B |
| Lot C3 | Retrait de Nikto du palier 2 (le palier 1 ne l'utilise déjà pas) | test end-to-end |
| Lot F | Frontend du parcours (bouton « Continuer », expiration, état `partial`) | Lot D |
| Intégration | Scan complet via Celery sur cible publique explicitement autorisée (le validateur SSRF refuse les cibles RFC1918 du laboratoire) | Lot B + C2 |

---

## 14. Statut final

**VALIDÉ TECHNIQUEMENT** :

- 1 102 tests verts, exit 0 ;
- concurrence vérifiée sur PostgreSQL (création, quota, avancement, claim) ;
- rétrocompatibilité confirmée par la suite complète et par les tests d'effets de bord ;
- aucune migration, aucun endpoint, aucun déploiement.

**À VÉRIFIER MANUELLEMENT** :

- exécution end-to-end d'un parcours complet via Celery contre une cible publique autorisée (les tests du Lot B mockent les scanners et le validateur SSRF refuse les cibles privées du laboratoire) ;
- comportement du monitoring planifié pendant un parcours en attente, à observer sur une instance réelle (le service ne modifie pas le monitoring).

**BLOQUÉ** : aucun.

**ÉCHEC** : aucun.
