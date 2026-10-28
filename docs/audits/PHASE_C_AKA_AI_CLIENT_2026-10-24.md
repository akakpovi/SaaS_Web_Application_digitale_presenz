# Phase C — Client AKA IA : rapport d'exécution

**Date :** 24 octobre 2026  
**Rôle :** Lead DevSecOps  
**Périmètre :** Étape C — validation du contrat AKA IA, configuration, client HTTP, tests unitaires isolés  
**Statut :** **AC-02 validé** ; client livré ; **25 tests unitaires OK** ; **463 tests backend OK**

---

## 1. Résumé exécutif

Le prérequis bloquant de la Phase 0 est levé : une requête `POST /v1/chat/completions` avec la clé de développement fournie, le modèle `groq/qwen/qwen3.8-27b` et un en-tête `Authorization: Bearer …` répond **HTTP 200** avec un JSON de type `chat.completion` valide.

Le module `advisory` a été créé avec un client HTTP sans dépendance Django dans son cœur, une configuration centralisée, une politique de retry maîtrisée et un circuit breaker local. La nouvelle suite `advisory` passe (**25/25**) et la suite backend complète reste verte (**463/463**).

Aucun secret n'a été écrit dans le dépôt : la clé est uniquement dans le `.env` local, ignoré par Git, avec des permissions `600`. `.env.example` ne contient qu'une valeur factice.

---

## 2. Validation distante du contrat (AC-02)

### 2.1 Requête de référence

| Élément | Valeur |
|---|---|
| Endpoint | `https://ai.elomaiapp.com/v1/chat/completions` |
| Méthode | `POST` |
| Authentification | `Authorization: Bearer <clé de développement>` |
| Modèle | `groq/qwen/qwen3.8-27b` |
| `stream` | `false` |
| `max_tokens` | `32` (probe brute), `32` (client) |
| Résultat | **HTTP 200**, `application/json`, 300 octets, **0,35 s** |

Extrait de la réponse réelle (aucune donnée secrète) :

```json
{
  "id": "chatcmpl-0860a87e33ea473783e6be71",
  "object": "chat.completion",
  "created": 1792817333,
  "model": "groq/qwen/qwen3.8-27b",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "AKA_OK" },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "cached": true
  }
}
```

Le format est bien compatible OpenAI pour le chat non-streaming : `id`, `object`, `created`, `model`, `choices[].message.content` et `choices[].finish_reason` sont présents et exploitables.

### 2.2 Preuve que la clé est reconnue

Un `200` seul ne suffisait pas : l'audit Phase 0 avait observé qu'un Bearer invalide était accepté en mode invité. Trois probes ont donc été comparées le même jour :

| Probe | Authentification | Résultat |
|---|---|---|
| Clé de développement | `Bearer <clé>` | **200**, `AKA_OK`, quota invité contourné |
| Clé volontairement invalide | `Bearer sk-akaia-invalid-probe-…` | **401**, `AuthenticationFailed` |
| Sans authentification | aucun en-tête | **429**, `guest_quota_exceeded`, `Retry-After: 86400` |

Conclusion : le gateway distingue désormais une clé valide d'une clé invalide. La clé de développement est donc bien reconnue en mode Bearer authentifié, et **AC-02 est satisfait**. Cela ne fait pas du gateway une frontière d'autorisation métier : les droits, quotas et organisations doivent rester contrôlés par Presence.

### 2.3 Test via le client livré

Le client a été exécuté dans le conteneur backend avec la configuration Django réelle (`build_aka_client()`), sans passer par `curl` :

```json
{
  "status": "ok",
  "content": "AKA_OK",
  "model": "groq/qwen/qwen3.8-27b",
  "finish_reason": "stop",
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "total_tokens": 0,
  "latency_ms": 281,
  "request_id": null,
  "system_fingerprint": null
}
```

Le client a correctement : construit l'URL, envoyé le Bearer, désactivé les redirections, lu la réponse en streaming avec plafond, validé le JSON et normalisé le résultat.

