# Rapport — Déploiement Lighthouse, verrouillage egress et tier sécurité avancée

**Projet :** Presence (`SaaS_Web_Application_digitale_presenz_v2/backend`)
**Date :** 24 octobre 2026
**Périmètre :** image du worker, réseau Docker du sandbox, adaptateurs ZAP/Nuclei, feature flag
**Verdict :** ✅ l'image worker intègre Node, Lighthouse et Chromium et a exécuté un audit réel ; ✅ l'egress du réseau scanner est filtré au niveau noyau et les tests réseau le prouvent ; ✅ ZAP et Nuclei passent par la sandbox et sont désactivés par défaut. ⚠️ ZAP n'a pas été exécuté en live (image non tirée sur cette machine) et le mode `process` ne bénéficie pas du filtrage réseau Docker.

---

## 1. Résumé exécutif

| Livrable | État | Preuve |
|---|---|---|
| Lighthouse + Chromium dans l'image worker | ✅ | build `INSTALL_LIGHTHOUSE=true`, `lighthouse 12.8.2`, `Chromium 156.0.8078.47` |
| Audit Lighthouse réel de bout en bout | ✅ | `https://example.com` → `performance 0.81–0.99`, 73 audits, exit 0 |
| Réseau scanner dédié | ✅ | `presence_scanner_sandbox` (172.31.240.0/24, IPv6 off) |
| Blocage RFC 1918 / link-local / metadata | ✅ | cibles privées et `169.254.169.254` bloquées ; Internet public OK |
| Blocage scanner → hôte | ✅ | `172.31.240.1` bloqué (chaîne `input` à priorité -250) |
| ZAP derrière un flag | ✅ | `SCANNER_ADVANCED_SECURITY_ENABLED=false` par défaut |
| Nuclei derrière un flag | ✅ | idem + une seule exécution par scan |
| Tests ZAP/Nuclei/flag | ✅ | 24 tests, `OK` |

Le garde-fou réseau est un conteneur `scanner-egress-guard` qui programme une table nftables dédiée dans le namespace réseau de l'hôte. Il est **fail-closed** : le worker Celery dépend de sa santé, donc il ne démarre pas si les règles n'ont pas été installées.

---

## 2. Mission 1 — Déploiement de Lighthouse

### 2.1 Modification du Dockerfile

`backend/Dockerfile` :

