# Rapport — Orchestrateur de scan et délégation sécurisée d'outils externes

**Projet :** Presence (`SaaS_Web_Application_digitale_presenz_v2/backend`)
**Date :** 24 octobre 2026
**Périmètre :** `scans.services.orchestrator`, `scanners.executors.sandbox`, `scanners.implementations.lighthouse`, `scanners.implementations.testssl`
**Verdict :** ✅ l'orchestrateur peut déléguer des outils externes sous contraintes de ressources et de sécurité. Lighthouse est intégré et normalisé. testssl.sh est migré sur le même chemin. OWASP ZAP et Nuclei sont derrière un feature flag et s'exécutent dans la sandbox ; l'egress réseau est verrouillé par un garde nftables (voir le rapport [`LIGHTHOUSE_EGRESS_ADVANCED_SECURITY.md`](LIGHTHOUSE_EGRESS_ADVANCED_SECURITY.md)).

---

## 1. Résumé exécutif

Le moteur de scan ne se contente plus d'exécuter des scanners Python « en interne » : il pilote désormais des binaires open source et, optionnellement, des conteneurs éphémères. La refonte repose sur trois couches distinctes :

| Couche | Responsabilité | Fichier |
|---|---|---|
| **Politique** | Orchestration, budget global, validation SSRF centrale, persistance `ScannerRun` / `Finding` / `CheckResult` | `scans/services/orchestrator.py` |
| **Isolation** | Timeout strict, CPU, RAM, descripteurs, output, concurrence, mode processus ou Docker | `scanners/executors/sandbox.py` |
| **Adaptation** | Commande propre à chaque outil, parsing, normalisation métier | `scanners/implementations/*`, `scanners/parsers/*` |

Garanties effectives :

- **Timeout dur** : chaque outil est tué (groupe de processus entier, pas seulement le PID parent) à l'échéance.
- **CPU** : `RLIMIT_CPU` en mode processus ; `--cpus` en mode Docker.
- **RAM** : watchdog RSS sur `/proc` (échantillonnage 250 ms) en mode processus ; `--memory` / `--memory-swap` (cgroup) en mode Docker.
- **Budget global** : `SCAN_TOTAL_TIME_BUDGET_SECONDS` (540 s par défaut) partagé par toutes les étapes ; les étapes restantes sont marquées `skipped` si le budget est épuisé.
- **Concurrence** : sémaphore Redis (`SCANNER_SANDBOX_MAX_CONCURRENCY`, 2 par défaut) pour éviter que deux scans lancent deux Chromium simultanément.
- **SSRF** : aucune cible n'est transmise à un outil externe sans validation centrale préalable (localhost, IP privées, link-local, métadonnées cloud, rebinding DNS).
- **Traçabilité** : chaque exécution écrit `ScannerRun.metadata` (`scanner_type`, `timeout_s`, `target_validated`, `memory_mb`, `cpu_seconds`, `blocked`, `reason`).
- **Enveloppe centralisée** : l'orchestrateur calcule `SandboxLimits` (`timeout`, CPU, RAM) et la transmet à l'adaptateur via `ScanContext.sandbox_limits` ; l'adaptateur ne peut pas élargir discrétionnairement son budget.

---

## 2. Architecture de délégation

### 2.1 Flux d'une étape externe

```
ScanOrchestrator._run_all_steps
        │
        ├─ 1. budget restant ? ── non ──> étapes restantes = skipped
        │
        ├─ 2. scanner disponible ? ── non ──> ScannerRun.status = unavailable
        │
        ├─ 3. target externe ? ──> _validated_target()  ← SSRF centralisé
        │        │                        └─ échec ──> blocked / ssrf (jamais exécuté)
        │        └─ ScanContext(target, timeout, deadline)
        │
        ├─ 4. scanner.execute(domain, context)   ← une seule exécution
        │        │
        │        └─ get_sandbox_executor().run(...)
        │              ├─ mode process : Popen + setsid + rlimits + watchdog RSS
        │              └─ mode docker  : docker run --rm … (cgroup + FS read-only)
        │
        ├─ 5. persistance Finding[] (normalisés)
        ├─ 6. persistance CheckResult (catégorie déclarée par le scanner)
        └─ 7. ScannerRun.finish(metadata={...})
```

