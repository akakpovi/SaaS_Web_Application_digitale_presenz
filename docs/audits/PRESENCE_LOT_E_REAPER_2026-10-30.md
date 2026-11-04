# Presence — Lot E : reaper des parcours, métriques et alertes de couverture

**Version du lot :** 2026-10-30
**Validation d'exécution :** 2026-11-04
**Périmètre :** maintenance automatique des parcours progressifs — aucune modification du schéma, de `JourneyService`, de l'API, du pipeline ni du reaper des scans.
**Statut final :** **VALIDÉ TECHNIQUEMENT** — 36 tests dédiés verts, suite backend complète verte, aucune migration.

---

## 1. Synthèse exécutive

Le Lot E ferme les trois trous de cycle de vie laissés par les lots précédents :

1. un parcours en `awaiting_confirmation` dont l'utilisateur ne confirme jamais reste actif et bloque son site via `unique_active_journey_per_website` ;
2. un parcours en `running` dont le scan enfant est devenu terminal mais dont le callback Celery s'est perdu reste `running` indéfiniment ;
3. un parcours en `running` dont le scan enfant a disparu (ou n'a jamais été créé) reste `running` pour toujours.

Trois passes idempotentes corrigent ces situations, une tâche Celery les exécute toutes les 5 minutes, et les compteurs/jauges Redis ainsi que les alertes de couverture rendent l'ensemble observable.

### Résultats vérifiés

| Contrôle | Résultat |
|---|---|
| Tests dédiés Lot E | **36 tests OK**, 39,566 s, exit 0 |
| Suite backend complète | **1 182 tests OK**, 1 496,070 s, exit 0 |
| `manage.py check` | **System check identified no issues (0 silenced)** |
| Migrations | `makemigrations --check --dry-run` → **No changes detected** |
| `JourneyService` / API / orchestrateur / pipeline | aucun diff |
| `reap_stale_scans` existant | aucun diff (ajout d'une tâche distincte uniquement) |
| Schéma / migrations | aucun diff |
| Frontend / Docker Compose | aucun diff |

---

## 2. Fichiers créés et modifiés

### 2.1 Fichiers créés

| Fichier | Contenu |
|---|---|
| `backend/scans/services/journey_reaper.py` | `reap_expired_journeys`, `reconcile_stale_journeys`, `reap_orphan_journeys`, `journey_gauges`, `reap_journeys` |
| `backend/scans/services/journey_coverage.py` | alertes de couverture, déduplication, vérification du tick précédent |
| `backend/scans/tests/test_journey_reaper.py` | 36 tests (expiration, réconciliation, orphelins, tâche, métriques, alertes) |
| `docs/audits/PRESENCE_LOT_E_REAPER_2026-10-30.md` | ce rapport |

### 2.2 Fichiers modifiés

| Fichier | Modification |
|---|---|
| `backend/scans/tasks.py` | ajout de la tâche `scans.tasks.reap_stale_journeys` (le reaper des scans est inchangé) |
| `backend/config/settings/base.py` | entrée beat `reap-stale-journeys` toutes les 300 s + quatre seuils opérationnels |
| `backend/core/reaper_metrics.py` | `kind="journeys"`, compteurs détaillés, jauges, exposition dans `read_reaper_metrics` |
| `backend/core/management/commands/reaper_status.py` | aide mise à jour pour mentionner les parcours |

### 2.3 Fichiers explicitement non modifiés

`ScanJourney`, `Scan`, `CheckResult`, `Finding`, `ScannerRun`, migrations, `JourneyService` et ses exceptions, `orchestrator.py`, pipelines de scan, `reap_stale_scans`, tâches Celery existantes, API du Lot D, profils/steps Nuclei, frontend, alertes de scan (`report_scan_issue`), scoring, monitoring.

---

## 3. Architecture du reaper

### 3.1 Flux

```text
Celery beat (toutes les 300 s)
        │
        ▼
scans.tasks.reap_stale_journeys
        │
        ▼
scans.services.journey_reaper.reap_journeys()
        │
        ├─ 1. reap_expired_journeys()       awaiting_confirmation + expires_at <= now → expired
        ├─ 2. reconcile_stale_journeys()    running + scan courant terminal → on_stage_completed()
        ├─ 3. reap_orphan_journeys()        running > TTL sans scan actif → failed
        ├─ 4. check_journey_coverage()      alertes stuck / accumulation / reaper inactif
        ├─ 5. journey_gauges()              comptages active/awaiting
        └─ 6. record_journey_reaper_tick()  compteurs + jauges Redis
```

L'ordre est volontaire : les réparations précèdent la couverture, afin qu'un parcours réparé pendant le tick ne déclenche pas une alerte déjà obsolète. La vérification d'inactivité lit le tick **précédent**, avant l'écriture du tick courant.

### 3.2 `reap_expired_journeys`

- cible : `state="awaiting_confirmation"` et `expires_at <= now` ;
- action : `UPDATE state="expired", expires_at=now, updated_at=now` avec condition d'état dans le `WHERE` ;
- idempotence : un parcours déjà `expired`, `running`, `completed`, etc. n'est jamais candidat ; un `advance` concurrent fait échouer l'`UPDATE` conditionnel ;
- trace : un log INFO par parcours avec `journey_id`, `previous_state`, `new_state`, `reason=confirmation_window_elapsed` et l'horodatage ;
- borne : 500 parcours par passe.

`expires_at` est écrasé par l'instant d'expiration, conformément au cahier des charges. L'échéance d'origine reste dans les logs ; l'API expose donc, pour un parcours expiré, l'instant où le reaper l'a fermé.

### 3.3 `reconcile_stale_journeys`

- cible : `state="running"`, scan enfant du `current_stage` avec statut terminal (`completed`, `partial`, `failed`, `cancelled`) ;
- action : appel de `JourneyService.on_stage_completed(scan_id)`, jamais une écriture directe ;
- conséquences normales du service : palier 1 réussi → `awaiting_confirmation` + nouvelle échéance ; palier 1 échoué → `failed` ; palier 2 → `completed`/`partial`/`failed` ;
- scan encore `pending`/`queued`/`running` : aucune action, le reaper des scans possède ce cas ;
- aucun scan enfant : log WARNING `journey_reaper_no_child`, aucune modification (inspection manuelle) ;
- idempotence : le service relit le parcours sous verrou et ignore un parcours qui n'est plus `running` ; une deuxième passe retourne 0.

### 3.4 `reap_orphan_journeys`

- cible : `state="running"`, `created_at <= now - SCAN_JOURNEY_TTL_HOURS` ;
- action : sous `transaction.atomic()` + `select_for_update()` sur le parcours, re-vérification qu'aucun scan du stage courant n'est `pending`/`queued`/`running`, puis passage à `failed` avec `expires_at=None` ;
- un scan actif, même ancien, protège le parcours : le reaper des scans fermera le scan, puis la passe de réconciliation fermera le parcours au tick suivant ;
- trace : un log WARNING par parcours avec `journey_id`, états, `created_at` et TTL ;
- borne : 500 parcours par passe.

### 3.5 `reap_journeys`

Retourne un dictionnaire exploitable par Celery et les tests :

```json
{
  "expired": 2,
  "reconciled": 1,
  "orphans": 0,
  "total": 3,
  "active": 4,
  "awaiting": 2,
  "coverage_alerts": 1,
  "reaper_inactive": false
}
```

Une panne de cache lors de l'écriture des métriques est attrapée et loguée en WARNING : elle ne bloque jamais le balayage PostgreSQL.

---

## 4. Tâche Celery et configuration beat

### 4.1 Tâche

```python
@shared_task(name="scans.tasks.reap_stale_journeys")
def reap_stale_journeys() -> dict:
    from scans.services.journey_reaper import reap_journeys
    return reap_journeys()
```

Le nom est distinct de `scans.tasks.reap_stale_scans`. Aucune tâche existante n'a été modifiée.

### 4.2 Beat

Ajout dans `CELERY_BEAT_SCHEDULE.update(...)` de `config/settings/base.py` :

```python
"reap-stale-journeys": {
    "task": "scans.tasks.reap_stale_journeys",
    "schedule": 300.0,
},
```

Les entrées existantes (`reap-stale-ai-runs`, `reap-stale-scans`, etc.) sont inchangées.

---

## 5. Métriques Redis

Extension du module existant `core/reaper_metrics.py`, pas d'infrastructure nouvelle.

| Clé Redis | Type | Contenu |
|---|---|---|
| `reaper:journeys_total` | compteur | total des parcours fermés par le reaper (expirés + réconciliés + orphelins) |
| `reaper:journeys_expired_total` | compteur | parcours expirés |
| `reaper:journeys_reconciled_total` | compteur | parcours réconciliés via `on_stage_completed` |
| `reaper:journeys_orphans_total` | compteur | parcours orphelins passés à `failed` |
| `reaper:journeys_active_count` | jauge | parcours `running` + `awaiting_confirmation` |
| `reaper:journeys_awaiting_count` | jauge | parcours `awaiting_confirmation` |
| `reaper:journeys_last_tick` | horodatage | dernier tick du reaper des parcours |
| `reaper:last_tick` | horodatage | dernier tick, toutes catégories confondues |

`record_reaper_tick(kind="journeys")` accepte désormais la troisième catégorie ; `record_journey_reaper_tick(...)` ajoute les compteurs détaillés et les jauges. `read_reaper_metrics()` expose les clés `journeys_*`, donc `python manage.py reaper_status` les affiche sans autre modification.

Toutes les clés sont préfixées `reaper:journeys_` : aucune collision avec `reaper:ai_*` ou `reaper:scans_*`.

---

## 6. Alertes de couverture

### 6.1 Pourquoi un module dédié

`alerts.tasks.report_scan_issue(scan_id)` exige un `Scan` : un parcours en attente n'a pas de scan actif, et une inactivité globale n'a aucun site. Étendre cette tâche aurait soit créé un faux scan, soit cassé sa signature. `scans/services/journey_coverage.py` crée donc directement les alertes de parcours en réutilisant :

- la table `Alert` et le type `scan_failed` (aucun nouveau type, aucune migration) ;
- la préférence `scan_failed_enabled` ;
- les `MuteWindow` de l'utilisateur et du site ;
- `notifications.dispatcher.dispatch_alert`.

Les alertes de scan classiques continuent de passer par `report_scan_issue`, inchangé.

### 6.2 Conditions

| Alerte | Condition | Sévérité | Destinataire |
|---|---|---|---|
| `journey_stuck_awaiting` | `awaiting_confirmation` et `updated_at` > 12 h (moitié du TTL) | WARNING | propriétaire du site |
| `journey_stuck_running` | `running` et `updated_at` > 60 min sans progression | WARNING | propriétaire du site |
| `journey_accumulation` | plus de 3 parcours `awaiting_confirmation` sur un même site | WARNING | propriétaire du site |
| `journey_reaper_inactive` | dernier tick `journeys_last_tick` > 15 min | CRITICAL | logs + métrique (pas de ligne `Alert`) |

Les trois premières créent une alerte `scan_failed` avec `scan=None` et les métadonnées :

```json
{
  "kind": "journeys",
  "issue": "journey_stuck_awaiting",
  "journey_id": 42,
  "state": "awaiting_confirmation",
  "stage": 1
}
```

### 6.3 Déduplication

Une alerte déjà `FIRING` pour le même couple `(site, issue, journey_id)` empêche la création d'une doublon à chaque tick. L'accumulation se déduplique au niveau du site (`journey_id` ignoré), car le parcours représentatif peut changer.

### 6.4 Inactivité du reaper

`Alert` exige un `user` et un `website` : une panne globale de beat n'a ni l'un ni l'autre. La condition est donc un log **CRITICAL** `journey_reaper_inactive` et le booléen `reaper_inactive` dans le résultat de la tâche. Un moniteur externe peut surveiller `reaper:journeys_last_tick`. Le contrôle lit le tick précédent : lors d'une reprise après une panne, la première exécution signale donc bien l'inactivité ; un beat totalement mort ne peut pas s'alerter lui-même (voir §10).

### 6.5 Seuils configurables

Ajoutés dans `config/settings/base.py` :

```python
SCAN_JOURNEY_STUCK_AWAITING_HOURS = 12
SCAN_JOURNEY_STUCK_RUNNING_MINUTES = 60
SCAN_JOURNEY_REAPER_INACTIVE_MINUTES = 15
SCAN_JOURNEY_ACCUMULATION_THRESHOLD = 3
```

Le code garde des valeurs par défaut sûres si un déploiement ne les définit pas.

---

## 7. Tests

Fichier : `backend/scans/tests/test_journey_reaper.py` — **36 tests, 39,566 s, exit 0**.

| Classe | Nb | Couverture |
|---|---:|---|
| `JourneyExpiryTests` | 6 | expiration due, échéance future, déjà expiré, running avec échéance passée, completed, lot mixte 3+2 |
| `JourneyReconciliationTests` | 8 | échec palier 1, succès palier 1 → attente, completed/partial palier 2, scan running/queued non réconcilié, scan absent → WARNING, idempotence |
| `JourneyOrphanTests` | 4 | orphelin ancien sans scan, récent intact, ancien avec scan actif intact, ancien avec scan terminal → failed |
| `FullJourneyReaperTests` | 3 | sweep complet + métriques, second sweep sans effet, jauges active/awaiting |
| `ReapStaleJourneysTaskTests` | 1 | exécution de la tâche Celery et résultat |
| `BeatScheduleTests` | 1 | entrée beat à 300 s |
| `JourneyReaperMetricsTests` | 4 | `kind="journeys"`, rejet d'un kind inconnu, compteurs détaillés + jauges, accumulation entre ticks |
| `JourneyCoverageTests` | 9 | alerte stuck awaiting/running, seuil, déduplication, préférence désactivée, mute window, inactivité CRITICAL, absence de tick |

Les tests utilisent la base PostgreSQL de test et le cache locmem ; aucun broker Celery n'est nécessaire. La tâche est exécutée avec `.apply()`.

### 7.1 Cas non couverts par les tests dédiés

- concurrence réelle entre deux reapers (les verrous et l'`UPDATE` conditionnel sont couverts par la logique et par les tests de concurrence du Lot B) ;
- panne Redis réelle (le chemin défensif est présent mais non exercé) ;
- accumulation réelle de plusieurs parcours actifs sur un même site, impossible sous la contrainte `unique_active_journey_per_website` (testée avec un seuil 0) ;
- résolution automatique des alertes après réparation.

---

## 8. Non-régression

Commande exécutée depuis la racine du dépôt :

```bash
bash scripts/run_backend_tests.sh
```

Résultat :

```text
Ran 1182 tests in 1496.070s

OK
```

- 1 146 tests existants : **tous verts** ;
- 36 nouveaux tests Lot E : **tous verts** ;
- exit code : **0**.

Le reaper des scans (`reap_stale_scans`) n'a pas été modifié : le diff de `scans/tasks.py` ne contient que l'ajout de la nouvelle tâche. Les alertes de scan (`report_scan_issue`), l'API du Lot D, `JourneyService` et les migrations sont inchangés.

---

## 9. Scénarios de défaillance couverts

| Scénario | Comportement attendu | Test |
|---|---|---|
| Utilisateur ne confirme jamais | expiration à l'échéance, site libéré | `JourneyExpiryTests` |
| Worker mort après un scan terminal | réconciliation via `on_stage_completed` | `JourneyReconciliationTests` |
| Scan enfant supprimé | parcours `running` ancien → `failed` | `JourneyOrphanTests` |
| Worker encore lent | scan `queued`/`running` non touché | `JourneyReconciliationTests` |
| Reaper exécuté deux fois | aucun double effet | tests d'idempotence |
| Site bloqué > 12 h | alerte WARNING au propriétaire | `JourneyCoverageTests` |
| Beat en retard > 15 min | log CRITICAL au tick suivant | `JourneyCoverageTests` |
| Panne Redis | le balayage continue, WARNING logué | chemin défensif (non testé) |

---

## 10. Limites connues

1. **Accumulation impossible en fonctionnement normal.** `unique_active_journey_per_website` autorise au plus un parcours actif par site, donc le compteur `awaiting_confirmation` par site ne peut pas dépasser 1. L'alerte `journey_accumulation` reste implémentée comme garde d'invariant (seuil configurable, testé avec 0) ; elle ne se déclenchera que si la contrainte est retirée ou contournée.
2. **Un beat totalement mort ne peut pas s'alerter lui-même.** La vérification d'inactivité s'exécute dans le reaper : elle détecte un retard lors de la reprise, pas une absence prolongée. La supervision externe doit surveiller `reaper:journeys_last_tick` ou l'absence de la tâche.
3. **Les alertes ne se résolvent pas automatiquement.** Une alerte `journey_stuck_*` reste `FIRING` après expiration ou réconciliation ; elle doit être acquittée/résolue manuellement. Aucun mécanisme de résolution n'a été ajouté, pour ne pas modifier la sémantique des alertes existantes.
4. **`expires_at` est écrasé à l'expiration.** Le cahier des charges demande `expires_at=now()` ; l'échéance d'origine n'est plus lisible dans la ligne, seulement dans les logs. Les parcours orphelins, eux, passent à `expires_at=None`.
5. **Dispatch synchrone des alertes.** `check_journey_coverage` appelle `dispatch_alert` dans la tâche Celery (bornée à 200 alertes par passe). Une panne d'un fournisseur est attrapée par le dispatcher, mais peut ralentir le tick.
6. **TTL des orphelins basé sur `created_at`.** Un parcours légitime de plus de 24 h serait fermé ; les budgets de palier (150 s / 360 s) rendent ce cas théorique.
7. **Pas de résolution ni de réouverture.** Une alerte levée pour un parcours qui se répare reste visible ; c'est cohérent avec les alertes de couverture existantes, qui ne se résolvent que sur un scan complet.
8. **Pas de test de concurrence réel entre deux reapers.** L'atomicité repose sur les `UPDATE` conditionnels et les verrous du service, déjà couverts par les tests de concurrence du Lot B.

---

## 11. Prochaines étapes

| Lot | Contenu | Dépendance |
|---|---|---|
| Test end-to-end | parcours complet API + Celery + reaper sur cible publique autorisée | Lots B + C2 + D + E |
| Lot F | frontend du parcours (Continuer, compte à rebours, états terminal) | Lot D |
| Maintenance | résolution automatique des alertes de parcours, supervision de `journeys_last_tick` | Lot E |
| Lot C3 | retrait de Nikto du palier 2 | test end-to-end |

---

## 12. Statut final

**VALIDÉ TECHNIQUEMENT** :

- 36 tests dédiés verts, exit 0 ;
- suite backend complète verte (voir §8) ;
- reaper idempotent, atomique et non interférent ;
- métriques Redis disponibles via `reaper_status` ;
- alertes de couverture créées, dédupliquées et respectueuses des préférences/mutes ;
- aucune migration, aucun service métier, aucune API modifiée.

**À VÉRIFIER MANUELLEMENT** :

- exécution de `python manage.py reaper_status` sur un environnement avec Redis réel après plusieurs ticks ;
- comportement d'un beat arrêté puis redémarré (log CRITICAL attendu au premier tick de reprise) ;
- rendu des alertes de parcours dans l'interface existante.

**BLOQUÉ :** aucun.

**ÉCHEC :** aucun.