- `ARG INSTALL_LIGHTHOUSE=false` (l'image reste légère pour `web` et `beat`) ;
- quand l'argument vaut `true` :
  - installation de `ca-certificates`, `curl`, `gnupg`, `chromium`, `fonts-liberation` ;
  - ajout du dépôt NodeSource 22 (Debian trixie fournit Node 18, trop ancien pour Lighthouse 12) ;
  - `npm install --global lighthouse@12` ;
  - **validation au build** : `node --version`, `npm --version`, `lighthouse --version`, `chromium --version`.
- `ENV CHROME_PATH=/usr/bin/chromium` ;
- répertoire personnel réel `/home/app` (`HOME`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`).

Le point `HOME` est important : avec le compte système Debian par défaut (`/nonexistent`), Chromium échoue avec `Failed to create headless user data directory container` et Lighthouse attend indéfiniment son port de debug. C'est exactement l'erreur observée au premier essai ; elle est corrigée et revalidée.

### 2.2 Compose

Le service `celery-worker` (pile canonique à la racine du dépôt) passe désormais :

```yaml
build:
  context: ./SaaS_Web_Application_digitale_presenz_v2/backend
  args:
    INSTALL_LIGHTHOUSE: "true"
```

`web`, `staticfiles` et `celery-beat` conservent l'image sans navigateur.

### 2.3 Résultat du build

```text
node=v22.23.4
npm=10.9.9
lighthouse=12.8.2
chromium=Chromium 156.0.8078.47 built on Debian GNU/Linux 13 (trixie)
CHROME_PATH=/usr/bin/chromium
```

Image : `presence-backend:lighthouse-test`, **1,43 Go** (Chromium + Node + Lighthouse). C'est le prix du moteur performance/SEO ; il n'est payé que par le worker.

### 2.4 Audit réel

```bash
docker run --rm presence-backend:lighthouse-test sh -c '
  cd /tmp &&
  lighthouse https://example.com \
    --output=json --output-path=/tmp/lh.json \
    --chrome-flags="--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu" \
    --only-categories=performance --quiet
'
```

Résultat :

```text
EXIT=0
version 12.8.2
finalUrl https://example.com/
performance 0.81
audits 73
```

Le score varie selon le run (0,81–0,99 observés sur `example.com`) : c'est une mesure réelle, pas une valeur figée.

L'adaptateur Django (`scanners/implementations/lighthouse.py`) reste couvert par ses 25 tests mockés : construction de commande, parsing, normalisation `CheckResult`/`Finding`, timeout, RAM, JSON invalide, redirection privée.

---

## 3. Mission 2 — Verrouillage egress (SSRF réseau)

### 3.1 Pourquoi un garde nftables et pas un conteneur-passerelle

La première tentative consistait à faire du garde la passerelle du bridge scanner. Docker réserve l'adresse de passerelle du réseau à l'interface du bridge sur l'hôte : un conteneur ne peut pas posséder cette IP (`Address already in use`). La deuxième tentative, des règles `iptables DOCKER-USER`, a montré ses limites : Docker 29 isole les bridges dans ses propres chaînes **avant** que le trafic inter-réseaux n'atteigne `DOCKER-USER`. Les compteurs restaient à zéro pour une cible sur un autre bridge Docker.

La solution retenue est une table nftables dédiée, **hookée à priorité -250**, donc avant l'isolation Docker et avant `filter` :

```nft
table inet presence_egress {
    set private_nets {
        type ipv4_addr
        flags interval
        elements = { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8,
                     169.254.0.0/16, 172.16.0.0/12, 192.0.0.0/24,
                     192.0.2.0/24, 192.168.0.0/16, 198.18.0.0/15,
                     198.51.100.0/24, 203.0.113.0/24, 224.0.0.0/4, 240.0.0.0/4 }
    }
    chain forward {
        type filter hook forward priority -250; policy accept;
        ip saddr 172.31.240.0/24 ip daddr 169.254.169.254 counter drop
        ip saddr 172.31.240.0/24 ip daddr @private_nets counter drop
    }
    chain input {
        type filter hook input priority -250; policy accept;
        ip saddr 172.31.240.0/24 counter drop
    }
}
```

- **forward** : bloque les destinations privées, y compris celles atteintes après une redirection HTTP suivie par Chromium, ZAP ou Nuclei. Inclut explicitement `169.254.169.254`.
- **input** : les scanners n'ont aucune raison de joindre un service de l'hôte (SSH, API Docker, IP publique de l'hôte). Tout nouveau paquet scanner → hôte est supprimé. La résolution DNS n'est pas affectée : le résolveur Docker écoute sur `127.0.0.11` dans le namespace de chaque conteneur.
- **policy accept** : le trafic public reste autorisé et suit ensuite les règles Docker/UFW normales.

Le conteneur tourne en `network_mode: host` avec uniquement `NET_ADMIN`, `read_only`, `cap_drop: ALL`, et un healthcheck qui vérifie la présence des hooks et des règles.

### 3.2 Compose

```yaml
scanner-egress-guard:
  build: ./SaaS_Web_Application_digitale_presenz_v2/backend/docker/egress-guard
  network_mode: host
  cap_drop: [ALL]
  cap_add: [NET_ADMIN]
  read_only: true
  tmpfs: [/run]
  environment:
    SCANNER_SUBNET: 172.31.240.0/24
  healthcheck:
    test: ["CMD", "/usr/local/bin/egress-guard-healthcheck"]

celery-worker:
  environment:
    SCANNER_SANDBOX_DOCKER_NETWORK: presence_scanner_sandbox
  depends_on:
    scanner-egress-guard:
      condition: service_healthy

networks:
  scanner_sandbox:
    name: presence_scanner_sandbox
    enable_ipv6: false
    driver_opts:
      com.docker.network.bridge.enable_icc: "false"
    ipam:
      config:
        - subnet: 172.31.240.0/24
```

Deux détails d'exploitation :

- Compose ne crée un réseau que s'il est référencé par un service. Le garde utilisant `network_mode: host`, un service `scanner-sandbox-anchor` (Alpine, `sleep infinity`, read-only, `cap_drop: ALL`) matérialise `presence_scanner_sandbox` avant le premier scan ; sans lui, `docker run --network presence_scanner_sandbox` échouerait.
- `enable_icc: false` interdit le trafic conteneur-à-conteneur sur le bridge scanner : deux scans concurrents ne peuvent pas s'attaquer, et l'anchor reste injoignable.

### 3.3 Validation réseau réelle

Réseau de test `172.31.250.0/24`, cible nginx sur un second bridge privé `192.168.250.40`, garde nftables actif :

| Test depuis le réseau scanner | Résultat |
|---|---|
| `http://192.168.250.40` (RFC 1918, autre bridge Docker) | **PRIVATE_BLOCKED** |
| `http://169.254.169.254` (métadonnées cloud) | **METADATA_BLOCKED** |
| `http://172.31.250.1` (hôte / passerelle) | **HOST_BLOCKED** |
| `http://example.com` (Internet public) | **PUBLIC_OK** |

Même contrôle sur le réseau de production `presence_scanner_sandbox` (172.31.240.0/24, `enable_icc=false`), après `docker compose up -d scanner-sandbox-anchor scanner-egress-guard` :

| Test | Résultat |
|---|---|
| `http://example.com` | **PUBLIC_OK** |
| `http://172.31.240.1` (hôte) | **HOST_BLOCKED** |
| `http://169.254.169.254` | **METADATA_BLOCKED** |
| `ping 172.31.240.2` (anchor, même bridge) | **ICC_BLOCKED** |

Compteurs nftables après les tentatives :

```text
ip saddr 172.31.250.0/24 ip daddr @private_nets counter packets 8 bytes 480 drop
ip saddr 172.31.250.0/24 counter packets 6 bytes 408 drop
```

Les paquets privés sont donc bien interceptés **par la règle du garde**, avant l'isolation Docker, et le trafic public n'est pas coupé. Healthcheck : `HEALTH_OK`.

Nettoyage effectué après le test (conteneurs, réseaux, table `presence_egress`).

---

## 4. Mission 3 — Tier sécurité avancée (ZAP & Nuclei)

### 4.1 Feature flag

`backend/config/settings/base.py` :

```python
SCANNER_ADVANCED_SECURITY_ENABLED = env_bool(
    "SCANNER_ADVANCED_SECURITY_ENABLED", False
)
```

Défense en profondeur :

1. **Orchestrateur** : si `scanner.requires_advanced_security is True` et flag faux, l'étape est marquée `skipped` avec la raison, **aucun `ScannerRun` n'est créé**, aucune cible n'est résolue.
2. **Adaptateur** : `NucleiScanner.execute()` et `ZAPScanner.execute()` retournent un résultat `neutral` + finding `*.disabled` si le flag est faux, même appelés directement.
3. **Disponibilité** : `is_available()` renvoie `False` quand le flag est faux, donc l'admin/registry les voit inactifs.

Le flag est absent de la pile Compose : il se règle dans `backend/.env` et vaut `false` par défaut. Il n'est donc pas possible de l'activer par inadvertance via un `docker compose up`.

### 4.2 Nuclei

- `scanner_type=CLI`, `requires_advanced_security=True`.
- `execute(domain, context)` : une seule exécution, `ScanOutcome(result, findings)`.
- Cible et budget viennent du `ScanContext` (`target`, `sandbox_limits`, `effective_timeout`).
- Commande : `-jsonl`, `-silent`, `-no-color`, `-disable-update-check`, timeouts/bulk/concurrency/rate-limit configurables, `-tags`, `-severity` optionnel.
- Gestion explicite : timeout, limite mémoire, `SandboxError`, cible invalide, doublons de findings.
- `scan()` et `scan_findings()` restent compatibles mais délèguent à `execute()`.

### 4.3 ZAP

Deux transports, sélectionnés par `SCANNER_ZAP_MODE` (`auto`, `docker`, `api`) :

| Transport | Comportement |
|---|---|
| `docker` (préféré en `auto` si mode Docker + image configurée) | Sandbox : image officielle `ghcr.io/zaproxy/zap-stable`, entrypoint `zap-baseline.py`, rapport JSON écrit dans un répertoire temporaire monté sur `/out`, tmpfs `/zap/wrk`, `read_only`, limites CPU/RAM |
| `api` | Sidecar REST existant ; spider + alertes, **pas d'active scan par défaut** (`SCANNER_ZAP_ACTIVE_SCAN=false`) |

- Le scan Docker est **passif** (baseline). L'active scan reste une option explicite du transport API.
- Les montages de sortie sont validés par le sandbox : uniquement des répertoires sous `tempfile.gettempdir()`, chemin conteneur absolu sans `..`.
- Le parser gère le rapport baseline (`site[].alerts`) et la réponse `/JSON/core/view/alerts/` (`alerts[]`), avec mapping `riskdesc`/`risk`/`riskcode`.
- Normalisation : `zap.alert.<pluginid>`, sévérité, `FAIL` pour high/critical, `WARNING` sinon, déduplication par alerte + URL, référence CWE ou première URL.

### 4.4 Configuration

```dotenv
SCANNER_ADVANCED_SECURITY_ENABLED=false
SCANNER_ZAP_MODE=auto
SCANNER_ZAP_SCRIPT=zap-baseline.py
SCANNER_ZAP_ACTIVE_SCAN=false
SCANNER_TIMEOUT_ZAP=300
SCANNER_ZAP_MEMORY_MB=1536
SCANNER_DOCKER_IMAGE_ZAP=
```

Pour le transport Docker, pré-tirer l'image sur le worker (le sandbox ne tire jamais au moment du scan) :

```bash
docker pull ghcr.io/zaproxy/zap-stable
```

---

## 5. Tests

| Suite | Résultat |
|---|---|
| `scanners.tests.test_advanced_security` + `scans.tests.test_advanced_security_gate` | **24 tests, OK** |
| `scanners.tests.test_sandbox`, `test_lighthouse`, `scans.tests.test_orchestrator_delegation` | **53 tests, OK** (les 2 erreurs de la commande initiale venaient de modules `test_testssl`/`test_nuclei` inexistants, pas du code) |
| Suite backend complète | **623 tests, OK** en 886 s (voir journal `/tmp/full_suite_final.log`) |

Les tests couvrent notamment :

- flag faux → aucune exécution, finding `*.disabled`, `is_available() == False` ;
- flag vrai → Nuclei exécuté une seule fois, `-jsonl`, findings normalisés ;
- timeout / mémoire / `SandboxError` → findings `unknown`, pas de faux « succès » ;
- ZAP Docker → commande `zap-baseline.py -t … -J /out/… -I`, entrypoint image vidé, montage, tmpfs, parsing baseline ;
- ZAP API → alertes racine, pas d'`ascan` par défaut ;
- sandbox → tmpfs supplémentaire, montage `/tmp` accepté, montage `/etc` refusé, `..` refusé ;
- orchestrateur → étape avancée `skipped` sans `ScannerRun`, puis `completed` quand le flag est activé.

---

## 6. Exploitation

### 6.1 Construire et démarrer

```bash
cd ~/Schreibtisch/SaaS_Web_Application_digitale_presenz
docker compose build celery-worker
docker compose up -d celery-worker scanner-egress-guard
```

Vérifier :

```bash
docker compose ps scanner-egress-guard          # healthy
docker exec <guard> /usr/local/bin/egress-guard-healthcheck
docker exec <worker> lighthouse --version
docker exec <worker> chromium --version
```

### 6.2 Activer le tier avancé (worker dédié uniquement)

1. Passer en mode Docker pour la sandbox :
   `SCANNER_SANDBOX_MODE=docker`.
2. Monter le socket Docker sur le worker (ligne commentée dans Compose) : accès root à l'hôte, à ne jamais faire sur le conteneur web.
3. Pré-tirer les images Nuclei/ZAP.
4. Mettre `SCANNER_ADVANCED_SECURITY_ENABLED=true` dans `backend/.env`.
5. Redémarrer le worker et vérifier que l'étape n'est plus `skipped`.

### 6.3 Garde-fous

- Le garde est **fail-closed** : si son healthcheck échoue, Compose ne démarre pas le worker.
- La table nftables survit à l'arrêt du garde (les règles restent actives) ; un redémarrage les remplace proprement.
- Si `SCANNER_SUBNET` change, mettre à jour le réseau Compose et redémarrer le garde.

---

## 7. Limites connues

1. **ZAP non exécuté en live** : l'image `ghcr.io/zaproxy/zap-stable` n'a pas été tirée sur cette machine. Le transport Docker est couvert par des tests mockés (commande, montage, tmpfs, parsing) mais doit être validé sur le worker après `docker pull`.
2. **Nuclei non exécuté en live** : binaire absent de l'image actuelle ; les tests couvrent la commande et la normalisation.
3. **Mode `process`** : le filtrage réseau nftables protège les conteneurs du sandbox Docker (réseau `presence_scanner_sandbox`). En mode `process`, les outils tournent dans le conteneur worker et ne passent pas par ce réseau : il faut soit passer en mode Docker, soit appliquer un filtrage équivalent au conteneur worker (non fait ici, car il doit joindre PostgreSQL/Redis).
4. **Socket Docker** : le mode Docker du sandbox reste équivalent à un accès root sur l'hôte. Worker dédié obligatoire.
5. **Image 1,43 Go** : conséquence de Chromium + Node ; seuls les workers de scan la portent.

---

## Annexe — Fichiers modifiés / ajoutés

| Fichier | Nature |
|---|---|
| `backend/Dockerfile` | Node 22 + Lighthouse 12 + Chromium, validation au build, `HOME` inscriptible |
| `docker-compose.yml` (racine) | build arg worker, réseau scanner, garde egress, dépendance fail-closed |
| `backend/docker/egress-guard/Dockerfile` | image Alpine + nftables |
| `backend/docker/egress-guard/entrypoint.sh` | table nftables priorité -250 (forward + input) |
| `backend/docker/egress-guard/healthcheck.sh` | vérification des hooks et règles |
| `backend/config/settings/base.py` | flag avancé, config ZAP, image ZAP |
| `backend/scanners/features.py` | **nouveau** — lecture du flag |
| `backend/scanners/base.py` | `requires_advanced_security` |
| `backend/scans/services/orchestrator.py` | saut d'étape avant création de `ScannerRun` |
| `backend/scanners/implementations/nuclei.py` | sandbox, exécution unique, flag |
| `backend/scanners/implementations/zap.py` | sandbox Docker / API, flag, baseline |
| `backend/scanners/parsers/zap.py` | rapport baseline + alertes core |
| `backend/scanners/executors/sandbox.py` | tmpfs supplémentaires, montages de sortie validés |
| `backend/scanners/tests/test_advanced_security.py` | **nouveau** — 22 tests |
| `backend/scans/tests/test_advanced_security_gate.py` | **nouveau** — 2 tests |
| `backend/.env.example` | flag, ZAP, réseau scanner |
