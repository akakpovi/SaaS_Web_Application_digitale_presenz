# Phase F — validation live du 2026-10-24

Environnement : pile Compose canonique, backend Django `config.settings.production`,
worker Celery avec socket Docker, réseau scanner filtré.

## 1. Scanners avancés — scan #3354

Cible autorisée et unique : **`appchat.elomaiapp.com`**.

| Paramètre | Valeur |
|---|---|
| Site | id `24`, organisation `a694ddef-a833-4d17-bc0c-44804a74180b` |
| Scan | `#3354`, type `full`, déclenchement manuel |
| Statut | `completed`, progression 100 %, 287 s |
| Score de santé | 69 / 100 (`critical`) |
| CheckResults | 9 (7 catégories santé + `zap` + `nuclei`) |
| Findings | 15 |

### Résultats ZAP / Nuclei

| Scanner | Statut | Durée | Findings | Détail |
|---|---|---:|---:|---|
| `nuclei` | `completed` | 178 818 ms | 1 | `nuclei.http-missing-security-headers`, template `http-missing-security-headers` |
| `zap` | `completed` | 106 244 ms | 7 | `zap.alert.10020`, `10038`, `10021`, `10027`, `10109`, `10015`, `10050` |

`CheckResult` :

- `zap` : statut `warning`, `score=null`, `technical_details.transport=docker` ;
- `nuclei` : statut `neutral`, `score=null` ;
- les deux catégories sont exclues du score de santé pondéré.

Conteneurs observés :

```text
presence-scan-0276bff6b463  projectdiscovery/nuclei:latest  Up 2 minutes
presence-scan-8ba449270ac0  zaproxy/zap-stable:latest        Up About a minute
```

Images :

- `zaproxy/zap-stable:latest` — digest `sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6` ;
- `projectdiscovery/nuclei:latest` — digest `sha256:582d5546902e67052097cb2d07296c642d50a1afc5e44623cb038845df9a32eb`.

Le tirage `ghcr.io/zaproxy/zap-stable:latest` a échoué avec `denied` ; l'image
officielle Docker Hub équivalente a été pré-tirée et utilisée.

### Préparation vérifiée

```text
uid=100(app) gid=101(app) groups=101(app),984
engine=29.9.1
/tmp/presence-scanner -> /tmp/presence-scanner
/var/run/docker.sock -> /var/run/docker.sock
mode docker
advanced True
zap zaproxy/zap-stable:latest
nuclei /tmp/presence-scanner/nuclei-templates
scanner-egress-guard  Up (healthy)
scanner-sandbox-anchor Up
```

## 2. Synchronisation multi-tenant

`python manage.py migrate --noinput` : aucune migration en attente (les
migrations `organizations/0001–0003`, `websites/0005–0006` et
`scans/0005_add_external_security_categories` sont appliquées).

Contrôle :

```text
websites_total 10
websites_owned 9
owned_orphans 0
guest_sites 1
guest_without_org 1
orgs_total 9, personal 7
users_without_any_org 0
```

Le seul site sans organisation est le site invité `example.com`
(`owner=NULL`, `is_guest=True`), créé par le scanner public : il est hors
périmètre multi-tenant et n'est pas un site propriétaire orphelin.

## 3. Smoke test HTTP des rôles

Exécuté avec `python3 scripts/smoke_phase_f_roles.py --base-url https://localhost/api/v1`.

| Vérification | Résultat |
|---|---|
| Organisation personnelle `test@test.com` | `200`, `is_personal=true`, rôle `owner`, id `71f1d9b6-8767-4a2a-890c-4900bdb7697d` |
| Liste membres owner | `200`, 4 membres avant invitation |
| Création invitation (owner) | `202`, invitation `95bf55fe-dcd9-4d40-8256-3d87675c129e`, envoi SMTP `true` |
| Token stocké | SHA-256 `68d9c14099ef207901a61de72fa190f6e1d02ceb8e5134b2d0d92823560646d1`, identique au hash du token reçu |
| Viewer : liste invitations | `403` |
| Viewer : création site | `403` |
| Outsider : lecture membres | `404` |
| Invité : acceptation | `200`, `membership_id=1201f236-e7d6-4a9d-8538-3a10f92a5bc5`, rôle `viewer` |
| Seconde acceptation | `200`, même `membership_id` (idempotent, aucun doublon) |

## 4. Documentation

- [`docs/API.md`](../API.md) — routes, matrice des rôles, flux d'invitation,
  stockage du token haché, procédure Docker ZAP/Nuclei et validation live.
- [`README.md`](../../README.md) — liens vers ces sections.
- Scripts reproductibles :
  [`scripts/smoke_phase_f_roles.py`](../../scripts/smoke_phase_f_roles.py),
  [`scripts/live_scan_authorized_target.py`](../../scripts/live_scan_authorized_target.py).

## 5. Tests automatisés

```text
bash scripts/run_backend_tests.sh scans.tests.test_scans \
  scans.tests.test_orchestrator_delegation scanners.tests.test_advanced_security

Ran 89 tests in 121.441s
OK
```

## Limites connues

- Le scan `full` a exécuté uniquement ZAP et Nuclei côté sécurité : `nmap`,
  `nikto`, `whatweb`, `testssl`, `dnsrecon` et `gobuster` ne sont pas installés
  dans l'image worker et ont été marqués `unavailable` (sans échec du scan).
- Lighthouse n'est pas disponible dans le conteneur worker (binaire absent),
  donc le score de performance repose sur le scanner Python interne.
- `ghcr.io` refuse le manifeste ZAP sans authentification ; utiliser l'image
  Docker Hub officielle ou configurer un `docker login ghcr.io`.
