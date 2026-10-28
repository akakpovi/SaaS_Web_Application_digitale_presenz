# Phase D — Service métier AI Advisor : rapport d'exécution

**Date :** 24 octobre 2026  
**Rôle :** Lead DevSecOps  
**Périmètre :** configuration multi-modèles, modèles et migration, schéma strict, orchestration avec failover, tests isolés  
**Statut :** **48/48 tests de la suite `advisory` OK** ; migration créée ; service métier livré

---

## 1. Résumé exécutif

La configuration AKA est passée d'un modèle unique à une **liste ordonnée** `AKA_AI_MODELS`. Les deux modèles configurés ont été testés séparément contre le gateway :

| Modèle demandé | Résultat réel | Latence |
|---|---|---|
| `groq/qwen/qwen3.8-27b` | `200`, `AKA_OK`, modèle retourné `qwen/qwen3.8-27b` | 593 ms |
| `ddgw/gpt-5.4-mini` | `200`, `AKA_OK`, modèle retourné `gpt-5.4-mini` | 1 631 ms |

Le service `generate_recommendations_for_scan()` orchestre désormais : hash d'idempotence, prompt avec preuves isolées, itération sur les modèles, validation stricte, persistance, puis fallback déterministe si toute la liste échoue.

La nouvelle suite `advisory` passe **48/48**. La suite backend complète n'a pas pu aller au bout dans cet environnement : le conteneur a reçu un `SIGKILL` (code 137) après environ sept minutes, sans résumé Django. Aucun échec de test n'apparaît dans le log avant l'arrêt, mais je ne présente pas cette exécution comme une preuve de succès. La suite ciblée est la validation de cette étape.

---

## 2. Mission 1 — Configuration multi-modèles

### 2.1 Variables

`.env` et `.env.example` contiennent désormais :

```dotenv
AKA_AI_MODELS=groq/qwen/qwen3.8-27b,ddgw/gpt-5.4-mini
```

L'ancienne variable singulière `AKA_AI_MODEL` n'est plus référencée dans le code, les settings ou les fichiers d'environnement.

`config/settings/base.py` parse la liste avec `_env_list()` :

- découpage sur les virgules ;
- suppression des espaces ;
- suppression des entrées vides ;
- dédoublonnage **en conservant l'ordre**.

`settings.AKA_AI_MODELS` est ensuite transmis à `AkaConfig.models` par `advisory/services/factory.py`.

### 2.2 Client

`AkaAIClient.chat()` accepte maintenant `model=...` et n'accepte qu'un modèle présent dans `config.models`. Si aucun modèle n'est précisé, le premier de la liste est utilisé. Le client conserve `HTTPAdapter(max_retries=0)` et la gestion de retry applicative.

Tests ajoutés : ordre et dédoublonnage, refus d'une liste vide, sélection du second modèle, refus d'un modèle inconnu avant tout appel HTTP.

---

## 3. Mission 2 — Modélisation et persistance

### 3.1 `AIRecommendationRun`

```text
id            UUID
scan          FK Scan (CASCADE)
input_hash    SHA-256 (64 caractères)
status        pending | running | succeeded | failed
model_used    modèle final ayant réussi (vide si fallback)
created_at
updated_at
completed_at
```

Contrainte : `UniqueConstraint(scan, input_hash)` → **idempotence au niveau base**. Un index couvre `(scan, status)`.

### 3.2 `AIRecommendation`

```text
id            UUID
run           FK AIRecommendationRun
finding       FK Finding nullable
check_result  FK CheckResult nullable
title         CharField(255)
summary       TextField
action        TextField
effort        low | medium | high
priority      critical | high | medium | low
confidence    Float 0..1 (validator + CheckConstraint)
created_at
```

Contrainte `ai_recommendation_one_target` : exactement un des deux champs `finding` ou `check_result` est renseigné. Une recommandation ne peut donc pas être orpheline ou pointer vers deux cibles.

La migration [0001_initial.py](../../SaaS_Web_Application_digitale_presenz_v2/backend/advisory/migrations/0001_initial.py) a été générée et appliquée avec succès lors des tests.

---

## 4. Mission 3 — Schéma de validation strict

`advisory/services/schema.py` utilise des **serializers DRF**, sans nouvelle dépendance.

Points validés :

