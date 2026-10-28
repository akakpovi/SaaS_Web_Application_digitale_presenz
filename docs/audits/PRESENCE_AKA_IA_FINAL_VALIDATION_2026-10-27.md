# Presence — AKA IA, validation finale

**Date :** 27 octobre 2026
**Périmètre :** environnement Docker local Presence, passerelle AKA IA réelle. Aucun déploiement.
**Références :** `docs/audits/PHASE_C_AKA_AI_CLIENT_2026-10-24.md`, `PRESENCE_AI_ADVISOR_AUDIT.md`, `PRESENCE_AI_ADVISOR_AUTOMATION_2026-10-25.md`.

---

## 1. Ce qui existait déjà et qui a été réutilisé (aucun second système créé)

| Brique | Fichier | Rôle |
|---|---|---|
| Client passerelle | `advisory/services/aka_client.py` | Appels OpenAI-compatibles vers `AKA_AI_BASE_URL`, liste de modèles ordonnée, timeouts connect/read, reprises limitées avec back-off, disjoncteur, plafond de taille de réponse, parsing strict. |
| Fabrique | `advisory/services/factory.py` | Construit le client depuis les réglages (`AKA_AI_*`) ; erreurs de configuration converties en indisponibilité propre. |
| Conseiller sécurité | `advisory/services/security_advisor.py` | Chat en lecture seule sur les `SecurityFinding` **ouverts d'une seule organisation**, contexte borné, prompt système anti-dérive. |
| Conseiller de scan | `advisory/services/advisor.py` + `advisory/tasks.py` | Recommandations structurées par scan, snapshots bornés, reprise/idempotence par `AIRecommendationRun`, repli déterministe. |
| API | `advisory/views.py`, `advisory/urls.py`, `advisory/permissions.py` | Chat par organisation (`/organizations/<id>/ai-advisor/chat/`), recommandations par scan, import de rapports ZAP/Nuclei, liste des constats. |
| Interface | `src/pages/SecurityAdvisor.tsx`, `src/components/SecurityAdvisorChat.tsx`, `AssetSecurityPanel` | Résumé, questions suggérées, chat contextualisé, limites affichées, retour aux preuves. |

La passerelle est configurée localement (`AKA_AI_BASE_URL`, `AKA_AI_API_KEY` présente, `AKA_AI_MODELS`, timeouts, disjoncteur). **Aucune clé n'apparaît côté frontend** : tous les appels partent du backend.

> `AI_ADVISOR_ENABLED` est **désactivé** dans l'environnement local : les recommandations *automatiques* après scan ne se déclenchent donc pas (interrupteur d'arrêt volontaire). Le chat et la génération manuelle restent utilisables, comme validé ci-dessous.

---

## 2. Corrections apportées dans cette mission

### 2.1 Honnêteté sur la couverture (exigence centrale)

Le chat ne recevait que les constats : un scan partiel était indiscernable d'un scan complet et le modèle pouvait présenter l'absence de résultat comme une preuve de sécurité.

- `security_advisor.build_coverage_note(organization, asset=None)` : construit un bloc `LATEST SCAN COVERAGE` déterministe (statut, type, date, et **liste des scanners non terminés** : `partial`/`failed`/`timeout`/`unavailable`), avec la phrase explicite « COVERAGE IS INCOMPLETE… missing findings are not proof that the site is healthy ».
- Le prompt système impose désormais de **commencer par signaler une couverture incomplète** et de nommer les scanners concernés.
- Le bloc est intégré au message utilisateur ; il reste balisé comme donnée non fiable (au même titre que les constats).
- Tests ajoutés (`advisory/tests/test_security_advisor.py::CoverageHonestyTests`, 4 tests) : le scanner incomplet est nommé, un scan complet confirme la couverture, le prompt de chat transporte bien le bloc, et l'absence de scan ne produit aucune affirmation.

### 2.2 Maîtrise de la consommation (nouveau)

Aucune limite n'existait sur le chat : un membre autorisé pouvait appeler le modèle sans plafond et consommer les crédits du projet.

- `config/settings/base.py` : `DEFAULT_THROTTLE_RATES["advisor_chat"]` = `AI_ADVISOR_CHAT_THROTTLE` (défaut **60/heure par utilisateur**, surchargeable par déploiement).
- `advisory/views.py` : `throttle_scope = "advisor_chat"` sur la vue de chat (le `ScopedRateThrottle` est déjà la classe par défaut du projet).
- Test ajouté : la 2ᵉ requête au-delà de la limite reçoit **429 sans atteindre le fournisseur** (`test_chat_is_rate_limited_per_user`).

