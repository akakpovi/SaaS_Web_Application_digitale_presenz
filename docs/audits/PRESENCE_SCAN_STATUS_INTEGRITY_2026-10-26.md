# Présence — Intégrité des statuts de scan et archives

**Date :** 2026-10-26
**Périmètre :** agrégation des statuts `Scan` / `ScannerRun` / étapes, propagation Celery, API, interface, montage des archives du worker
**Statut :** amélioré et vérifié par les tests et le build — validation réelle de bout en bout non effectuée
**Référence :** `NUCLEI_POSITIVE_INGESTION_2026-10-26.md`

---

## 1. Audit initial et cause racine

### 1.1 Constat sur le scan 3584

| Élément | Valeur observée |
|---|---|
| `Scan.status` | `completed` |
| `ScannerRun.status` (Nuclei) | `timeout` |
| Étape Nuclei | `timeout` |
| Ingestion | bloquée correctement (`complete=False`) |
| Résolution de constats | aucune |

### 1.2 Cause racine confirmée

Le défaut n'était pas un problème d'affichage. Il était dans l'orchestrateur :

1. `ScanOrchestrator.run()` exécutait toutes les étapes, puis appelait systématiquement `scan.transition_to(Scan.Status.COMPLETED)`.
2. Le chemin de timeout de `_run_scanner()` marquait bien le `ScannerRun` et l'étape en `timeout`, mais **retournait normalement** à la boucle d'orchestration.
3. `_run_all_steps()` se terminait sans erreur ; l'orchestrateur considérait donc l'exécution comme terminée et forçait `completed` sur le `Scan`.
4. Le modèle `Scan` ne possédait que `completed` pour exprimer une fin technique. Il ne pouvait pas distinguer un scan complet d'un scan partiel.
5. `_finalize_scan()` et `run_authenticated_scan()` traitaient ensuite `completed` comme un succès complet : alertes, recommandations et déclenchement de l'analyse IA pouvaient partir malgré un scanner en timeout.

L'ingestion était déjà correcte : elle s'appuie sur `ScannerRun.complete` et non sur le seul statut du `Scan`. C'est pourquoi 3584 n'a produit aucune résolution abusive, alors que son statut agrégé était faux.

### 1.3 Sémantique avant correction

`completed` signifiait en pratique « l'orchestrateur a fini de s'exécuter », et non « tous les contrôles requis ont abouti ». La correction sépare explicitement ces deux notions.

---

## 2. Règles d'agrégation retenues

La source de vérité est l'orchestrateur, dans `scans/services/status.py`, après exécution de toutes les étapes.

Un scanner est **requis** s'il est présent dans `scan.scanners` et activé dans `settings.SCANNERS`. Un scanner configuré mais volontairement désactivé n'est pas compté comme échec. Le seul cas de doublon de couverture est le scanner Lighthouse avancé, facultatif lorsque la catégorie `performance` historique est déjà contrôlée ; ce comportement préexistant est conservé et documenté.

| Résultat des scanners | Statut agrégé |
|---|---|
| Tous les scanners requis terminent `completed` avec complétude confirmée | `completed` |
| Au moins un résultat exploitable, mais un scanner requis est `timeout`, `partial`, `failed`, indisponible ou ignoré faute de budget | `partial` |
| Aucun résultat exploitable et exécution en échec | `failed` |
| Timeout global sans résultat persistant exploitable | `failed` |
| Timeout d'un scanner avec résultat persistant | `partial` |
| Annulation confirmée | `cancelled` |
| Tâche encore active, en attente ou en reprise | `pending` / `queued` / `running` |

### Choix de modélisation

- `partial` a été ajouté à `Scan.Status` avec la migration `0007_scan_partial_status.py`. C'est une extension minimale nécessaire : aucun statut existant ne permettait de distinguer un scan complet d'un scan partiel.
- Aucun statut agrégé `timeout` n'a été ajouté. Un scan multi-scanners peut avoir un scanner en timeout et un autre réussi ; `partition` décrit mieux l'ensemble. Le détail `timeout` reste disponible sur `ScannerRun` et sur l'étape concernée. Cela évite une nouvelle ambiguïté et une migration supplémentaire.
- `completed` est désormais terminal et ne peut plus être atteint depuis `partial` ou `failed`.
- Les statuts détaillés par scanner sont conservés, même lorsque l'agrégat est `partial` ou `failed`.

