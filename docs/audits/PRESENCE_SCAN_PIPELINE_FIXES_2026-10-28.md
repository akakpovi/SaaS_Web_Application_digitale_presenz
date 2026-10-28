# Presence — Correctifs de robustesse du pipeline de scan

**Date :** 2026-10-28 (UTC)
**Dépôt :** `~/Schreibtisch/SaaS_Web_Application_digitale_presenz`
**Rapport précédent :** `docs/audits/PRESENCE_SCAN_PIPELINE_ROBUSTNESS_2026-10-28.md`
**Périmètre :** les deux défaillances bloquantes identifiées dans le rapport précédent, plus les deux points annexes (gobuster, libellé Celery). Aucun commit, aucun déploiement, aucune modification Nginx, URL ou sitemap.

---

## 1. Synthèse des statuts

| Élément | Statut | Preuve |
|---|---|---|
| Correctif 1 — clé AKA invalide détectée et refusée | **VALIDÉ TECHNIQUEMENT** | 4 probes réelles `check_aka_key` (valide/invalide/absente/valide) + run IA réel `failed/invalid_api_key`, 0 recommandation IA |
| Correctif 1 — arrêt du fallback entre modèles sur clé invalide | **VALIDÉ TECHNIQUEMENT** | test unitaire + test API chat : 1 seul appel provider, 503 `ai_invalid_credentials` |
| Correctif 2 — reprise automatique des runs IA bloqués | **VALIDÉ TECHNIQUEMENT** | run backdaté 30 min, reaped par beat à 16:58:09, sans dispatch manuel |
| Correctif 2 — reprise automatique des scans bloqués | **VALIDÉ TECHNIQUEMENT** | scan 56 backdaté 20 min, reaped à 16:58:10, alerte de couverture créée |
| Correctif 2 — pas de reap d'un scan réellement en cours | **VALIDÉ TECHNIQUEMENT** | tick du reaper à 17:08:10 : `reaped=0` alors que le scan 58 tournait (17:01:35 → 17:10:36) |
| Non-régression — scan de santé | **VALIDÉ TECHNIQUEMENT** | scan 57 : `completed`, score 69, 7 CheckResults, 8 runs, 2 s |
| Non-régression — scan full | **LIMITE DOCUMENTÉE** | scan 58 : `partial` en 541 s ; `testssl` timeout 90 s et `nikto` maxtime 100 s ; testssl autonome OK en 56 s |
| Annexe — gobuster `exit 1` | **QUALIFIÉ (non corrigé)** | reproduction réelle : refus soft-404 du serveur, pas « aucun répertoire » |
| Annexe — libellé `failed_quota_exhausted` | **CORRIGÉ** | `failed_quota_exhausted` / `failed_configuration` / `failed_upstream_error` selon la cause |

**Conclusion de lot :** les deux défaillances bloquantes sont corrigées et prouvées en conditions réelles. Le pipeline **n'est pas déclaré « prêt pour gel en production »** dans ce rapport : le scan full reste `partial` sur cette cible pour des raisons de budget d'outils, et le comportement gobuster sur une cible SPA reste une limite connue.

---

## 2. Correctif 1 — validation réelle de la clé AKA/OmniRoute

### 2.1 Cause

La passerelle ne renvoie pas `401` pour une clé absente ou invalide : elle sert la requête en **mode invité** avec `200`, un quota de 3 requêtes/jour, puis `429 guest_quota_exceeded`. Le client traitait ce `200` comme un succès authentifié.

### 2.2 Implémentation

- `advisory/services/aka_client.py`
  - nouvelle exception `AkaAuthenticationError` (sous-classe de `AkaConfigurationError`, donc **non retryable**) ;
  - `AkaConfig.guest_mode_header = "x-ratelimit-limit"` ;
  - détection sur toute réponse : présence de l'en-tête invité, ou code `guest_quota_exceeded` ;
  - rejet explicite, y compris sur un `200`, avec log `aka_ai_invalid_credentials` (sans clé ni corps de réponse).