### 2.2 Deux modes d'exécution

| | `process` (défaut) | `docker` |
|---|---|---|
| Isolation | Processus séparé, session/groupe dédié | Conteneur jetable |
| CPU | `RLIMIT_CPU` | `--cpus` (cgroup) |
| RAM | Watchdog RSS (échantillonné) | `--memory` + `--memory-swap` (dur) |
| Processus enfants | Groupe tué via `killpg` | `--pids-limit` |
| Système de fichiers | `umask 077`, `RLIMIT_FSIZE` | `--read-only`, tmpfs `/tmp`, `--cap-drop=ALL` |
| Réseau | Réseau de l'hôte | `--network` configurable |
| Prérequis | Binaire sur le `PATH` du worker | CLI Docker + socket + image pré-téléchargée (`--pull never`) |
| Recommandé pour | testssl.sh, nmap, nuclei, gobuster… | Lighthouse/Chromium, outils à risque |

**Important :** le mode `process` est une isolation **de ressources**, pas une isolation de privilèges. Le binaire tourne avec l'utilisateur du worker et voit le même noyau. Pour du multi-tenant hostile, utiliser le mode Docker sur un worker dédié, ou un runner séparé.

### 2.3 Limites par outil

Valeurs par défaut (surchargables par `SCANNER_CONFIG[name]["sandbox"]`) :

| Scanner | Timeout | RAM (process) | RAM/CPU (docker) | Fichiers ouverts |
|---|---:|---:|---|---:|
| Lighthouse | 120 s | 2048 MB (watchdog) | 1 CPU, 2048 MB | 4096 |
| testssl.sh | 60 s | 384 MB | 1 CPU, 384 MB | 1024 |
| nmap / nikto / nuclei / whatweb / dnsrecon / gobuster / feroxbuster | 30–180 s | 512 MB | 1 CPU, 512 MB | 1024 |

Plafond absolu : `SCANNER_SANDBOX_MAX_TIMEOUT=300`. Un timeout configuré à 9999 s est ramené à 300 s, puis au budget restant du scan.

### 2.4 Budget et concurrence

- `SCAN_TOTAL_TIME_BUDGET_SECONDS=540` : au-delà, plus aucun outil n'est lancé. Les étapes non exécutées sont explicitement `skipped` avec la raison, jamais silencieusement « réussies ».
- `SCANNER_SANDBOX_MAX_CONCURRENCY=2` : jeton Redis `scanner-sandbox-slot:*`, TTL `timeout + 120 s`. En cas d'indisponibilité du cache, le garde-fou est **fail-open** et journalisé : une panne Redis ne doit pas bloquer tous les scans (Celery dépend déjà de Redis).
- Le timeout effectif d'une étape est `min(timeout configuré, SCANNER_SANDBOX_MAX_TIMEOUT, budget restant)`.

---

## 3. Protection SSRF centralisée

### 3.1 Point d'entrée unique

`ScanOrchestrator._validated_target(domain)` appelle `scanners.security.target_validator.validate_target()`, lui-même adossé à `core.security`. La validation est **mémoïsée** pour le scan (succès ou rejet), et intervient **avant** tout appel à `scanner.execute()` pour un scanner `CLI` ou `API`.

Ce qui est refusé :