---

## 3. Propagation et idempotence

### 3.1 Changements de comportement

- `ScanOrchestrator.run()` calcule le statut via `aggregate_scan_status()` au lieu de forcer `completed`.
- `transition_to()` vérifie la transition demandée. `completed`, `partial`, `failed` et `cancelled` sont terminaux : une réponse tardive ou un retry ne peut plus transformer un timeout en succès.
- La finalisation n'a lieu que si le scan est encore `running` au moment du calcul.
- Si aucun `ScannerRun` n'existe (étape non exécutée), le statut obtenu est `failed`, jamais `completed`.
- `run_authenticated_scan()` vérifie désormais `Scan.Status.COMPLETED`, et non plus seulement `Scan.Status`.
- En cas d'exception Celery, la tâche ne force plus `failed` sur un scan déjà `partial` ou `completed`.
- Les alertes, recommandations automatiques et le déclenchement de l'analyse IA ne sont plus exécutés pour un scan `partial`.

### 3.2 Transitions avant / après

| Situation | Avant | Après |
|---|---|---|
| ZAP terminé, Nuclei en timeout, résultats ZAP persistés | `completed` | `partial` |
| Tous les scanners requis terminés | `completed` | `completed` |
| Tous les scanners en échec | `failed` | `failed` |
| Timeout global sans résultat | `failed` ou `completed` selon le chemin | `failed` |
| Retry Celery après un `partial` | risque d'écrasement | `partial` conservé |
| Résultat tardif après un `failed` | risque de passage en `completed` | refusé |
| Étape sans `ScannerRun` | `completed` possible | `failed` |

---

## 4. Fichiers modifiés

### Backend

| Fichier | Modification |
|---|---|
| `backend/scans/models.py` | ajout de `Scan.Status.PARTIAL` et de sa contrainte de validité |
| `backend/scans/migrations/0007_scan_partial_status.py` | migration de la contrainte et du champ `status` |
| `backend/scans/services/status.py` | **nouveau** : agrégation déterministe, distinction requis/facultatif, calcul des raisons d'incomplétude |
| `backend/scans/services/orchestrator.py` | calcul du statut agrégé, transitions terminales, finalisation conditionnelle, trace des statuts par scanner |
| `backend/scans/services/steps_builder.py` | étape sans `ScannerRun` traitée comme échec explicite |
| `backend/scans/tasks.py` | `completed` requis pour les alertes/IA, préservation d'un statut terminal en cas d'erreur Celery |
| `backend/scans/tests/test_status_integrity.py` | **nouveau** : 13 cas de régression, dont la reproduction du cas 3584 |
| `backend/scans/tests/test_scanner_engine.py` | couverture des nouveaux statuts d'étapes et de l'agrégation |
| `backend/scans/tests/test_orchestrator_delegation.py` | attentes mises à jour vers `Scan.Status.COMPLETED` |
| `backend/scans/tests/test_advanced_security_gate.py` | idem pour les scans délégués |
| `backend/monitoring/services.py` | événement `Scan incomplete` pour les scans `partial` |
| `backend/monitoring/tests/test_overview_api.py` | test de l'événement de scan partiel |
| `backend/public_checker/serializers.py` | `partial` exposé dans le rapport public |
| `backend/public_checker/tasks.py` | statut public propagé sans transformation en succès |

### Frontend

| Fichier | Modification |
|---|---|
| `SaaS_Web_Application_UI_UX_frontendV2/src/api/types.ts` | `ScanStatus` et `PublicScanReport` incluent `partial` |
| `src/lib/format.ts` | helpers de libellé, tonalité et description des statuts de scan |
| `src/pages/Scans.tsx` | filtre `partial`, badge, bannière explicative, détail des scanners et raisons d'incomplétude |
| `src/pages/WebsiteDetails.tsx` | badge de statut de scan et alerte sur l'historique partiel |
| `src/components/AssetSecurityPanel.tsx` | avertissement explicite lorsque le dernier scan est partiel ; l'analyse IA reste liée au dernier scan complet |
| `src/pages/PublicScanResult.tsx` | avertissement « analyse partielle » dans le rapport public |

