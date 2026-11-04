# Presence — Lot D : API REST du parcours progressif

**Version du lot :** 2026-10-30
**Validation d'exécution :** 2026-11-04
**Périmètre :** couche HTTP uniquement — exposition des services du Lot B.
**Statut final :** **VALIDÉ TECHNIQUEMENT** — 44 tests API verts, suite backend complète verte, aucune migration, aucun service métier modifié.

---

## 1. Synthèse exécutive

Le Lot D expose le parcours progressif via cinq opérations REST, sans réimplémenter aucune règle métier :

- `POST /api/v1/scan-journeys/` — admission et création du palier 1 ;
- `GET /api/v1/scan-journeys/` — liste paginée, filtrée par site et par état ;
- `GET /api/v1/scan-journeys/{id}/` — détail avec les scans enfants ;
- `POST /api/v1/scan-journeys/{id}/advance/` — confirmation du palier 2 ;
- `POST /api/v1/scan-journeys/{id}/cancel/` — annulation.

La vue ne fait que : valider l'entrée, résoudre le site dans le périmètre de lecture (404 hors organisation), appeler `JourneyService`, puis traduire ses exceptions en codes HTTP. Aucune transition d'état, aucun verrou, aucun quota n'est recalculé dans la couche API.

### Résultats vérifiés

| Contrôle | Résultat |
|---|---|
| Tests API dédiés | **44 tests OK**, 10,294 s, exit 0 |
| Suite backend complète | **1 146 tests OK**, 1 108,517 s, exit 0 |
| Migrations | `makemigrations --check --dry-run` → **No changes detected** |
| `manage.py check` | **System check identified no issues (0 silenced)** |
| Services du Lot B | aucun diff sur `journey_service.py`, `exceptions.py`, `orchestrator.py`, `tasks.py` |
| Schéma / migrations | aucun diff |
| Frontend / Docker / workers | aucun diff |

---

## 2. Fichiers créés et modifiés

### 2.1 Fichiers modifiés

| Fichier | Modification |
|---|---|
| `backend/scans/serializers.py` | ajout de `ScanSummarySerializer`, `JourneyCreateSerializer`, `JourneyListSerializer`, `JourneyDetailSerializer` |
| `backend/scans/views.py` | ajout de `JourneyWritePermission`, `JourneyViewSet` et du helper de périmètre `_journey_websites_for` |
| `backend/scans/urls.py` | enregistrement du routeur `scan-journeys` |
| `docs/audits/PRESENCE_LOT_D_API_2026-10-30.md` | ce rapport |

### 2.2 Fichiers créés

| Fichier | Contenu |
|---|---|
| `backend/scans/tests/test_journey_api.py` | 44 tests API (création, liste, détail, avancement, annulation, matrice de rôles) |

### 2.3 Fichiers explicitement non modifiés

`JourneyService`, `scans/services/exceptions.py`, `ScanJourney`, `Scan`, `CheckResult`, `Finding`, `ScannerRun`, migrations, orchestrateur, pipeline de scan, tâches Celery, profils Nuclei, étapes de scan, frontend, alertes, scoring, monitoring, reaper, endpoints existants `/scans/` et `/monitoring/`.

Aucune migration n'a été générée.

---

## 3. Endpoints implémentés

Toutes les routes sont sous le préfixe existant `/api/v1/`, via le `DefaultRouter` déjà utilisé par `scans/urls.py`. L'authentification est celle du projet : JWT (`rest_framework_simplejwt`) ou clé API (`subscriptions.authentication.ApiKeyAuthentication`).

### 3.1 Créer un parcours

```http
POST /api/v1/scan-journeys/
Content-Type: application/json

{"website": 42}
```