- `advisory/services/factory.py`
  - marqueur de cooldown partagé `advisory:aka_credentials_invalid` (15 min par défaut), pour éviter que chaque scan consomme une requête invitée ;
  - helpers `mark_aka_credentials_invalid`, `aka_credentials_marked_invalid`, `clear_aka_credentials_invalid`.
- `advisory/services/advisor.py`
  - si le marqueur est présent : run marqué `failed/invalid_api_key` **sans appel réseau** ;
  - sur `AkaAuthenticationError` : arrêt immédiat du fallback entre modèles (une seule clé), marquage du cache.
- `advisory/services/security_advisor.py`
  - même arrêt du fallback et même marquage pour le chat ; réponse API `503 ai_invalid_credentials`.
- `advisory/management/commands/check_aka_key.py`
  - commande de diagnostic : `0` si l'appel est authentifié, `1` si la passerelle répond en invité ou si la clé manque.
- `advisory/tasks.py`
  - tâche périodique `verify_aka_credentials` (toutes les 6 h) : alerte ERROR si invité, efface le cooldown si OK.

### 2.3 Preuves réelles — 4 exécutions de `check_aka_key`

Commande exécutée avec le code monté dans le conteneur `web`, contre la passerelle réelle :

```text
=========== 1. VALID KEY ===========
AKA credentials OK — authenticated call succeeded (model=groq/qwen/qwen3.8-27b, latency=398 ms)
EXIT=0
=========== 2. INVALID KEY ===========
{"asctime": "2026-10-28 16:43:29,493", "levelname": "ERROR", "name": "advisory.services.aka_client", "message": "aka_ai_invalid_credentials status=429 guest_limit=3 detail=guest_quota_exceeded"}
CommandError: AKA key is NOT authenticated: the gateway answered in guest mode (HTTP 429). The advisor will refuse to serve AI until AKA_AI_API_KEY is fixed.
EXIT=1
=========== 3. ABSENT KEY ===========
CommandError: AKA client cannot be built: ImproperlyConfigured
EXIT=1
=========== 4. VALID KEY AGAIN (clears cooldown) ===========
AKA credentials OK — authenticated call succeeded (model=groq/qwen/qwen3.8-27b, latency=320 ms)
EXIT=0
```

Le cas `429` est utilisé pour la clé invalide car le quota invité de l'adresse réseau avait déjà été consommé par les probes de diagnostic. Le chemin `200` invité est couvert par les tests unitaires et par la capture brute suivante, réalisée avant épuisement du quota :

```text
INVALID HTTP=200
x-ratelimit-limit: 3
x-ratelimit-remaining: 2
{"id":"chatcmpl-f5e315c89e344f13a41051e7",...,"content":"pong",...,"usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"cached":true}}

ABSENT HTTP=200
x-ratelimit-limit: 3
x-ratelimit-remaining: 1
```

Réponse authentifiée correspondante :

```text
HTTP=200 time=0.449109s
headers filtrés : content-type: application/json ; server: cloudflare
{"id":"chatcmpl-baa1ff14f9664749b563044c",...,"model":"qwen/qwen3.8-27b",...,"usage":{"prompt_tokens":19,"completion_tokens":2,"total_tokens":21}}
```

### 2.4 Preuve réelle — refus de servir l'IA

Exécution réelle de `generate_recommendations_for_scan(55)` avec `AKA_AI_API_KEY` invalide :

```text
{"levelname": "ERROR", "name": "advisory.services.aka_client", "message": "aka_ai_invalid_credentials status=429 guest_limit=3 detail=guest_quota_exceeded"}
{"levelname": "ERROR", "name": "advisory.services.advisor", "message": "ai_advisor_credentials_invalid scan=55 model=groq/qwen/qwen3.8-27b status=429"}
run_status=failed error_code=invalid_api_key used_fallback=True should_retry=False
ai_recommendations=0 fallback_recommendations=12
run_attempts=1 model_used=''
EXIT=0
```

