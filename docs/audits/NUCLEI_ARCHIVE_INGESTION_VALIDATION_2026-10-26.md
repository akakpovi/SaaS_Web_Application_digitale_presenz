# Nuclei — Archivage des rapports et validation de l’ingestion

**Date :** 26 octobre 2026  
**Périmètre :** Presence AI Security Advisor — pipeline Nuclei, archives privées, ingestion `SecurityFinding`  
**Mode :** corrections locales, tests ciblés, validation réelle sur un actif autorisé. Aucun déploiement production, aucune suppression de données, aucune modification de l’intégration AKA IA.

## 1. Statut final

**Partiellement vérifié en conditions réelles.**

- L’archivage des rapports **complets** est vérifié de bout en bout sur un scan Nuclei réel : le fichier JSONL et son sidecar sont créés, liés au bon `ScannerRun`, avec permissions privées.
- L’archivage des rapports **partiels**, la déduplication, la mise à jour, la résolution et l’isolation inter-tenant sont vérifiés par des tests automatisés déterministes.
- Aucun rapport réel contenant un constat positif n’a été produit pendant cette passe (le profil `standard` a terminé avec 0 constat sur la cible). Le cycle création → mise à jour → résolution n’est donc pas validé par un scan réel, mais l’est par les tests d’ingestion.
- Aucun scan incomplet réel n’a été forcé ; ce cas est couvert par les tests et par le comportement existant du pipeline.

## 2. Audit initial

### État Git

- Branche : `main`.
- Le dépôt contient de nombreuses modifications locales préexistantes, non liées à cette mission. Elles n’ont pas été écrasées, réinitialisées ni indexées.
- Les fichiers de cette mission ont été modifiés dans l’arbre de travail uniquement.

### Chaîne existante

Le pipeline d’archivage et d’ingestion était déjà présent avant cette passe :

- `scanners/implementations/nuclei.py` expose le JSONL brut via `raw_report` et les métadonnées de complétude (`scan_complete`, `timed_out`, `partial_reason`, versions, profil, compteurs).
- `scans/services/orchestrator.py` archive le rapport avant l’ingestion, puis ingère les résultats.
- `scanners/artifacts.py` rédige les secrets, écrit le JSONL et un sidecar de diagnostic, déduplique par hash et applique une rétention.
- `advisory/services/scan_ingestion.py` et `advisory/services/ingestion.py` assurent l’upsert par `(organisation, actif, source, nom)` et la résolution conditionnelle.
- Une exécution incomplète (`complete=False`, timeout, mémoire, méta d’exécution) désactive la résolution.
- Les archives sont désactivées dans les tests (`config/settings/test.py`) et activées explicitement dans les tests dédiés.

### Causes de défaillance observées avant correction

1. **Volume Docker possédé par root.** Le volume nommé `scanner_archive_data` est créé par Docker avec `root:root`. Le worker tourne avec l’utilisateur `app` et ne peut ni créer ni chmoder les sous-répertoires. Le premier scan réel (3576) a produit :
   `scanner_archive_failed ... PermissionError` et `archive.status = failed`.
2. **Image de test périmée.** Un scan intermédiaire (3577) a tourné sur une image construite avant l’ajout des réglages d’archive : `SCANNER_ARCHIVE_*` était absent et aucune archive n’était tentée. L’image a été reconstruite avant les mesures finales.
3. **Permissions des répertoires intermédiaires.** `Path.mkdir(parents=True, mode=0o700)` n’applique le mode qu’au dernier composant. Les répertoires `nuclei/YYYY/MM` restaient en `0755`, révélant les noms d’archives aux autres utilisateurs locaux malgré des fichiers en `0600`.

## 3. Modifications apportées

### `docker-compose.yml`

- Le service `staticfiles`, qui tourne déjà en `root` et s’exécute avant le worker, monte désormais `scanner_archive_data:/app/scanner-archives`.
- Il crée le répertoire, applique `chown -R app:app` puis `chmod 700`.
- `celery-worker` dépend désormais de `staticfiles` avec `condition: service_completed_successfully`.
- Cela corrige la cause racine du `PermissionError` sans donner de privilèges root au worker.

### `SaaS_Web_Application_digitale_presenz_v2/backend/scanners/artifacts.py`

- `_ensure_private_dir()` ne se contente plus de chmoder le dernier composant.
- Elle remonte jusqu’à la racine d’archive (sans jamais la dépasser) et applique `0700` à chaque répertoire : racine, `scanner`, `YYYY`, `MM`, jour.
- Les anciens répertoires `0755` sont corrigés lors de la prochaine écriture.

### `SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_artifacts.py`

- Le test d’archive complète vérifie maintenant que **tous** les répertoires parents de l’archive sont en `0700`, pas seulement le répertoire feuille.

### Documentation

- Ce rapport : `docs/audits/NUCLEI_ARCHIVE_INGESTION_VALIDATION_2026-10-26.md`.