- `localhost`, `.local`, `.internal`, `.lan`, `.home`, `.corp`, `.test`, `.invalid`, `.example` et autres suffixes internes ;
- les IP littérales fournies par l'utilisateur (aucun scan direct d'IP) ;
- les schémas autres que HTTP/HTTPS, les ports autres que 80/443, les credentials dans l'URL ;
- toute adresse résolue non globalement routable : loopback, RFC1918, link-local, multicast, CGNAT, IPv6 ULA, etc. ;
- les endpoints de métadonnées cloud (`169.254.169.254`, `fd00:ec2::254`, `100.100.100.200`, `metadata.google.internal`) ;
- un nom qui résout vers un mélange d'adresses publiques et privées (rejet total, pas de « sélection de la bonne IP »).

### 3.2 Défense en profondeur

| Niveau | Contrôle |
|---|---|
| 1. Orchestrateur | Gate central avant toute délégation (`ScannerBlocked`) |
| 2. Adaptateur | Chaque scanner réseau revalide sa cible (`validate_target`) |
| 3. Transport Python | `core.security.safe_request` : DNS pinning sur l'IP validée, redirects revalidés hop par hop, taille de réponse plafonnée |
| 4. Exécution | `shell=False`, cible toujours passée comme argument séparé |
| 5. Post-exécution Lighthouse | `finalUrl` revalidée : un rapport obtenu après redirection vers une adresse privée est **rejeté** |
| 6. DNS rebinding Lighthouse | `--host-resolver-rules=MAP <host> <ip>` épingle l'hôte audité sur l'IP validée (IPv4), activé par défaut |

Un rejet SSRF n'échoue **pas** le scan entier : l'étape est marquée `failed` avec `metadata={"blocked": true, "reason": "ssrf"}`, l'outil n'est jamais lancé, et les scanners internes continuent. C'est un choix produit : un domaine invalide reste un scan utile pour le reste du diagnostic, sans jamais toucher le réseau interne.

### 3.3 Risque résiduel explicitement documenté

Un navigateur headless charge des **sous-ressources** (CDN, iframes, redirections) que le contrôle de la navigation principale ne couvre pas intégralement. Les mitigations en place :

1. validation de l'URL initiale et de l'URL finale ;
2. épinglage DNS de l'hôte principal ;
3. `--proxy-server` optionnel (`SCANNER_LIGHTHOUSE_CHROME_PROXY`) pour forcer la sortie via un proxy filtrant ;
4. mode Docker avec réseau dédié (`SCANNER_SANDBOX_DOCKER_NETWORK`).

**Exigence d'infrastructure :** le réseau utilisé par les scanners doit refuser toute destination RFC1918, link-local, loopback et `169.254.169.254` (règle nftables/iptables ou politique d'egress du VPC). C'est la seule barrière réellement complète contre un navigateur qui suit une sous-ressource malveillante. À défaut d'un tel filtrage, le risque SSRF résiduel du navigateur reste **moyen** et doit être accepté explicitement.

---

## 4. Intégration Lighthouse

### 4.1 Exécution

```bash
lighthouse https://example.com \
  --output=json --output-path=stdout --quiet \
  --only-categories=performance,seo \
  --preset=desktop \
  --chrome-flags="--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu \
                  --host-resolver-rules=MAP example.com 93.184.216.34"
```

- Lancé par `SandboxedCommandExecutor` (mode `process` ou `docker`).
- Aucune exécution depuis un shell ; la cible est un argument distinct.
- `--chrome-flags` reçoit `CHROME_PATH` via un environnement filtré (aucun secret hérité).
- Le binaire n'est pas installé par défaut : `INSTALL_LIGHTHOUSE=true` à la construction de l'image, ou image Docker configurée via `SCANNER_DOCKER_IMAGE_LIGHTHOUSE`.

### 4.2 Normalisation vers le schéma existant

`parse_lighthouse_json()` extrait :

- scores de catégorie (0–1) pour `performance` et `seo` ;
- audits actionnables (score < 1.0) + métriques Cœur du Web systématiquement conservées : FCP, LCP, TBT, CLS, Speed Index, TTFB, poids total ;
- `runtimeError`, `runWarnings`, version, URL finale.

L'adaptateur produit :

**Un `CheckResult` `performance`** (catégorie existante, aucune migration) :