Aucun changement n'a été apporté à l'intégration AKA IA, aux scanners eux-mêmes, ni aux règles d'ingestion.

---

## 5. API et interface

### API

- `GET /api/v1/websites/{id}/scans/` expose désormais `status: "partial"` sans changement de schéma.
- Le filtre `?status=partial` fonctionne via le filtre existant sur `Scan.status`.
- `GET /api/v1/scans/{id}/` expose les `ScannerRun` avec leurs statuts individuels (`timeout`, `partial`, etc.), ce qui permet d'identifier le scanner en cause.
- Le rapport public (`PublicScanReport`) expose `partial` et n'est jamais présenté comme complet.
- Les consommateurs existants ne reçoivent pas de champ supprimé ; seule une valeur d'énumération s'ajoute.

### Interface

- Un scan `partial` affiche **« Partiel »** avec une tonalité d'avertissement, jamais **« Terminé »**.
- Le détail indique quels scanners ont réussi, échoué ou expiré.
- La page `Scans` affiche les raisons d'incomplétude fournies par le backend et une bannière précisant que le score ne reflète pas une évaluation complète.
- `WebsiteDetails` affiche le statut de scan à côté de l'historique.
- `AssetSecurityPanel` signale un dernier scan partiel et renvoie vers le dernier scan complet pour l'analyse IA.
- Le rapport public affiche un bandeau d'analyse partielle avant les résultats.

---

## 6. État réel du montage des archives

### Constat

La configuration Compose déclare bien :

```yaml
volumes:
  - scanner_archive_data:/app/scanner-archives
```

Le volume `presence_scanner_archive_data` existe et contient des archives des scans récents. Ses permissions sont :

- répertoire racine : `0700` ;
- fichiers d'archive : `0600`.

Cependant, le conteneur `presence_celery-worker` actuellement en cours d'exécution a été créé il y a environ 10 heures, **avant** l'ajout de ce montage. Son inspection (`docker inspect`) ne montre pas `/app/scanner-archives` dans `Mounts`. Il ne voit donc pas les archives du volume partagé.

### Conséquence

Tant que le worker n'est pas recréé, les nouvelles archives ne sont pas persistées dans `scanner_archive_data`. Le code d'archivage journalise explicitement l'indisponibilité du répertoire et n'invente pas de contenu. L'ingestion continue de fonctionner à partir du rapport du processus, mais la conservation des preuves brutes n'est pas garantie sur ce worker.

### Pourquoi la recréation n'a pas été appliquée

Le worker n'utilise pas de montage de code source : le code est intégré à l'image. Une simple recréation attacherait le volume mais exécuterait l'ancien code, sans la correction des statuts. Une reconstruction complète de l'image est nécessaire pour aligner code, schéma et montage. Cette opération n'a pas été réalisée dans cette mission pour éviter :

- d'exécuter du code `partial` contre une base dont la migration `0007` n'est pas encore appliquée ;
- de modifier l'état d'un service local sans validation préalable de la migration ;
- de perturber des tâches en cours.

Aucun redémarrage, aucune reconstruction et aucune migration n'ont été exécutés sur l'environnement actif.

### Procédure de validation restante

1. Appliquer `python manage.py migrate scans` dans un environnement contrôlé.
2. Reconstruire l'image du worker avec le code courant.
3. Recréer uniquement `celery-worker` avec `docker compose up -d --no-deps --force-recreate celery-worker`.
4. Vérifier `docker inspect` : le montage `/app/scanner-archives` doit apparaître.
5. Lancer un scan autorisé et vérifier la présence de l'archive et de son sidecar.

---

## 7. Validation exécutée

### Tests backend

```bash
bash scripts/run_backend_tests.sh \
  scans.tests.test_status_integrity \
  scans.tests.test_orchestrator_delegation \
  scans.tests.test_scanner_engine \
  scans.tests.test_advanced_security_gate \
  scans.tests.test_scans \
  scans.tests.test_alert_pipeline \
  advisory.tests.test_scan_ingestion \
  advisory.tests.test_nuclei_lifecycle \
  scanners.tests.test_artifacts \
  monitoring \
  public_checker.tests.test_legacy_public_checker
```