| Code | Condition | Corps |
|---|---|---|
| `201` | parcours créé, scan palier 1 `queued` | `JourneyDetailSerializer` : id, website, website_url, requested_by, state, current_stage, total_stages, expires_at, created_at, updated_at, scans |
| `400` | `website` absent ou non entier | `{"website": [...]}` |
| `401` | non authentifié | `{"detail": "..."}` |
| `403` | viewer (rôle insuffisant) | `{"detail": "Rôle viewer insuffisant pour lancer un scan"}` |
| `404` | site inexistant ou hors organisation | `{"detail": "Site introuvable."}` |
| `409` | parcours actif existant | `{"detail": "...", "journey_id": 1, "state": "running"}` |
| `429` | quota mensuel dépassé | `{"detail": "...", "used": 10, "limit": 10}` |

Le site est d'abord résolu dans le périmètre de lecture de l'utilisateur : un site étranger renvoie **404**, jamais **403**, conformément au contrat. Le service applique ensuite la matrice d'écriture (403 pour un viewer).

### 3.2 Lister les parcours

```http
GET /api/v1/scan-journeys/?website=42&state=awaiting_confirmation
```

| Code | Condition |
|---|---|
| `200` | liste paginée (`count`, `next`, `previous`, `results`) |
| `401` | non authentifié |

- sans superuser : uniquement les parcours des sites de l'organisation de l'utilisateur ;
- superuser : tous les parcours ;
- `website` filtre par identifiant de site ;
- `state` filtre par état (`running`, `awaiting_confirmation`, `completed`, `partial`, `failed`, `expired`, `cancelled`). Une valeur inconnue renvoie une liste vide, pas une erreur ;
- tri `-created_at`, pagination globale du projet (`PageNumberPagination`, 50 par page).

### 3.3 Détail d'un parcours

```http
GET /api/v1/scan-journeys/{id}/
```

| Code | Condition |
|---|---|
| `200` | parcours accessible, avec `scans` (résumé des scans enfants) |
| `401` | non authentifié |
| `404` | parcours inexistant ou hors organisation |

Le corps contient les champs du parcours et un tableau `scans` :

```json
{
  "id": 1,
  "website": 42,
  "website_url": "https://example.com",
  "requested_by": 5,
  "state": "awaiting_confirmation",
  "current_stage": 1,
  "total_stages": 2,
  "expires_at": "2026-10-31T12:00:00Z",
  "created_at": "2026-10-30T12:00:00Z",
  "updated_at": "2026-10-30T12:05:00Z",
  "scans": [
    {
      "id": 101,
      "journey_stage": 1,
      "status": "completed",
      "quota_charged": true,
      "created_at": "2026-10-30T12:00:00Z",
      "completed_at": "2026-10-30T12:04:00Z"
    }
  ]
}
```

### 3.4 Avancer un parcours

```http
POST /api/v1/scan-journeys/{id}/advance/
Content-Type: application/json

{}
```

| Code | Condition | Corps |
|---|---|---|
| `200` | palier 2 créé et publié | `JourneyDetailSerializer`, `state=running`, `current_stage=2` |
| `400` | état incompatible | `{"detail": "...", "current_state": "running"}` |
| `401` | non authentifié | `{"detail": "..."}` |
| `403` | viewer | `{"detail": "..."}` |
| `404` | parcours inexistant ou hors organisation | `{"detail": "..."}` |
| `409` | scan classique actif sur le site | `{"detail": "..."}` |
| `410` | fenêtre de confirmation expirée | `{"detail": "...", "expired_at": "..."}` |

Cas particulier hérité du Lot B : si Nuclei est désactivé (`SCANNER_ADVANCED_SECURITY_ENABLED=False`), le service persiste `state=failed` et retourne le parcours. La vue répond alors **200** avec `state=failed`, sans créer de palier 2. Ce n'est pas une erreur HTTP : l'état est la réponse métier. Voir §10.

### 3.5 Annuler un parcours

```http
POST /api/v1/scan-journeys/{id}/cancel/
```

| Code | Condition |
|---|---|
| `200` | parcours annulé, scans actifs passés à `cancelled` |
| `400` | parcours déjà terminal (`current_state` fourni) |
| `401` | non authentifié |
| `403` | viewer |
| `404` | parcours inexistant ou hors organisation |

Une seconde annulation renvoie `400` : l'opération n'est pas idempotente au sens HTTP, le service refusant tout état terminal.

