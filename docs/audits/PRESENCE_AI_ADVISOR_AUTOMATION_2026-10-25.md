# Presence AI Security Advisor — automatisation de bout en bout

**Date :** 2026-10-25
**Périmètre :** `SaaS_Web_Application_digitale_presenz_v2` (Django REST / React / Celery)
**Environnement de vérification :** pile Compose locale (`config.settings.production`), worker Celery avec socket Docker, réseau scanner filtré, cible autorisée `appchat.elomaiapp.com`.
**Aucun déploiement en production n'a été effectué.**

## 1. Conclusion

**Statut : partiellement vérifié en conditions réelles.**

Le parcours automatique est implémenté et prouvé jusqu'à l'ingestion :

1. une politique de scan est stockée par actif et par organisation (`MonitoringConfig.scan_type`) ;
2. la tâche planifiée crée le scan sans intervention (`trigger=monitoring`) ;
3. ZAP s'exécute réellement en conteneur, son rapport est ingéré, dédupliqué et rejoué de façon idempotente ;
4. un scan incomplet (Nuclei interrompu par le délai) n'invente aucun constat et ne résout rien ;
5. l'analyse IA est déclenchée automatiquement après persistance, sans jamais bloquer le scan ni les alertes ;
6. l'interface expose l'état du scan, la politique, les constats et les recommandations, avec un lien contextuel vers le chat.

Deux points n'ont **pas** pu être validés en réel :

- **Nuclei** dépasse systématiquement son délai sur cette cible (180 s puis 300 s) : ses résultats ne sont donc pas ingérés par le pipeline (comportement sûr, voir §6.2).
- **AKA IA** a répondu `502` sur les deux modèles pendant toute la fenêtre de test : aucune réponse IA réelle n'a été produite. Le repli déterministe, le `503` propre du chat et le nouvel espacement des tentatives ont en revanche été vérifiés.

L'import manuel de rapports ZAP/Nuclei reste disponible, mais n'est plus le chemin principal.

## 2. Audit initial

### 2.1 Déjà présent et réutilisé

| Élément | État constaté |
|---|---|
| Adaptateurs ZAP | `scanners/implementations/zap.py`, transport Docker et sidecar API, baseline passive par défaut (`SCANNER_ZAP_ACTIVE_SCAN=false`) |
| Adaptateur Nuclei | `scanners/implementations/nuclei.py`, image Docker officielle, templates montés, profil `cve,exposure,misconfig` |
| Exécution asynchrone | `ScanOrchestrator` + tâches Celery `run_authenticated_scan`, limites CPU/RSS/temps, validation anti-SSRF de la cible |
| Statuts de scan | `pending/queued/running/completed/failed/cancelled`, progression, `ScannerRun`, `Scan.steps` |
| Ingestion manuelle | `advisory/parsers.py` + `advisory/services/ingestion.py` + endpoint `POST …/scans/import/` |
| Conseiller IA | Client AKA (`aka_client.py`), service de chat, endpoint `POST …/ai-advisor/chat/`, 503 normalisé |
| Recommandations IA | `AIRecommendationRun` idempotent par `(scan, input_hash)`, `AIRecommendation`, repli déterministe |
| Audit social | `SocialAuditEvent` (hors périmètre de cette mission) |

### 2.2 Écarts constatés

1. Les résultats ZAP/Nuclei n'alimentaient **pas** le modèle `SecurityFinding` : seuls les `scans.Finding` et `CheckResult` existaient.
2. Aucune politique de scan par actif : `run_due_monitors` ne savait lancer que des contrôles de santé.
3. Aucun endpoint de lecture des constats de sécurité par actif.
4. Le chat n'acceptait aucun contexte d'actif : il répondait toujours sur toute l'organisation.
5. Aucun bloc d'interface ne reliait scan → constats → analyse IA.
6. Le worker conteneurisé ne pouvait pas monter le répertoire temporaire de ZAP : `tempfile` retombait silencieusement sur `/tmp`, que le démon Docker ne voit pas (`bind source path does not exist`). Le code d'ingestion d'alors créait en plus un faux constat « ZAP sandbox unavailable » et résolvait les vrais constats ZAP.
7. Une panne fournisseur (`AkaServerError`) ne déclenchait aucune reprise : le scan restait définitivement sans analyse IA.

