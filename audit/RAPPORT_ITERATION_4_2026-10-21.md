# Itération 4 — Remédiation des P0 et préparation production

**Date :** 21 octobre 2026
**Périmètre :** `SaaS_Web_Application_digitale_presenz_v2` (seule version canonique)
**Contexte :** tests et déploiement sur `localhost`, disque libéré, TLS auto-signé local.
**Verdict :** les P0 de l'audit du 19/10 sont traités et **vérifiés par exécution**. Le lancement commercial reste conditionné à la fourniture des clés Paddle et d'un domaine public (voir § 8).

---

## 1. Synthèse

| P0 de l'audit | État | Preuve |
|---|---|---|
| Premium gratuit (`/upgrade/`) | ✅ Fermé | `409 use_checkout` (billing actif) ou `503` ; plan jamais modifié |
| Aucun prestataire de paiement | ✅ Paddle complet | checkout, portail, webhook signé + idempotent, 12 tests |
| Quotas jamais appliqués | ✅ Serveur | sites, scans/mois, PDF, canaux, clés API — 6 tests + test HTTP live |
| Trois catalogues de prix | ✅ Unifiés | 0/9/29/79 € + annuel ; `check_pricing_sync.py` OK |
| SPA non pré-rendue / soft 404 | ✅ Corrigé | 31 routes + 6 articles, vrai 404, sitemap absolu |
| OG/PWA en SVG | ✅ PNG | 1200×630, 192, 512, maskable, 180 |
| Blog figé dans le bundle | ✅ Headless | client WordPress `VITE_WP_API_URL` + mocks temporaires |
| Données fictives (scanners/social) | ✅ Supprimées | URLhaus/Safe Browsing, Graph/X, Reddit, AggregateRating |
| SMTP placeholder | ✅ Réel local | Mailpit ; e-mail d'alerte effectivement reçu |
| Aucune sauvegarde automatique | ✅ Scriptée + restauration testée | dump 1,8 Mo restauré : 46 tables, 5 users, 3 082 scans |

### Exécutions

| Vérification | Résultat |
|---|---|
| Suite backend complète | **393 tests — OK — exit 0** (355 avant itération) |
| Sous-suite `subscriptions` après derniers correctifs | **37 tests — OK — exit 0** |
| `check --deploy` (settings production) | exit 0, **0 alerte `security.W*`** (123 avertissements OpenAPI `drf_spectacular`, non bloquants) |
| `tsc --noEmit` | exit 0 |
| `pnpm run build` (+ pré-rendu) | exit 0, 31 routes + 6 articles |
| `docker compose config -q` / `nginx -t` | OK |
| Conteneurs | tous les services `Up`, healthchecks `healthy` (db, redis, web, frontend, Mailpit) |
| `scripts/check_pricing_sync.py` | `OK — pricing in sync` |

---

## 2. Monétisation (Mission 1)

### Catalogue unifié

Nouvelle offre **Agency** pour que les trois prix demandés (9/29/79 €)
correspondent à trois offres payantes, et non à un mélange Free/Pro/Business :

| Offre | Mensuel | Annuel | Sites | Scans/mois |
|---|---:|---:|---:|---:|
| Free | 0 € | 0 € | 1 | 10 |
| Pro | 9 € | 90 € | 10 | 500 |
| Business | 29 € | 290 € | 50 | 5 000 |
| Agency | 79 € | 790 € | 200 | 20 000 |

Sources alignées :
- `backend/subscriptions/pricing.py` (source de vérité),
- `create_plans` (base),
- `src/data/plans.json` (miroir pour le pré-rendu / repli),
- `/pricing` et `/app/billing` consomment désormais l'API.

`scripts/check_pricing_sync.py` échoue à la moindre divergence ; il est branché
dans la CI.

### Paddle

- `POST /api/v1/subscriptions/checkout/` : le client envoie uniquement
  `plan_tier` + `billing_cycle` ; le `price_id` vient de `Plan`, jamais du client.
- `POST /api/v1/subscriptions/portal/` : session portail client (factures,
  moyen de paiement, annulation).
- `POST /api/v1/webhooks/paddle/` : signature `Paddle-Signature`
  (HMAC-SHA256 sur `ts:body`, fenêtre anti-rejeu 5 min), journal
  `BillingEvent` unique `(provider, event_id)`, rejeu = `duplicate`,
  échec = 500 (Paddle réessaie).
- Événements gérés : `subscription.created/updated/activated/trialing/
  past_due/paused/canceled`, `transaction.completed` (provisionnement de
  secours).
- `POST /subscriptions/upgrade/` ne peut plus changer un plan : `503` si
  billing désactivé, sinon `409 use_checkout`.
- Configuration : `manage.py configure_billing` mappe les `PADDLE_PRICE_*`.

Tests : checkout (503/502/400/201, absence de montant client), signature
invalide/absente/expirée, création, annulation, doublon idempotent, prix
inconnu → 500 + événement `failed`, transaction complétée.