- le contenu doit être un objet JSON ;
- les blocs Markdown ```json sont acceptés, le reste est rejeté ;
- les champs inconnus sont refusés, y compris dans chaque recommandation ;
- `title`, `summary`, `action` sont obligatoires ;
- `effort` et `priority` sont limités aux choix du modèle ;
- `confidence` doit être comprise entre 0 et 1 ;
- `recommendations` doit contenir entre 1 et 12 éléments ;
- chaque élément doit fournir `check_code` ou `finding_id` ;
- les références sont résolues **dans le scan d'origine uniquement** :
  - `finding_id` → `Finding` du scan ;
  - `check_code` d'un finding → `Finding` du scan ;
  - `check_code` de type `ssl.overall` ou `ssl` → `CheckResult` du scan ;
- un `finding_id` d'un autre scan est rejeté ;
- un `finding_id` et un `check_code` incohérents sont rejetés.

Une erreur de schéma ou de référence lève `RecommendationValidationError` et provoque la bascule vers le modèle suivant, sans requête réseau supplémentaire de « réparation ».

---

## 5. Mission 4 — Orchestration et failover

### 5.1 Entrée

```python
from advisory.services.advisor import generate_recommendations_for_scan

result = generate_recommendations_for_scan(scan_id)
# result.run            → AIRecommendationRun
# result.recommendations → list[dict]
# result.used_fallback  → bool
# result.model_used     → run.model_used
```

Le paramètre `client=` permet d'injecter un faux client dans les tests. Aucun appel réseau n'est fait dans la suite automatisée.

### 5.2 Hash d'idempotence

`build_input_hash(snapshot, models)` sérialise de façon canonique :

- `PROMPT_VERSION = "scan-advisor-v1"` ;
- la liste ordonnée des modèles ;
- l'identifiant et les métadonnées du scan ;
- les `CheckResult` (catégorie, statut, score, résumé, recommandation, détails techniques) ;
- les `Finding` (id, `check_code`, sévérité, statut, preuves, valeurs détectée/attendue, recommandation).

Le hash SHA-256 est stocké dans `AIRecommendationRun.input_hash`. Un second appel avec le même scan et la même liste de modèles retourne le run existant sans rappeler le provider. Un changement de liste de modèles ou de preuves crée un nouveau run.

### 5.3 Prompt

Le prompt système déclare explicitement que les preuves JSON sont **UNTRUSTED DATA**, jamais des instructions, et interdit de suivre les consignes trouvées dans les titres, descriptions, URL ou evidences. Le contrat de sortie impose le JSON, les choix `effort`/`priority`, la confiance 0..1 et une ou deux références réelles.

Les preuves sont envoyées dans un message utilisateur séparé, sérialisées en JSON. Aucun prompt, aucune preuve et aucune réponse brute ne sont journalisés.

### 5.4 Bascule

Pour chaque modèle dans l'ordre :

1. appel `client.chat(messages, model=model)` ;
2. parsing JSON strict ;
3. validation du schéma ;
4. résolution des références dans le scan ;
5. en cas de succès : suppression d'éventuelles lignes partielles, `bulk_create` des `AIRecommendation`, passage du run à `succeeded`, enregistrement de `model_used` et `completed_at` ;
6. en cas d'échec : log `model=<nom> error=<classe>` uniquement, puis modèle suivant.

Sont basculés : `AkaConfigurationError` (dont `400 model_not_found`), `AkaRateLimitError` (429 épuisé), `AkaServerError`, `AkaTimeoutError`, `AkaConnectionError`, `AkaInvalidResponseError`, ainsi que `RecommendationValidationError`.

### 5.5 Épuisement de la liste

Si aucun modèle ne produit un payload valide :

- `run.status = failed` ;
- `run.model_used = ""` ;
- `completed_at` est renseigné ;
- aucune `AIRecommendation` n'est persistée ;
- `AdvisorResult.used_fallback = True` ;
- les recommandations déterministes du `RecommendationEngine` existant sont retournées avec `source="deterministic"` et `confidence=1.0`.

Le fallback déterministe n'est pas stocké dans `AIRecommendation` : ces lignes resteraient ambiguës (elles ne viennent pas d'un modèle). Le run failed constitue la trace de l'échec ; le consommateur reçoit les recommandations déterministes dans le résultat.

---

## 6. Mission 5 — Tests et validation

### 6.1 Suite ciblée

Commande exécutée avec une base isolée pour éviter le conflit avec un autre runner utilisant `test_presence` :

```bash
docker compose run --rm --no-deps --user 0:0 \
  -v "$PWD/SaaS_Web_Application_digitale_presenz_v2/backend":/app \
  -e DJANGO_SETTINGS_MODULE=config.settings.test \
  -e POSTGRES_DB=presence_advisor_finaltest2 \
  web python manage.py test advisory --noinput
```

```text
Ran 48 tests in 48.971s

