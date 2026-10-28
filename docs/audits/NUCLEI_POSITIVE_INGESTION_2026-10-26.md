# Nuclei — Validation d’un constat positif réel

**Date :** 26 octobre 2026  
**Périmètre :** Presence AI Security Advisor — détection Nuclei, archive, ingestion `SecurityFinding`, déduplication et non-résolution  
**Mode :** validation locale sur une cible déjà autorisée. Aucun déploiement production, aucune suppression de données, aucune modification de l’intégration AKA IA.

## 1. Conclusion

**Création et déduplication vérifiées en conditions réelles. Résolution non vérifiée en conditions réelles.**

Un scan Nuclei réel (3581) a détecté un constat réel, l’a archivé avec son `ScannerRun`, l’a persisté dans `SecurityFinding`, puis le rejeu du rapport archivé a mis à jour ce constat sans créer de doublon. Un second scan positif réel (3585) a confirmé la stabilité de la détection, l’archivage durable et l’idempotence de l’ingestion. Deux autres scans réels ont confirmé qu’un scan hors couverture (3582) et un timeout (3584) ne résolvent pas le constat.

La résolution réelle n’a pas été exécutée : elle exigerait soit une correction réelle de la cible, soit un environnement de test contrôlé où le constat peut disparaître. Aucun rapport n’a été fabriqué pour simuler cette étape.

## 2. Audit préalable

### Profils Nuclei

- `standard` : tags `exposure`, `misconfig`, sévérités `critical,high`, timeout 150 s, `resolve_missing=False`.
- `thorough` : mêmes tags, sévérités `critical,high,medium`, timeout 178 s, `resolve_missing=False`.
- `deep` : tags `cve`, `exposure`, `misconfig`, sévérités `critical,high,medium`, timeout 540 s (clampé par la sandbox), `resolve_missing=False`.

Aucun de ces profils ne couvre les constats de sévérité `info`. Le constat recherché, `HTTP Missing Security Headers`, est justement de sévérité `info`.

### Cible et autorisation

La cible utilisée est `appchat.elomaiapp.com`, déjà utilisée pour les scans réels précédents (3578, 3579, 3580, 3582). Aucun test intrusif n’a été ajouté. Aucune modification n’a été apportée au profil `standard`.

### Vérification de la condition réelle

Un appel Nuclei direct, avec le template officiel `http-misconfiguration/http-missing-security-headers.yaml`, a confirmé la présence réelle de plusieurs en-têtes manquants sur la réponse HTTPS : `Content-Security-Policy`, `X-Permitted-Cross-Domain-Policies`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Embedder-Policy`, `Referrer-Policy`, etc. Il ne s’agit donc pas d’un constat inventé ou forcé.

### Pourquoi un locataire de test isolé

L’actif existant 24 (`appchat.elomaiapp.com`, organisation `a694ddef-a833-4d17-bc0c-44804a74180b`) possède déjà un constat Nuclei `HTTP Missing Security Headers`. Un même domaine ne peut pas être ajouté deux fois à la même organisation. Pour démontrer une **création** sans modifier les données du tenant existant, un locataire de test isolé a été créé :

- utilisateur 52 : `nuclei-positive-validation-20261026@example.invalid`, inactif, sans mot de passe utilisable ;
- organisation `ecfdd74c-e5ec-4f70-9742-b51298434504` ;
- actif 32 : `appchat.elomaiapp.com`.

Le tenant existant et l’actif 24 n’ont pas été modifiés.

## 3. Profil de diagnostic utilisé

Le profil de test n’est **pas** un profil de production et n’a pas été persisté dans les réglages. Il a été ajouté uniquement dans le processus Python de validation :

```text
positive-info
  tags: misconfig
  exclude_tags: dos, fuzz, fuzzing, intrusive, brute-force,
                default-login, credential-stuffing, token-spray
  severity: info
  protocol: http
  request_timeout: 10 s
  retries: 1
  concurrency: 10
  bulk_size: 10
  rate_limit: 30
  max_host_error: 40
  resolve_missing: false
  timeout: 120 s