## 4. Tests automatisés exécutés

### Suite ciblée archive / ingestion / orchestration / cycle Nuclei

```bash
bash scripts/run_backend_tests.sh \
  scanners.tests.test_artifacts \
  advisory.tests.test_scan_ingestion \
  advisory.tests.test_ingestion \
  scans.tests.test_orchestrator_delegation \
  scanners.tests.test_advanced_security
```

**Résultat : 120 tests, OK** (122,3 s), base de test détruite proprement.

Couverture utile :

- archive complète, partielle, vide et non fabriquée ;
- permissions `0600` sur les fichiers et `0700` sur tous les répertoires ;
- sidecar avec `scan_id`, `scanner_run_id`, complétude, profil, diagnostics ;
- réutilisation par hash (pas de doublon d’archive au retry) ;
- troncature et échec de stockage explicite ;
- création, rejeu sans doublon, mise à jour, réouverture, résolution ;
- absence de résolution sur scan partiel, timeout, sortie tronquée ou couverture insuffisante ;
- isolation par actif, par source et par organisation ;
- refus d’un actif d’une autre organisation ;
- contrainte d’unicité en base ;
- ingestion d’un rapport vide uniquement lorsqu’il est explicitement complet.

### Suite ciblée monitoring / moteur de scan / sandbox / cycle Nuclei

```bash
bash scripts/run_backend_tests.sh \
  monitoring \
  scans.tests.test_scanner_engine \
  scans.tests.test_advanced_security_gate \
  scanners.tests.test_sandbox \
  advisory.tests.test_nuclei_lifecycle
```

**Résultat : 144 tests, OK** (100,0 s).

### Contrôles Django

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

**Résultat :**

- `System check identified no issues (0 silenced).`
- `No changes detected`

### Validation de la configuration Compose

```bash
docker compose config --quiet
```

**Résultat : OK.** La dépendance `celery-worker -> staticfiles` est bien résolue en `service_completed_successfully`.

## 5. Validation réelle

### Actif et profil

- Actif : `appchat.elomaiapp.com` (actif de test déjà utilisé pour les scans précédents).
- Profil : `standard`.
- Nuclei : `v3.11.1`.
- Templates : `14126`, 646 templates chargés pour le scan.
- Sandbox : Docker, timeout 150 s, mémoire 1536 Mo, 1 CPU.
- Aucun test intrusif supplémentaire n’a été lancé sur un tiers.

### Mesures finales

| Scan | Durée | Code sortie | Templates | Requêtes | Constats | Complétude | Archive |
|---|---:|---:|---:|---:|---:|---|---|
| 3578 | 61,329 s | 0 | 646 | 1 300 | 0 | complète | `stored` |
| 3579 | 57,834 s | 0 | 646 | 1 300 | 0 | complète | `stored` |

Les deux scans sont sous le budget de 150 s et sous la limite absolue de 180 s. Le scan 3579 a été exécuté après reconstruction de l’image et après la correction des permissions.

### Archive du scan 3579