## 3. Implémentation

### 3.1 Phase A — orchestration et politique

- `MonitoringConfig.scan_type` (`health`, `security`, `full`) + migration `monitoring/0002_monitoringconfig_scan_type.py`.
- `monitoring/tasks.py::run_due_monitors` crée le `Scan` avec la politique de l'actif, refuse un second scan actif, respecte les fenêtres de silence et plafonne le nombre de scans par passage.
- `POST /api/v1/monitoring/websites/<id>/scan/` : « Scan now » ponctuel, réservé aux rôles d'écriture, `409` si un scan est déjà actif, `scan_type` optionnel.
- `PATCH /api/v1/monitoring/websites/<id>/` : changement de politique, contrôlé par le rôle.
- Un actif créé reçoit immédiatement une politique de contrôle de santé ; les scanners actifs restent opt-in (aucun trafic intrusif déclenché par défaut).

### 3.2 Phase B — ingestion et déduplication automatiques

`advisory/services/scan_ingestion.py` :

- convertit les `NormalizedFinding` de ZAP/Nuclei en `ParsedReport` borné (nom, description, preuve) ;
- fusionne les doublons d'un même rapport (même nom) ;
- appelle `ingest_report(..., resolve_missing=complete)` : upsert par `(asset, scanner_source, vulnerability_name)`, réouverture si revu, résolution des absents uniquement pour un scan **complet** ;
- ignore les runs où l'outil n'a pas réellement scanné (`*.sandbox_unavailable`, `*.timeout`, `*.blocked`, …) : aucun constat fantôme, aucune résolution abusive ;
- ne traite jamais un actif invité ou sans organisation ;
- toute erreur est journalisée et absorbée par l'orchestrateur : un incident d'ingestion ne transforme pas un scan réussi en échec.

### 3.3 Phase C — analyse IA automatique

- Déclenchement après persistance : `_finalize_scan` → `_dispatch_advisor` (uniquement pour un scan `completed`, drapeau `AI_ADVISOR_ENABLED` revérifié dans la tâche).
- Idempotence : `(scan, input_hash)` empêche une double analyse sur reprise ; un run `running` n'est pas réclamé par un second worker.
- Reprise contrôlée ajoutée dans `advisory/services/advisor.py` : les erreurs transitoires (`AkaServerError`, timeout, connexion, circuit ouvert) sont désormais reprises par Celery avec backoff borné (max 3, 30 s à 900 s), au même titre que les quotas. Les réponses invalides ne sont pas rejouées.
- Le contenu des rapports reste une donnée non fiable : prompt système strict, preuves bornées, aucune instruction issue d'un constat n'est suivie.
- Échec IA : le scan, ses constats et les alertes restent intacts ; l'API sert le repli déterministe.

### 3.4 Phase D — interface

- `AssetSecurityPanel.tsx`, intégré à la page de détail d'un actif :
  - dernier scan (type, date, statut, échec éventuel), politique planifiée et prochaine échéance ;
  - sélecteur de politique pour les rôles autorisés, bouton « Run full scan » ;
  - constats ouverts/résolus, sévérité, source, date, état vide honnête ;
  - recommandations IA du dernier scan complété, avec origine (`ai` ou repli déterministe) et erreur du run ;
  - lien « Discuss findings » / « Ask the advisor » vers `/app/advisor?org=…&asset=…`.
- Aucune progression simulée : tout provient des réponses API.

### 3.5 Phase E — chat contextualisé

