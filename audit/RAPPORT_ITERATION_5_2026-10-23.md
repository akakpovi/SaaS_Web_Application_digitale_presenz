# Rapport d'exécution — Itération 5

**Date :** 23 octobre 2026
**Périmètre :** finalisation frontend, Paddle Sandbox, WordPress headless, charge k6, préparation TLS.
**Environnement mesuré :** pile Docker canonique (`docker-compose.yml` racine), 4 vCPU, 15,8 Go de RAM.
**Verdict global :** les données de démonstration ont disparu de l'UI authentifiée et le blog est branché sur un vrai WordPress. Le chemin serveur Paddle (webhook signé → abonnement → quota) est prouvé de bout en bout via une URL publique. **Le paiement Sandbox réel n'a pas pu être exécuté : aucune clé API Paddle n'est présente dans le projet.** C'est le seul blocage restant pour la mise en production commerciale.

---

## 1. Mission 1 — Données réelles dans l'UI authentifiée

Aucune valeur fictive ne subsiste dans `Dashboard`, `Monitoring`, `Reviews` et `Reports` : les quatre pages lisent leurs données via `useApiList` / `useApiResource` et les endpoints de `src/api/endpoints.ts`. Aucun tableau de démonstration n'est défini dans les pages (vérifié par recherche `mock|demo|fake|sample|dummy`).

Vérification exécutée dans un navigateur réel, connecté au compte de test, sur la pile en marche :

| Page | Endpoint source | Rendu observé |
|---|---|---|
| Dashboard | `/websites/`, `/scans/`, `/alerts/?status=firing` | 3 sites, score 85/100, 22 scans, 3 alertes, dernières analyses horodatées |
| Monitoring | `/monitoring/overview/?period=30D`, `/monitoring/` | 3 sites, 22 checks, uptime 100 %, timeline d'événements issue des scans |
| Reviews | `/reviews/`, `/reviews/summary/` | 3 avis, note moyenne 3,3 ★, 1 réponse attendue |
| Reports | `/reports/` | rapport d'octobre 2026, 8 scans analysés, score 85/100, ventilation par catégorie |

Les valeurs affichées correspondent exactement aux réponses API et aux lignes PostgreSQL. Les données « example.com » visibles appartiennent au seul compte de test `it5-demo@presence.io` ; ce ne sont pas des constantes du code.

Tests backend des apps concernées : **83 tests OK** (`subscriptions reports reviews monitoring`).

---

## 2. Mission 2 — Paddle Sandbox : pipeline validé, paiement hébergé bloqué

### Ce qui a été construit

- `backend/subscriptions/management/commands/create_paddle_sandbox.py` : crée les produits, les prix mensuels/annuels aux montants du catalogue (9/29/79 € et 90/290/790 €), remplit `Plan.external_price_id_*`, crée la destination de webhook et écrit le secret en 0600 sans jamais l'afficher.
- `scripts/paddle_webhook_tunnel.sh` : tunnel HTTPS public (Cloudflare quick tunnel par défaut, ngrok en option), URL écrite dans `/tmp/presence-webhook-url.txt`.
- `backend/subscriptions/tests/test_paddle_sandbox.py` : 4 tests OK (mapping, refus sans clé, refus du live, secret non affiché).

### Cycle serveur démontré sur une URL publique

Le webhook a été appelé via `https://<tunnel>.trycloudflare.com/api/v1/webhooks/paddle/`, avec une signature `Paddle-Signature` HMAC-SHA256 réelle :

| Requête | Résultat |
|---|---|
| `subscription.created` signé (`pri_sdbx_it5_pro_9eur`, `custom_data.user_id=11`) | `200 {"status":"processed","result":{"plan":"pro","subscription_status":"active"}}` |
| Rejeu du même `event_id` | `200 {"status":"duplicate"}` — aucun second changement |
| Signature forgée | `400 invalid_signature` |
| Timestamp expiré (rejeu) | `400 invalid_signature` |