```

Il est volontairement étroit (`misconfig` + `info`), non intrusif et sans résolution automatique. Le profil `standard` reste inchangé.

## 4. Scan positif 3581

| Élément | Valeur |
|---|---|
| Scan Presence | 3581 |
| `ScannerRun` | 24759 |
| Actif | 32 (`appchat.elomaiapp.com`) |
| Organisation | `ecfdd74c-e5ec-4f70-9742-b51298434504` |
| Profil | `positive-info` |
| Statut du run | `completed` |
| Durée | 60 605 ms (60,6 s) |
| Code de sortie | 0 |
| Templates chargés | 115 |
| Requêtes | 197 |
| Erreurs réseau | 4 |
| Complétude | `scan_complete = true` |
| Constats normalisés | 1 |
| Archive | `stored` |

### Archive

- Référence : `nuclei/2026/10/26/nuclei-scan3581-659bfa732c991f1f.jsonl`
- Taille : 90 142 octets
- SHA-256 : `659bfa732c991f1fa7e843be809f7f586db88d1ea20d3a16229eab3a3e7a2bd3`
- Lignes / enregistrements : 9
- `partial: false`, `truncated: false`
- Sidecar : `nuclei/2026/10/26/nuclei-scan3581-run24759-659bfa732c991f1f.meta.json` (3 829 octets)
- Sidecar : `scan_id = 3581`, `scanner_run_id = 24759`, `complete = true`, `records = 9`, profil `positive-info`, `scanner_version = v3.11.1`, `templates_version = 14126`.

Le JSONL contient 9 matches du même template (un par en-tête manquant) ; la normalisation les a correctement regroupés en **un seul** `SecurityFinding`, ce qui évite les doublons intra-scan.

### Sécurité et persistance de l’archive

- Volume configuré : `saas_web_application_digitale_presenz_scanner_archive_data`.
- Fichier JSONL : `600 app:app` (`100:101` dans le conteneur), 90 142 octets.
- Sidecar : `600 app:app`, 3 829 octets.
- Répertoires d’archive : `700 app:app` jusqu’au jour.
- Recherche de motifs sensibles (`authorization`, `cookie`, `token=`, `password=`, `secret`, `bearer`, clé API, JWT) dans le JSONL et le sidecar : **aucun résultat**.
- `redactions = 0` : le rapport réel ne contenait pas de valeur correspondant aux motifs de rédaction. Cette mesure ne remplace pas les tests de rédaction existants.

## 5. Ingestion et déduplication

### Création

L’ingestion du scan 3581 a produit :

```text
security_report_ingested org=ecfdd74c-... asset=32 source=nuclei
received=1 created=1 updated=0 resolved=0 resolve_missing=False
```

Constat créé :

- ID : `b969bafe-b327-45e2-b3b1-c5f5bca0b91c`
- Nom : `HTTP Missing Security Headers`
- Sévérité : `info`
- Statut : `open`
- `resolved_at` : `null`
- `detected_at` initial : `2026-10-26 06:07:08.441260+00:00`
- Organisation : `ecfdd74c-e5ec-4f70-9742-b51298434504`
- Actif : 32
- Source : `nuclei`

### Rejeu du rapport 3581

Le fichier JSONL réel a été relu depuis le volume, parsé avec `parse_nuclei_jsonl`, normalisé avec l’adaptateur Nuclei, puis réingéré :

```text
PARSED_RECORDS 9
NORMALISED_FINDINGS 1
OUTCOME IngestOutcome(source='nuclei', received=1, created=0, updated=1, resolved=0)
```

Après le rejeu :

- nombre de constats pour l’actif 32 : **1** (inchangé) ;
- `created = 0` ;
- `updated = 1` ;
- `resolved = 0` ;
- même UUID ;
- `status = open`, `resolved_at = null`.

### Confirmation réelle 3585

Un second scan positif réel a été exécuté pour vérifier la reproductibilité et produire une archive supplémentaire :

| Élément | Valeur |
|---|---|
| Scan | 3585 |
| `ScannerRun` | 24770 |
| Profil | `positive-info` |
| Durée | 53 798 ms (53,8 s) |
| Code de sortie | 0 |
| Templates chargés | 115 |
| Requêtes | 197 |
| Erreurs réseau | 4 |
| Constats normalisés | 1 |
| Archive | `nuclei/2026/10/26/nuclei-scan3585-54d6b74943c2c5a9.jsonl` |
| Taille / lignes | 90 232 octets / 9 |
| SHA-256 | `54d6b74943c2c5a971fe1fc85c687c07941511f883d54aa8795bea461c484285` |
| Sidecar | `nuclei-scan3585-run24770-54d6b74943c2c5a9.meta.json` (3 376 octets) |
| Complétude | `complete = true`, `partial = false` |

L’ingestion automatique du scan 3585 a donné :

```text
received=1 created=0 updated=1 resolved=0 resolve_missing=False
```

Le rejeu du JSONL 3585 a confirmé le même comportement :

```text
PARSED_RECORDS 9
NORMALISED_FINDINGS 1
BEFORE_FINDINGS 1
OUTCOME IngestOutcome(source='nuclei', received=1, created=0, updated=1, resolved=0)
AFTER_FINDINGS 1
```

Le même UUID `b969bafe-b327-45e2-b3b1-c5f5bca0b91c` a été conservé et `detected_at` a été actualisé à `2026-10-26 06:31:27.139713+00:00`.

L’archive 3585 a été exécutée avec un répertoire de validation privé (`/tmp/presence-scanner/validation-archives`), puis copiée dans le volume configuré. Le hash et le sidecar ont été vérifiés après copie. Le sidecar 3585 indique `scanner_version = unknown` et `templates_version = unknown` car le processus one-off ne portait pas les variables de version de déploiement ; le scan 3581 fournit ces valeurs.

## 6. Non-résolution sur couverture insuffisante

Un scan `standard` réel a ensuite été exécuté sur le même actif :

| Élément | Valeur |
|---|---|
| Scan | 3582 |
| `ScannerRun` | 24760 |
| Profil | `standard` |
| Durée | 58 105 ms (58,1 s) |
| Code de sortie | 0 |
| Templates | 646 |
| Requêtes | 1 300 |
| Constats | 0 |
| Complétude | `scan_complete = true` |
| Archive | `stored`, 0 octet (rapport vide valide) |

Résultat :

```text
BEFORE [('HTTP Missing Security Headers', 'info', 'open', None)]
AFTER  [('HTTP Missing Security Headers', 'info', 'open', None)]
```

L’ingestion a reçu 0 constat, créé 0, mis à jour 0 et résolu 0, avec `resolve_missing=False`. Le constat `info` est hors couverture du profil `standard` ; il reste ouvert. L’archive de 0 octet est un rapport complet vide, et non un rapport manquant : le sidecar `complete = true` et l’absence de constat sont cohérents.

## 7. Non-résolution sur timeout réel

Un scan volontairement court a été exécuté avec un profil de diagnostic `positive-timeout` (timeout 5 s, `resolve_missing=False`) :

| Élément | Valeur |
|---|---|
| Scan | 3584 |
| `ScannerRun` | 24769 |
| Statut du run | `timeout` |
| Statut de l’étape Nuclei | `timeout` |
| Durée | 5 583 ms (5,6 s) |
| Code de sortie | 137 |
| `scan_complete` | `false` |
| `partial_reason` | `timeout` |
| Archive | `unavailable` / `empty_report`, `partial: true` |
| Ingestion | ignorée (`tool_not_executed`) |

Résultat :

```text
BEFORE [('HTTP Missing Security Headers', 'info', 'open', None)]
AFTER  [('HTTP Missing Security Headers', 'info', 'open', None)]
```

Le timeout réel n’a produit aucun rapport récupérable ; l’archive a explicitement enregistré cette limitation (`empty_report`). Aucun constat n’a été résolu. Le `findings_count = 1` du `ScannerRun` correspond au constat de diagnostic `nuclei.timeout` (visibilité de l’interruption), et non à un `SecurityFinding` de vulnérabilité : l’ingestion a bien été refusée.

### Statut agrégé du scan

Le `Scan.status` de 3584 vaut `completed` tandis que `ScannerRun.status` et `Scan.steps[nuclei].status` valent `timeout`. C’est le comportement préexistant de l’orchestrateur : le statut agrégé indique que la chaîne de traitement est terminée, pas que chaque scanner a réussi. L’ingestion reste correctement bloquée. Cette ambiguïté d’affichage (l’UI de liste utilise `Scan.status`) doit être traitée dans une mission dédiée avec un statut partiel explicite ; elle n’est pas présentée ici comme un scan réussi.

## 8. Isolation

Les deux actifs partagent le même domaine mais appartiennent à deux organisations distinctes :

- actif 32 → `ecfdd74c-e5ec-4f70-9742-b51298434504` (locataire de test) ;
- actif 24 → `a694ddef-a833-4d17-bc0c-44804a74180b` (tenant existant).

Le constat créé est uniquement rattaché à l’actif 32 et à son organisation. L’actif 24 conserve ses 14 constats existants, dont son propre constat Nuclei `HTTP Missing Security Headers`. Aucune ligne de l’autre tenant n’a été créée, modifiée ou résolue.

## 9. Tests exécutés

```bash
bash scripts/run_backend_tests.sh \
  scanners.tests.test_artifacts \
  advisory.tests.test_scan_ingestion \
  advisory.tests.test_nuclei_lifecycle \
  scans.tests.test_orchestrator_delegation \
  monitoring
