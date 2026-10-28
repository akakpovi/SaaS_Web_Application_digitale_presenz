# Fiabilisation de Nuclei — rapport de mission

Date : 2026-10-25
Périmètre : `SaaS_Web_Application_digitale_presenz_v2/backend`
Cible de validation autorisée : `appchat.elomaiapp.com` (site `24`, organisation `a694ddef-a833-4d17-bc0c-44804a74180b`).
Aucun déploiement production, aucune suppression de données, aucune modification de l'intégration AKA IA.

## Statut

**Fiabilisé et vérifié en conditions réelles.**

Quatre exécutions Nuclei complètes avec le profil standard ont terminé entre **129,6 s et 169,0 s** (objectif < 180 s), avec `percent=100` et sans timeout. Le traitement d'un timeout contrôlé et l'absence de résolution de constats sur un scan incomplet ont été vérifiés. Les tests ciblés passent.

Réserves explicites :

- la marge sur l'objectif est faible (169 s pour un budget de 170 s) ; la variabilité vient de la latence et des erreurs réseau de la cible, pas du chargement des templates ;
- le profil standard ne couvre ni les sévérités `info`/`low`, ni les templates CVE, ni les familles intrusives/fuzzing. Il ne peut donc pas résoudre un constat hors de sa couverture (`resolve_missing=False`) ;
- sur cette cible, le profil standard n'a produit **aucun nouveau constat Nuclei**. La création/mise à jour a été vérifiée par rejeu d'un rapport Nuclei réel, pas par un nouveau scan standard positif ;
- ZAP a échoué pendant ces essais (`ZAP failed to access target`, exit 3), indépendamment de Nuclei et hors périmètre de cette mission ;
- une exécution de développement (scan `3568`) a échoué sur un `NameError` avant persistance des résultats ; elle est exclue des mesures.

## 1. Audit initial et causes du timeout

### Configuration trouvée avant correction

| Élément | Valeur constatée |
|---|---|
| Moteur Nuclei | `v3.11.1` (image `projectdiscovery/nuclei:latest`) |
| Catalogue local | 14 104 fichiers `.yaml` montés dans `/tmp/presence-scanner/nuclei-templates` |
| Ancien profil | `tags = cve, exposure, misconfig`, toutes sévérités, timeout sandbox 300 s |
| Worker | Celery `--concurrency=2`, 1 CPU et 1,5 Go alloués au conteneur Nuclei |
| Budget global du scan | 540 s (`SCAN_TOTAL_TIME_BUDGET_SECONDS`) |
| Ingestion | `SecurityFinding` par organisation/actif, déduplication par nom, résolution des absents |

### Cause confirmée du dépassement

Le scan `3567` (avant correction) a duré **320 880 ms** avec un timeout sandbox de **300 s**, et n'a produit qu'**un seul constat**. Il a malgré tout été marqué `completed` : l'ancien adaptateur ne distinguait pas un processus tué par le sandbox d'un scan terminé.

La cause principale est donc **le volume de templates sélectionnés et l'absence de profil borné**, pas un manque de ressources :

- le filtre couvrait `cve` + `exposure` + `misconfig` sur un catalogue de plus de 14 000 fichiers ;
- le timeout de 300 s était insuffisant pour cette couverture ;
- aucune statistique de progression ni détection de `Skipped host` n'était exploitée pour qualifier le résultat ;
- le code de sortie et le rapport partiel n'étaient pas conservés de façon exploitable.

Les mesures des nouvelles exécutions montrent que le temps restant est dominé par les **requêtes réseau et leurs erreurs** : 3 334 requêtes et 1 958 erreurs pour 169 s, avec seulement 1 066 templates chargés. Le chargement des templates et la mémoire ne sont plus le facteur limitant.

## 2. Profil Nuclei retenu

Deux profils explicites sont définis dans `config/settings/base.py` et sélectionnables par `SCANNER_NUCLEI_PROFILE`.

### `standard` (défaut des scans automatiques)