Effet en base, immédiatement après l'événement :

- plan `pro`, statut `active`, `billing_provider=paddle`, `external_id=sub_sdbx_it5_demo_001` ;
- quota passé de **10 à 500 scans/mois**, période jusqu'au **23 novembre 2026** ;
- page **Billing** : « Pro plan · Active · €9/month · Renews 23 November 2026 · **22/500 scans this month** ».

### Blocage explicite

`PADDLE_API_KEY` est absente de `backend/.env`. La commande s'arrête donc volontairement :

```
CommandError: PADDLE_API_KEY is empty. Create a Sandbox API key in Paddle
(Developer tools → Authentication) and put it in backend/.env.
```

Conséquences, à ne pas masquer :

- aucun `price_id` réel (9/29/79 €) n'a été créé dans Paddle ;
- aucun checkout hébergé Paddle n'a été exécuté, donc **aucun paiement Sandbox encaissé** ;
- le prix de test `pri_sdbx_it5_pro_9eur` utilisé pour la démonstration a été retiré de la base ;
- `BILLING_ENABLED=false`, le secret de webhook de test a été supprimé et le tunnel arrêté ;
- le compte de test `it5-demo@presence.io` conserve son abonnement Pro (preuve de la mise à jour du quota) ; aucun autre compte n'est affecté.

L'environnement reste configuré vers le Sandbox (`PADDLE_API_URL=https://sandbox-api.paddle.com`, `PADDLE_ENVIRONMENT=sandbox`). La procédure complète (clé → tunnel → `create_paddle_sandbox` → carte `4242 4242 4242 4242`) est documentée dans le README, section « Activer Paddle ».

---

## 3. Mission 3 — Blog WordPress headless