---

## 3. Quotas (Mission 2)

`subscriptions/services/quotas.py` résout l'offre effective (abonnement
absent/annulé/expiré → Free ; `past_due` conserve l'offre jusqu'à échéance)
puis applique :

| Contrôle | Point d'application | Réponse |
|---|---|---|
| `max_websites` | `WebsiteViewSet.perform_create` | 403 `website_limit_reached` |
| `max_scans_per_month` | scan manuel site + scan monitoring | 403 `scan_quota_exceeded` |
| `can_export_reports` | PDF + génération de rapport | 403 `can_export_reports_required` |
| `max_alert_channels` | création de canal | 403 `alert_channel_limit_reached` |
| `can_use_api` | création/gestion de clés API | 403 |

La réponse contient `limit`, `usage`, `plan`, `upgrade_url` pour que le
frontend propose l'upgrade. `GET /subscriptions/me/` expose limites + usage.

**Correctif de robustesse :** le plan est relu en base (`select_related`) et non
via `user.subscription`, dont le cache d’instance pouvait ignorer un changement
appliqué par webhook pendant la requête.

Vérification live (utilisateur Free) : 1er site `201`, 2e `403
website_limit_reached` ; `/me` renvoie `max_websites: 1`.

---

## 4. SEO, blog et assets (Mission 3)

### Pré-rendu

`scripts/prerender.mjs`, exécuté après `vite build` (aucun Puppeteer) :

- 31 routes publiques + 6 articles → un HTML par URL ;
- titre/description/robots/canonical/OG/Twitter/JSON-LD propres à chaque page ;
- contenu de repli lisible sans JavaScript ;
- `sitemap.xml` (32 URL) et `robots.txt` absolus depuis `VITE_BASE_URL` ;
- `404.html` réel, servi avec un statut **404**.

Vérifications HTTP sur le conteneur reconstruit :

```
/                                 200  Website Monitoring for Small Businesses | Presence
/pricing                          200  Simple Website Monitoring Pricing | Presence
/blog/what-is-dmarc               200  What is DMARC … | Presence Blog
/blog/does-not-exist              404  Page not found | Presence
/app/dashboard                    200  (coquille privée, noindex)
```

Le sitemap servi contient `https://localhost/...` (aucun `YOURDOMAIN.COM`,
aucun `${VITE_BASE_URL}`) et `robots.txt` pointe dessus.

Nginx : `try_files $uri/index.html $uri =404` évite la redirection 301 vers
`/pricing/` qui aurait cassé le canonical ; `/app/`, `/report/` et `/admin`
gardent une coquille SPA privée.

### Images

`public/og-image.png` (1200×630), `icons/icon-192.png`,
`icons/icon-512.png`, `icons/icon-maskable-512.png`, `apple-touch-icon.png`
(180×180), déclarés dans `index.html` et `manifest.json` ; servis en
`image/png` (vérifié).

### Blog headless

- `src/api/blog.ts` : lecture de `VITE_WP_API_URL` (base ou `/wp-json`),
  `_embed`, catégorie, auteur, image, temps de lecture.
- `BlogPage` / `BlogArticle` : états chargement, erreur avec retry, article
  inexistant → page 404.
- HTML WordPress assaini par **DOMPurify** avant `dangerouslySetInnerHTML`.
- Les six articles historiques sont sortis de `BlogArticle.tsx` vers
  `src/data/mock-posts.json` (mocks temporaires explicitement signalés dans
  l’UI tant que le CMS n’est pas branché).

---

## 5. Scanners et modules métier (Mission 4)

| Module | Avant | Après |
|---|---|---|
| `advanced_security/malware.py` | `return clean` statique | URLhaus (sans clé) + Google Safe Browsing (si clé) ; `unknown` si injoignable, jamais « clean » par défaut |
| `scanners/reviews.py` | placeholder `not_configured` | lecture réelle du JSON-LD `AggregateRating` (note, volume, score) |
| `social/tasks.py` — followers | `random.randint(-2, 30)` | Meta Graph / X API ; sans credentials → `skipped`, valeurs inchangées |
| `social/tasks.py` — mentions | 2 fausses mentions | recherche publique Reddit, déduplication par URL |
| `reports/urls.py` | monté à la racine, donc `404` sur `/reports/...` | préfixé `reports/`, conforme au contrat frontend |

Tests ajoutés : URLs des appels fournisseurs, absence de credentials,
indisponibilité réseau (pas de fausses données), déduplication Reddit,
URLhaus clean/threat/unknown, Safe Browsing, scanner d’avis.

`can_use_api` est désormais une fonctionnalité réelle : `ApiKey`
(`pk_<prefix>_<secret>`, hash SHA-256, révocation immédiate), authentification
`Authorization: Api-Key ...`, endpoints `/api/v1/api-keys/`.

---

## 6. DevOps (Mission 5)

### Compose iso-production