Après ce test, une exécution `check_aka_key` avec la clé valide a effacé le cooldown (`EXIT=0`).

### 2.5 Preuve réelle — sonde périodique

```text
$ docker compose exec -T celery-worker celery -A config call advisory.tasks.verify_aka_credentials
f3921c75-7a87-4e9e-97a5-ba94ca86826f
[2026-10-28 17:15:10,550: INFO/ForkPoolWorker-2] aka_ai_credentials_ok model=qwen/qwen3.8-27b
```

---

## 3. Correctif 2 — reprise automatique après crash/blocage

### 3.1 Implémentation

- `advisory/tasks.py` : `reap_stale_ai_runs`
  - cible les runs `running`/`pending` dont `updated_at` dépasse `AI_ADVISOR_STALE_RUN_SECONDS` (600 s par défaut) ;
  - mise à jour conditionnelle (`status` + `updated_at` encore périmés) pour ne jamais écraser un run qui vient de progresser ;
  - `status=failed`, `error_code=stale_run_reaped`, `completed_at`, log `ERROR ai_advisor_run_reaped` avec `run_id`, `scan_id`, `attempts`, `idle_s`.
- `scans/tasks.py` : `reap_stale_scans`
  - cible les scans `pending`/`queued`/`running` sans mise à jour depuis le seuil (900 s par défaut, plancher 300 s) ;
  - verrou de ligne + re-vérification avant `transition_to(FAILED)` ;
  - `failure_message` explicite, `failed_at`, mise à jour du suivi de monitoring et **alerte de couverture** via `report_scan_issue`.
- `config/settings/base.py`
  - `AI_ADVISOR_STALE_RUN_SECONDS=600`
  - `SCAN_REAP_RUNNING_AFTER_SECONDS=900`
  - `SCAN_REAP_QUEUED_AFTER_SECONDS=900`
  - `AKA_AI_AUTH_FAILURE_COOLDOWN=900`
  - beat : `reap-stale-ai-runs` et `reap-stale-scans` toutes les 300 s ; `verify-aka-credentials` toutes les 6 h.
- `.env.example` : les quatre nouveaux réglages sont documentés.

Justification des seuils : le `time_limit` Celery des scans est de 600 s ; 900 s laisse 5 min de marge. Le reaper ne peut donc pas tuer un scan encore autorisé à tourner. Les tests vérifient le plancher de 300 s.

Délai maximal de détection : seuil + période de beat, soit environ **15 min** pour un run IA (10 + 5) et **20 min** pour un scan (15 + 5).

### 3.2 Preuve réelle — run IA et scan bloqués

Lignes de test créées le 2026-10-28 à 16:46:28 UTC :

```text
SCAN_ID=56 WEBSITE_ID=37 RUN_ID=3327f441-5781-48be-ba57-4bbfba9786db ALERTS_BEFORE=0
```

