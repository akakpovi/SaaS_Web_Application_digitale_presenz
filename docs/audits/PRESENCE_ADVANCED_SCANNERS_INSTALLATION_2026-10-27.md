# Présence — Installation et validation des scanners avancés

**Date** : 27 octobre 2026
**Hôte** : `elom-Latitude-E7470` — utilisateur `elom`
**Projet** : `/home/elom/Schreibtisch/SaaS_Web_Application_digitale_presenz` (branche `main`, arbre de travail déjà chargé de modifications non commitées — **conservées**, aucune remise à zéro)
**Démon Docker** : **partagé** avec d'autres projets (`ai-platform`, `fingptfinrobot`, `backend`, `presence-validation`, autres) — aucun nettoyage global, aucune ressource d'un autre projet touchée
**Objet** : installer les six scanners avancés manquants (Nmap, Nikto, WhatWeb, testssl.sh, DNSRecon, Gobuster), les relier au pipeline Presence (orchestrateur → sandbox → archivage → constats), puis **valider chaque scanner par une exécution réelle** sur la cible autorisée `appchat.elomaiapp.com`.

---

## 1. Architecture retenue

Les six outils sont installés **dans une image sandbox dédiée**, jamais dans les conteneurs applicatifs :

| Élément | Valeur |
|---|---|
| Image | `presence-scanner-tools:2026-10-27` — `sha256:1dabdd7313d4d0b9e8edb545e24b5906cf26d4115e50353db20764748259a887` (334 MB) |
| Dockerfile | `backend/docker/scanner-tools/Dockerfile` |
| Utilisateur | `scanner` (uid/gid 10001), non-root |
| Durcissement à l'exécution | `--read-only`, `--cap-drop ALL`, `--pids-limit`, `--memory`, `--cpus`, `--tmpfs /tmp` (64 Mo), aucun secret injecté |
| Réseau | `presence_scanner_sandbox`, derrière `scanner-egress-guard` (inchangé) |
| Exécution | depuis **`celery-worker`** uniquement : c'est le seul service qui possède le client Docker et `/var/run/docker.sock` |
| Collecte du rapport | stdout pour nmap / nikto / whatweb / dnsrecon / nuclei ; **fichier dans un répertoire bind-monté** pour testssl.sh (son rapport et sa sortie lisible ne partagent pas le même flux) |
| Archivage | JSONL horodaté par scanner sous `/app/scanner-archives/<scanner>/<AAAA>/<MM>/<JJ>/<scanner>-scan<N>-<sha12>.jsonl` (volume nommé monté dans le worker) |

Raisons du choix :

1. **Isolation** — un scanner qui plante, sature la mémoire ou écrit n'importe où ne peut pas atteindre le code applicatif ni la base.
2. **Aucun outil dans l'image web** — le service `web` n'a ni binaire de scan ni accès au démon Docker ; y lancer un scan produit honnêtement `unavailable` (cf. § 7.3, scan 4).
3. **Reproductibilité** — image taguée, outils épinglés par version + somme de contrôle à la construction ; la sandbox ne fait jamais `docker pull` pendant un scan.

---

## 2. Versions exactes des six scanners

Relevées **dans l'image réellement exécutée** (`docker run … --version`) :