- Référence : `nuclei/2026/10/26/nuclei-scan3579-e3b0c44298fc1c14.jsonl`
- Taille : 0 octet (rapport complet sans constat).
- SHA-256 : `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `records: 0`, `partial: false`, `truncated: false`
- Sidecar : `nuclei/2026/10/26/nuclei-scan3579-run24757-e3b0c44298fc1c14.meta.json`
- `scanner_run_id` : 24757
- `scan_id` : 3579

Permissions vérifiées après le scan :

```text
drwx------ app:app  /app/scanner-archives
drwx------ app:app  /app/scanner-archives/nuclei
drwx------ app:app  /app/scanner-archives/nuclei/2026
drwx------ app:app  /app/scanner-archives/nuclei/2026/10
drwx------ app:app  /app/scanner-archives/nuclei/2026/10/26
-rw------- app:app  .../nuclei-scan3579-e3b0c44298fc1c14.jsonl
-rw------- app:app  .../nuclei-scan3579-run24757-e3b0c44298fc1c14.meta.json
```

### Résultat d’ingestion réel

Avant et après le scan 3579, le constat Nuclei existant est resté :

```text
BEFORE [('HTTP Missing Security Headers', 'open')]
AFTER  [('HTTP Missing Security Headers', 'open')]
```

L’ingestion a reçu 0 constat, créé 0, mis à jour 0 et résolu 0. C’est le comportement attendu :

- le profil `standard` exclut les constats de sévérité `info` ;
- l’orchestrateur transmet `resolve_missing=False` pour ce profil ;
- l’absence d’un constat hors couverture ne doit donc jamais le résoudre.

Aucun conteneur Nuclei résiduel n’a été observé après les scans (`docker ps -a --filter ancestor=projectdiscovery/nuclei:latest` vide).

### Échec de stockage contrôlé

Le premier scan réel (3576), lancé avec un répertoire d’archive monté depuis l’hôte et possédé par `root`, a produit :

- scan : `completed` ;
- `ScannerRun.metadata.archive.status` : `failed` ;
- `detail` : `PermissionError` ;
- ingestion : toujours exécutée ;
- aucun constat existant résolu.

Cela confirme que l’échec d’archivage est **explicite** et ne rend pas l’ingestion silencieusement incomplète. La cause a ensuite été corrigée.

## 6. Ce qui est réellement vérifié

### Vérifié en conditions réelles

- Un scan Nuclei complet peut être exécuté, ingéré et archivé.
- Le JSONL brut est stocké dans le volume privé.
- Le sidecar contient l’identifiant du scan, celui du `ScannerRun`, la complétude, le profil, la version, les templates, les requêtes, la durée et les diagnostics.
- Les fichiers sont en `0600` et tous les répertoires en `0700`.
- Un scan complet sans constat n’entraîne aucune résolution lorsque la couverture ne le permet pas.
- Aucun processus ou conteneur Nuclei ne subsiste après exécution.
- Une erreur de stockage est enregistrée dans les métadonnées et ne bloque pas l’ingestion.

### Vérifié par tests déterministes uniquement

- Archivage d’un rapport partiel récupérable, marqué `partial: true`.
- Absence de fabrication d’archive quand le rapport partiel est vide.
- Déduplication de l’archive au retry.
- Cycle complet création → rejeu → mise à jour → résolution.
- Absence de résolution sur timeout, mémoire, sortie tronquée et couverture insuffisante.
- Isolation par actif, source et organisation.
- Rétention configurable et purge des fichiers anciens.
- Échec de stockage simulé (`OSError`) sans propagation.

## 7. Limites et risques restants

1. **Pas de constat positif réel pendant cette passe.** Le cycle création/mise à jour/résolution est couvert par les tests, mais pas par un rapport Nuclei réel contenant une vulnérabilité. Un prochain scan sur une cible de test présentant un constat `medium` ou supérieur permettrait de compléter cette validation.
2. **Pas de timeout réel forcé.** Le comportement partiel est testé avec des rapports et des méta déterministes. Un test réel de dépassement de 150 s n’a pas été provoqué pour ne pas ajouter une charge inutile à la cible.
3. **Version des templates.** Le sidecar enregistre `14126` (valeur configurée), tandis que Nuclei affiche `Current nuclei-templates version: (unknown)` dans ce montage. Le nombre réellement chargé (646) est mesuré et enregistré.
4. **Image Docker.** Les tests réels utilisent l’image construite. Toute modification du code d’archivage nécessite `docker compose build celery-worker` avant un scan réel ; sinon l’image périmée est utilisée.
5. **Volume existant.** La correction Compose s’applique au prochain `docker compose up` via `staticfiles`. Pour un volume déjà créé et root-owned, le service `staticfiles` le corrige au démarrage. Un `docker compose run --no-deps celery-worker` direct ne lance pas cette étape ; il faut alors exécuter `staticfiles` ou initialiser le volume.
6. **Aucun déploiement production.** Aucun déploiement, aucune migration de données et aucune suppression n’ont été effectués.
7. **Artefact de smoke test.** Un petit fichier `nuclei-scan1-*.jsonl` et son sidecar ont été créés lors du test direct d’`archive_report` (`scan_id=1`, `scanner_run_id=2`) dans le volume. Ils ne correspondent à aucun scan réel et seront purgés par la rétention ; ils n’ont pas été supprimés pour respecter la consigne de non-suppression.

## 8. Critères d’acceptation

| Critère | État |
|---|---|
| Rapports partiels récupérables archivés et identifiés incomplets | Vérifié par tests |
| Rapports complets associés au bon `ScannerRun` | Vérifié en réel (3579) |
| Cycle création → déduplication → mise à jour → résolution testé | Vérifié par tests |
| Aucun scan incomplet ne résout de constat | Vérifié par tests |
| Aucun accès inter-organisation | Vérifié par tests |
| Tests et commandes rapportés avec résultats réels | Oui |
| Stockage privé et permissions | Vérifié en réel |
| Erreur de stockage non silencieuse | Vérifié en réel (3576) |

## 9. Conclusion

L’archivage des rapports Nuclei complets est opérationnel et vérifié sur des scans réels. Les deux défauts bloquants découverts pendant la validation — volume Docker possédé par root et répertoires intermédiaires en `0755` — ont été corrigés. L’ingestion continue de respecter strictement la complétude, la déduplication, la résolution conditionnelle et l’isolation des locataires.

La validation reste **partielle** pour les rapports partiels et le cycle positif d’ingestion : ces cas sont couverts par des tests automatisés, pas par un scan réel avec constat. Aucun élément ne permet de déclarer l’ensemble du cycle « vérifié en conditions réelles » à ce stade.
