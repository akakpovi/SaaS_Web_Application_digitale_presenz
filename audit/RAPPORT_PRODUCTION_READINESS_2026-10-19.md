# Audit « prêt pour la production » — Presence

**Date :** 19 octobre 2026  
**Périmètre :** backend Django, frontend React, SEO, blog/articles, monétisation, hébergement.  
**Méthode :** lecture du code + exécution réelle (tests, build, conteneurs, requêtes HTTP), pas seulement revue statique.

---

## 1. Verdict

**Le projet n'est pas encore prêt pour une mise en production commerciale.**

Le socle applicatif est solide (355 tests au vert, sécurité Django correcte, alerting et RGPD vérifiés lors de l'itération précédente), mais **la partie « premium » ne peut pas encaisser un paiement** et **quatre bloquants d'exploitation/SEO** subsistent.

| Bloc | État | Commentaire |
|---|---|---|
| Backend / API | ✅ Bon | 355 tests, health DB+Redis OK, `check --deploy` sans alerte `security.W*` |
| Frontend applicatif | ✅ Bon | TypeScript 0 erreur, build Vite OK |
| Alerting e-mail | ⚠️ Configuré, non prouvé | SMTP encore sur des placeholders `example.com` |
| Paiement premium | ❌ Absent | Aucun SDK, aucun checkout, aucun webhook |
| Quotas premium | ❌ Non appliqués | Les limites existent en base mais ne sont jamais vérifiées |
| SEO technique | ⚠️ Corrigé partiellement | Title/meta dupliqués corrigés ; SPA toujours non pré-rendue |
| Blog / articles | ⚠️ Fonctionnel mais figé | 6 articles codés en dur dans le bundle |
| Déploiement | ⚠️ Prototype avancé | TLS auto-signé, pas de sauvegarde automatique, un seul serveur |
| VPS actuel | ⚠️ Utilisable au démarrage | 4 vCPU / 16 Go, mais disque à **93 %** et aucun load balancing |

---

## 2. Preuves exécutées

| Vérification | Résultat |
|---|---|
| Suite backend complète | `Found 355 test(s)` — `Ran 355 tests` — `OK` — exit **0** |
| `manage.py check --deploy` (settings production) | 0 alerte de sécurité ; 48 avertissements `drf_spectacular` (schéma OpenAPI uniquement) |
| Frontend `tsc --noEmit` | exit **0** |
| Frontend `pnpm run build` | exit **0** |
| `GET /api/v1/health/` | `{"status":"ok","dependencies":{"database":true,"redis":true}}` |
| En-têtes HTTPS | HTTP/2, HSTS, `X-Frame-Options: DENY`, `nosniff`, gzip, cache immutable sur `/assets/` |
| Certificat TLS | **auto-signé**, `CN=localhost`, émetteur = sujet |
| `sitemap.xml` | **29 URLs** contenant encore `YOURDOMAIN.COM` |
| `robots.txt` | directive `Sitemap` toujours commentée, contient `${VITE_BASE_URL}` littéral |
| 404 | `/blog/does-not-exist` → **HTTP 200** (soft 404) |
| Meta par page | `/blog/what-is-dmarc` sert le `<title>` de la home (SPA non pré-rendue) |
| Disque du serveur | **206 Go / 234 Go utilisés (93 %)** |
| Sauvegardes | 2 archives manuelles du 14/10, **aucune tâche planifiée** |

---

## 3. Bloquants P0

### 3.1 Premium gratuit — **corrigé dans cet audit**

`POST /api/v1/subscriptions/upgrade/` passait n'importe quel utilisateur authentifié en Pro/Business **sans paiement**. C'était à la fois une fuite de revenus et une faille d'autorisation.

Correctif appliqué dans `SaaS_Web_Application_digitale_presenz_v2/backend/subscriptions/views.py` :

- l'endpoint échoue désormais en **503 `billing_not_configured`** tant que `BILLING_ENABLED` et `BILLING_PROVIDER` ne sont pas explicitement configurés ;
- le changement de plan devra être déclenché par le **webhook du prestataire après encaissement**, jamais par le client ;
- 2 tests de non-régression ajoutés (plan reste `free`).

Variables documentées dans `.env.example`. **Ne pas activer `BILLING_ENABLED` avant que le webhook de paiement existe** : l'endpoint ne vérifie pas encore de transaction.

### 3.2 Aucun prestataire de paiement

- `requirements.txt` ne contient ni `stripe`, ni `paddle`, ni SDK équivalent.
- Aucun endpoint checkout / portail client / webhook.
- Le modèle `Subscription` est déjà prêt (`external_id`, `billing_provider`, `billing_metadata`) : bonne base, mais rien ne l'alimente.

### 3.3 Quotas premium jamais appliqués

`max_websites`, `max_scans_per_month`, `can_export_reports`, `can_use_api`, `max_alert_channels` existent en base et sont exposés par l'API, mais **aucune vue ne les vérifie** :

- `WebsiteViewSet.perform_create` crée un site sans limite ;
- le déclenchement de scan ne compte pas les scans du mois ;
- l'export PDF n'est pas réservé aux plans payants ;
- l'accès API n'est pas restreint.

Conséquence : même après paiement, l'offre premium n'a **aucune valeur fonctionnelle**.

### 3.4 Trois catalogues de prix contradictoires

| Source | Free | Pro / milieu | Business / haut |
|---|---|---|---|
| `create_plans.py` (base de données) | 0 € | **19 €** | **49 €** |
| Page `/pricing` | 0 € | **5,99 €** | **14,99 €** |
| Page `/billing` | 0 € | Starter 5,99 € / Pro 14,99 € | Agency 39,99 € |

Le prix affiché, le prix facturé et le nom des plans ne correspondent pas. À trancher **avant** d'intégrer un prestataire, sinon les `price_id` seront faux.

### 3.5 Sortie de production non configurée

- Certificat **auto-signé `localhost`** → tous les navigateurs affichent un avertissement.
- `sitemap.xml` et `robots.txt` non finalisés (domaine placeholder).
- SMTP sur `smtp.example.com` : les alertes sont créées mais aucun e-mail ne part.
- Disque à **93 %** : une croissance normale (PostgreSQL, Redis AOF, images Docker, scans) suffit à saturer le serveur.
- **Aucune sauvegarde automatique** ni test de restauration ; la seule archive existante date du 14/10.

---

## 4. SEO — ce qui a été corrigé et ce qui reste

### Corrigé pendant cet audit

1. **`<title>` pollué** : le build produisait `<title>Figma Make AppWebsite Monitoring…</title>` à cause du plugin Figma. Corrigé dans `index.html`, `.figma/make/site.json` et `vite.config.ts`. Vérifié sur le conteneur reconstruit : titre propre, **une seule** meta description, **zéro** occurrence de « Figma Make App ».
2. **Meta dupliquées** (`description`, `og:title`, `og:description`) injectées par le plugin : suppression de la double source.
3. **Canonical relatif** quand `VITE_BASE_URL` est absent : repli sur `window.location.origin`, donc URL absolue.
4. **JSON-LD `BlogPosting`** ajouté sur chaque article (+ `og:type=article`).
5. **Sitemap** : ajout des 6 pages `/solutions/*` qui existaient mais n'étaient pas déclarées.

### Reste à faire (bloquant SEO)

| Problème | Impact | Correctif recommandé |
|---|---|---|
| SPA 100 % client-side : `/blog`, `/pricing`, `/features/*` servent le `<title>` de la home | Google render le JS, mais LinkedIn/X/Slack et de nombreux crawlers ne le font pas ; mauvais CTR et aperçus | Pré-rendu au build (`vite-plugin-prerender`, `react-snap`) **ou** basculer le marketing/blog en Astro/Next statique |
| Toutes les URL inconnues renvoient **200** | Soft 404, indexation de pages vides | Pré-rendu + vraie page 404, ou règle nginx avec liste de slugs |
| `sitemap.xml` avec `YOURDOMAIN.COM` | Sitemap invalide, non soumisable à Search Console | Générer le sitemap au build depuis `VITE_BASE_URL` (les 29 URLs sont déjà listées) |
| `robots.txt` : `Sitemap:` commenté + `${VITE_BASE_URL}` littéral | Découverte du sitemap impossible | Écrire l'URL absolue au build |
| `og:image` en **SVG** | Facebook, LinkedIn, X n'acceptent pas le SVG → aucun aperçu | Fournir `og-image.png` 1200×630 |
| `lang="en"` uniquement, aucun `hreflang` | Marché FR/DE non exploité | Décider si le marketing est multilingue ; sinon retirer les promesses i18n |
| Blog sans RSS, sans pagination, sans pages catégories/auteur | Maillage et découverte limités | Ajouter flux RSS + pages catégories si le blog devient un canal d'acquisition |
| `manifest.json` et `apple-touch-icon` en SVG uniquement | Installation PWA Android/iOS dégradée | Ajouter PNG 192/512 et 180×180 |

**Priorité SEO n°1 : le pré-rendu.** Sans lui, tout le reste (JSON-LD, canonical, sitemap) ne compense pas des pages dont le contenu et les balises n'existent pas dans le HTML initial.

---

## 5. Blog / Articles

- Routes `/blog` et `/blog/:slug` fonctionnelles, 6 articles rédigés, design correct, JSON-LD désormais présent.
- **Tout le contenu est dans `BlogArticle.tsx`** : publier un article = modifier le code + rebuild + redéploiement. Aucun rôle éditeur, aucune planification, aucun brouillon.
- Aucun back-office, aucun modèle `Article`, aucune image de couverture, aucun auteur réel (tous « Presence Team »).
- Le sitemap liste bien les 6 slugs existants (vérifié), donc pas de lien mort côté sitemap.

**Options, par ordre de coût croissant :**

1. **Garder le statique**, extraire les articles en Markdown/MDX et générer les pages au build (le plus simple, mais toujours un déploiement par article).
2. **Modèle Django `Article` + admin** + API publique, puis pré-rendu ou rendu serveur des pages blog. Cohérent avec la stack existante, mais ne règle pas seul le SEO SPA.
3. **Sortir le marketing/blog en Astro ou Next.js statique**, garder React pour l'application authentifiée. C'est la meilleure architecture SEO à moyen terme : pages HTML complètes, build rapide, blog en Markdown ou CMS headless.

Recommandation : option 3 si le SEO est un canal d'acquisition sérieux ; option 1 si le blog reste secondaire à court terme.

---

## 6. Solutions de paiement pour le premium

### Comparatif

| Critère | **Stripe Billing** | **Paddle Billing** | **Lemon Squeezy** |
|---|---|---|---|
| Rôle légal | Vous êtes le vendeur | **Merchant of Record** | **Merchant of Record** |
| TVA UE | Calculée par Stripe Tax, **déclarée par vous** | Calculée, collectée et reversée par Paddle | Collectée et reversée par Lemon |
| Frais indicatifs | 1,5 % + 0,25 € (carte EEA standard) + 0,7 % Billing (+0,5 % Tax) | **5 % + 0,50 $** par transaction | 5 % + 0,50 $ + surcharges (international 1,5 %, PayPal 1,5 %, abonnement 0,5 %) |
| Coût sur un abonnement à 5,99 € | ≈ 0,38–0,41 € (~6,5 %) | ≈ 0,76 € (~12,7 %) | ≈ 0,80–0,90 € |
| Coût sur un abonnement à 49 € | ≈ 0,98 € (~2 %) | ≈ 2,91 € (~5,9 %) | ≈ 3,10 € |
| Essais / portail client | Oui | Oui | Oui |
| SDK Python officiel | Oui | Oui (+ vérification de signature Django) | Non (REST + webhooks) |
| Adaptation à votre stack | Excellente | Très bonne | Correcte mais plus de plomberie |

Sources : [Stripe Pricing](https://stripe.com/pricing), [Stripe Tax](https://docs.stripe.com/tax), [Stripe Managed Payments](https://stripe.com/managed-payments), [Paddle Pricing](https://www.paddle.com/pricing), [Paddle Python SDK](https://developer.paddle.com/sdks/libraries/python/), [Lemon Squeezy Pricing](https://www.lemonsqueezy.com/pricing), [Fees Lemon](https://docs.lemonsqueezy.com/help/getting-started/fees).

### Recommandation

**Paddle** est le choix par défaut pour un fondateur solo vendant en Allemagne/France : il devient le vendeur légal, gère la TVA/OSS et les factures, et son SDK Python s'intègre proprement à Django. Le surcoût (≈ 5 % + 0,50 $) est le prix de la tranquillité fiscale.

**Stripe Billing** devient meilleur si :
- vous gardez des tickets à 5,99 € (l'écart de marge est alors du simple au double) ;
- vous êtes à l'aise avec la TVA UE / un comptable ;
- vous voulez un portail et une relation de paiement directe.

**Lemon Squeezy** : correct pour un lancement rapide, mais surcharges, pas de SDK Python officiel et validation de boutique en 2–3 jours. Pas mon premier choix ici.

> Décision préalable obligatoire : **unifier les prix** (section 3.4). La structure actuelle à 5,99 €/14,99 € rend Paddle proportionnellement très cher. Un catalogue 9 €/29 €/79 € règle à la fois la marge et la cohérence.

### Plan d'intégration (provider-agnostique)

1. Choisir le prestataire et créer les produits/prix ; stocker les `price_id` dans `Plan` (nouveau champ ou `billing_metadata`).
2. `POST /api/v1/subscriptions/checkout/` → crée une session hébergée, renvoie l'URL. Le client ne choisit qu'un `plan_tier`, jamais un montant.
3. `POST /api/v1/webhooks/<provider>/` → vérifier la signature, journaliser l'événement, être **idempotent** (`event_id`), puis mettre à jour `Subscription` (`external_id`, statut, période, `current_period_end`).
4. Gérer `past_due`, `paused`, `canceled`, remboursements ; désactiver les fonctionnalités à l'expiration.
5. Portail client via URL fournie par le prestataire (moyen de paiement, factures, annulation).
6. **Appliquer les quotas côté serveur** : sites, scans/mois, export PDF, API, canaux d'alerte. Sans cela, le premium reste cosmétique.
7. Tests : signature invalide, rejeu d'événement, webhook en double, downgrade, échec de paiement, expiration.

---

## 7. Déploiement : que faire du VPS actuel ?

### Ce que dit la machine

- **4 vCPU, 15 Go de RAM**, Ubuntu 24.04, Docker 29.6.
- **Disque 234 Go occupé à 93 %** (17 Go libres) — risque immédiat.
- Une seule machine : **aucune haute disponibilité**, quel que soit l'outil installé dessus.

### Verdict

Ce VPS est **suffisant pour démarrer** (application + Celery + PostgreSQL + Redis sur une machine), probablement jusqu'à quelques centaines d'utilisateurs actifs, à condition de :

1. libérer de l'espace disque et mettre en place une rétention (logs Docker, vieilles images, scans) ;
2. remplacer le certificat auto-signé par Let's Encrypt ;
3. automatiser les sauvegardes PostgreSQL + Redis vers un stockage externe (S3) et **tester une restauration** ;
4. ajouter une supervision externe (uptime, erreurs, saturation disque).

Il n'est **pas idéal pour du load balancing** : on ne répartit pas une charge sur un seul serveur. Et un load balancer sur ce même serveur serait lui-même un point de défaillance unique.

### Solution recommandée pour l'exploitation

**Coolify auto-hébergé sur le VPS** (gratuit, open source) :

- déploiement Git automatique, rollback, variables d'environnement ;
- TLS Let's Encrypt automatique via Traefik ;
- sauvegardes PostgreSQL planifiées vers S3 ;
- métriques serveur/conteneurs et alertes disque.

Alternative : **Dokploy** (aussi gratuit en auto-hébergé) si vous préférez Traefik/Swarm. Alternative minimaliste : **Docker Compose + Caddy** (TLS automatique) si vous voulez garder la main sans plateforme.

À mettre devant : **Cloudflare** (DNS, CDN, WAF, protection DDoS). Cloudflare ne fait pas de répartition multi-origines sans l'offre **Load Balancing** payante.

### Quand et comment ajouter le load balancing

Ce n'est **pas nécessaire au lancement**. Le jour où une machine ne suffit plus :

1. Rendre l'application **stateless** (elle l'est déjà : JWT, pas de session serveur, fichiers servis par nginx).
2. Sortir PostgreSQL et Redis du VPS applicatif → services managés (Neon/Supabase pour Postgres, Upstash pour Redis) ou serveurs dédiés avec réplication.
3. Lancer **2 VPS applicatifs** derrière un **load balancer managé** (Hetzner Load Balancer, ou Cloudflare Load Balancing) avec health checks sur `/api/v1/health/`.
4. Séparer les **workers Celery** (scans = CPU + réseau) des serveurs web ; **un seul** `celery-beat`.
5. Stocker les fichiers/rapports dans S3, pas sur le disque local.
6. Ajouter autoscaling, métriques et tests de charge **seulement après** cette étape.

Pour information : Coolify et Dokploy savent déployer sur plusieurs serveurs, mais **ne répartissent pas le trafic à eux seuls** — il faut un ingress/load balancer devant. (Sources : [Coolify multi-server](https://coolify.io/docs/core/infrastructure/scaling/multi-server-deployments), [Coolify rolling updates](https://coolify.io/docs/applications/deployments/rolling-updates), [Dokploy cluster](https://docs.dokploy.com/docs/core/cluster), [Cloudflare Load Balancing](https://developers.cloudflare.com/load-balancing/), [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).)

### Alternatives managées

- **Railway / Render / Fly.io** : déploiement et scaling plus simples, Postgres/Redis managés, mais les scans longue durée et l'egress nécessitent des workers dédiés, et le coût grimpe avec les workers.
- **Kubernetes** : prématuré. À envisager seulement avec une équipe d'exploitation et un vrai besoin multi-région.

---

## 8. Plan de mise en production (proposé)

| Jour | Action |
|---|---|
| J1 | Trancher le catalogue de prix ; unifier DB + `/pricing` + `/billing` |
| J2–J4 | Intégrer Paddle (ou Stripe) : checkout, portail, webhooks signés, tests |
| J5 | Appliquer les quotas serveur (sites, scans, PDF, API, canaux) + tests |
| J6 | Pré-rendu des pages marketing/blog ; sitemap et robots générés avec le vrai domaine ; PNG OG + icônes PWA |
| J7 | Let's Encrypt, SMTP réel, monitoring (Sentry + uptime), rotation des secrets |
| J8 | Sauvegardes automatiques + **restauration testée** ; nettoyage disque ; rétention logs |
| J9 | Test de charge léger (scan + API) ; vérification des 404, en-têtes, cache |
| J10 | Répétition générale sur staging, puis bascule production |

---

## 9. Limites de cet audit

- Aucun paiement réel n'a été testé : il n'existe pas encore d'intégration.
- L'envoi SMTP réel n'a pas pu être validé (identifiants placeholder) ; le code utilise bien un backend SMTP.
- Pas de test de charge ni de test de bascule/restauration.
- Le nom de domaine de production n'étant pas connu, le sitemap et les canonical n'ont pas pu être finalisés avec la bonne origine.
- Les écrans `Monitoring`, `Reports`, `Reviews`, `Billing` restent partiellement ou totalement sur des données d'exemple (déjà signalé dans l'itération 3).