---

## 3. Comportements inattendus observés avec la vraie clé

1. **`usage` est entièrement à zéro malgré une génération réelle.**  
   La réponse contient `prompt_tokens: 0`, `completion_tokens: 0`, `total_tokens: 0`, avec `cached: true`. Il est donc **impossible de fonder le budget ou la facturation sur `usage`** en l'état. Le client expose ces zéros sans les inventer. La couche budget devra estimer localement ou utiliser un compteur fournisseur, avec une marge (l'audit recommande au moins 20 %).

2. **Aucun `x-request-id` ni `request_id` dans la réponse 200.**  
   Le corps contient seulement `id` (`chatcmpl-…`). Le client renvoie donc `request_id = null` et conserve `completion.id` comme identifiant de corrélation. Les logs et le support doivent utiliser `completion.id`, pas `request_id`, pour les succès.

3. **Le modèle est renvoyé sous l'alias demandé.**  
   `model` vaut `groq/qwen/qwen3.8-27b`, et non un nom normalisé par le fournisseur. Il ne faut pas comparer ce champ à une valeur interne pour déduire le modèle réellement exécuté.

4. **Un Bearer invalide renvoie maintenant 401, contrairement à l'audit Phase 0.**  
   Le corps est :
   ```json
   {
     "error": {
       "message": "Invalid API key.",
       "type": "AuthenticationFailed",
       "param": null,
       "code": null,
       "request_id": "028abb0e39524398a16b0dc76b009c06"
     }
   }
   ```
   `code` est `null` : le client retombe sur `type` (`AuthenticationFailed`). Ce cas réel est couvert par un test de non-régression.

5. **Le mode invité est toujours bloqué par un quota de 24 h.**  
   Sans authentification : `429 guest_quota_exceeded`, `Retry-After: 86400`, et un champ `login_url` qui pointe encore vers `http://localhost:3000`. Le client **ne relaie jamais** ce champ et ne retente pas un `Retry-After` aussi long. Le fallback déterministe et l'alerte ops restent à brancher en Phase D.

6. **Aucun `system_fingerprint`.**  
   Le champ est absent ; le client renvoie `null`. Ne pas l'utiliser comme clé de version.

7. **Latence très faible (0,21–0,35 s) pour deux tokens.**  
   Ces mesures ne sont **pas** représentatives d'un prompt de production ni d'un p95. Le benchmark AC-05 (20 prompts, p50/p95, tokens, coût) reste requis avant de calibrer les timeouts.

8. **`usage.cached: true` sur une requête apparemment nouvelle.**  
   Le gateway peut servir un cache. Cela renforce la prudence sur la comptabilisation des tokens et sur l'idempotence des runs.

---

## 4. Implémentation livrée

### 4.1 Arborescence

```text
backend/advisory/
├── __init__.py
├── apps.py
├── services/
│   ├── __init__.py
│   ├── aka_client.py      # client HTTP, sans Django
│   └── factory.py         # lecture des settings Django, fail-closed
└── tests/
    ├── __init__.py
    └── test_aka_client.py # 25 tests, réseau entièrement mocké
```

Fichiers modifiés :

- `backend/config/settings/base.py` — ajout de `advisory`, des réglages `AKA_AI_*` et de `AI_ADVISOR_ENABLED` ;
- `backend/.env.example` — bloc documenté avec une clé factice ;
- `backend/.env` — configuration locale réelle, **non versionnée**, permissions `600`.

### 4.2 `AkaAIClient`