**Résultat : 269 tests exécutés, `OK`, 199,403 s.**

Cas couverts par `scans/tests/test_status_integrity.py` :

1. tous les scanners requis réussissent → `completed` ;
2. ZAP réussit, Nuclei expire → `partial` ;
3. Nuclei réussit, ZAP échoue → `partial` ;
4. tous les scanners échouent → `failed` ;
5. timeout global sans résultat → `failed` ;
6. retry Celery → statut terminal conservé ;
7. résultat tardif → aucune transition vers `completed` ;
8. rapport vide avec complétude explicite → pas de résolution ;
9. rapport vide sans complétude → aucune résolution ;
10. ingestion d'un scan partiel → aucune résolution ;
11. isolation inter-organisations → inchangée ;
12. sérialisation API → `partial` exposé ;
13. reproduction du cas 3584 → `partial`, pas `completed`.

### Contrôles Django

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose config --quiet
```

**Résultat :** aucune erreur, aucune migration manquante, configuration Compose valide.

### Frontend

```bash
pnpm exec tsc --noEmit
pnpm run build
```

**Résultat :** TypeScript sans erreur, build Vite réussi.

---

## 8. Limites et éléments non vérifiés

- **Le scan 3584 n'a pas été rejoué ni modifié.** Sa reproduction est un test déterministe qui applique ses statuts réels à un `Scan` et un `ScannerRun` de test. La ligne historique 3584 reste `completed` en base : aucune donnée historique n'a été altérée.
- **Aucun scan réel n'a été exécuté après la correction.** La migration `0007` n'est pas appliquée sur la base active et le worker tourne encore avec l'ancien code.
- **Le montage des archives n'est pas corrigé sur le worker actif.** Voir section 6.
- **Aucun test navigateur de bout en bout** n'a été exécuté ; l'interface est vérifiée par TypeScript, build et inspection du code.
- **La suite backend complète** n'a pas été exécutée ; 269 tests ciblés l'ont été.
- **Les scans `partial` ne déclenchent plus les alertes automatiques ni l'analyse IA.** C'est un choix conservateur : un score calculé sur une couverture incomplète ne doit pas produire d'alerte ou de conclusion automatique trompeuse. Les résultats restent consultables et l'analyse peut être demandée sur le dernier scan complet. Cette règle devra être revue si le produit souhaite alerter sur des constats partiels confirmés.
- **Le scanner Lighthouse avancé reste facultatif** lorsque la performance historique est déjà mesurée. Cette politique préexistante évite un doublon de couverture ; elle n'a pas été modifiée.

---

## 9. Risques résiduels

1. **Migration non appliquée** : toute exécution du nouveau code avant `migrate scans` échouera à l'écriture d'un statut `partial` à cause de l'ancienne contrainte. C'est le prérequis de déploiement le plus important.
2. **Worker non aligné** : le worker actif ne monte pas le volume d'archives et exécute l'ancien code. Les preuves brutes des prochains scans peuvent ne pas être conservées.
3. **Historique incohérent** : 3584 restera `completed` tant qu'aucune correction de données n'est décidée. Une telle correction est volontairement hors périmètre.
4. **Absence d'alerte sur partiel** : un constat critique détecté uniquement par un scanner réussi, dans un scan par ailleurs partiel, ne déclenchera pas d'alerte automatique.
5. **Pas de validation réelle** : les règles sont couvertes par des tests et le build, mais pas par un scan multi-scanners réel après déploiement.

---

## 10. Conclusion

La cause racine est corrigée : l'orchestrateur calcule désormais un statut agrégé à partir des `ScannerRun` et des étapes, `partial` est un état explicite, les transitions sont terminales et l'API comme l'interface distinguent un scan complet d'un scan partiel ou expiré. L'ingestion reste bloquée pour tout scan incomplet et aucune donnée historique n'a été modifiée.

La validation reste **partielle** : 269 tests ciblés passent, les contrôles Django et le build frontend passent, mais aucun scan réel n'a été rejoué après la correction et le worker actif ne monte toujours pas le volume d'archives. La prochaine étape contrôlée est l'application de la migration `0007`, la reconstruction du worker et un scan autorisé de vérification.