---

## 4. Sérialiseurs

Ajoutés à `backend/scans/serializers.py`, sans modifier les sérialiseurs existants.

### 4.1 `JourneyCreateSerializer`

| Champ | Type | Règle |
|---|---|---|
| `website` | `IntegerField(min_value=1)` | requis ; résolu dans le périmètre de lecture par la vue (404 si inconnu ou étranger) |

Le champ est volontairement un entier et non un `PrimaryKeyRelatedField` global : cela permet de distinguer un identifiant invalide (400) d'un site inexistant ou hors organisation (404), sans exposer l'existence des sites d'autres tenants.

### 4.2 `JourneyListSerializer`

`id`, `website`, `website_url`, `state`, `current_stage`, `total_stages`, `expires_at`, `created_at`, `updated_at`. Tous en lecture seule.

`website_url` est un `SerializerMethodField` qui renvoie `https://<website.domain>` : le modèle `Website` n'a pas de champ URL, seulement un domaine.

### 4.3 `JourneyDetailSerializer`

Hérite de `JourneyListSerializer` et ajoute :

- `requested_by` (identifiant du demandeur, nullable si le compte a été supprimé) ;
- `scans` : `ScanSummarySerializer(source="stages", many=True)`.

`source="stages"` correspond au `related_name` réel de `Scan.journey`.

### 4.4 `ScanSummarySerializer`

`id`, `journey_stage`, `status`, `quota_charged`, `created_at`, `completed_at`. Tous en lecture seule. Aucun champ de résultat ni de finding n'est exposé ici : le détail complet reste disponible via `/api/v1/scans/{id}/`.

---

## 5. Permissions

### 5.1 Mécanisme

- `permission_classes = [IsAuthenticated, JourneyWritePermission]` ;
- `JourneyWritePermission.has_object_permission` applique la matrice existante `check_write_permission` du Lot B sur le site du parcours ;
- les méthodes sûres (`GET`) sont toujours autorisées à un membre de l'organisation ;
- la création n'a pas d'objet : le service vérifie le rôle d'écriture, la vue ayant déjà résolu le site dans le périmètre de lecture.

La vérification est donc faite deux fois pour les mutations : permission objet (403 immédiat) puis service (défense en profondeur). Aucune règle métier n'est dupliquée : la permission appelle la fonction du Lot B.

### 5.2 Matrice rôles × actions

| Acteur | Liste | Détail | Création | Avancement | Annulation |
|---|---|---|---|---|---|
| Owner | 200 | 200 | 201 | 200 | 200 |
| Admin | 200 | 200 | 201 | 200 | 200 |
| Analyst | 200 | 200 | 201 | 200 | 200 |
| Viewer | 200 | 200 | 403 | 403 | 403 |
| Hors organisation | liste vide | 404 | 404 | 404 | 404 |
| Superuser | tous | tous | 201 | 200 | 200 |
| Anonyme | 401 | 401 | 401 | 401 | 401 |

L'isolation inter-organisations est portée par `website_access_q` (organisations), avec un cas explicite pour le superuser, que ce Q object ne couvre pas.

---

## 6. Gestion des erreurs

### 6.1 Mapping exceptions → HTTP

| Exception / condition | Code | Corps enrichi |
|---|---|---|
| `JourneyConflictError` (création) | `409` | `journey_id`, `state` du parcours actif |
| `JourneyConflictError` (avancement) | `409` | `detail` |
| `JourneyStateError` | `400` | `current_state` |
| `JourneyExpiredError` | `410` | `expired_at` |
| `QuotaExceededError` | `429` | `used`, `limit` |
| `PermissionError` | `403` | `detail` |
| `Website` introuvable / hors périmètre | `404` | `detail` |
| `ScanJourney` introuvable / hors périmètre | `404` | `detail` |
| Champ `website` invalide | `400` | erreurs DRF par champ |