| Champ | Valeur |
|---|---|
| `score` | score Lighthouse performance (0–1) × 15, arrondi → 0–15 (`CHECK_WEIGHTS["performance"]`) |
| `status` | `healthy` ≥ 90, `warning` ≥ 50, `critical` < 50 |
| `summary` | « Lighthouse performance 87/100, SEO 92/100 (LCP 2.1 s, CLS 0.02) » |
| `technical_details` | scores par catégorie, métriques, audits en échec, version, URL finale |
| `technical_details.scanner` | `"lighthouse"` (provenance pour AKA IA) |
| `technical_details.previous_measurement` | mesure `performance` précédente (legacy), conservée |

**Des `Finding` granulaires**, compatibles avec `Finding.Severity` / `Finding.Status` et le champ libre `Finding.category` :

| `check_code` | `category` | Sévérité |
|---|---|---|
| `lighthouse.performance_score` | `performance` | selon score |
| `lighthouse.seo_score` | `seo` | selon score |
| `lighthouse.largest-contentful-paint` | `performance` | seuils LCP + score |
| `lighthouse.meta-description` | `seo` | score |
| `lighthouse.render-blocking-resources` | `performance` | score |
| … | … | … |

Chaque `Finding` porte `detected_value`, `expected_value`, `evidence` (score, displayValue, numericValue, unité, poids) et `recommendation` pour les échecs. Les findings sont plafonnés (`SCANNER_LIGHTHOUSE_MAX_FINDINGS=60`) et triés par sévérité décroissante.

**SEO :** le schéma `CheckResult.Category` ne comporte pas de catégorie SEO et n'a pas été modifié. Le score SEO est donc exposé dans `technical_details.category_scores.seo` et dans les `Finding.category="seo"` (champ libre, déjà supporté par le modèle). AKA IA peut ainsi analyser le SEO sans migration de base.

**Coexistence avec le scanner `performance` historique :** l'étape Lighthouse est ajoutée après `performance` dans les scans `health` et `full`. Si Lighthouse réussit, son `CheckResult` (plus riche) remplace celui du scanner legacy et l'ancienne mesure est archivée dans `previous_measurement`. Si Lighthouse est indisponible ou échoue, le `CheckResult` legacy **reste intact** : aucune régression du score santé.

### 4.3 Modes d'échec (jamais silencieux)