- Instance WordPress 6.7 + MariaDB réelle, exposée uniquement via `/cms/wp-json/` et `/cms/wp-content/` ; admin sur `127.0.0.1:8081`.
- 6 articles publiés servis par l'API REST (`digital-presence-checklist-small-business`, `website-security-checklist-small-business`, `how-to-check-ssl-certificate`, `what-is-dmarc`, `how-to-monitor-website-uptime`, `what-is-website-monitoring`).
- `VITE_WP_API_URL=/cms` renseignée dans le `.env` local, documentée dans `.env.example`, et **cuite dans le bundle de production** (vérifié dans l'image : `cms_refs=1`).
- Les mocks du blog ont disparu : `mock_refs=0` dans `blog-*.js`, et la page affiche 6 titres, dates et catégories issus du CMS.
- Correction Dockerfile : les arguments `VITE_BASE_URL` / `VITE_WP_API_URL` sont désormais répétés sur la commande de build, ce qui empêche une couche de cache de figer un bundle sans URL de CMS.

**Assainissement prouvé** : un article de test contenant `<script>window.__it5_xss=1</script>`, `<img src=x onerror="window.__it5_xss=2">` et un lien `javascript:` a été publié, puis ouvert dans le navigateur. Le HTML rendu était :

```html
<p>SAFE_MARKER_IT5</p>
<p><img src="x"><a>click</a></p>
<p>END_MARKER_IT5</p>
```

`window.__it5_xss` est resté `undefined`, aucun `<script>` ni attribut `onerror` n'a subsisté. L'article de test a été supprimé.

---

## 4. Mission 4 — Charge k6 et TLS

### Scénarios exécutés

`load/k6/presence_load_test.js` — 40 VUs navigation publique + 25 VUs navigation authentifiée + 2 VUs orchestration de scans Celery.

| Métrique | Charge complète | Charge stable (répétition) |
|---|---|---|
| VUs max | 67 | 23 |
| Requêtes | 5 142 | 2 069 puis 1 382 |
| Débit | 50,2 req/s | 31,0 req/s |
| Latence moyenne | 66 ms | 25–28 ms |
| p95 | **293 ms** | **92–100 ms** |
| Erreurs HTTP | **0 %** | **0 %** |
| Checks | 100 % (5 146/5 146) | 100 % |
| Scans Celery | 4/4 terminés, médiane 2,38 s, p95 3,22 s | — |

Tous les seuils (`p95<800 ms`, `p99<1500 ms`, erreurs `<2 %`, checks `>98 %`, scans `<60 s`) sont respectés.

### CPU : mesure honnête

La machine de test n'est **pas** un VPS dédié : elle héberge aussi `ai-platform-gateway` (~30 % CPU), des navigateurs, Xorg et un processus de healthcheck anormalement actif. Le générateur k6 tourne lui-même sur les mêmes 4 vCPU.

- Charge complète : CPU hôte moyen 89,5 %, max 100 %, load1 max 16,7.
- Charge stable : CPU hôte moyen 80,9 %.
- **Part de la pile applicative mesurée pendant la charge stable : 31,4 % du CPU total**, soit environ 1,25 vCPU sur 4 :
  - `web` 20,3 % (max 55,1 %), `db` 7,2 % (max 35,3 %), `frontend` 2,1 %, `redis` 1,6 %, `celery-worker` 0,2 %.
- RAM : 8,7 Go utilisés au maximum sur 15,8 Go pour l'ensemble des charges de la machine.

Conclusion : l'application tient 31–50 req/s avec une p95 inférieure à 300 ms et zéro erreur, et la pile elle-même ne consomme qu'un tiers du CPU. La saturation observée au niveau de l'hôte est due aux charges colocalisées et au générateur, pas à l'application. **La certification « 4 vCPU sans saturation » doit être refaite sur un VPS dédié avec k6 externe** ; elle ne peut pas être affirmée depuis cette machine.

### Let's Encrypt — checklist exacte

1. **DNS** : `A presence.example.com → IP_VPS` (et `AAAA` si IPv6) ; vérifier `dig +short presence.example.com`.
2. **Pare-feu** : ports 80 et 443 ouverts.
3. **`backend/.env`** : `DJANGO_ALLOWED_HOSTS=presence.example.com,www.presence.example.com`, `FRONTEND_URL=https://presence.example.com`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://presence.example.com`.
4. **Frontend** : `VITE_BASE_URL=https://presence.example.com docker compose build frontend && docker compose up -d frontend` (canonical, sitemap, robots absolus).
5. **Certificat** : `bash scripts/enable_letsencrypt.sh presence.example.com admin@example.com`.
6. **Renouvellement** : `15 4 * * 1 cd /srv/presence && bash scripts/renew_letsencrypt.sh >> /var/log/presence-certbot.log 2>&1` (script ajouté, il ne recharge nginx qu'après un `nginx -t` réussi).
7. **Vérification** : `curl -I https://presence.example.com` → 200 avec certificat valide ; `/api/v1/health/` → `{"status":"ok"}`.

---

## 5. État final et blocages

| Point | État |
|---|---|
| Données de démo dans l'UI authentifiée | **Supprimées** — pages 100 % API |
| Blog WordPress headless | **Connecté**, 6 articles, HTML assaini |
| Webhook Paddle public signé → quota | **Validé** (200, idempotence, rejets 400) |
| `price_id` réels 9/29/79 € | **Non créés** — clé API absente |
| Paiement Sandbox de bout en bout | **Non exécuté** — même cause |
| k6 | **Exécuté** — 50 req/s, p95 293 ms, 0 erreur |
| Certification CPU du VPS 4 vCPU | **À refaire sur VPS dédié** |
| Let's Encrypt | **Prêt** — checklist + renouvellement automatisable |

**Action unique pour débloquer le lancement :** créer une clé Paddle Sandbox, la placer dans `backend/.env` avec `BILLING_ENABLED=true`, relancer le tunnel, exécuter `create_paddle_sandbox`, puis payer avec la carte de test. Le reste du chemin (webhook, idempotence, quota, UI Billing) est déjà prouvé.