Les exceptions du Lot B ne portent pas d'attributs structurés (`journey_id`, `used`, `limit`, `expired_at`, `current_state`). La vue relit ces valeurs en lecture seule après l'exception, sans modifier le service ni relancer l'opération. Si le parcours a disparu entre-temps, les champs concernés restent absents ou nuls.

Les exceptions non prévues remontent au gestionnaire DRF global : la vue n'attrape jamais `Exception`.

### 6.2 Format

Le format existant est conservé : `{"detail": "..."}` pour les erreurs simples, erreurs par champ pour la validation DRF. Les messages propres au parcours sont en français, comme le service du Lot B ; les messages de validation DRF restent dans la langue configurée du projet.

---

## 7. Tests API

Fichier : `backend/scans/tests/test_journey_api.py` — **44 tests, 10,294 s, exit 0**.

| Classe | Nb | Couverture |
|---|---:|---|
| `JourneyCreateAPITests` | 10 | 201 + scan palier 1 publié, 400 champ absent/invalide, 401, 403 viewer, 404 site inconnu/étranger, 409 parcours actif, 429 quota (`used`/`limit`), double POST = un seul parcours |
| `JourneyListAPITests` | 7 | périmètre organisation, filtres `website` et `state`, superuser, pagination standard, 401, lecture viewer |
| `JourneyDetailAPITests` | 6 | détail + scans enfants, champs exacts, 404 hors organisation/inconnu, 401, lecture viewer |
| `JourneyAdvanceAPITests` | 9 | 200 + palier 2 `quota_charged=False` publié, 400 running/completed, 410 expiré, 409 scan classique, Nuclei désactivé → `failed`, 403 viewer, 404 étranger, 401 |
| `JourneyCancelAPITests` | 7 | annulation en attente/en cours + scan annulé, 400 terminal, seconde annulation 400, 403 viewer, 404 étranger, 401 |
| `JourneyPermissionMatrixAPITests` | 5 | admin et analyst créent, superuser crée/lit hors organisation, outsider 404 |

Les tests utilisent `APITestCase`, `force_authenticate` et `captureOnCommitCallbacks(execute=True)` pour vérifier la publication Celery réelle après commit, sans broker. `run_authenticated_scan.delay` est mocké.

### 7.1 Cas non couverts par les tests API

- exécution réelle des scanners et du pipeline Celery (couvert par les tests du Lot B/C2, pas par la couche HTTP) ;
- pagination au-delà de 50 éléments (comportement global DRF, non spécifique au parcours) ;
- génération du schéma OpenAPI : vérifiée (`manage.py spectacular --validate`, exit 0, cinq routes `scan-journeys` présentes) ; le seul avertissement spécifique est l'absence préexistante d'extension drf-spectacular pour `ApiKeyAuthentication`, commun à toutes les vues.

---

## 8. Non-régression

Commande exécutée depuis la racine du dépôt :

```bash
bash scripts/run_backend_tests.sh
```

Résultat :

```text
Ran 1146 tests in 1108.517s

OK
```

- 1 102 tests existants : **tous verts** ;
- 44 nouveaux tests API : **tous verts** ;
- exit code : **0**.

Aucun test existant n'a été modifié. Les endpoints `/api/v1/scans/`, `/api/v1/scans/{id}/results/` et `/api/v1/monitoring/` gardent leur contrat et leurs sérialiseurs.

---

## 9. Conventions respectées

| Convention existante | Application au Lot D |
|---|---|
| Préfixe `/api/v1/` | route incluse par `config/urls.py`, pas de préfixe dupliqué |
| Routeur DRF | `DefaultRouter` de `scans/urls.py`, `basename="scan-journey"` |
| Vues | `GenericViewSet` + mixins, comme `ScanViewSet` (lecture seule) |
| Authentification | JWT + clé API par défaut, aucun override |
| Permission de base | `IsAuthenticated` |
| Permission métier | matrice `organizations.access`, comme `WebsiteRolePermission` |
| Pagination | `PageNumberPagination` globale, 50 par page, format `count/next/previous/results` |
| Erreurs | `{"detail": ...}`, `NotFound` DRF pour les 404 |
| Requêtes | `select_related("website", "requested_by")`, `prefetch_related("stages")` |
| Documentation | `@extend_schema(tags=["scan-journeys"])`, `request=None` pour les actions sans corps |
| Style | type hints, `from __future__ import annotations`, docstrings courtes |