- `mailpit` ajouté (SMTP réel local, UI 8025) et injecté dans `web` et
  `celery-worker` par variables d’environnement (sans écraser les secrets du
  `.env`) ;
- limites de logs `json-file` 10 Mo × 3 sur tous les services ;
- healthcheck Postgres utilisant `$POSTGRES_USER/$POSTGRES_DB` ;
- builds frontend paramétrés par `VITE_BASE_URL` / `VITE_WP_API_URL` ;
- worker Celery limité à 2 processus (4 vCPU, scans réseau) ;
- certificats, webroot ACME et dossier Let’s Encrypt montés ;
- proxy API résolu à chaque requête (`resolver` Docker + variable
  `proxy_pass`) : un redéploiement de `web` ne laisse plus nginx sur l’ancienne
  IP avec des 502 jusqu’à son redémarrage.

### TLS / Let’s Encrypt

`nginx.conf` inclut `/etc/nginx/ssl/tls.conf` : auto-signé en local, remplacé
par `scripts/enable_letsencrypt.sh <domaine> <email>` (certbot webroot, reload
sans coupure). Le challenge ACME reste servi en HTTP.

### Sauvegardes

`scripts/backup.sh` : `pg_dump` custom + RDB Redis compressé + SHA-256,
rétention 14 jours, export S3 optionnel.
`scripts/verify_backup_restore.sh` restaure dans une base jetable.
`scripts/restore.sh` gère la restauration réelle avec confirmation.

**Preuve :** dump du 21/10 17:22 (1,8 Mo) restauré sans erreur — 46 tables,
5 utilisateurs, 3 sites, 3 082 scans.

### SMTP / alertes

`scripts/configure_local_smtp.sh` a écrit les variables SMTP dans
`backend/.env` (Mailpit, port 1025). Deux e-mails réels ont été remis :
un `send_mail` de contrôle, puis une **alerte** créée et passée au
`dispatch_alert` (`sent_to: ['email']`), reçue dans Mailpit avec l’objet
`🟡 [WARNING] SSL expires in 7 days`.

---

## 7. Fichiers principaux

Backend : `subscriptions/{pricing.py,services/billing.py,services/quotas.py,
authentication.py,permissions.py,api_views.py,views.py,models.py,urls.py}`,
migrations `0002`/`0003`, `management/commands/{create_plans,configure_billing}.py`,
quotas dans `websites/views.py`, `monitoring/views.py`, `reports/views.py`,
`notifications/views.py`, `advanced_security/scanners/malware.py`,
`social/tasks.py`, `scanners/reviews.py`, `config/settings/base.py`.

Frontend : `pages/{Pricing,Billing,BlogPage,BlogArticle}.tsx`,
`api/{blog.ts,endpoints.ts,types.ts}`, `components/{SEO,BlogBody}.tsx`,
`data/{plans,mock-posts}.json`, `lib/pricing.ts`,
`scripts/{prerender.mjs,generate_brand_assets.py}`, `nginx.conf`, `index.html`,
`manifest.json`, assets PNG.

Ops : `docker-compose.yml`, `nginx/ssl/tls.conf`, `scripts/{backup.sh,
restore.sh,verify_backup_restore.sh,enable_letsencrypt.sh,
configure_local_smtp.sh,check_pricing_sync.py}`, `.github/workflows/ci.yml`,
`README.md`.

---

## 8. Limites restantes (honnêtes)

1. **Aucun paiement réel encaissé** : les clés Paddle, les `price_id` et le
   webhook public ne sont pas fournis. Le flux est testé avec signatures
   valides/invalides et réponses fournisseur simulées, pas contre Paddle live.
2. **WordPress non branché** : `VITE_WP_API_URL` est vide, donc le blog sert
   les mocks. Le chemin CMS est implémenté mais pas testé contre une instance
   réelle.
3. **Certificat auto-signé** : la vérification visuelle dans le navigateur
   intégré est bloquée par l’avertissement TLS. Les pages ont été validées par
   HTTP (statuts, titres, métas) et par build TypeScript, pas par capture
   d’écran.
4. **Let’s Encrypt non exécuté** : aucun domaine public ni port exposé ; le
   script et les blocs nginx sont prêts mais non déclenchés.
5. **Sauvegarde Redis** : le snapshot est produit et restauré dans le script
   réel, mais seul PostgreSQL a été vérifié par restauration complète.
6. **Pas de test de charge** ni de bascule multi-serveurs : le load balancing
   reste une étape ultérieure (2 VPS + LB managé, Postgres/Redis managés).
7. **Pages applicatives encore partiellement démo** (`Monitoring`, `Reviews`,
   `Reports`, `Dashboard`) : hors P0 de cet audit, mais à traiter avant de
   vendre l’offre comme complète.
8. **Avertissements OpenAPI** : 123 `drf_spectacular.W002` (serializers non
   inférés sur des `APIView`), sans impact sécurité ni runtime.