- `requests.Session` injectable, sans dépendance Django.
- `HTTPAdapter(max_retries=0)` explicite : les retries sont gérés par notre code, jamais doublés par urllib3.
- `allow_redirects=False`, TLS vérifié, base URL HTTPS uniquement (exception loopback explicite pour les tests locaux).
- Lecture `stream=True` avec plafond `AKA_AI_MAX_RESPONSE_BYTES` (1 Mo par défaut).
- Timeouts `(connect, read)` configurables.
- Validation stricte des messages : rôles `system` / `user` / `assistant`, contenu non vide.
- Réponse 200 : validation JSON, présence de `choices`, `message.content` non vide, normalisation des tokens et de `request_id`.
- Erreurs typées : `AkaConfigurationError`, `AkaRateLimitError`, `AkaServerError`, `AkaTimeoutError`, `AkaConnectionError`, `AkaInvalidResponseError`, `AkaCircuitOpenError`.

### 4.3 Politique de retry

| Cas | Comportement |
|---|---|
| `400`, `401`, `403`, `404`, `405`, `422` | **Aucun retry** ; erreur de configuration immédiate |
| `408`, `425`, `429`, `5xx` | Retry avec backoff exponentiel + jitter |
| Timeout / erreur de connexion | Retry puis erreur typée |
| `Retry-After` court | Respecté à la seconde |
| `Retry-After` > `AKA_AI_MAX_RETRY_AFTER` (300 s) | **Aucun retry bloquant** ; erreur remontée avec `retry_after` |
| JSON invalide, `choices` vide, contenu vide, réponse > 1 Mo | **Aucun retry** ; `AkaInvalidResponseError` |