```

**Résultat : 84 tests, OK** (189,0 s).

Couverture : archives et permissions, ingestion/déduplication, cycle Nuclei, orchestration, monitoring, isolation, timeouts et absence de résolution.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
docker compose config --quiet
```

**Résultat :**

- `System check identified no issues (0 silenced).`
- `No changes detected`
- `docker compose config: OK`

## 10. Ce qui est vérifié et ce qui ne l’est pas

### Vérifié en conditions réelles

- Détection d’un constat réellement présent (`HTTP Missing Security Headers`).
- Création d’un `SecurityFinding` pour un actif et une organisation donnés.
- Archives JSONL et sidecar liées au bon scan et au bon `ScannerRun`.
- 9 matches Nuclei normalisés en 1 constat.
- Rejeu des rapports 3581 et 3585 : 0 doublon, 1 mise à jour, UUID conservé.
- Scan `standard` complet hors couverture : aucune résolution.
- Timeout réel : aucune résolution, archive explicitement indisponible.
- Isolation entre deux organisations partageant le même domaine.
- Permissions `0600/0700` et absence de motifs sensibles dans l’archive réelle.

### Vérifié uniquement par tests déterministes

- Résolution effective d’un constat lorsqu’un scan complet couvre le contrôle et ne le détecte plus.
- Résolution avec date `resolved_at` correcte.
- Réouverture d’un constat résolu s’il réapparaît.
- Autres cas de rapports invalides, troncature, mémoire et erreurs de parsing.