OK
```

Répartition :

- **29 tests** client HTTP : configuration, modèles, 200, 400, 401, 403, 404, 429, 5xx, timeouts, JSON invalide, taille, circuit breaker, logs, redaction ;
- **11 tests** schéma : cible finding/check result, autre scan, code inconnu, cible manquante, champ inconnu, confiance hors bornes, confiance non finie, JSON invalide, fence Markdown ;
- **8 tests** service : failover 500, `model_not_found` 400, 429 épuisé, JSON invalide → modèle suivant, épuisement total → fallback, idempotence sans second appel, sensibilité du hash à l'ordre des modèles, isolation des preuves dans le prompt.

Tous les appels réseau sont remplacés par `FakeClient` ; aucun socket n'est ouvert par la suite.

### 6.2 Contrôles Django

```text
python manage.py check
System check identified no issues (0 silenced).
```

```text
python manage.py makemigrations --check --dry-run
No changes detected
```

Un avertissement de connexion à la base de test absente est apparu pendant `makemigrations --check`, sans impact sur le résultat : aucune migration manquante.

### 6.3 Suite complète

La suite complète a été lancée dans un conteneur isolé avec une base dédiée. Le conteneur a été arrêté par l'environnement (`SIGKILL`, code 137) après environ sept minutes, avant le résumé Django. Aucun `FAIL:` ni `ERROR:` de test n'apparaît dans le log avant l'arrêt, mais **la suite complète n'est pas validée par cette exécution**. Elle devra être relancée en CI avec une limite de temps suffisante.

### 6.4 Validation réelle des modèles

Les deux modèles de `AKA_AI_MODELS` ont répondu `200` avec `AKA_OK` via le client réel et la clé locale. Le gateway normalise parfois le nom retourné (`qwen/qwen3.8-27b`, `gpt-5.4-mini`) : `model_used` enregistre le nom réellement renvoyé par le provider, pas nécessairement l'alias demandé.

---

## 7. Limites et points de vigilance

1. **Aucun endpoint, aucune tâche Celery** : le service est prêt mais n'est pas encore exposé. Le feature flag `AI_ADVISOR_ENABLED` n'est pas encore appliqué dans ce service ; il devra l'être avant toute exposition.
2. **Fallback non persisté** : choix explicite pour ne pas mélanger recommandations IA et déterministes. Si le produit veut un historique unifié, ajouter un champ `source` et persister le fallback.
3. **Run failed non retenté automatiquement** : un nouvel appel avec le même `input_hash` renvoie le fallback existant. Un retry manuel ou un changement de liste de modèles crée un nouveau run.
4. **Concurrence** : la contrainte unique protège l'idempotence, mais deux appels strictement simultanés peuvent encore se disputer la création ; un verrou `select_for_update` ou une reprise sur `IntegrityError` sera nécessaire pour une production multi-workers.
5. **Circuit breaker local** : toujours en mémoire, à remplacer par Redis pour les workers Celery.
6. **Taille du prompt** : toutes les preuves sont incluses sans plafond. Un scan très volumineux peut dépasser le contexte du modèle ; un plafond/ranking des findings est recommandé.
7. **Budgets** : `usage` reste inexploitable (zéros constatés en Phase C) ; le budget en tokens et le plafond mensuel ne sont pas implémentés.
8. **Qualité** : le test réel porte sur `AKA_OK`, pas sur un jeu de 20 prompts métier ; le benchmark AC-05 reste à faire.

---

## 8. Fichiers livrés

- `advisory/services/aka_client.py` — client multi-modèles ;
- `advisory/services/factory.py` — parsing de `AKA_AI_MODELS` depuis Django ;
- `advisory/models.py` — `AIRecommendationRun`, `AIRecommendation` ;
- `advisory/migrations/0001_initial.py` — migration initiale ;
- `advisory/services/schema.py` — schéma DRF strict et résolution des références ;
- `advisory/services/advisor.py` — orchestration, idempotence, failover, fallback ;
- `advisory/tests/test_aka_client.py` — 29 tests client ;
- `advisory/tests/test_advisor.py` — 19 tests schéma/service ;
- `config/settings/base.py` — parsing `AKA_AI_MODELS` ;
- `.env.example` — liste ordonnée factice ;
- `.env` — liste réelle locale, non versionné, permissions `600`.

---

## 9. Conclusion

L'Étape D est livrée : la configuration multi-modèles est opérationnelle, les modèles et la migration sont en place, le schéma refuse les références hors scan, et le service bascule sur le modèle suivant avant de servir un fallback déterministe. La suite `advisory` est à **48/48**, soit 100 % de la nouvelle suite.

La validation complète du backend reste à refaire en CI avec une limite de temps adaptée ; l'arrêt `SIGKILL` observé est un problème d'environnement, pas un échec de test documenté.