| Situation | Score | Statut | Finding |
|---|---:|---|---|
| Timeout | 0 | warning | `lighthouse.timeout` |
| RAM dépassée | 0 | warning | `lighthouse.memory_limit` |
| Aucune sortie | 0 | warning | `lighthouse.no_output` |
| JSON invalide | 0 | warning | `lighthouse.parse_error` |
| Erreur Chromium | 0 | warning | `lighthouse.runtime_error` |
| Cible SSRF refusée | `null` | critical | `lighthouse.target_validation` |
| Binaire absent | `null` | neutral | `lighthouse.unavailable` (étape `unavailable`, pas d'échec de scan) |

Un score `0` est volontaire : une mesure absente ne doit jamais paraître « saine » dans le score global.

---

## 5. Validation

### 5.1 Tests ajoutés (51 tests)

| Fichier | Couverture |
|---|---|
| `scanners/tests/test_sandbox.py` | limites et clamp, exécution réelle, timeout + kill du groupe, watchdog RAM, troncature de sortie, environnement filtré, argv Docker durci, échec fermé sans Docker/image |
| `scanners/tests/test_lighthouse.py` | parsing JSON, bruit Chromium, audits ignorés, normalisation `CheckResult`/`Finding`, score 0–15, timeout, RAM, JSON invalide, `runtimeError`, SSRF, redirection privée, indisponibilité, cap des findings |
| `scans/tests/test_orchestrator_delegation.py` | blocage SSRF central (domaine interne, IP brute), absence de DNS si binaire absent, contexte de délégation, clamp timeout/budget, budget épuisé, fusion des `CheckResult`, conservation du legacy en cas d'échec |

L'exécution de Lighthouse est **mockée** dans tous les tests : aucun Chromium n'est lancé, aucun réseau externe n'est requis.

### 5.2 Résultats

```text
# Suites directement affectées
python manage.py test scans scanners public_checker core --noinput
Ran 292 tests in 328.356s
OK

# Suite backend complète
python manage.py test --noinput
Ran 536 tests in 608.456s
OK
```

Les 51 nouveaux tests font partie de ces 536. Aucune régression sur l'ensemble du backend.

---

## 6. Prêt pour testssl.sh et OWASP ZAP

### 6.1 testssl.sh — ✅ migré

- Passe par `get_sandbox_executor()` (timeout, CPU, RAM, concurrence).
- Une **seule** exécution par scan : `execute()` produit `ScanResult` + `Finding` à partir de la même sortie `--jsonfile /dev/stdout` (auparavant le binaire tournait deux fois).
- Ne crée **pas** de `CheckResult` : la catégorie `ssl` reste la propriété du scanner SSL interne, ce qui évite qu'un `score=None` écrase le score santé. Les findings testssl enrichissent l'analyse.

### 6.2 OWASP ZAP et Nuclei — ✅ sandbox + feature flag

Les deux outils sont opt-in (`SCANNER_ADVANCED_SECURITY_ENABLED=false` par défaut) :

- l'orchestrateur marque leur étape `skipped` avant toute résolution DNS et ne crée aucun `ScannerRun` ;
- chaque adaptateur refuse de s'exécuter s'il est appelé directement quand le flag est faux ;
- Nuclei passe par `SandboxedCommandExecutor` et produit `ScanResult` + `Finding` en **une seule** exécution ;
- ZAP accepte deux transports : image Docker officielle dans la sandbox (baseline passive, rapport monté depuis `/out`) ou sidecar REST ; l'active scan reste désactivé par défaut ;
- le réseau `presence_scanner_sandbox` est filtré par un garde nftables qui bloque RFC 1918, link-local, loopback, CGNAT et `169.254.169.254`, ainsi que tout accès scanner → hôte.

Voir les détails, commandes et preuves réseau dans [`LIGHTHOUSE_EGRESS_ADVANCED_SECURITY.md`](LIGHTHOUSE_EGRESS_ADVANCED_SECURITY.md).

### 6.3 Checklist pour un nouvel outil

1. Créer `scanners/implementations/<outil>.py` héritant de `BaseScanner` (`scanner_type=CLI` ou `API`).
2. Construire la commande avec la cible **en argument séparé** (`shell=False`).
3. Passer par `get_sandbox_executor().run(...)` et `limits_for("<outil>", timeout=context.effective_timeout(...))`.
4. Implémenter `execute()` pour produire `ScanResult` + `Finding` en une seule exécution.
5. Déclarer `check_result_category` si l'outil doit alimenter le score santé, puis l'enregistrer dans `scanners/__init__.py` et, si nécessaire, dans `steps_builder.py`.
6. Ajouter les tests avec l'exécution mockée (timeout, RAM, SSRF, sortie invalide).

---

## 7. Configuration et déploiement

### 7.1 Variables principales

```dotenv
SCANNER_SANDBOX_MODE=process            # ou docker
SCANNER_SANDBOX_MAX_TIMEOUT=300
SCANNER_SANDBOX_DEFAULT_MEMORY_MB=512
SCANNER_SANDBOX_MAX_CONCURRENCY=2
SCAN_TOTAL_TIME_BUDGET_SECONDS=540

SCANNER_TIMEOUT_LIGHTHOUSE=120
SCANNER_LIGHTHOUSE_MEMORY_MB=2048
SCANNER_LIGHTHOUSE_CATEGORIES=performance,seo
SCANNER_LIGHTHOUSE_PIN_TARGET_IP=true
SCANNER_LIGHTHOUSE_CHROME_PROXY=
SCANNER_DOCKER_IMAGE_LIGHTHOUSE=
```

### 7.2 Activer Lighthouse dans l'image

```bash
docker compose build --build-arg INSTALL_LIGHTHOUSE=true
```

L'image installe alors Node, Chromium et `lighthouse@12`. Sans ce build arg, l'étape est proprement `unavailable` (pas d'échec de scan).

### 7.3 Avertissement mode Docker

Le mode Docker exige le socket Docker sur le worker. Un socket monté équivaut à un accès root à l'hôte : ne l'activez que sur un worker dédié, jamais sur un hôte multi-tenant, et préférez un runner isolé (VM ou hôte séparé) pour les outils à risque. En mode `process`, les limites sont réelles mais ne constituent pas une frontière de privilèges.

---

## 8. Limites connues et prochaines étapes

1. **Watchdog RSS échantillonné** (250 ms) : un pic très bref peut dépasser la limite avant le kill. Le mode Docker (cgroup) est la garantie dure.
2. **Adaptateurs legacy** (nmap, nikto, nuclei, whatweb, dnsrecon, gobuster, feroxbuster) : ils utilisent désormais le sandbox, mais conservent leur ancien schéma `scan()` + `scan_findings()` (deux exécutions). Une migration vers `execute()` diviserait leur coût par deux.
3. **Egress navigateur** : le risque SSRF résiduel de Chromium/ZAP est couvert par le garde nftables du réseau scanner (mode Docker). En mode `process`, le worker lui-même n'est pas filtré, car il doit joindre PostgreSQL/Redis.
4. **Pas de `RLIMIT_AS`** : volontaire, car Node/Chromium réservent des espaces d'adressage incompatibles avec un plafond bas ; le watchdog RSS et les cgroups couvrent le besoin réel.
5. **SEO sans catégorie `CheckResult` dédiée** : choix de compatibilité. Une évolution ultérieure (catégorie `seo` + poids dans `CHECK_WEIGHTS`) nécessiterait une migration et une redistribution des poids.

---

## Annexe — Fichiers modifiés / ajoutés

| Fichier | Nature |
|---|---|
| `backend/scanners/executors/sandbox.py` | **nouveau** — exécuteur isolé (process/Docker, limites, concurrence) |
| `backend/scanners/executors/command.py` | `memory_exceeded`, `killed_reason`, environnement enfant partagé |
| `backend/scanners/executors/__init__.py` | exports publics du sandbox |
| `backend/scanners/base.py` | `ScanContext`, `ScanOutcome`, `check_result_category`, `execute()`, disponibilité Docker |
| `backend/scans/services/orchestrator.py` | gate SSRF central, budget, contexte, `ScannerBlocked`, fusion `CheckResult` |
| `backend/scans/services/steps_builder.py` | étape Lighthouse (health/full) |
| `backend/scanners/parsers/lighthouse.py` | **nouveau** — parser JSON défensif |
| `backend/scanners/implementations/lighthouse.py` | **nouveau** — adaptateur + normalisation |
| `backend/scanners/implementations/testssl.py` | migration sandbox + exécution unique |
| `backend/scanners/implementations/{nmap,nikto,nuclei,whatweb,dnsrecon,gobuster,feroxbuster}.py` | passage au sandbox |
| `backend/scanners/__init__.py` | enregistrement Lighthouse |
| `backend/config/settings/base.py` | `SCANNER_SANDBOX`, budget, configuration Lighthouse |
| `backend/.env.example` | variables de configuration documentées |
| `backend/Dockerfile` | build arg `INSTALL_LIGHTHOUSE` |
| `backend/scanners/tests/test_sandbox.py` | **nouveau** — 16 tests |
| `backend/scanners/tests/test_lighthouse.py` | **nouveau** — 25 tests |
| `backend/scans/tests/test_orchestrator_delegation.py` | **nouveau** — 10 tests |