### 2.3 Rappels de comportement déjà couverts (vérifiés, non modifiés)

- Isolation : la requête filtre d'abord sur `organization` ; un extérieur reçoit **404** (pas de confirmation d'existence), un lecteur (`viewer`) **403** avant tout appel modèle.
- Contenu non fiable : le prompt système interdit d'obéir aux instructions trouvées dans un constat, un en-tête ou un nom d'hôte ; les secrets sont mentionnés comme expurgés.
- Bornes : 40 constats max, descriptions 1 200 caractères, preuves 800, contexte 24 000, question 2 000, budget global `AKA_AI_MAX_PROMPT_CHARS` ; compteurs de troncature exposés à l'interface.
- Résilience : toute panne (clé absente, circuit ouvert, timeout, 429, 5xx, corps illisible) devient **503 avec code stable** (`ai_timeout`, `ai_rate_limited`, `ai_circuit_open`, …) — jamais un 500, et l'accès aux scans/constats reste disponible.
- Automatisme : `scans/tasks._dispatch_advisor` n'est déclenché que pour un scan `completed`, et la tâche revalide le drapeau et le statut avant tout appel modèle.

---

## 3. Preuves d'exécution réelle

### 3.1 Appel direct à la passerelle (conteneur `web`, image reconstruite)

```
model= qwen/qwen3.8-27b  chars= 22  seconds= 0.7  request_id_present= False
```

Le modèle configuré répond réellement ; le client gère la réponse complète (pas de repli).

### 3.2 Chat contextualisé via l'API (recette intégrée)

Exécution : `docker compose exec -T web python - < scripts/integrated_acceptance_recipe.py` — **17/17 contrôles réussis**, dont :

| Contrôle | Résultat observé |
|---|---|
| Membre extérieur → chat d'une organisation | **404**, aucun appel modèle |
| Propriétaire → question sur son scan | **200**, modèle `groq/qwen/qwen3.8-27b`, réponse bornée (323–364 caractères), `Cache-Control: no-store` |
| Latence | 0,3–0,9 s sur la passerelle locale |

La question envoyée portait explicitement sur la complétude du scan : le contexte contient donc le bloc de couverture (testé unitairement) et l'interface rappelle les limites de l'analyse.

### 3.3 Interface

- `AssetSecurityPanel` : 0 constat affiché pour un site sans finding (`« No open vulnerability recorded for this asset »`, avec la mention que les constats proviennent de scans complets ZAP/Nuclei) ; lien « Discuss findings »/« Ask the advisor ».
- Page **AI Advisor** accessible depuis la navigation, aucune erreur console lors du chargement.
- Indisponibilité : codes 503 structurés testés côté API ; l'interface expose l'état et n'empêche pas la consultation des résultats déterministes.

---

## 4. Tests exécutés

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh advisory` | **181 tests, OK** (821 s) — inclut les 4 tests de couverture |
| `bash scripts/run_backend_tests.sh advisory.tests.test_security_advisor` (après ajout du throttle) | **30 tests, OK** (184 s) |
| `pnpm exec tsc --noEmit`, `pnpm run build` | OK |
| Recette intégrée (scan réel + chat réel) | 17/17 |

---

## 5. Limites et décisions en attente

- **`AI_ADVISOR_ENABLED=false` en local** : les recommandations automatiques post-scan ne sont donc pas observées en conditions réelles ; leur logique est couverte par les tests. L'activation est un choix d'exploitation (consommation de crédits).
- **Quota IA par offre non décidé** : la limitation actuelle est un plafond par utilisateur (60/h). Rattacher l'usage d'AKA IA aux forfaits (ex. messages/mois par plan) est une décision produit qui reste à prendre ; elle s'implémenterait via `subscriptions/services/quotas.py`, comme les autres quotas.
- **Étiquetage des constats** (vulnérabilité confirmée vs signal à vérifier) : le modèle reçoit sévérité et scanner, mais aucune classification « confirmé / à vérifier » n'est stockée ; l'IA ne peut donc pas l'afficher de façon fiable sans extension du modèle de données.
- **Injection par contenu analysé** : interdiction explicite dans le prompt + balisage « données non fiables » ; aucun test adversarial avec un modèle réel n'a été exécuté (les tests utilisent un client simulé).
- **Coûts** : latence et nombre de constats sont mesurables, mais aucun compteur de tokens/coût n'est persisté localement.