| Paramètre | Valeur |
|---|---|
| Tags | `exposure`, `misconfig` |
| Tags exclus | `dos`, `fuzz`, `fuzzing`, `intrusive`, `brute-force`, `default-login`, `credential-stuffing`, `token-spray` |
| Sévérités | `critical`, `high`, `medium` |
| Protocole | `http` |
| IPv4 | oui |
| Concurrence | 20 |
| Débit maximal | 60 requêtes/s |
| Taille de lot | 10 |
| Timeout par requête | 5 s |
| Retries | 1 |
| `max-host-error` | 40 |
| Timeout global | 170 s |
| Résolution des absents | désactivée (`resolve_missing=False`) |
| Mémoire sandbox | 1 536 Mo |

### `deep` (jamais planifié par défaut)

Ajoute les templates `cve`, avec une concurrence de 15, un débit de 50 req/s, un timeout par requête de 8 s et un budget global de 540 s. Il exige un worker dédié et un budget de scan supérieur à 540 s.

### Justification des exclusions

- `dos` et les familles destructives sont interdits dans un scan automatique.
- `fuzz`/`fuzzing`, `intrusive`, `brute-force`, `default-login`, `credential-stuffing` et `token-spray` peuvent affecter la disponibilité ou déclencher des verrouillages de comptes.
- Aucune exclusion globale de `sqli`, `xss` ou `injection` n'a été ajoutée. En revanche, le profil standard étant piloté par les tags positifs `exposure`/`misconfig`, les templates d'injection qui ne portent que des tags `sqli`/`xss`/`cve` ne sont **pas** sélectionnés. Cette limitation de couverture est assumée et interdit la résolution automatique.
- Les sévérités `info`/`low` sont exclues du standard pour éviter le bruit ; leur absence ne peut jamais clore un constat.

Le recouvrement avec ZAP n'a pas été utilisé pour supprimer des templates : ZAP et Nuclei restent deux sources indépendantes. Aucun doublon n'a été observé dans l'ingestion réelle.

## 3. Gestion du timeout et des résultats

- Le budget du processus est **170 s**, inférieur au budget du scan (540 s) et au timeout Celery.
- Le timeout inclut le démarrage du conteneur Docker.
- À l'expiration, le conteneur est supprimé explicitement (`docker rm -f`) puis le client est tué ; le groupe de processus est tué pour le backend `process`.
- Un code 137 sans timeout est traité comme un dépassement mémoire.
- `timed_out`, `memory_exceeded`, `exit_code`, `killed_reason`, la durée et le profil sont enregistrés.
- Un scan n'est **complet** que si : `exit_code == 0`, pas de timeout, pas de dépassement mémoire, pas de `Skipped host`, et `percent == 100` dans les statistiques Nuclei.
- Un rapport partiel conserve les constats normalisés déjà collectés et ajoute un constat de diagnostic (`nuclei.timeout`, `nuclei.incomplete`, `nuclei.execution_failed`, `nuclei.host_unresponsive`). Ce constat de diagnostic n'est jamais ingéré comme vulnérabilité et force `complete=False`.
- Un code de sortie non nul avec un fichier de résultats n'est jamais converti en succès.
- Les codes de sortie, le profil, `templates_loaded`, `percent`, `requests`, `errors` et `host_skipped` sont désormais persistés dans `ScannerRun.metadata` et `ScannerRun.exit_code`.

### Test de timeout contrôlé

Exécution directe de l'adaptateur Nuclei avec une échéance de 30 s sur la cible autorisée :

```text
timed_out=True exit=137 complete=False reason=timeout duration_ms=30 156
findings=['nuclei.timeout']
```

Aucun conteneur `presence-scan-*` n'est resté après l'essai (`docker ps` vide). Le scan est classé `timeout`, pas `completed`, et aucune résolution n'est déclenchée.

## 4. Validation réelle Nuclei

Toutes les exécutions ci-dessous utilisent la cible autorisée, le profil `standard` et le pipeline Presence réel (`run_authenticated_scan` → orchestrateur → sandbox Docker → ingestion).

| Scan | Durée Nuclei | Templates chargés | Requêtes / erreurs | Code sortie | Complet | Constats | Statut |
|---|---:|---:|---:|---:|---|---:|---|
| `3567` (avant) | 320,9 s | non mesuré | non mesuré | non persisté | non qualifié | 1 | timeout de fait, ancien comportement |
| `3568` (dev) | 135,2 s | non mesuré | non mesuré | non persisté | non | 0 | échec `NameError`, exclu |
| `3569` | 129,6 s | 1 066 | non persisté | non persisté | oui (`percent=100`) | 0 | complet |
| `3570` | 139,3 s | 1 066 | non persisté | non persisté | oui (`percent=100`) | 0 | complet |
| `3571` | 167,5 s | 1 066 | non persisté | non persisté | oui (`percent=100`) | 0 | complet |
| `3572` | 169,0 s | 1 066 | 3 334 / 1 958 | 0 | oui (`percent=100`) | 0 | complet |