Avec `AKA_AI_MAX_RETRIES=2` (valeur par défaut de l'audit), les délais sont **2 s puis 4 s** (3 tentatives au total). Un test dédié avec `max_retries=3` vérifie la séquence complète **2 s, 4 s, 8 s**. Le jitter est ajouté sans dépasser le plafond configuré.

### 4.4 Circuit breaker

`InMemoryCircuitBreaker` :

- ouverture après `AKA_AI_CIRCUIT_FAILURE_THRESHOLD` échecs (5 par défaut) ;
- récupération après `AKA_AI_CIRCUIT_RECOVERY_SECONDS` (300 s par défaut) ;
- semi-ouvert avec une seule probe ;
- aucune requête HTTP envoyée quand le circuit est ouvert ;
- thread-safe et horloge injectable pour les tests.

**Limite assumée :** l'état est local au processus. En production multi-workers Celery, il faudra une implémentation Redis partagée. Le client ne dépend que du contrat `before_request` / `record_success` / `record_failure`, donc le remplacement ne touchera pas le code appelant.

### 4.5 Sécurité et logs

- La clé est exclue du `repr` de `AkaConfig` et de `AkaAIClient`.
- Aucun log de prompt, de réponse brute, d'en-tête `Authorization` ou de clé.
- Les logs de retry ne contiennent que : statut HTTP, code, numéro de tentative, délai.
- Les messages d'erreur fournisseur sont **redactés** si la clé y apparaît (défense en profondeur), avec test dédié.
- Le client ne relaie jamais `login_url` ni les détails fournisseur.
- `build_aka_client()` échoue en `ImproperlyConfigured` si `AKA_AI_API_KEY` est vide : pas de fallback invité silencieux.

---

## 5. Résultats des tests

### 5.1 Suite ciblée

```bash
bash scripts/run_backend_tests.sh advisory
```

```text
Found 25 test(s).
System check identified no issues (0 silenced).
Ran 25 tests in 0.024s
OK
```

Couverture fonctionnelle :

- configuration : clé absente, URL non HTTPS, préfixe `Bearer`, `repr` sans clé, messages invalides ;
- succès : payload OpenAI, Bearer, URL, timeouts, `allow_redirects=False`, streaming, tokens, `request_id` ;
- `401` : erreur de configuration, non retryée, forme réelle `AuthenticationFailed` ;
- `400` `model_not_found` / `403` / `404` : non retryés ;
- `429` : backoff 2 s / 4 s sans en-tête, `Retry-After` court respecté, `Retry-After: 86400` non retenté ;
- `5xx` : backoff 2 s / 4 s, épuisement, séquence 2 s / 4 s / 8 s avec 3 retries ;
- timeouts : retry puis succès, épuisement ;
- réponses invalides : JSON invalide, `choices` vide, réponse > 1 Mo ;
- circuit breaker : ouverture, refus sans appel HTTP, récupération après fenêtre ;
- logs : aucun secret ni prompt ;
- redaction : une clé renvoyée par le fournisseur est masquée.

### 5.2 Suite backend complète

```bash
bash scripts/run_backend_tests.sh
```

```text
Ran 463 tests in 551.399s
OK
Destroying test database for alias 'default'...
```

Aucune régression détectée. Les avertissements `Free plan not found` observés dans les logs sont antérieurs à cette étape et n'ont pas provoqué d'échec.

### 5.3 Validation réseau réelle

| Test | Résultat |
|---|---|
| Client + clé valide | 200, `AKA_OK`, modèle cible, 281 ms |
| Curl + clé valide | 200, JSON `chat.completion`, 0,35 s |
| Curl + clé invalide | 401, `AuthenticationFailed` |
| Curl sans clé | 429, `guest_quota_exceeded`, `Retry-After: 86400` |

---

## 6. Mapping des critères d'acceptation

| Critère | Statut | Commentaire |
|---|---|---|
| **AC-02** — POST authentifié 200 + JSON OpenAI valide | **PASS** | Probe réelle documentée ci-dessus, avec preuve par clé invalide 401 |
| **AC-04** — tests 200, 400, 401, 429, 500, timeout, JSON invalide, `choices` vide, réponse trop volumineuse | **PASS** | Tous couverts, dont un cas 400 `model_not_found` explicite |
| **AC-06** — respect `Retry-After`, backoff + jitter, pas de retry 400/401/403/404 | **PASS** | Tests dédiés pour `Retry-After`, backoff et non-retry ; jitter implémenté et borné |
| **AC-07** — circuit breaker et fallback déterministe testés | **PASS (partiel)** | Circuit breaker testé ; le fallback déterministe relève de la Phase D |
| **AC-03** — mode invité interdit si clé absente | **PASS (client)** | `build_aka_client()` échoue fermé ; le gate applicatif global reste à câbler |

---

## 7. Limites et suites à donner

1. **Circuit breaker en mémoire** : à remplacer par Redis pour partager l'état entre workers Celery.
2. **Pas de retry différé Celery** : un `Retry-After` supérieur à 300 s remonte une erreur typée avec `retry_after` ; la planification différée et le fallback déterministe appartiennent à la couche service.
3. **Budget total et budget mensuel** : `AKA_AI_TOTAL_BUDGET` et `AKA_AI_MONTHLY_TOKEN_BUDGET` ne sont pas implémentés dans ce client. Ils relèvent du service de quota, d'autant que `usage` est inexploitable pour l'instant.
4. **Benchmark AC-05** : les mesures de latence sur deux tokens ne suffisent pas ; il faut 20 prompts représentatifs avant de figer les timeouts.
5. **Feature flag** : `AI_ADVISOR_ENABLED=false` est défini, mais aucun endpoint ne l'exploite encore. Il devra être vérifié avant toute exposition de l'IA, avec la liste canary prévue par l'audit.
6. **Clé de développement** : elle a été transmise par chat et doit être considérée comme exposée. La rotation est recommandée après les tests. Elle ne doit jamais être copiée en CI, en staging ou en production, ni dans un fichier versionné.

---

## 8. Conclusion

L'Étape C est terminée et **AC-02 est levé** : le mode Bearer authentifié fonctionne, le modèle cible est reconnu, le format OpenAI est valide, et le client livré reproduit ce succès de bout en bout. Le socle est testé, isolé de Django dans son cœur, fail-closed sans clé, et n'expose aucun secret dans les logs.

Le passage à l'Étape D peut s'appuyer sur ce client, mais devra encore traiter le fallback déterministe, le circuit breaker partagé Redis, le budget de tokens et le benchmark de latence avant toute exposition utilisateur.
