# 🌐 Presence — Monitoring de présence digitale

> Surveillance de site web, SSL, DNS, sécurité e-mail, performance et réputation
> en ligne, depuis un tableau de bord simple.

**Version canonique : `SaaS_Web_Application_digitale_presenz_v2/`**
Les dossiers `backend/` et `frontend/` de la racine sont des vestiges (non
utilisés par Docker Compose). Toute modification doit se faire dans `v2`.

---

## Pile technique

| Couche | Technologie |
|---|---|
| Backend | Django 5.1, DRF 3.15, Celery 5 |
| Base / cache | PostgreSQL 16, Redis 7 |
| Frontend | React 19, TypeScript, Vite 8, Tailwind 4 |
| Serveur | Gunicorn + nginx (TLS, pages pré-rendues) |
| Paiement | Paddle Billing (checkout hébergé + webhooks signés) |
| E-mail local | Mailpit (capture SMTP réelle sur http://localhost:8025) |

---

## Démarrage local

```bash
cd ~/Schreibtisch/SaaS_Web_Application_digitale_presenz
bash scripts/setup_local_tls.sh          # certificat auto-signé + nginx/ssl/tls.conf
cp SaaS_Web_Application_digitale_presenz_v2/backend/.env.example \
   SaaS_Web_Application_digitale_presenz_v2/backend/.env   # puis ajuster les secrets
bash scripts/configure_local_smtp.sh     # SMTP -> Mailpit, sans toucher aux autres secrets
docker compose up -d --build
docker compose exec web python manage.py create_plans
```

- Application : https://localhost (certificat auto-signé)
- API santé : https://localhost/api/v1/health/
- E-mails capturés : http://localhost:8025
- Swagger : https://localhost/api/docs/

---

## Abonnements et quotas

Catalogue unique (backend `subscriptions/pricing.py`, miroir frontend
`src/data/plans.json`, vérifié par `scripts/check_pricing_sync.py`) :

| Offre | Mensuel | Annuel | Sites | Scans/mois | Canaux d'alerte |
|---|---:|---:|---:|---:|---:|
| Free | 0 € | 0 € | 1 | 10 | 1 |
| Pro | 9 € | 90 € | 10 | 500 | 5 |
| Business | 29 € | 290 € | 50 | 5 000 | 10 |
| Agency | 79 € | 790 € | 200 | 20 000 | 25 |

Les quotas sont appliqués **côté serveur** : création de site, déclenchement
de scan, export PDF, canaux de notification et accès API (clés `pk_...`).
Les plans payants ne peuvent être activés **que** par un webhook Paddle après
paiement ; `POST /subscriptions/upgrade/` ne modifie jamais un plan.

### Activer Paddle

1. Créer un compte **Paddle Sandbox**, puis une clé API `pdl_sdbx_...`
   (Developer tools → Authentication).
2. Renseigner `backend/.env` : `BILLING_ENABLED=true`,
   `BILLING_PROVIDER=paddle`, `PADDLE_API_KEY=pdl_sdbx_...`,
   `PADDLE_API_URL=https://sandbox-api.paddle.com`, `PADDLE_ENVIRONMENT=sandbox`.
3. Exposer le webhook local en HTTPS public, puis ajouter le domaine du tunnel
   à `DJANGO_ALLOWED_HOSTS` :
   ```bash
   bash scripts/paddle_webhook_tunnel.sh          # écrit l'URL publique, ou ngrok
   docker compose up -d --force-recreate web
   ```
4. Provisionner produits, prix et webhook en une commande :
   ```bash
   URL=$(cat /tmp/presence-webhook-url.txt)
   docker compose exec web python manage.py create_paddle_sandbox \
     --webhook-url "$URL/api/v1/webhooks/paddle/"
   ```
   La commande crée un produit par offre, les prix mensuels et annuels aux
   montants du tableau (9/29/79 € et 90/290/790 €), remplit
   `Plan.external_price_id_*`, crée la destination de webhook et écrit son
   secret dans `backend/.paddle_webhook_secret` (0600, jamais affiché).
5. Copier ce secret dans `PADDLE_WEBHOOK_SECRET`, puis
   `docker compose up -d --force-recreate web`. Payer avec la carte de test
   Sandbox `4242 4242 4242 4242` : le webhook active le plan et le quota.

Si les prix existent déjà dans Paddle, `manage.py configure_billing` avec
`PADDLE_PRICE_*` reste disponible pour mapper les `price_id` sans appeler l'API.

Endpoints : `POST /api/v1/subscriptions/checkout/`, `POST /api/v1/subscriptions/portal/`,
`POST /api/v1/webhooks/paddle/` (signature `Paddle-Signature`, idempotence
`event_id`), `GET /api/v1/subscriptions/me/` (plan + limites + usage).

---

## Organisations, équipes et invitations

Presence est multi-tenant : chaque site appartient à une `Organization` et
l'accès dépend de la `Membership` (`owner`, `admin`, `analyst`, `viewer`), pas
du seul champ `Website.owner`. Les routes sont :

- `GET /api/v1/organizations/` — organisations accessibles et rôle courant ;
- `GET|POST /api/v1/organizations/<id>/members/` — lister / ajouter ;
- `PATCH|DELETE /api/v1/organizations/<id>/members/<membership_id>/` — rôle / révocation ;
- `GET /api/v1/organizations/<id>/invitations/` — invitations en attente ;
- `DELETE /api/v1/organizations/<id>/invitations/<invitation_id>/` — révocation ;
- `POST /api/v1/organizations/invitations/<token>/accept/` — acceptation.

L'ajout d'une adresse sans compte crée une invitation valable 7 jours, dont
seul le hash SHA-256 du token est stocké. `owner` et `admin` gèrent l'équipe ;
seul `owner` peut nommer ou modifier un autre `admin`. Détails, exemples JSON
et matrice complète : [`docs/API.md`](docs/API.md).

---

## Scanners avancés (ZAP / Nuclei)

Le tier est strictement opt-in (`SCANNER_ADVANCED_SECURITY_ENABLED=true`) et
s'exécute dans des conteneurs one-shot sur le réseau filtré
`presence_scanner_sandbox`. Procédure complète (images, templates Nuclei,
socket Docker, mémoire, vérifications) : [`docs/API.md`](docs/API.md#3-activer-zap-et-nuclei-en-sandbox-docker).

> Le montage de `/var/run/docker.sock` équivaut à un accès root sur l'hôte :
> worker de scan dédié uniquement, jamais sur `web` ni `celery-beat`.

---

## SEO technique

Le build Vite est suivi d'un pré-rendu sans navigateur headless
(`scripts/prerender.mjs`) :

- un fichier HTML par route publique, avec `<title>`, description, canonical,
  Open Graph, Twitter Card et JSON-LD corrects ;
- `sitemap.xml` et `robots.txt` générés avec `VITE_BASE_URL` ;
- vraie page `404.html` (nginx renvoie un statut 404, plus de soft 404) ;
- images PNG : `og-image.png` 1200×630, icônes PWA 192/512 et
  `apple-touch-icon.png` (générées par `scripts/generate_brand_assets.py`).

Pour un domaine public :

```bash
VITE_BASE_URL=https://presence.example bash scripts/build-frontend.sh
```

Sans cette variable, le build utilise `https://localhost` et affiche un
avertissement.

Ce script est la commande unique de reconstruction : le pré-rendu joint
WordPress sur la loopback de l'hôte, donc le build déclare `network: host`, que
BuildKit refuse via `docker compose build` tant que son allow-list ne l'autorise
pas (`additional privileges requested: pass "--allow=network.host"`). Le script
lance `docker buildx bake` sur le *même* `docker-compose.yml` avec `--allow`,
puis recrée uniquement le service `frontend`. Il devient inutile dès que le
builder Compose est créé avec `--allow-insecure-entitlement network.host`.

---

## Blog headless (WordPress)

`src/api/blog.ts` interroge l'API REST WordPress si `VITE_WP_API_URL` est
définie (`https://cms.example.com` ou `.../wp-json`). Le contenu est assaini
par DOMPurify avant rendu. Sans CMS configuré, six articles de démonstration
(`src/data/mock-posts.json`) sont servis avec les états de chargement/erreur
réels, ce qui permet de brancher WordPress sans changer les composants.

---

## Exploitation

### Sauvegardes

```bash
bash scripts/backup.sh                  # PostgreSQL + Redis + SHA-256, rétention 14 j
bash scripts/verify_backup_restore.sh   # restaure dans une base jetable et vérifie les compteurs
bash scripts/restore.sh backups/<fichier> --yes   # restauration réelle (destructive)
```

Export externe : `BACKUP_S3_URI=s3://bucket/presence` + CLI `aws` configuré.
Cron conseillé : `30 3 * * * cd <dépôt> && bash scripts/backup.sh`.

### TLS Let's Encrypt

Le certificat auto-signé reste actif en local. Sur le VPS public, dans cet
ordre :

1. **DNS** — un enregistrement `A` (et `AAAA` si IPv6) pour le domaine et
   `www` pointe vers l'IP du VPS. Vérifier avec
   `dig +short presence.example.com` : l'IP doit être celle du serveur.
2. **Pare-feu** — les ports 80 et 443 sont ouverts (le port 80 sert au
   challenge ACME et redirige ensuite vers HTTPS).
3. **Variables** — dans `backend/.env` :
   `DJANGO_ALLOWED_HOSTS=presence.example.com,www.presence.example.com`,
   `FRONTEND_URL=https://presence.example.com`,
   `DJANGO_CSRF_TRUSTED_ORIGINS=https://presence.example.com`.
4. **Origine du frontend** — reconstruire avec l'URL publique pour que
   canonical, sitemap et robots.txt soient absolus :
   `VITE_BASE_URL=https://presence.example.com bash scripts/build-frontend.sh`
   (le script reconstruit l'image puis recrée le service `frontend`).
5. **Certificat** :
   `bash scripts/enable_letsencrypt.sh presence.example.com admin@example.com`
   Le script obtient le certificat en mode webroot, réécrit
   `nginx/ssl/tls.conf` et recharge nginx sans coupure.
6. **Renouvellement** — cron hebdomadaire (certbot n'agit qu'à J-30) :
   `15 4 * * 1 cd /srv/presence && bash scripts/renew_letsencrypt.sh >> /var/log/presence-certbot.log 2>&1`

Vérification finale : `curl -I https://presence.example.com` doit renvoyer
`200` avec un certificat valide, et `https://presence.example.com/api/v1/health/`
un JSON `{"status": "ok"}`.

### SMTP

`scripts/configure_local_smtp.sh` configure Mailpit. Pour Mailtrap/SES/Postmark,
remplacer les variables `EMAIL_*` dans `backend/.env` (voir `.env.example`).
Une alerte réelle a été validée de bout en bout : le dispatcher remet le
message au serveur SMTP et Mailpit le reçoit.

---

## Tests

```bash
bash scripts/run_backend_tests.sh                 # suite complète (Django)
bash scripts/run_backend_tests.sh subscriptions   # un module
python3 scripts/check_pricing_sync.py             # cohérence des prix
cd SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2
./node_modules/.bin/tsc --noEmit && pnpm run build
```

CI GitHub Actions : `.github/workflows/ci.yml` (backend + typecheck/build
frontend + vérification du pré-rendu et des prix).

---

## Structure

```
SaaS_Web_Application_digitale_presenz_v2/
├── backend/
│   ├── accounts/  websites/  scans/  monitoring/  alerts/
│   ├── notifications/  reports/  reviews/  subscriptions/
│   ├── scanners/  advanced_security/  seo/  social/
│   ├── public_checker/  analytics/  core/
│   └── config/
└── SaaS_Web_Application_UI_UX_frontendV2/
    ├── src/{pages,components,api,data,lib,seo}
    └── scripts/{prerender.mjs,generate_brand_assets.py}
nginx/            certificats, tls.conf, webroot ACME
scripts/          TLS, Let's Encrypt, sauvegardes, SMTP, tests
```
