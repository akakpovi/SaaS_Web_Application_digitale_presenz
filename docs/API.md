# Presence API — organisations, invitations et scanners avancés

Base locale : `https://localhost/api/v1` (certificat auto-signé).
Authentification : JWT `Authorization: Bearer <access>` obtenu via
`POST /auth/login/`. Les routes ci-dessous sont toutes authentifiées.

---

## 1. Organisations et rôles

Chaque site appartient à une `Organization`. L'accès est résolu par la
`Membership` (ou par `billing_owner`, qui vaut toujours `owner`), jamais par le
seul champ `Website.owner`.

### Routes

| Méthode | Route | Rôle minimum | Effet |
|---|---|---|---|
| `GET` | `/organizations/` | membre | Organisations accessibles + rôle courant, `is_personal`, `member_count`, invitations en attente |
| `GET` | `/organizations/<org_id>/members/` | viewer | Liste des membres |
| `POST` | `/organizations/<org_id>/members/` | admin | Ajoute un compte existant (201) ou crée une invitation (202) |
| `GET` | `/organizations/<org_id>/members/<membership_id>/` | viewer | Détail d'un membre |
| `PATCH` | `/organizations/<org_id>/members/<membership_id>/` | admin | Change le rôle |
| `DELETE` | `/organizations/<org_id>/members/<membership_id>/` | admin | Retire le membre |
| `GET` | `/organizations/<org_id>/invitations/` | admin | Invitations en attente (`?status=accepted|revoked|expired` pour l'historique) |
| `DELETE` | `/organizations/<org_id>/invitations/<invitation_id>/` | admin | Révoque une invitation en attente |
| `POST` | `/organizations/invitations/<token>/accept/` | compte connecté | Accepte l'invitation et crée la `Membership` |

Un non-membre reçoit **404** (pas 403) pour ne pas révéler l'existence d'un
tenant. Un membre sans rôle suffisant reçoit **403**.

### Matrice des rôles

| Capacité | owner | admin | analyst | viewer |
|---|:--:|:--:|:--:|:--:|
| Lire sites, scans, résultats | ✅ | ✅ | ✅ | ✅ |
| Créer / modifier un site | ✅ | ✅ | ✅ | ❌ |
| Supprimer un site | ✅ | ✅ | ❌ | ❌ |
| Lancer un scan | ✅ | ✅ | ✅ | ❌ |
| Gérer les invitations | ✅ | ✅ | ❌ | ❌ |
| Ajouter / modifier un `analyst` ou `viewer` | ✅ | ✅ | ❌ | ❌ |
| Ajouter / modifier un `admin` | ✅ | ❌ | ❌ | ❌ |
| Modifier ou retirer le `owner` / billing owner | ❌ | ❌ | ❌ | ❌ |

L'ajout d'un compte existant crée directement la `Membership` (HTTP 201).
L'ajout d'une adresse sans compte crée une invitation (HTTP 202) :

```bash
curl -sk -X POST https://localhost/api/v1/organizations/$ORG_ID/members/ \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"collaborateur@example.com","role":"viewer"}'
```

```json
{
  "status": "invited",
  "email": "collaborateur@example.com",
  "email_sent": true,
  "accept_url": "https://localhost/accept-invitation?token=<token>",
  "invitation": {
    "id": "95bf55fe-dcd9-4d40-8256-3d87675c129e",
    "email": "collaborateur@example.com",
    "role": "viewer",
    "status": "pending",
    "expires_at": "2026-10-31T09:18:26Z"
  }
}
```

### Flux d'invitation et token haché

1. L'owner/admin appelle `POST /organizations/<org_id>/members/`.
2. Le serveur génère un token aléatoire (`secrets.token_urlsafe(32)`), envoie
   l'e-mail et **ne stocke que `SHA-256(token)`** dans
   `OrganizationInvitation.token_hash`. Le token en clair n'existe que dans
   l'e-mail et dans `accept_url`, retourné une seule fois.
3. L'invité crée son compte (`POST /auth/register/`) puis se connecte.
4. `POST /organizations/invitations/<token>/accept/` vérifie le hash, l'adresse
   e-mail du compte connecté, l'expiration (7 jours) et le statut.
5. Succès : **200** avec la `Membership` créée. Une seconde acceptation est
   idempotente (même `membership_id`, aucun doublon).
6. Erreurs : token inconnu **404**, expiré **410 `invitation_expired`**,
   e-mail différent **403**, invitation déjà consommée par un autre compte
   **409**.

Vérification du stockage :

```bash
docker compose exec -T web python manage.py shell -c "
from organizations.models import OrganizationInvitation
i = OrganizationInvitation.objects.get(pk='<invitation_id>')
print(i.status, i.token_hash, len(i.token_hash))
"
```

Le hash doit faire 64 caractères hexadécimaux et correspondre à
`hashlib.sha256(token.encode()).hexdigest()`.

### Smoke test HTTP

```bash
python3 scripts/smoke_phase_f_roles.py --base-url https://localhost/api/v1
```

Le script utilise les comptes de test `phasef.smoke.*` et `test@test.com`, et
vérifie : organisation personnelle, rôles owner/viewer/outsider, création
d'invitation, hash du token, acceptation, refus 403/404. Il ne crée aucune
donnée en dehors de son invitation.

---

## 2. Migrations multi-tenant

```bash
docker compose exec -T web python manage.py migrate --noinput
```

Migrations attendues :

- `organizations/0001_initial` — Organization, Membership ;
- `organizations/0002_backfill_personal_organizations` — crée une organisation
  personnelle par utilisateur et rattache les sites existants ;
- `organizations/0003_organizationinvitation` — invitations + index ;
- `websites/0005_website_organization` — FK nullable ;
- `websites/0006_...` — index `(organization, created_at)`.

Contrôle de backfill :

```bash
docker compose exec -T web python manage.py shell -c "
from websites.models import Website
from organizations.models import Organization
print('owned_orphans', Website.objects.filter(owner__isnull=False, organization__isnull=True).count())
print('personal_orgs', Organization.objects.filter(is_personal=True).count())
"
```

`owned_orphans` doit valoir `0`. Un site invité (`owner=NULL`, `is_guest=True`,
créé par le scanner public) n'a volontairement pas d'organisation : il ne fait
pas partie du périmètre multi-tenant et n'est jamais visible dans
`/organizations/`.

---

## 3. Activer ZAP et Nuclei en sandbox Docker

> ⚠️ `SCANNER_ADVANCED_SECURITY_ENABLED=true` autorise des requêtes d'attaque
> réelles. N'activez ce tier que sur un worker de scan dédié et uniquement sur
> des domaines pour lesquels vous avez une autorisation écrite. Le montage de
> `/var/run/docker.sock` donne au worker un pouvoir équivalent à root sur
> l'hôte.

### 3.1 Variables (`backend/.env`)

```dotenv
SCANNER_SANDBOX_MODE=docker
SCANNER_ADVANCED_SECURITY_ENABLED=true

SCANNER_DOCKER_IMAGE_ZAP=zaproxy/zap-stable:latest
SCANNER_DOCKER_IMAGE_NUCLEI=projectdiscovery/nuclei:latest
SCANNER_ZAP_MODE=docker
SCANNER_ZAP_SCRIPT=/zap/zap-baseline.py
SCANNER_NUCLEI_TEMPLATES_PATH=/tmp/presence-scanner/nuclei-templates
SCANNER_NUCLEI_MEMORY_MB=1536
```

Le tag GHCR `ghcr.io/zaproxy/zap-stable` a renvoyé `denied` lors de la
validation du 2026-10-24 ; l'image officielle équivalente publiée sur Docker Hub
(`zaproxy/zap-stable:latest`) est utilisée.

### 3.2 Socket Docker et répertoire partagé

Le `docker-compose.yml` canonique monte déjà, **uniquement sur
`celery-worker`** :

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - /tmp/presence-scanner:/tmp/presence-scanner
group_add:
  - "${DOCKER_GID:-984}"   # stat -c '%g' /var/run/docker.sock
environment:
  TMPDIR: /tmp/presence-scanner
```

Créer le répertoire hôte accessible en écriture :

```bash
install -d -m 1777 /tmp/presence-scanner
docker compose exec -T celery-worker sh -lc 'id; docker version --format "{{.Server.Version}}"'
```

### 3.3 Images et templates

```bash
docker pull zaproxy/zap-stable:latest
docker pull projectdiscovery/nuclei:latest

# L'image Nuclei ne contient pas les templates : clone obligatoire.
git clone --depth 1 https://github.com/projectdiscovery/nuclei-templates \
  /tmp/presence-scanner/nuclei-templates
chmod -R a+rX /tmp/presence-scanner/nuclei-templates
```

Les images ne sont **jamais** tirées au moment du scan : un scan échoue
immédiatement si l'image est absente.

### 3.4 Réseau filtré

```bash
docker compose up -d scanner-egress-guard scanner-sandbox-anchor
docker compose up -d --no-deps --force-recreate celery-worker
docker compose ps scanner-egress-guard scanner-sandbox-anchor celery-worker
```

Le worker ne démarre que si `scanner-egress-guard` est `healthy`. Le guard
installe les règles `DOCKER-USER` qui interdisent RFC 1918, loopback,
link-local et métadonnées cloud depuis `presence_scanner_sandbox` ; seules les
destinations publiques sont autorisées.

### 3.5 Lancer une validation

```bash
# Scan full (health + security) sur un domaine autorisé
curl -sk -X POST https://localhost/api/v1/websites/$WEBSITE_ID/scan/ \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scan_type":"full"}'
```

Suivre et vérifier :

```bash
curl -sk https://localhost/api/v1/scans/$SCAN_ID/ -H "Authorization: Bearer $TOKEN"
curl -sk https://localhost/api/v1/scans/$SCAN_ID/results/ -H "Authorization: Bearer $TOKEN"
curl -sk https://localhost/api/v1/scans/$SCAN_ID/findings/ -H "Authorization: Bearer $TOKEN"
curl -sk https://localhost/api/v1/scans/$SCAN_ID/scanner-runs/ -H "Authorization: Bearer $TOKEN"
```

Les `CheckResult` ZAP et Nuclei portent les catégories `zap` et `nuclei`, avec
`score=null` : ce sont des résultats de sécurité, hors score de santé pondéré.
Les alertes détaillées sont dans `Finding` (`check_code` = `zap.alert.<id>` ou
`nuclei.<template_id>`).

Preuve d'exécution Docker dans les logs worker :

```bash
docker compose logs --since=10m celery-worker | grep -E 'delegating|zap|nuclei|sandbox'
```

---

## 4. Validation live du 2026-10-24

Cible **strictement autorisée** : `appchat.elomaiapp.com` (aucune autre cible
exécutée par ce run).

| Élément | Résultat |
|---|---|
| Scan | `#3354`, type `full`, statut `completed`, 287 s |
| CheckResults | 9, dont `nuclei` (neutral, score null) et `zap` (warning, score null) |
| Findings | 15, dont 1 Nuclei (`nuclei.http-missing-security-headers`) et 7 ZAP (`zap.alert.10020`, `10038`, `10021`, `10027`, `10109`, `10015`, `10050`) |
| Nuclei | `completed`, 178,8 s, conteneur `projectdiscovery/nuclei:latest`, cible validée SSRF, 1536 Mo |
| ZAP | `completed`, 106,2 s, conteneur `zaproxy/zap-stable:latest`, transport `docker`, cible validée SSRF |
| Score de santé | 69 / 100 (`critical`), ZAP/Nuclei exclus du score pondéré |

Images pré-tirées : `zaproxy/zap-stable:latest` (digest
`sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6`)
et `projectdiscovery/nuclei:latest` (digest
`sha256:582d5546902e67052097cb2d07296c642d50a1afc5e44623cb038845df9a32eb`).
Le tirage GHCR `ghcr.io/zaproxy/zap-stable:latest` a été refusé (`denied`) ;
l'image Docker Hub officielle a été utilisée.

Conteneurs observés pendant le run :

```text
presence-scan-0276bff6b463  projectdiscovery/nuclei:latest  Up 2 minutes
presence-scan-8ba449270ac0  zaproxy/zap-stable:latest        Up About a minute
```

---

## 5. Notes d'exploitation

- ZAP baseline écrit son rapport sous `/zap/wrk` et son automation framework
  duplique ce préfixe ; l'adaptateur monte donc le répertoire de travail sur
  `/zap/wrk` et lance `zap-baseline.py --autooff`.
- Nuclei consomme 1,5 Go de RAM avec les templates ; le worker doit disposer
  d'au moins 2 Go libres. Un dépassement est remonté en `timeout`/`memory limit`
  dans `ScannerRun`, jamais en succès trompeur.
- Le budget global `SCAN_TOTAL_TIME_BUDGET_SECONDS=540` s'applique à tous les
  scanners ; ZAP et Nuclei sont les derniers étapes d'un scan `full`.