## 11. Limites et risques

1. **Résolution réelle non exécutée.** Le constat `HTTP Missing Security Headers` est toujours présent sur `appchat.elomaiapp.com`. Le corriger ou utiliser un environnement contrôlé où l’en-tête peut être ajouté puis retiré serait nécessaire. Aucun rapport n’a été fabriqué.
2. **Profil `positive-info` non persistant.** Il a servi uniquement à la validation, dans le processus Python. Il n’est ni planifié ni exposé par l’API. Le profil `standard` reste `critical/high` uniquement.
3. **Locataire de test créé.** L’utilisateur 52, l’organisation `ecfdd74c-...` et l’actif 32 restent en base pour permettre l’audit. Ils sont isolés et inactifs, sans mot de passe utilisable. Aucune donnée n’a été supprimée.
4. **Statut agrégé ambigu.** Le scan 3584 est `completed` au niveau `Scan`, alors que le scanner est `timeout`. L’ingestion est correcte, mais l’affichage agrégé ne distingue pas un job terminé avec échec d’un scan réussi. Correction à planifier.
5. **Worker courant non recréé.** Le conteneur `celery-worker` en cours d’exécution a été créé avant l’ajout du volume `scanner_archive_data` ; `docker inspect` ne montre pas ce montage. La configuration Compose le prévoit, et les archives de validation sont présentes dans le volume, mais le worker doit être recréé avant un usage réel pour que ses futures archives soient persistantes. Aucun redémarrage n’a été effectué dans cette mission.
6. **Archive volumineuse.** Le rapport réel fait environ 90 Ko car Nuclei conserve les réponses HTTP complètes. La rétention de 30 jours et les permissions privées s’appliquent ; les motifs sensibles n’ont pas été trouvés, mais la rédaction reste heuristique pour des secrets non reconnus.
7. **Aucun déploiement production.** Aucune migration, aucun redémarrage de production et aucune suppression n’ont été effectués.

## 12. Fichiers et données touchés

- **Créé :** `docs/audits/NUCLEI_POSITIVE_INGESTION_2026-10-26.md` (ce rapport).
- **Aucun fichier de code modifié** dans cette mission.
- **Scans réels exécutés :** 3581 (création), 3582 (couverture standard), 3584 (timeout), 3585 (confirmation et archive durable).
- **Données de validation créées :** utilisateur 52, organisation `ecfdd74c-e5ec-4f70-9742-b51298434504`, actif 32, constat `b969bafe-b327-45e2-b3b1-c5f5bca0b91c`.
- **Archives :** 3581 et 3585 dans le volume `saas_web_application_digitale_presenz_scanner_archive_data`.

## 13. Conclusion détaillée

La chaîne réelle **détection → archivage → ingestion → persistance → déduplication** est validée avec deux scans Nuclei positifs et deux rapports réels d’environ 90 Ko. Les constats sont reliés à leurs archives, à leurs `ScannerRun` et à leur organisation. Les rejeux ne créent aucun doublon et mettent à jour la même ligne.

La résolution reste **non vérifiée en conditions réelles** : les scans réels disponibles ne permettent pas de faire disparaître le constat de manière sûre. Les tests déterministes couvrent ce comportement, mais ils ne remplacent pas une preuve réelle. Le statut global est donc **partiellement vérifié en conditions réelles**, avec les points ci-dessus clairement distingués.