| Scanner | Version | Source de l'installation |
|---|---|---|
| Nmap | **7.93** | paquet Debian bookworm |
| Nikto | **2.6.1** | archive amont vérifiée par `sha256sum`, wrapper `/usr/local/bin/nikto`, `/etc/nikto.conf` avec mise à jour/telemetry désactivées |
| WhatWeb | **0.5.5** | paquet Debian bookworm (Ruby) |
| testssl.sh | **3.0.8+dfsg-1** | paquet Debian bookworm (`/usr/bin/testssl` — le paquet n'installe pas de nom `testssl.sh`) |
| DNSRecon | **1.1.3** | paquet Debian bookworm (Python) |
| Gobuster | **3.6** | binaire amont vérifié par `sha256sum` |

Outils conservés sans modification : `projectdiscovery/nuclei:latest` (Nuclei 3.11.1, catalogue de templates monté depuis l'hôte) et `zaproxy/zap-stable:latest`.

Contrôle de présence/version : `backend/docker/scanner-tools/check-tools.sh` (installé comme `scanner-tools-check` dans l'image) — vérifie les six binaires, leurs versions et les listes de chemins.

---

## 3. Fichiers modifiés

### 3.1 Installation et intégration (mission complète)

- `backend/docker/scanner-tools/Dockerfile`, `backend/docker/scanner-tools/check-tools.sh` — image sandbox des six outils.
- `backend/config/settings/base.py` — `SCANNER_CONFIG` des six scanners (timeouts, limites sandbox, mot de passe/wordlist, `SCANNER_ARCHIVE_SCANNERS`), `SCANNER_SANDBOX` (image par scanner, `shared_work_dir`, `docker.user`).
- `backend/scanners/implementations/{nmap,nikto,whatweb,testssl,dnsrecon,gobuster}.py` — adaptateurs (commande, parse, normalisation, complétude, rapport brut).
- `backend/scanners/parsers/{nmap,nikto,whatweb}.py` — analyseurs de sortie.
- `backend/scanners/base.py`, `backend/scanners/registry.py`, `backend/scanners/executors/sandbox.py`, `backend/scanners/artifacts.py` — exécution sandbox, montages contrôlés, archivage `0600`/`0700`.
- `backend/scans/services/steps_builder.py`, `backend/scans/services/status.py`, `backend/scans/services/orchestrator.py` — étapes de scan, agrégation `partial`/`failed`, archivage et ingestion.
- `backend/scans/management/commands/validate_advanced_scanners.py` — commande de validation réelle, ne rapportant que ce qui est observé.
- `backend/scanners/tests/*`, `backend/scans/tests/*` — couverture (commandes, parseurs, complétude, timeout, statut agrégé, isolation).

### 3.2 Corrections issues de cette validation (27/10, après-midi)

| Fichier | Correction |
|---|---|
| `backend/scanners/implementations/nikto.py` | suppression de `-Format json` (et de toute sortie fichier) : l'image sandbox est en lecture seule, Nikto ne pouvait pas écrire son rapport et ne produisait rien (sortie vide, code 30). Le rapport par défaut de Nikto va sur stdout et est collecté par le lanceur. |
| `backend/scanners/parsers/nikto.py` | analyseur texte réel : identifiants `+ [011799] /: …`, `+ OSVDB-… /chemin: …`, `+ /chemin: …` ; les lignes de contexte (`Target IP:`, `Server:`, `Start Time:`, `host(s) tested`…) ne deviennent plus des constats. |
| `backend/scanners/implementations/dnsrecon.py` | extraction du document JSON **dans un flux mixte** (`raw_decode` à partir de chaque `[`/`{`) : dnsrecon écrit son rapport JSON et sa progression sur **le même flux**, ce qu'un `json.loads` strict rejetait (rapport complet compté comme « 0 enregistrement »). Le pseudo-enregistrement `ScanInfo` (ligne de commande, horodatage) n'est plus transformé en constat. |
| `backend/scanners/implementations/testssl.py` | exécution bornée `--std` (protocoles, catégories de chiffrement standard, valeurs par défaut + certificat serveur, HSTS/en-têtes) au lieu d'un run complet impossible à terminer dans un budget d'étape. |
| `backend/config/settings/base.py` | `SCANNER_TIMEOUT_TESTSSL` 50 → **90 s**, `SCANNER_TESTSSL_CPU_SECONDS` 75 → **120 s**, avec la mesure qui justifie ces valeurs. |
| `backend/.env.example` | documentation du budget testssl (`SCANNER_TIMEOUT_TESTSSL`, `SCANNER_TESTSSL_CPU_SECONDS`). |
| `backend/scanners/tests/__init__.py` | nouveaux tests : parseur texte Nikto (constats conservés, métadonnées écartées), extraction JSON dnsrecon en flux mixte, en-tête `ScanInfo` non normalisé. |
| `backend/scanners/tests/test_advanced_security.py` | nouveaux tests de commandes : nikto sans sortie fichier, testssl borné (`--std`), dnsrecon `-t std` uniquement, gobuster borné. |
| `backend/scanners/tests/test_advanced_tool_adapters.py` | attentes de commandes mises à jour pour refléter les corrections (l'ancienne attente encodait le bug nikto `-Format json`). |

Aucun test n'a été supprimé ni affaibli ; les attentes modifiées portent sur des commandes dont le comportement réel a été observé.

---

## 4. Images reconstruites et services recréés

```
docker compose build web celery-worker          # OK
docker compose up -d --no-deps --force-recreate web celery-worker
```

| Service | Image après mission | Accès Docker |
|---|---|---|
| `web` | `saas_web_application_digitale_presenz-web:latest` — `sha256:ec62d5ced5c21ff1bdf0ab24bd10a1808141052ecaf1f7b44ac868c012b1b220` | **non** (volontaire) |
| `celery-worker` | `saas_web_application_digitale_presenz-celery-worker:latest` — `sha256:0347fd20e05cfb3efdc8ed5553287303c9f3fee47806cdf1488b9afa16fc6094` | oui (`/usr/bin/docker`, `/var/run/docker.sock` monté) |
| sandbox | `presence-scanner-tools:2026-10-27` — `sha256:1dabdd73…` | — |

Vérifié **dans le conteneur actif** (et non déduit du `build`) : présence de `--std` dans `scanners/implementations/testssl.py`, de `_NON_RECORD_TYPES` dans `implementations/dnsrecon.py`, et `SCANNER_CONFIG['testssl']['timeout'] == 90`. Aucun volume, aucune base et aucune archive supprimés ; base et jeux d'essai conservés.

---

## 5. Tests automatisés

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh scanners` | **163 tests, OK** |
| `bash scripts/run_backend_tests.sh scanners.tests.NiktoParserTests scanners.tests.DnsreconParserTests scanners.tests.test_advanced_tool_adapters` | **35 tests, OK** |
| `bash scripts/run_backend_tests.sh scanners.tests.NiktoParserTests scanners.tests.DnsreconParserTests scans.tests.test_status_integrity advisory.tests.test_scan_ingestion` | **42 tests, OK** |
| `python manage.py check` | `System check identified no issues (0 silenced).` |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `docker compose config --quiet` | OK |
| `bash scripts/run_backend_tests.sh scans` | **195 tests, OK** (212 s) |
| `bash scripts/run_backend_tests.sh advisory` | **177 tests, OK** |

`pnpm exec tsc --noEmit` et `pnpm run build` n'ont **pas** été relancés : aucun fichier frontend n'a été modifié par cette mission.

---

## 6. Preuves d'exécution réelle — scan **5**

Commande : `docker compose exec -T celery-worker python manage.py validate_advanced_scanners --domain appchat.elomaiapp.com --scan-type security --json`
Cible : `appchat.elomaiapp.com` (cible autorisée du projet), scan **complet du profil `security`**.

| Étape | Statut | Code sortie | Durée | Constats en base | Archive |
|---|---|---|---|---|---|
| nmap | `completed` | 0 | 6,0 s | 4 | `nmap/2026/10/27/nmap-scan5-5c3a6b791fb3d0ae.jsonl` (10 363 o) |
| nikto | `completed` | 0 | 8,6 s | 3 | `nikto/2026/10/27/nikto-scan5-eee0dada1009fb19.jsonl` (1 467 o, 20 lignes) |
| nuclei | `completed` | 0 | 68,4 s | 0 | `nuclei/2026/10/27/nuclei-scan5-e3b0c44298fc1c14.jsonl` (0 o — aucun constat) |
| whatweb | `completed` | 0 | 8,7 s | 10 | `whatweb/2026/10/27/whatweb-scan5-73f234203fa5b15a.jsonl` (542 o) |
| testssl | `completed` | 0 | 71,9 s | 2 | `testssl/2026/10/27/testssl-scan5-59726f3cbb0b1d46.jsonl` (7 147 o, 168 lignes) |
| dnsrecon | `completed` | 0 | 4,1 s | 3 | `dnsrecon/2026/10/27/dnsrecon-scan5-8ac269cf08691ab3.jsonl` (1 249 o) |
| gobuster | `partial` (`exit_code_1`) | 1 | 2,4 s | 1 | aucune (`no_raw_report` — l'outil a refusé de continuer, cf. § 8) |
| zap | `completed` | — | 107,0 s | 12 | — |

**Statut agrégé du scan : `partial`** — correct : sept étapes ont terminé, gobuster a explicitement refusé d'analyser la cible. Aucun succès complet n'a été revendiqué, et aucun constat n'a été résolu à partir de ce scan (cf. § 9).

Montage du volume d'archives, vérifié par `docker inspect` sur le worker réellement actif :

```
volume saas_web_application_digitale_presenz_scanner_archive_data
  -> /app/scanner-archives (rw=true)
```

Contenu : 30 fichiers, 240 Ko au total, répartis par scanner (nmap 64 Ko, nikto 40 Ko, whatweb 40 Ko, dnsrecon 40 Ko, testssl 28 Ko, nuclei 24 Ko). Permissions conformes aux missions précédentes (répertoires `0700`, fichiers `0600`).

---

## 7. Validation des trois corrections

### 7.1 Nikto — avant/après

| | Avant | Après |
|---|---|---|
| Commande | `nikto -h … -Format json` (sans `-o`) | `nikto -h … -nointeractive -ask no -timeout 10 -maxtime 85s` |
| Comportement | Nikto tente d'écrire `nikto_<hôte>_<date>.json` dans un système de fichiers **en lecture seule**, échoue et termine en code **30** | rapport par défaut sur stdout, collecté par le lanceur |
| Résultat | archive de **91 octets**, statut `partial` | archive de **1 467 octets / 20 lignes**, statut `completed`, **3 constats** |
| Reproductions | `-o -` (flux stdout) ne produit **rien** (vérifié) | `+ [011799] /: An alt-svc header …`, `+ [999106] /: Cloudflare detected …` correctement analysés |

### 7.2 DNSRecon — flux mixte

Le rapport JSON et les lignes de progression (`[*] AAAA …`, `[+] 0 Records Found`, `[*] Saving records to JSON file: /dev/stdout`) partagent stdout : un `json.loads` sur tout le tampon échouait, si bien qu'un run **complet** était enregistré avec `records: 0`.

- Contrôle par rejeu sur l'archive réelle du scan 5 : `parsed records = 5` (ScanInfo + 2 A + 2 AAAA).
- Contrôle par exécution réelle de l'adaptateur seul dans le worker (sandbox Docker) : `complete=True`, `dnsrecon found 5 DNS record(s)`, constats `dnsrecon.a_records` (2 enregistrements : 188.114.97.3, 188.114.96.3) et `dnsrecon.aaaa_records` (2), **aucun constat `scaninfo`**.
- Périmètre dnsrecon inchangé : `-t std` uniquement (NS/SOA/A/AAAA/MX/SRV/PTR), `--lifetime 8` ; aucun transfert de zone, aucune force brute.

### 7.3 testssl.sh — portée bornée

Mesures réelles dans la sandbox sur la cible autorisée :

| Variante | Résultat |
|---|---|
| Run complet (toutes les vérifications) | **> 200 s**, interrompu — ne peut pas tenir dans un budget d'étape |
| `--fast` | **> 200 s**, interrompu (conteneur de mesure arrêté et supprimé) |
| **`--std`** (retenu) | **50 s** en isolation, **71,9 s** lors du scan réel → `completed`, rapport de 7 147 o |

Décision : conserver une portée que l'étape peut réellement terminer plutôt qu'augmenter le timeout pour masquer un outil trop lent. Budget : 90 s (marge ~1,25× sur la mesure la plus défavorable) et 120 s de CPU. Ce que la portée `--std` **ne couvre pas** est explicité au § 10.

### 7.4 `web` sans accès Docker — dégradation honnête (scan 4)

Un scan lancé depuis le service `web` (qui n'a volontairement ni client Docker ni socket) a produit : **les huit étapes `unavailable` en 8–13 ms**, `Scan.status = failed`, aucune archive, aucun constat, aucune résolution. C'est le comportement attendu : un environnement incapable d'exécuter la sandbox est déclaré comme tel plutôt que présenté comme un scan réussi. Le scan 4 est conservé en base comme preuve.

---

## 8. Gobuster sur une cible « catch-all » — limite documentée

Message réel de l'outil :

```
Error: the server returns a status code that matches the provided options for non existing urls.
  https://appchat.elomaiapp.com/4fc70b3d-… => 200 (Length: 7473).
  To continue please exclude the status code or the length
```

Vérification indépendante : deux chemins inexistants tirés au hasard renvoient **HTTP 200** (application monopage). Gobuster refuse donc de poursuivre, termine en code 1 et n'énumère aucun chemin. L'adaptateur :

- enregistre le run en `partial` avec `partial_reason=exit_code_1` ;
- ne fabrique **aucun** constat de chemin trouvé ;
- n'archive pas de rapport (aucun rapport n'existe) — l'échec est explicite (`no_raw_report`), pas silencieux.

Enumération volontairement bornée (`-t 10`, wordlist `common.txt` de 4 614 entrées livrée par l'image, jamais fournie par l'entrée utilisateur).

---

## 9. Ingestion, déduplication et non-résolution

Rejeu d'ingestion sur des données **réelles** (12 constats ZAP du scan 5, cible autorisée) :

| Appel | `created` | `updated` | `resolved` | Lignes `SecurityFinding` de l'actif |
|---|---|---|---|---|
| 1er | 0 | 12 | 0 | 12 |
| Rejeu du même rapport | **0** | 12 | 0 | **12** |
| Run incomplet et vide (`complete=False`) | 0 | 0 | **0** | 12 |

- Aucun doublon créé au rejeu : la déduplication par `(actif, source, vulnérabilité)` est confirmée sur données réelles.
- Un run **incomplet** ne résout rien : `resolve_missing=False` est propagé et `resolved=0`.
- Les constats opérationnels (`.unavailable`, `.timeout`, `.sandbox_unavailable`, …) restent des diagnostics : ils ne créent pas de `SecurityFinding` et forcent une ingestion non résolvante.
- Périmètre : `advisory.services.scan_ingestion.SECURITY_SCANNERS = (zap, nuclei)`. Les six outils avancés persistant leurs constats dans `scans.Finding` (un par type/port/technologie, rattaché au `ScannerRun` et affichable dans l'interface), ils **n'alimentent pas** la table `SecurityFinding` lue par l'assistant IA. Étendre cette ingestion (ports/DNS/TLS/technologies) est une décision produit distincte : elle n'a pas été prise ici.

---

## 10. État de Nuclei et ZAP (non-régression)

| Scanner | Scan 1 | Scan 2 | Scan 5 |
|---|---|---|---|
| nuclei | `completed`, 100 %, 0 constat (60,6 s) | **`partial` — `host_unresponsive`, `host_skipped=true`, 2 % de couverture** (39,8 s) | `completed`, 0 constat (68,4 s) |
| zap | `completed` (104,2 s) | `completed` (83,1 s) | `completed`, 12 constats (107,0 s) |

Le run nuclei du scan 2 est le cas le plus instructif : l'hôte est devenu non réactif en cours de scan, Nuclei l'a signalé (`percent=2`), et l'étape a été enregistrée en `partial` avec `partial_reason=host_unresponsive` **sans aucun constat résolu** — exactement le comportement attendu d'un scan incomplet. Ni Nuclei ni ZAP n'ont régressé du fait de l'ajout des six outils.

---

## 11. Disque et journaux

| Mesure | Valeur |
|---|---|
| Système de fichiers `/` | 234 Go, 204 Go utilisés, **18 Go libres** (92 %), inodes 22 % utilisés |
| Images Docker | 20,96 Go au total, dont 12,02 Go récupérables (partagé avec les autres projets — **non nettoyé**) |
| Volumes Docker | 2,19 Go, dont 1,19 Go récupérables |
| Cache de construction | 2,76 Go, dont 1,1 Go récupérables |
| Archives de scan (volume worker) | 240 Ko / 30 fichiers |
| `/var/log/syslog` | 13,9 Mo, croissance mesurée **149 Kio/min ≈ 8,7 Mio/h** |
| Journal systemd | 153,5 Mo, **stable** sur la fenêtre mesurée |

**Cause de la croissance des journaux, mesurée** : `csc_vpnagent` (Cisco Secure Client) écrit **~92 % des lignes** de `syslog` (461 des 500 dernières lignes), en boucle sur `GetDNSConfig` / `getDnsConfiguration` / `TestNetEnv`. Ce service n'appartient pas à Presence et son fonctionnement n'a **pas** été modifié.

Action appliquée (déjà validée plus tôt dans la journée, avec accord explicite) : rotation `/etc/logrotate.d/rsyslog` en `daily`, **`maxsize 50M`**, `rotate 7`, `compress`, `delaycompress` — la croissance est désormais **bornée** (~50 Mo par rotation, une semaine d'historique compressé) au lieu de gonfler sans limite. Configuration validée par `logrotate -d` et effet constaté (syslog retombé de 519 Mo à ~14 Mo).

Recommandations (non appliquées, hors périmètre Presence) :

1. Plafonner le journal systemd (`SystemMaxUse=500M`) : `journald.conf` ne définit aujourd'hui aucune limite explicite.
2. `docker builder prune` reste possible (1,1 Go récupérable) mais **le cache est partagé** entre projets : à faire par l'opérateur, en connaissance de cause.
3. Sur un hôte « catch-all » comme celui-ci, un scan `deep` produit des rapports volumineux ; la rétention d'archives (30 jours) et les limites de taille par rapport sont en place et suffisent.

---

## 12. Limites et actions restantes

1. **testssl.sh** : portée `--std` (protocoles, catégories de chiffrement standard, valeurs par défaut + certificat, HSTS/en-têtes). **Ne sont pas couverts** : sondes de vulnérabilités (`-U` : HEARTBLEED, CCS, ticketbleed, ROBOT, CRIME, BREACH…) et énumération par chiffrement (`-e`/`-E`). Ces variantes dépassent 200 s sur cette cible et ne peuvent pas tenir dans un budget d'étape.
2. **Gobuster** : décline par conception les cibles à réponse « catch-all » ; aucun contournement par `--exclude-length` codé en dur n'a été introduit (la longueur dépend de la cible).
3. **DNSRecon** : énumération standard uniquement ; pas de transfert de zone ni de force brute (choix de sécurité, maintenu).
4. **Ingestion IA** : les six outils ne construisent pas de `SecurityFinding` (périmètre `(zap, nuclei)` inchangé).
5. **Validation navigateur** : l'interface n'a pas été parcourue dans cette mission ; les statuts exposés sont ceux de la base et de l'API. Les six outils apparaissent dans les détails de scan et le panneau de sécurité de l'actif (code inchangé depuis les missions UI précédentes).
6. **Journald** : plafond recommandé, non appliqué (modification système, décision opérateur).
7. **Aucun scan `deep`** n'a été lancé (budget dédié), et aucun scan n'a été exécuté sur une autre cible que la cible autorisée.

---

## 13. Critères de réussite

| Critère | État | Preuve |
|---|---|---|
| Les six scanners sont installés dans les environnements appropriés | ✅ | image `presence-scanner-tools:2026-10-27`, `scanner-tools-check`, versions § 2 |
| Versions et dépendances documentées | ✅ | § 2 |
| Le worker actif utilise les images mises à jour | ✅ | vérification dans le conteneur actif (§ 4) |
| Chaque scanner a passé un test d'exécution réelle autorisée | ✅ | § 6 (tableau scan 5) + § 7 (contrôles ciblés) |
| Les résultats sont récupérés et archivés | ✅ | archives par scanner, 30 fichiers, volume vérifié par `docker inspect` |
| Ingestion et déduplication validées | ✅ | § 9 (rejeu : 0 créé, 0 résolu) |
| Timeouts et statuts incomplets gérés honnêtement | ✅ | § 7.3, § 7.4, § 8, § 10 |
| Aucun constat résolu sur la base d'un scan incomplet | ✅ | § 9 (`resolved=0`), gobuster `partial` sans résolution |
| Nuclei et ZAP continus de fonctionner | ✅ | § 10 |
| Les autres projets Docker restent intacts | ✅ | aucun volume/image/conteneur d'un autre projet touché |
| Consommation disque raisonnable | ✅ | § 11 (18 Go libres, archives 240 Ko, rotation bornée) |
| Rapport final créé | ✅ | ce document |

---

## 14. Séparation explicite des vérifications

**Tests automatisés** — 163 + 35 + 42 tests ciblés OK (scanners, parseurs, commandes, intégrité de statut, ingestion), `manage.py check`, `makemigrations --check`, `docker compose config`. Ces tests utilisent des fixtures et ne prouvent pas le comportement réel des outils.

**Exécutions locales réelles** — scans 1, 2, 4 et 5 via la pile Docker locale (worker + sandbox + egress-guard) ; mesures d'exécution des outils dans la sandbox (nikto, dnsrecon, testssl, gobuster) ; rejeu d'archives et rejeu d'ingestion sur données réelles.

**Cible externe autorisée** — `appchat.elomaiapp.com` uniquement (propriétaire du projet), profils `security` (scan 5) ; aucun scan agressif ni test d'exploitation.

**Vérifications non effectuées** — parcours navigateur de l'interface ; scan `deep` ; plafond journald ; ingestion `SecurityFinding` des six outils ; variantes testssl `-U`/`-e`/`-E` ; test sur une seconde cible.

Aucun résultat de ce rapport n'est extrapolé : chaque chiffre provient d'une ligne de base, d'un fichier d'archive, d'une sortie de commande ou d'une mesure d'horloge citée ci-dessus.