Aucun nouveau style, aucun package, aucune dépendance.

---

## 10. Limites connues

1. **Double POST = 409, pas 200 idempotent.** Le service du Lot B lève `JourneyConflictError` sur un parcours actif ; la vue le traduit en 409, conformément au contrat du Lot B. Le rapport de conception évoquait un 200 idempotent pour le même demandeur : ce comportement n'a pas été introduit, car il aurait fallu modifier le service ou interpréter l'exception au niveau HTTP.
2. **Nuclei désactivé = 200 avec `state=failed`.** Le service persiste l'échec et retourne le parcours ; la vue ne peut pas distinguer ce cas d'un avancement réussi sans inspecter l'état. Un client doit donc lire `state` et pas seulement le code HTTP. Un code dédié (409/503) aurait exigé un nouveau contrat du Lot B.
3. **`website_url` synthétique.** `Website` n'a pas de champ URL : la valeur est `https://<domain>`. Le schéma et le port réel du site ne sont pas connus de ce modèle.
4. **Pas de `journey_id`/`journey_stage` sur `/scans/{id}/`.** Le sérialiseur existant n'a pas été modifié (interdiction de toucher aux endpoints existants). Les scans enfants restent visibles dans le détail du parcours ; un client qui part d'un scan ne peut pas retrouver son parcours par cet endpoint.
5. **Enrichissement des erreurs par relecture.** Les exceptions du Lot B ne portent pas d'attributs ; `journey_id`, `state`, `used`, `limit`, `expired_at` et `current_state` sont relus après coup. En cas de suppression concurrente, un champ peut être absent.
6. **429 pour le quota du parcours, 403 pour le quota classique.** Le contrat Lot D impose 429 ; les endpoints existants (`/monitoring/.../scan/`) conservent le 403 structuré de `QuotaExceeded`. L'incohérence est assumée et documentée ; un client frontend doit gérer les deux.
7. **Filtre `state` non validé.** Une valeur inconnue renvoie une liste vide (comportement d'un filtre Django), pas un 400. Cela évite un enum dupliqué dans la couche API.
8. **Pas de throttle dédié.** Les limites globales DRF s'appliquent ; aucun `throttle_scope` n'est ajouté, le Lot D ne demandant pas de limite spécifique.
9. **Pas de test end-to-end API + Celery.** La publication est vérifiée après commit, mais les scanners sont mockés. Le parcours complet sur une cible publique autorisée reste à valider (Lot d'intégration).

---

## 11. Prochaines étapes

| Lot | Contenu | Dépendance |
|---|---|---|
| Intégration | Parcours complet via API + Celery sur cible publique autorisée | Lot D + B + C2 |
| Lot E | Reaper des parcours (expiration, réconciliation `running` orphelin), métriques | Lot B |
| Lot F | Frontend : bouton « Continuer », compte à rebours, états `partial`/`failed`/`expired` | Lot D |
| Lot C3 | Retrait de Nikto du palier 2 | test end-to-end |

---

## 12. Statut final

**VALIDÉ TECHNIQUEMENT** :

- 44 tests API verts, exit 0 ;
- suite backend complète verte (voir §8) ;
- permissions owner/admin/analyst/viewer/superuser/hors organisation vérifiées ;
- isolation inter-organisations vérifiée (404) ;
- aucun service métier, schéma, migration, orchestrateur ou tâche modifié ;
- aucune migration générée, aucun déploiement.

**À VÉRIFIER MANUELLEMENT** :

- parcours complet via API + Celery sur une cible publique autorisée ;
- comportement du frontend sur `state=failed` après avancement sans Nuclei ;
- rendu visuel du schéma dans Swagger/Redoc (les routes et les tags `scan-journeys` sont bien générés).

**BLOQUÉ** : aucun.

**ÉCHEC** : aucun.