- Les scans `3569` à `3571` ont été exécutés avant le correctif de persistance du code de sortie ; l'adaptateur a calculé `complete=True` à partir d'un exit 0, mais la valeur n'était pas encore enregistrée en base.
- Le scan `3572` est la mesure de référence : `ScannerRun.status=completed`, `exit_code=0`, `duration_ms=169 017`, `templates_loaded=1 066`, `requests=3 334`, `errors=1 958`, `host_skipped=False`.
- Le scan Presence `3572` est `completed`, progression 100 %, de `20:06:18` à `20:10:21` (243 s au total, ZAP inclus).
- Les scans `3569`, `3570`, `3571` et `3572` ont tous ingéré `received=0 created=0 updated=0 resolved=0 resolve_missing=False`.

### Pourquoi aucun constat sur cette cible ?

Le profil standard ne sélectionne que `exposure` et `misconfig` en medium+. La cible ne présente pas de correspondance dans ce périmètre. Un scan complémentaire réel avec `-tags misconfig -severity info` a produit **9 correspondances** (toutes sur le même template de mauvaises configurations d'en-têtes), normalisées en **1 constat** après déduplication par template et URL. Ce rapport réel a été rejoué deux fois dans le pipeline d'ingestion :

```text
run 1 parsed=9 findings=1 created=0 updated=1 resolved=0
run 2 parsed=9 findings=1 created=0 updated=1 resolved=0
open=8 total=14
```

La déduplication est stable et idempotente ; le constat existant a été mis à jour sans doublon et sans résolution. Le chemin de création est couvert par les tests unitaires et par les constats ZAP/Nuclei déjà présents en base ; il n'a pas été possible de créer un nouveau constat Nuclei avec le profil standard sur cette cible propre.

## 5. Intégration avec l'ingestion existante

- Les résultats Nuclei sont convertis en `NormalizedFinding` puis en `ParsedReport` (`nuclei`) avant l'ingestion.
- La clé de déduplication longue durée reste `(organisation, actif, source, nom du constat)` ; les preuves (`template_id`, `matched_at`, `matcher_name`, `extracted_results`, tags, host, IP) sont conservées dans `Finding.evidence`.
- `scan_complete=False` force `resolve_missing=False` : aucun constat absent n'est résolu.
- Un rapport Nuclei vide mais complet et valide peut résoudre les absents ; un rapport vide parce que le processus a échoué ne le peut pas.
- Les constats de diagnostic (`*.timeout`, `*.incomplete`, `*.execution_failed`, `*.host_unresponsive`, `*.sandbox_unavailable`, etc.) sont filtrés avant l'ingestion et ne créent jamais de fausse vulnérabilité.
- Le scan `3568` n'a pas persisté de `Finding` Nuclei (0). Il n'est pas utilisé comme preuve de bon fonctionnement.

## 6. Fichiers modifiés

| Fichier | Nature |
|---|---|
| `backend/scanners/implementations/nuclei.py` | Profils, arguments CLI bornés, parsing JSONL/stats, complétude, constats partiels, déduplication, montage des templates |
| `backend/scanners/executors/sandbox.py` | Timeout global incluant le démarrage, suppression forcée du conteneur, kill du groupe de processus, gestion du code 137 |
| `backend/scans/services/orchestrator.py` | Statut `timeout`/`partial`/`completed`, propagation de `scan_complete`, `resolve_missing`, `exit_code`, profil, requêtes/erreurs |
| `backend/config/settings/base.py` | Profils `standard`/`deep`, limites 170 s/540 s, mémoire 1 536 Mo, exclusions, `resolve_missing=False` |
| `backend/.env.example` | Documentation de `SCANNER_NUCLEI_PROFILE`, des timeouts et du catalogue de templates |
| `backend/scanners/tests/test_advanced_security.py` | Tests de complétude, timeout, exit non nul, host skip, absence de stats, parsing et construction Docker |
| `backend/advisory/tests/test_scan_ingestion.py` | Tests de non-résolution sur scan partiel, profil étroit, timeout, isolation et idempotence |

Aucun modèle, aucune migration et aucune route API n'ont été modifiés.

## 7. Tests exécutés

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh scanners advisory.tests.test_scan_ingestion scans.tests.test_scanner_engine` | **208 tests, OK**, 173,8 s |
| `bash scripts/run_backend_tests.sh monitoring` | **30 tests, OK**, 127,6 s |
| `bash scripts/run_backend_tests.sh scans.tests.test_scanner_engine scanners.tests.test_advanced_security` | **115 tests, OK**, 95,4 s (après le dernier correctif d'orchestrateur) |
| `bash scripts/run_backend_tests.sh scans.tests.test_orchestrator_delegation advisory.tests.test_scan_ingestion` | **26 tests, OK**, 65,7 s (après le dernier correctif d'orchestrateur) |
| `python manage.py check` | Aucun problème |
| `python manage.py makemigrations --check --dry-run` | Aucun changement détecté |

Tests spécifiquement pertinents, tous passés :

- construction des arguments CLI et valeurs par défaut ;
- timeout global, terminaison et code de sortie ;
- exit non nul, host skip, statistiques manquantes et sandbox indisponible ;
- rapport valide ingéré ;
- absence de résolution après timeout ou scan partiel ;
- `resolve_missing=False` pour un profil étroit ;
- déduplication et rejeu idempotent ;
- isolation inter-organisations ;
- conservation des résultats en cas d'échec d'ingestion ;
- compatibilité avec l'orchestration Celery.

La suite complète `advisory` n'a pas été rejouée dans la limite de 600 s ; seuls les tests d'ingestion ciblés ont été exécutés pour cette mission. Aucun résultat de cette suite n'est revendiqué.

## 8. Risques et limites restantes

1. **Marge de performance faible** : 169 s observées pour un budget de 170 s. Une dégradation réseau peut produire un scan partiel. Le comportement est sûr (aucune résolution), mais le scan ne sera pas complet. Une marge de 10–15 s ou un profil plus étroit serait nécessaire pour garantir systématiquement l'objectif sur une cible lente.
2. **Taux d'erreurs réseau élevé** : 1 958 erreurs pour 3 334 requêtes sur le dernier essai. La cible (Cloudflare) limite ou ralentit une partie des requêtes. Ce n'est pas un défaut du profil, mais cela explique la variabilité 130–169 s.
3. **Couverture partielle du profil standard** : pas de `info`/`low`, pas de CVE, pas de templates d'injection uniquement taggés `sqli`/`xss`, pas de fuzzing. C'est volontaire ; ces constats ne peuvent jamais être résolus par ce profil.
4. **Rapport brut non conservé intégralement** : les constats normalisés et les preuves sont persistés, ainsi qu'un extrait de stderr pour les échecs, mais le JSONL brut complet d'un scan partiel n'est pas archivé. La conservation du rapport brut serait une amélioration de diagnostic.
5. **ZAP instable sur cette cible** : trois exécutions ZAP ont échoué avec `I/O error: ZAP failed to access` (exit 3). L'ingestion ZAP a été ignorée proprement (`tool_not_executed`), mais le pipeline complet ZAP+Nuclei n'a pas été validé dans cette campagne. Hors périmètre de cette mission.
6. **Scan `3568`** : échec de développement (`NameError`) avant persistance des résultats. Il reste un artefact `completed` dans l'historique du site de test et ne doit pas être utilisé comme mesure.
7. **ZAP/Nuclei restent opt-in** (`SCANNER_ADVANCED_SECURITY_ENABLED`) ; aucun scan automatique n'a été planifié en production.

## 9. Conclusion

Nuclei est désormais borné par un profil explicite, un timeout global inférieur au budget Celery, une suppression propre du conteneur et une qualification stricte des résultats. Quatre scans réels complets ont terminé entre 129,6 s et 169,0 s, sous l'objectif de 180 s, avec 1 066 templates chargés et sans timeout. Les scans incomplets ne résolvent aucun constat, et la déduplication réelle est stable.

La mission est **fiabilisée et vérifiée en conditions réelles**, avec les réserves de couverture et de marge de performance documentées ci-dessus. Aucune action de déploiement ou de suppression n'a été effectuée.