- L'endpoint accepte `asset_id` optionnel, résolu **dans l'organisation du chemin** ; un actif d'un autre locataire répond `404`.
- Le service ne charge que les constats ouverts de cette organisation (et de cet actif), triés par sévérité, bornés en nombre et en taille.
- La page `/app/advisor` lit `?org=` et `?asset=`, recharge l'actif via l'API (donc avec le contrôle d'appartenance) et ne conserve le focus que si `asset.organization_id == org sélectionnée`.
- Aucune action technique n'est exécutable depuis le chat.

### 3.6 Phase F — permissions et durcissement

- Lecture des constats : tout rôle membre ; import : owner/admin ; chat : owner/admin/analyst ; scan/politique : owner/admin/analyst.
- Isolation : filtre `organization` en première condition, actif résolu dans le locataire, `404` (et non `403`) pour ne pas énumérer les identifiants.
- Cibles : validation anti-SSRF existante réutilisée avant chaque scan ; les scanners reste limités par CPU/RSS/temps et par le sémaphore Redis de concurrence.
- Aucune preuve brute (`proof_or_payload`) dans l'API de lecture ; le chat en reçoit une version bornée.
- Secrets jamais exposés au frontend ni journalisés ; les erreurs fournisseur sont réduites à un code stable.

## 4. Preuves d'exécution réelle

### 4.1 Déclenchement planifié

Politique forcée à `full` sur l'actif de test (site `24`, organisation `a694ddef-a833-4d17-bc0c-44804a74180b`), `next_scan_at = now`, puis appel réel de la tâche planifiée :

```text
run_due_monitors.delay()  →  Scan #3566
scan 3566  trigger=monitoring  type=full  status=completed  progress=100  score=69
```

Log worker :

```text
Queued monitoring scan 3566 for appchat.elomaiapp.com type=full
```

La politique a ensuite été restaurée à `health` avec son échéance d'origine.

### 4.2 ZAP réel et ingestion

```text
delegating 'zap' to SSRF-validated target appchat.elomaiapp.com (timeout=300s, mem=1536MB)
zap: completed en 132 834 ms
security_report_ingested source=zap received=12 created=5 updated=7 resolved=1
ScanOrchestrator: ingested zap findings for scan 3566
```

Le constat fantôme créé par l'ancien code (« ZAP sandbox unavailable », statut `open`) a été **résolu automatiquement** par ce rapport complet.

Deuxième scan de contrôle (`#3567`, type `security`, ZAP 113 062 ms) :

```text
security_report_ingested source=zap received=12 created=0 updated=12 resolved=0
```

→ idempotence et déduplication confirmées sur la base réelle : 14 lignes au total, 13 ouvertes, aucune duplication.

### 4.3 Nuclei réel

```text
scan 3566 : nuclei running → completed en 202 230 ms (limite 180 s)
scan 3567 : nuclei running → completed en 320 880 ms (limite 300 s)
security_ingestion_skipped scanner=nuclei reason=tool_not_executed
```

Nuclei a bien été lancé dans son conteneur, mais le délai expire avant la fin du jeu de templates. Conformément à la règle de sûreté, **rien n'est ingéré et rien n'est résolu**. Le constat Nuclei antérieur reste ouvert, ce qui est correct : un scan incomplet ne prouve pas sa disparition.

Le délai par défaut est passé de 180 s à 300 s (`SCANNER_TIMEOUT_NUCLEI`). Une exécution à 300 s a toutefois encore expiré : un profil de templates plus court ou un budget dédié reste nécessaire pour une couverture Nuclei fiable.

### 4.4 Analyse IA

Dispatch automatique observé :

```text
AI advisor queued for scan 3566
aka_ai_retry status=502 … (modèle 1, 2 tentatives)
ai_advisor_model_failed model=groq/qwen/qwen3.8-27b
aka_ai_retry status=502 … (modèle 2)
ai_advisor_model_failed model=ddgw/gpt-5.4-mini
AI advisor finished scan=3566 status=failed fallback=True
```

- `AIRecommendationRun` : `failed`, `error_code=AkaServerError`, `attempts=1`.
- `GET /api/v1/advisory/recommendations/?scan_id=3566` : `200`, `source=deterministic`, **12 recommandations** déterministes, `run.status=failed`.
- Nouvelle politique de reprise vérifiée : `AI advisor … retrying scan=3566 in 120s (attempt 1/3)`.
- Chat réel : `POST …/ai-advisor/chat/` avec `asset_id=24` → **503** `{"error":"ai_unavailable"}`, `Cache-Control: no-store`, après épuisement borné des deux modèles. Aucune fuite de prompt, de preuve ou de secret dans la réponse.
- Aucune réponse IA réelle n'a donc été obtenue : le fournisseur AKA était indisponible (`502`) pendant toute la fenêtre.

### 4.5 API et isolation (client DRF authentifié, HTTPS forcé)

| Vérification | Résultat |
|---|---|
| Constats de l'actif | `200`, `count=13`, champs `id, asset_id, scanner_source, vulnerability_name, severity, status, description, detected_at, resolved_at, has_proof` |
| Preuve brute exposée | non (`proof_or_payload` absent) |
| Filtres `status=all&source=zap&severity=medium` | `200`, `count=3` |
| Actif d'un autre locataire | `404` |
| Chat avec actif d'un autre locataire | `404` `{"detail":"Asset not found."}` |
| Requête anonyme | `401` |

## 5. Tests et validations exécutés

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh advisory` | **167 tests OK** |
| `bash scripts/run_backend_tests.sh advisory.tests.test_resilience advisory.tests.test_tasks advisory.tests.test_scan_ingestion advisory.tests.test_asset_security_api advisory.tests.test_security_advisor` (après ajout du retry) | **69 tests OK** |
| `bash scripts/run_backend_tests.sh monitoring` | **30 tests OK** |
| `bash scripts/run_backend_tests.sh scans websites` | **214 tests OK** |
| `bash scripts/run_backend_tests.sh scanners` | **99 tests OK** |
| `python manage.py check` | aucune anomalie |
| `python manage.py makemigrations --check --dry-run` | « No changes detected » |
| `npx tsc --noEmit` (frontend) | aucune erreur |
| `npm run build` (frontend) | succès, 31 routes prérendues |

La suite backend **complète** n'a pas été relancée ; seules les applications affectées l'ont été. Les tests couvrent notamment : isolation des actifs, déclenchement planifié, limites de concurrence, upsert/déduplication, résolution conditionnelle, ingestion après scan, idempotence des runs IA, indisponibilité fournisseur, isolation des constats et du chat.

## 6. Limites et éléments non vérifiés

### 6.1 Fournisseur AKA indisponible

`502` sur les deux routes de modèles. Aucune analyse IA réelle produite. Le comportement de repli et de reprise est vérifié, mais la qualité des réponses IA ne l'est pas. Le drapeau `AI_ADVISOR_ENABLED` a été activé temporairement pour le test puis **remis à `false`** ; le chat reste utilisable indépendamment de ce drapeau.

### 6.2 Nuclei

Délai dépassé à 180 s puis à 300 s sur une cible réelle avec le jeu complet de templates. Conséquences :

- aucune résolution abusive (voulu) ;
- pas de nouveaux constats Nuclei automatiques tant que le profil n'est pas allégé ;
- le constat Nuclei existant reste ouvert.

Pistes : profil `exposure,misconfig` sans `cve`, jeu de templates dédié, ou budget de scan séparé avec reprise partielle des résultats déjà émis.

### 6.3 Autres scanners

`nmap`, `nikto`, `whatweb`, `testssl`, `dnsrecon`, `gobuster`, `lighthouse` sont `unavailable` dans cette pile (binaires absents du worker). Ils restent hors du chemin automatique actuel ; seuls ZAP et Nuclei alimentent `SecurityFinding`.

### 6.4 Analyse IA globale

Le modèle persistant fournit des recommandations **par constat** (titre, résumé, action, effort, priorité, confiance). Il n'existe pas encore d'objet « synthèse d'actif » persistant avec impact, étapes de vérification et limitations ; ces éléments sont produits à la demande par le chat contextualisé. C'est la principale dépendance restante pour une conformité complète à la Phase C.

### 6.5 Rendu des recommandations déterministes

Le repli reprend parfois la description HTML brute de ZAP (`<p>…`). Le rendu frontend assainit le Markdown, mais un nettoyage côté serveur serait préférable.

### 6.6 Historique et synthèse d'actif

Le panneau affiche le dernier scan, les constats courants (ouverts et résolus avec leurs dates) et les recommandations du dernier scan complété. Il n'existe pas encore de vue « historique des analyses » (liste des scans avec leur synthèse) ni de courbe d'évolution du nombre de constats. Les données nécessaires (`Scan`, `SecurityFinding.detected_at/resolved_at`, `AIRecommendationRun`) sont persistées et permettraient de l'ajouter sans nouvelle collecte.

## 7. Risques et dépendances

- **Coût IA** : une analyse est déclenchée pour chaque scan complété lorsque le drapeau est actif, y compris les scans de santé. Le kill switch reste la protection ; un filtrage « aucun constat » et une réutilisation inter-scans inchangés réduiraient la facture.
- **Egress des scanners** : dépend du réseau `presence_scanner_sandbox` et de l'image pré-tirée ; le worker possède le socket Docker (pouvoir équivalent root sur l'hôte) et doit rester isolé du web.
- **Templates Nuclei** : volume de 86 Mo monté depuis l'hôte (`/tmp/presence-scanner/nuclei-templates`) ; à rendre persistant et versionné en production.
- **Répertoire partagé ZAP** : doit être accessible en écriture au worker (`1777`) sur le même chemin que sur l'hôte ; une erreur de permission est désormais journalisée explicitement.
- **Reprise IA** : les reprises sont bornées (3) ; au-delà, le run reste `failed` et aucune analyse ultérieure n'est planifiée automatiquement pour ce scan.
- **Isolation** : vérifiée par tests et par appels API réels (404/401), mais la suite complète multi-tenant n'a pas été rejouée.

## 8. Fichiers principaux

**Backend**

- `advisory/services/scan_ingestion.py` (nouveau) — ingestion automatique ZAP/Nuclei vers `SecurityFinding`.
- `advisory/services/advisor.py` — reprise des erreurs transitoires.
- `advisory/services/security_advisor.py`, `advisory/views.py`, `advisory/serializers.py`, `advisory/urls.py` — constats par actif, chat avec `asset_id`.
- `monitoring/models.py`, `monitoring/migrations/0002_monitoringconfig_scan_type.py`, `monitoring/tasks.py`, `monitoring/views.py`, `monitoring/serializers.py` — politique par actif et déclenchement.
- `scans/services/orchestrator.py`, `scans/tasks.py` — ingestion après scan et dispatch IA.
- `scanners/executors/sandbox.py`, `scanners/implementations/zap.py` — répertoire partagé et erreurs explicites.
- `config/settings/base.py` — délai Nuclei, réglage du répertoire partagé.
- `advisory/tests/test_scan_ingestion.py`, `advisory/tests/test_asset_security_api.py`, `monitoring/tests/test_scan_policy.py`, `advisory/tests/test_resilience.py`.

**Frontend**

- `src/components/AssetSecurityPanel.tsx` — bloc scan/constats/recommandations.
- `src/pages/WebsiteDetails.tsx` — intégration du bloc.
- `src/pages/SecurityAdvisor.tsx`, `src/components/SecurityAdvisorChat.tsx` — contexte d'actif.
- `src/api/endpoints.ts`, `src/api/types.ts` — contrats API.

**Infrastructure**

- `docker-compose.yml` — `SCANNER_SANDBOX_SHARED_WORK_DIR` sur le worker.
- `backend/.env.example` — documentation du répertoire partagé et des délais.

## 9. Ce qui reste à faire avant de déclarer l'automatisation « terminée »

1. Rétablir AKA IA et rejouer un scan complet pour obtenir une analyse IA réelle persistée.
2. Alléger le profil Nuclei (ou augmenter son budget) jusqu'à obtenir une ingestion réelle reproductible.
3. Ajouter la synthèse d'actif persistée (impact, étapes de vérification, limitations) si elle est requise par le produit.
4. Nettoyer les descriptions HTML du repli déterministe.