Le run IA a été backdaté de 30 min, le scan de 20 min (simulation d'un crash survenu avant le redémarrage). Redémarrage **uniquement** de `celery-beat` et `celery-worker` à `16:52:54Z`, puis attente sans aucun dispatch manuel.

```text
t+4s run=running/ scan=running
t+13s run=running/ scan=running
t+21s run=failed/stale_run_reaped scan=failed
REAPED_AFTER_THIS_POLL=21s
```

État final en base :

```text
                  id                  | status |    error_code    | attempts |         completed_at
--------------------------------------+--------+------------------+----------+-------------------------------
 3327f441-5781-48be-ba57-4bbfba9786db | failed | stale_run_reaped |        1 | 2026-10-28 16:58:09.952669+00

 id | status |                                     failure_message                                      |        completed_at         |          failed_at
----+--------+------------------------------------------------------------------------------------------+-----------------------------+-----------------------------
 56 | failed | Scan abandoned: no progress since 2026-10-28T16:26:28.329980+00:00; reaped automatically | 2026-10-28 16:58:10.1076+00 | 2026-10-28 16:58:10.1076+00

 alerts
--------
      1
```

Logs worker correspondants :

```text
[2026-10-28 16:58:10,132: ERROR/ForkPoolWorker-1] ai_advisor_run_reaped run_id=3327f441-5781-48be-ba57-4bbfba9786db scan_id=55 attempts=1 idle_s=2501 error_code=stale_run_reaped
[2026-10-28 16:58:10,144: ERROR/ForkPoolWorker-1] ai_advisor_run_reaped run_id=ef3f8de9-d7f8-462a-b3f2-7b89368d1e97 scan_id=11 attempts=1 idle_s=6761 error_code=stale_run_reaped
[2026-10-28 16:58:10,152: ERROR/ForkPoolWorker-2] scan_reaped scan_id=56 previous_status=running idle_s=1901 error_code=stale_scan_reaped
[2026-10-28 16:58:10,160: ERROR/ForkPoolWorker-1] ai_advisor_run_reaped run_id=261fec42-0863-46a4-9ee9-b1e4941a92ba scan_id=7 attempts=1 idle_s=6801 error_code=stale_run_reaped
[2026-10-28 16:58:10,200: ERROR/ForkPoolWorker-1] ai_advisor_run_reaped run_id=f8ce1728-b84d-41d1-805d-776979c59136 scan_id=39 attempts=1 idle_s=6863 error_code=stale_run_reaped
[2026-10-28 16:58:10,202: INFO/ForkPoolWorker-1] ai_advisor_reaper cutoff=2026-10-28T16:48:09.952638+00:00 reaped=4
[2026-10-28 16:58:10,204: INFO/ForkPoolWorker-2] Coverage alert queued for scan 56
[2026-10-28 16:58:10,207: INFO/ForkPoolWorker-2] scan_reaper running_cutoff=2026-10-28T16:43:09.897224+00:00 queued_cutoff=2026-10-28T16:43:09.897224+00:00 reaped=1
```

Le reaper a aussi marqué `failed` **trois runs IA préexistants** laissés `running` par des lots antérieurs (scans 7, 11, 39). Aucune ligne n'a été supprimée : seuls des états bloqués ont été clos, conformément au correctif.

### 3.3 Preuve réelle — un scan vivant n'est pas reapé

Le scan full 58 a tourné de `17:01:35` à `17:10:36`. Le tick de beat de `17:08:10` a exécuté les deux reapers :

```text
[2026-10-28 17:08:10,074: INFO/ForkPoolWorker-1] scan_reaper running_cutoff=2026-10-28T16:53:09.873372+00:00 queued_cutoff=2026-10-28T16:53:09.873372+00:00 reaped=0
[2026-10-28 17:08:10,112: INFO/ForkPoolWorker-1] ai_advisor_reaper cutoff=2026-10-28T16:58:10.092048+00:00 reaped=0
```

Le scan 58 n'a pas été touché et s'est terminé normalement.

### 3.4 Tâches enregistrées et planification

```text
$ docker compose exec -T celery-worker celery -A config inspect registered | grep -E 'reap_stale|verify_aka'
* advisory.tasks.reap_stale_ai_runs
* advisory.tasks.verify_aka_credentials
* scans.tasks.reap_stale_scans

$ docker compose exec -T celery-worker celery -A config inspect ping
        pong
1 node online.
```

Les tâches ont bien été exécutées par beat à `16:58:09` et `17:08:10`, sans dispatch manuel. Le log beat de Celery 5.5 ne journalise pas les envois au niveau INFO, mais les exécutions worker à cadence de 300 s en sont la preuve.

---

## 4. Non-régression des scans

### 4.1 Scan de santé (réel, via l'API)

```text
HTTP=202 time=0.406074s
{"id":57,"domain":"appchat.elomaiapp.com","website_id":1,"status":"queued","scan_type":"health",...}
```

Résultat :

```text
 id | scan_type |  status   | health_score | progress | duration_s | checks | runs
----+-----------+-----------+--------------+----------+------------+--------+------
 57 | health    | completed |           69 |      100 |          2 |      7 |    8
```

Tous les scanners internes sont `completed` ; `lighthouse` reste `unavailable` (binaire absent de l'image worker), comportement préexistant.

### 4.2 Scan full (réel, via l'API)

```text
HTTP=202 time=0.253565s
{"id":58,"domain":"appchat.elomaiapp.com","website_id":1,"status":"queued","scan_type":"full",...}

 id | scan_type |  status   | health_score | progress | duration_s | checks | runs
----+-----------+-----------+--------------+----------+------------+--------+------
 58 | full      | partial   |           69 |      100 |        541 |      9 |   16
```

Détail des runs :

```text
 58 | dns              | completed   |
 58 | dnsrecon         | completed   |         0
 58 | email_security   | completed   |
 58 | gobuster         | partial     |         1
 58 | lighthouse       | unavailable |
 58 | nikto            | partial     |         0
 58 | nmap             | completed   |         0
 58 | nuclei           | completed   |         0
 58 | performance      | completed   |
 58 | security_headers | completed   |
 58 | ssl              | completed   |
 58 | testssl          | timeout     |        -9
 58 | uptime           | completed   |
 58 | website          | completed   |
 58 | whatweb          | completed   |         0
 58 | zap              | completed   |
```

Raisons enregistrées :

```text
testssl : status=timeout, exit=-9, duration_ms=90537, timeout_s=90, partial_reason=timeout
nikto   : status=partial, exit=0, duration_ms=92459, timeout_s=100, partial_reason=maxtime_reached, archive 2074 octets / 23 lignes
```

Le même `testssl --std` exécuté seul dans le bac à sable, sur la même cible, termine correctement :

```text
EXIT=0 DURATION_S=56
 Done 2026-10-28 17:13:37 [  55s] -->> 188.114.96.3:443 (appchat.elomaiapp.com) <<--
```

**Interprétation :** le timeout du scan 58 est conjoncturel (charge/parallelisme du scan complet), pas une régression du scanner ni des correctifs. Le scan 55 de référence était déjà `partial` (gobuster + lighthouse). Aucun code de scanner n'a été modifié.

Un second full scan de confirmation n'a pas pu être lancé : le quota Free du compte de test est épuisé (`403 scan_quota_exceeded`, 10/10). C'est une limite de test, pas un défaut du pipeline.

### 4.3 Annexe — gobuster `exit 1`

Reproduction réelle dans l'image `presence-scanner-tools:2026-10-27` :

```text
EXIT=1
stdout : (vide)
stderr : Error: the server returns a status code that matches the provided options for non existing urls. https://appchat.elomaiapp.com/6ddd239d-5416-4dc0-92b1-4b4cd712d205 => 200 (Length: 7473). To continue please exclude the status code or the length
```

**Qualification :** ce n'est **pas** « aucun répertoire trouvé ». Gobuster refuse de continuer parce que la cible renvoie `200` pour des chemins aléatoires (SPA/catch-all). Le statut `partial` est donc correct : l'énumération n'a pas couvert la wordlist. Limite de la cible, pas du pipeline. Piste future : détecter cette erreur et proposer `--exclude-length` / `--exclude-status` automatiquement, sans transformer l'échec en succès.

### 4.4 Annexe — libellé Celery

Ancien comportement : tout épuisement de retries renvoyait `failed_quota_exhausted`, y compris un 500 persistant.

Nouveau comportement (`advisory/tasks.py::_terminal_status`) :

| Cause | Libellé |
|---|---|
| `rate_limit_exceeded`, `guest_quota_exceeded` | `failed_quota_exhausted` |
| `invalid_api_key`, `client_unavailable` | `failed_configuration` |
| timeout, 5xx, connexion, circuit ouvert | `failed_upstream_error` |

Test dédié : `test_terminal_labels_reflect_the_cause` (OK).

### 4.5 Test existant modifié (changement voulu, pas un affaiblissement)

`advisory/tests/test_aka_client.py::test_429_with_long_retry_after_is_not_retried`

- **Avant :** réponse `429` avec code `guest_quota_exceeded` → attendait `AkaRateLimitError`, `retry_after=86400`, 1 appel, 0 sleep.
- **Après :** la même assertion est conservée, mais avec un `429` authentifié `rate_limit_exceeded` (le cas générique « long Retry-After »).
- Le cas `guest_quota_exceeded` est désormais couvert séparément par `test_guest_429_is_reported_as_a_bad_key_not_a_quota_issue` et `test_guest_quota_code_without_header_still_fails_credentials`, qui exigent `AkaAuthenticationError` et 1 seul appel.

Aucune assertion n'a été supprimée : le nombre d'appels, l'absence de sleep et la valeur `retry_after` restent vérifiés.

---

## 5. Tests exécutés

| Commande | Résultat | Code de sortie |
|---|---|---|
| `run_backend_tests.sh advisory.tests.test_credentials advisory.tests.test_reaper scans.tests.test_stale_scans` | **21 tests OK** | 0 |
| `run_backend_tests.sh advisory` (avant correction du test obsolète) | 197 tests, 1 erreur (`test_429_with_long_retry_after_is_not_retried`) | 1 |
| `run_backend_tests.sh advisory.tests.test_aka_client … test_advisor` (7 modules) | **110 tests OK** | 0 |
| `run_backend_tests.sh advisory.tests.test_security_advisor` | **31 tests OK** | 0 |
| `run_backend_tests.sh scans.tests.test_stale_scans scans.tests.test_scans monitoring.tests.test_scan_policy` | **77 tests OK** | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `check_aka_key` (clé valide) | authenticated, 247–398 ms | 0 |
| `check_aka_key` (clé invalide) | `guest mode (HTTP 429)` | 1 |
| `check_aka_key` (clé absente) | `ImproperlyConfigured` | 1 |
| `celery -A config inspect ping` | `pong`, 1 node | 0 |
| `testssl --std` autonome | 56 s, exit 0 | 0 |

Les tests de la suite advisory complète ont été exécutés avant la correction du test obsolète ; les 110 tests ciblés puis les 31 tests `security_advisor` couvrent tous les modules modifiés après cette exécution. Aucun test frontend/Playwright n'était concerné : aucun fichier frontend n'a été modifié.

---

## 6. Fichiers modifiés et créés

Modifiés :

```text
SaaS_Web_Application_digitale_presenz_v2/backend/.env.example
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/services/advisor.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/services/aka_client.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/services/factory.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/services/security_advisor.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/tasks.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/tests/test_aka_client.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/tests/test_security_advisor.py
SaaS_Web_Application_digitale_presenz_v2/backend/config/settings/base.py
SaaS_Web_Application_digitale_presenz_v2/backend/scans/tasks.py
```

Créés :

```text
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/management/__init__.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/management/commands/__init__.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/management/commands/check_aka_key.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/tests/test_credentials.py
SaaS_Web_Application_digitale_presenz_v2/backend/advisory/tests/test_reaper.py
SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_stale_scans.py
docs/audits/PRESENCE_SCAN_PIPELINE_FIXES_2026-10-28.md
```

Aucune migration, aucun changement de modèle, aucun changement de dépendance.

---

## 7. Contraintes et isolation

- **Aucun commit, aucun push, aucun déploiement distant.** `git diff --stat` reste une modification de travail non commitée.
- **Aucune modification Nginx, URL, sitemap, frontend, CMS ou base WordPress.**
- **Services Docker recréés :** uniquement `celery-beat` et `celery-worker`, nécessaires pour charger les nouvelles tâches. Preuve par `StartedAt` :

```text
--- diff before/after ---
< celery-beat-1    2026-10-27T09:58:55.180700613Z
< celery-worker-1  2026-10-28T14:59:21.33941944Z
---
> celery-beat-1    2026-10-28T16:52:58.977233608Z
> celery-worker-1  2026-10-28T16:52:58.526749756Z
```

Aucun autre conteneur (db, redis, web, frontend, wordpress, wordpress-db, mailpit, umami, scanner-*) n'a été redémarré ou recréé.

- **Scan anti-secrets** exécuté sur les 16 fichiers de code modifiés/créés (le présent rapport n'est pas couvert par ce scan). Deux correspondances de motif, toutes deux non sensibles :
  - `config/settings/base.py:429` : `AKA_AI_API_KEY = env("AKA_AI_API_KEY", "")` (lecture d'environnement) ;
  - `.env.example:81` : `AKA_AI_API_KEY=replace-with-your-aka-ia-api-key` (placeholder préexistant).
  Aucune clé réelle, aucun token, aucun mot de passe.

---

## 8. Limites restantes

1. **Scan full `partial`** : `testssl` a dépassé son budget de 90 s et `nikto` son `maxtime` de 100 s pendant le scan 58. Le même testssl termine en 56 s seul. Le budget devra être réévalué (ou le parallélisme des scanners revu) avant de qualifier le full de stable.
2. **Gobuster sur cible SPA** : `exit 1` est un refus soft-404 légitime ; l'énumération reste `partial`. Aucun correctif automatique n'a été ajouté (hors périmètre), pour ne pas masquer l'absence de couverture.
3. **Alerte des runs IA** : l'incident est journalisé en `ERROR` et le run est visible en `failed`, mais aucun canal de notification (email/Slack) n'est déclenché pour un run IA reapé. Les scans, eux, créent bien une alerte de couverture.
4. **Cooldown de clé** : 15 min par défaut. Une correction de clé suivie d'une sonde valide (`check_aka_key` ou tâche `verify_aka_credentials`) lève immédiatement le marqueur.
5. **Détection invitée** : elle repose sur l'en-tête `x-ratelimit-limit` de la passerelle actuelle (ou le code `guest_quota_exceeded`). Un changement de contrat de la passerelle devra mettre à jour `AkaConfig.guest_mode_header`.
6. **Données de test laissées en base locale** : scan 56 (site `reaper-live-20261028.example`), scans 57 et 58 sur `appchat.elomaiapp.com`, run IA de test sur le scan 55. Aucune suppression effectuée. Trois anciens runs `running` (scans 7, 11, 39) ont été clos `failed` par le reaper, sans suppression.
7. **Quota de scans** : le compte de test a atteint 10/10 scans mensuels ; un second full de confirmation n'a pas pu être lancé.
8. **Pas de métrique** : les reapers ne publient pas de compteur Prometheus/StatsD ; la supervision repose sur les logs `ERROR` et les alertes de couverture.

---

## 9. Recommandations avant gel

1. Réévaluer `SCANNER_TIMEOUT_TESTSSL` (90 s → 120 s) et le budget nikto, ou réduire la concurrence des scanners externes, puis rejouer un full sur machine au repos.
2. Ajouter une détection ciblée de l'erreur soft-404 gobuster (`--exclude-length` automatique) avec un statut explicite, sans transformer l'échec en succès.
3. Brancher les logs `ERROR` des reapers sur le canal d'alerte opérateur existant (email/Slack) pour les runs IA, comme c'est déjà fait pour les scans.
4. Ajouter un compteur de reaps et un indicateur « dernier tick beat » pour détecter un beat arrêté.
5. Rejouer les 197 tests advisory complets après les dernières modifications de test, puis envisager le gel.

---

## 10. Confirmation finale

- Les deux défaillances bloquantes du rapport précédent sont corrigées et prouvées par des exécutions réelles, avec codes de sortie et sorties brutes.
- Les scans de santé et full ont été rejoués ; le santé est conforme, le full reste `partial` pour des raisons de budget d'outils documentées.
- Aucun commit, aucun push, aucun déploiement, aucune modification Nginx/URL/sitemap.
- Le statut global du pipeline reste **non gelé** : correctifs validés, limites ci-dessus à traiter.
