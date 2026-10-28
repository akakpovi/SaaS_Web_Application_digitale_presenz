# Évaluation des connecteurs sociaux open source

## Postiz vs Pendpost vs développement sur mesure

| | |
|---|---|
| **Projet** | Presence — Phase 2 « Connecteurs sociaux » |
| **Date** | 24 octobre 2026 |
| **Statut** | Étude d'architecture terminée — **aucune modification de code applicatif** |
| **Auteur** | Architecte logiciel / Lead DevSecOps |
| **Périmètre** | OAuth, publication, statistiques, multi-tenant, sécurité des jetons, licence, maintenance |
| **Dépôts audités** | `gitroomhq/postiz-app` (`v2.25.2`, commit `9383f5b`) et `pendpost/pendpost` (`v2.7.0`, commit `42ac77b`) |
| **Livrable** | Ce document uniquement ; le code source de Presence n'a pas été modifié |

> **Avertissement juridique.** L'analyse de licence ci-dessous est une lecture technique préliminaire, pas un avis juridique. Une décision d'exploitation commerciale doit être validée par un conseil en propriété intellectuelle, notamment pour l'AGPL-3.0.

---

## 0. Résumé exécutif

**Recommandation : construire le registre de connecteurs OAuth et le coffre de jetons dans Presence (Django/DRF + Celery), sans embarquer Postiz ni Pendpost en production.** Le développement sur mesure est l'option la plus sûre, la plus rapide à mettre en production *conforme* et la plus facile à maintenir pour un périmètre de deux à quatre fournisseurs. Il s'intègre directement au modèle `Organization` / `Membership` existant et évite toute duplication de la base utilisateurs.

Les deux projets open source apportent des enseignements utiles, mais aucun ne répond au triple critère « multi-tenant + jetons OAuth protégés + intégration Django/React sans duplication d'identité » :

- **Postiz** est la solution la plus complète fonctionnellement (36 fournisseurs, API publique, analytics, workflows de rafraîchissement). Deux blockers majeurs ont été confirmés dans le code :
  1. **Les jetons OAuth sont stockés en clair** dans la table `Integration` (`token`, `refreshToken`), et le dépôt les écrit directement sans chiffrement applicatif. Une fuite de base, de sauvegarde ou de réplica exposerait les comptes sociaux de tous les tenants.
  2. **La licence racine est AGPL-3.0.** Toute version modifiée utilisée en réseau doit offrir sa source correspondante à ses utilisateurs. Un SaaS commercial qui veut corriger le stockage des jetons doit donc soit publier son fork, soit faire valider juridiquement un montage séparé — ce qui annule l'avantage « rapide à déployer ».
- **Pendpost** a la meilleure conception du **gate d'approbation humaine** (brouillon par défaut, approbation par un acteur distinct, échec fermé, pas d'auto-approbation) et des garde-fous anti-bannissement. Mais c'est un outil **local-first mono-opérateur** : un processus Node, des fichiers JSON, des jetons dans `.env`, pas de modèle utilisateurs/organisations, pas de RBAC, pas de base de données centrale. Il ne peut pas devenir le backend multi-tenant de Presence sans être réécrit.

**Chiffrage indicatif :** un MVP propriétaire pour deux fournisseurs (LinkedIn + Google, par exemple) représente **6 à 9 semaines-ingénieur**, avec l'infrastructure existante (Postgres, Redis, Celery) et un coffre AES-256-GCM en enveloppe. Quatre fournisseurs : 9 à 12 semaines. La maintenance courante est estimée à **0,15–0,25 ETP** pour ce périmètre, contre 0,3–0,5 ETP et 5 à 7 services supplémentaires pour Postiz.

| Critère | Postiz | Pendpost | Sur mesure |
|---|---|---|---|
| Isolation multi-tenant | Moyenne (applicative, sans RLS) | Faible (mono-opérateur) | **Forte** (org + RBAC + tests) |
| Sécurité des jetons OAuth | **Faible** (clair en base) | **Faible** (`.env` en clair) | **Forte** (enveloppe AES-256-GCM) |
| Intégration Django/React | Moyenne (API + OIDC, identités dupliquées) | Faible (sidecar local) | **Forte** (même backend) |
| Licence commerciale | **Bloquante** (AGPL) | Compatible (MIT) | **Propriétaire** |
| Maturité / couverture | **Élevée** (36 fournisseurs) | Faible (early, 2 comptes) | À construire, périmètre maîtrisé |
| Maintenance | Lourde (stack Node/Temporal) | Linéaire par tenant | **Modérée** (stack existante) |

---

## 1. Contexte et méthode

### 1.1 Ce que Presence possède déjà

Presence est une application Django REST Framework + React, avec PostgreSQL, Redis et Celery. Le multi-tenant est déjà matérialisé par :

- `Organization` : frontière de tenant, avec `billing_owner` et `is_personal` ;
- `Membership` : rôles `owner`, `admin`, `analyst`, `viewer` ;
- des helpers d'accès centralisés dans `organizations/access.py` (`role_for_organization`, `role_for_website`, `website_access_q`, etc.) ;
- des tests de non-régression multi-tenant dans `websites/tests/test_tenant_access.py` et `organizations/tests/test_team_api.py`.

Références : [`organizations/models.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/organizations/models.py#L17), [`organizations/access.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/organizations/access.py#L11), [`websites/models.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/websites/models.py#L23).

Le module `social` actuel n'est cependant **pas encore un registre de connecteurs OAuth** :

- `SocialProfile` est rattaché à un `Website`, pas à une `Organization`, et son unicité est `(website, provider)` ;
- les vues filtrent par `website__owner=request.user`, pas par l'organisation ;
- les synchronisations utilisent des jetons globaux d'environnement (`META_GRAPH_ACCESS_TOKEN`, `X_BEARER_TOKEN`), partagés par tous les tenants ;
- il n'existe ni modèle de connexion OAuth, ni refresh token, ni coffre de jetons, ni workflow de publication, ni gate d'approbation.

Références : [`social/models.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/social/models.py#L4), [`social/views.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/social/views.py#L10), [`config/settings/base.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/config/settings/base.py#L476).

La Phase F a validé l'isolation réseau et le multi-tenant de l'infrastructure. La Phase 2 doit maintenant ajouter la couche « comptes sociaux » sans affaiblir cette isolation. Le présent audit compare les options avant toute implémentation.

### 1.2 Questions d'audit

1. **Multi-tenant** : comment chaque solution isole-t-elle les organisations, les connexions et les données publiées ?
2. **Sécurité des jetons** : comment les access tokens et refresh tokens Google/LinkedIn sont-ils stockés, chiffrés, rafraîchis, révoqués et journalisés ?
3. **Intégration Django/React** : comment communiquer sans dupliquer les utilisateurs, les organisations et les rôles ?
4. **Licence et maturité** : quelles obligations pour un SaaS commercial, quel coût de maintenance, quel risque de rupture ?

### 1.3 Méthode

- Clones temporaires des dépôts, inspection du code réel (schémas Prisma, middlewares d'authentification, stockage des jetons, workflows de publication, webhooks, licences, CI) ;
- lecture des README, `SECURITY.md`, politiques de licence et métadonnées GitHub au 24 octobre 2026 ;
- comparaison avec l'architecture Presence existante et ses tests ;
- **aucun test dynamique OAuth n'a été exécuté** : les flux réels Google/LinkedIn n'ont pas été lancés, faute de comptes de test et de callbacks configurés. Les conclusions de sécurité portent sur le code et la configuration, pas sur un pentest runtime.

### 1.4 Limites

- Audit statique, pas de test d'intrusion des applications tierces ;
- le « cloud vault » optionnel de Pendpost n'est pas dans le dépôt open source : il n'a pas été audité ;
- les métriques GitHub (étoiles, contributeurs) sont des instantanés ;
- les estimations de charge et de coût sont des ordres de grandeur, à recalibrer après le choix du fournisseur cloud et du KMS ;
- l'analyse AGPL doit être confirmée par un avocat.

---

## 2. Exigences de référence

Les exigences ci-dessous servent de grille commune. Elles sont dérivées du modèle Presence et des contraintes de sécurité exprimées pour la Phase 2.

| ID | Exigence | Niveau | Critère d'acceptation |
|---|---|---|---|
| **R1** | Isolation par organisation | Critique | Aucune requête ne peut lire ou modifier une connexion d'une autre organisation, même avec un UUID deviné. |
| **R2** | Jetons OAuth au repos | Critique | Access/refresh tokens chiffrés en AES-256-GCM, clé de chiffrement hors base, AAD liée au tenant, rotation possible. |
| **R3** | Flux OAuth | Critique | `state` à usage unique, PKCE S256, redirect URI exact, échange côté serveur, aucun jeton dans l'URL ou le frontend. |
| **R4** | Publication fiable | Élevée | Gate d'approbation, idempotence, retries avec backoff, gestion 401/429/5xx, réconciliation après timeout. |
| **R5** | Statistiques | Moyenne | Collecte normalisée, upserts idempotents, quotas et rate limits par connexion. |
| **R6** | Intégration | Élevée | API DRF, UI React, webhooks signés, pas de duplication des utilisateurs/organisations. |
| **R7** | Licence | Critique | Compatible avec un SaaS propriétaire, sans obligation de publication du code Presence. |
| **R8** | Exploitation | Élevée | Pas de nouveau runtime lourd ; sauvegardes, rotation de clés, audit, procédure de reauth. |

**Conséquence directe :** une solution qui échoue sur R2 ou R7 est disqualifiée pour le cœur de Presence, quel que soit son nombre de fonctionnalités.

---

## 3. Audit de Postiz

### 3.1 Fiche technique

| Élément | Constat |
|---|---|
| Version auditée | `v2.25.2`, commit `9383f5b`, publiée le 23 octobre 2026 |
| Licence | **AGPL-3.0** (licence racine et README) ; les `package.json` de `apps/backend` et `apps/frontend` déclarent `ISC`, incohérence à clarifier |
| Stack | NestJS (backend), Next.js (frontend), Prisma/PostgreSQL, Redis, Temporal, stockage local ou S3/R2 |
| Fournisseurs | **36** providers sociaux dans `libraries/nestjs-libraries/src/integrations/social` |
| API | API publique `/public/v1`, authentifiée par clé d'organisation ou jeton OAuth `pos_` |
| SSO | OIDC générique (`POSTIZ_OAUTH_*`), pas de SCIM ni de provisioning natif |
| Communauté | ~37 700 étoiles, ~7 360 forks, 75 comptes contributeurs, 222 issues ouvertes |
| Tests | Aucune suite de tests unitaires visible dans le snapshot ; la CI principale exécute le build et CodeQL |

Postiz est un produit complet, avec une couverture fonctionnelle nettement supérieure à ce que Presence peut construire en Phase 2. La question n'est donc pas « est-ce que ça marche ? » mais « est-ce que ça peut être exploité dans notre modèle de sécurité et de licence ? ».

### 3.2 Multi-tenant : une isolation applicative, pas une isolation forte

Postiz utilise un modèle classique :

- `Organization` est la frontière de données ;
- `UserOrganization` relie un utilisateur à une ou plusieurs organisations, avec un rôle `SUPERADMIN`, `ADMIN` ou `USER` ;
- les entités métier (`Integration`, `Post`, `Media`, `Webhooks`, etc.) portent un `organizationId` ;
- le middleware d'authentification résout l'utilisateur depuis la base, puis sélectionne l'organisation à partir du cookie/header `showorg`, de l'abonnement ou de la première organisation ;
- l'API publique résout l'organisation à partir de la clé API ou du jeton OAuth.

Références : [`schema.prisma`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/libraries/nestjs-libraries/src/database/prisma/schema.prisma#L142), [`auth.middleware.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/apps/backend/src/services/auth/auth.middleware.ts#L95), [`public.auth.middleware.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/apps/backend/src/services/auth/public.auth.middleware.ts#L30).

**Points forts :**

- toutes les requêtes importantes sont filtrées par `organizationId` ;
- l'utilisateur ne peut choisir qu'une organisation dont il est membre ;
- le transfert de propriété et les rôles sont gérés dans la même base ;
- l'API publique permet d'automatiser publications et analytics par organisation.

**Limites :**

- **pas de Row-Level Security PostgreSQL** : l'isolation dépend entièrement de la discipline des requêtes Prisma. Une requête oubliant `organizationId` peut fuiter ;
- **pas de base ou de schéma par tenant** : tous les tenants partagent les mêmes tables, les mêmes sauvegardes et les mêmes migrations ;
- **rôles moins granulaires** que Presence (3 rôles contre 4, pas de notion d'analyste read/write distincte) ;
- **superadmin et impersonation** : fonctionnalités puissantes, mais surface d'attaque et journalisation à auditer ;
- **duplication d'identité** : Postiz possède ses propres `User`, `Organization` et `UserOrganization`. Même avec OIDC, il crée un utilisateur local et une organisation locale. Il n'y a pas de SCIM, pas de synchronisation de déprovisionnement, pas de mapping natif vers les memberships Presence.

**Verdict multi-tenant :** correct pour un produit autonome, insuffisant comme fondation d'un SaaS qui a déjà son propre modèle d'organisations et veut une défense en profondeur.

### 3.3 Sécurité des jetons : le blocker critique

C'est le point le plus grave de l'audit.

Le schéma Prisma déclare les jetons OAuth comme de simples chaînes :

```prisma
model Integration {
  ...
  token          String
  tokenExpiration DateTime?
  refreshToken   String?
  ...
}
```

Référence : [`schema.prisma`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/libraries/nestjs-libraries/src/database/prisma/schema.prisma#L368).

Le repository écrit directement les valeurs reçues du provider :

```ts
create: {
  ...
  token,
  ...
  refreshToken,
  ...
}
update: {
  ...
  token,
  ...
  ...(refreshToken ? { refreshToken } : {}),
}
```

Référence : [`integration.repository.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/libraries/nestjs-libraries/src/database/prisma/integrations/integration.repository.ts#L352).

Aucun chiffrement applicatif n'est appliqué à ces champs. Le helper `fixedEncryption` existe, mais il est utilisé pour d'autres secrets (clés API, credentials tiers, codes OAuth), pas pour les access/refresh tokens des intégrations sociales. Et ce helper n'est lui-même pas au niveau attendu :

```ts
const algorithm = 'aes-256-cbc';
...
const { key, iv } = EVP_BytesToKey(pass, null, keyLength * 8, ivLength, 'md5');
...
crypto.createCipheriv(algorithm, key, iv);
```

Référence : [`auth.service.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/libraries/helpers/src/auth/auth.service.ts#L6).

Caractéristiques de ce chiffrement :

- **AES-256-CBC** : pas d'authentification d'intégrité (pas de GCM, pas de HMAC) ; un ciphertext modifié peut produire un plaintext altéré ;
- **IV fixe dérivé de la clé** : chiffrement déterministe, donc deux jetons identiques produisent le même ciphertext, et une même valeur peut être corrélée entre lignes ;
- **clé dérivée de `JWT_SECRET` avec EVP_BytesToKey/MD5** : réutilisation de la clé de signature JWT pour le chiffrement, dérivation legacy, pas de séparation des clés ;
- **pas de key version, pas d'AAD, pas de rotation** : impossible de re-chiffrer proprement ou de lier le ciphertext à l'organisation/la connexion ;
- **pas de KMS** : le secret maître est une variable d'environnement unique.

**Impact concret :** un dump PostgreSQL, une sauvegarde, un réplica de lecture, un accès support ou une erreur de log exposant la table `Integration` permet de récupérer les access tokens et refresh tokens de tous les comptes connectés. Les refresh tokens Google/LinkedIn sont durables ; le vol peut survivre à une rotation de mot de passe et permettre de publier au nom de la victime. C'est exactement le scénario « anti-fuite » que Presence veut éviter.

**Nuance importante :** Postiz Cloud affirme dans son README ne pas stocker ni proxifier les clés API des utilisateurs. Cela ne s'applique pas à l'édition self-hosted auditée : le code que nous déploierions stocke bien les jetons en base.

**Verdict sécurité des jetons :** non conforme à R2. Corriger ce point dans Postiz impose de modifier le modèle, les repositories et les workflows de refresh — donc de créer un fork AGPL.

### 3.4 OAuth, publication et statistiques

**Points forts :**

- 36 providers, avec des implémentations spécifiques (LinkedIn Pages, Google/YouTube, Meta, X, TikTok, etc.) ;
- workflows de rafraîchissement de jetons et de reprise ;
- API publique pour créer des posts, lister les intégrations, récupérer des analytics ;
- UI complète de calendrier, médias, analytics ;
- gestion des médias et du stockage.

**Flux OAuth public :** `GET /public/v1/social/:integration` génère une URL d'autorisation et stocke en Redis l'organisation, le `codeVerifier` et l'état pendant une heure. Le callback est hébergé par Postiz, pas par Presence.

Référence : [`public.integrations.controller.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/apps/backend/src/public-api/routes/v1/public.integrations.controller.ts#L344).

**Webhooks sortants :** Postiz envoie un POST JSON après publication, mais :

- pas de signature HMAC, pas de secret partagé, pas d'en-tête d'événement ;
- pas de retry, pas de file d'attente, pas d'idempotence ;
- les erreurs sont avalées (`catch { /**empty**/ }`) ;
- le webhook est « best effort » et ne doit pas être utilisé comme source de vérité.

Référence : [`post.activity.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/apps/orchestrator/src/activities/post.activity.ts#L509).

Conséquence : Presence ne peut pas s'appuyer sur ces webhooks pour facturer, auditer ou déclencher un workflow critique. Il faudrait soit polling l'API, soit un proxy de confiance, soit modifier Postiz.

**Gate d'approbation :** Postiz gère des brouillons et une planification, mais l'audit n'a pas trouvé un mécanisme équivalent au « no self-approval » de Pendpost, avec un acteur distinct et un échec fermé. Il ne faut pas confondre « statut draft » et « gate d'approbation humaine vérifié ».

### 3.5 Intégration avec Django/React sans dupliquer les utilisateurs

Deux scénarios sont possibles.

#### Scénario A — Postiz comme service externe, appelé par l'API

- Presence mappe chaque `Organization` à une organisation Postiz ;
- Presence stocke la clé API Postiz de cette organisation dans son propre coffre ;
- Presence appelle `/public/v1/posts`, `/public/v1/integrations`, `/public/v1/analytics/...` ;
- l'utilisateur est redirigé vers Postiz pour le consentement OAuth, puis revient dans Presence.

**Avantages :** pas de fork, mise en route rapide, couverture fonctionnelle immédiate.

**Inconvénients :**

- **duplication des utilisateurs et des organisations** : Postiz a son propre `User` et son propre `Organization` ; l'OIDC générique crée un compte local. Il n'y a pas de SCIM ni de synchronisation de déprovisionnement ;
- **mapping des rôles non natif** : les rôles Presence (`owner/admin/analyst/viewer`) ne correspondent pas aux trois rôles Postiz ;
- **cycle de vie des comptes** : un utilisateur retiré de Presence peut conserver un compte Postiz actif ; il faut un job de déprovisionnement ;
- **callback OAuth chez Postiz** : Presence ne contrôle pas le stockage des jetons, qui reste en clair ;
- **webhooks non fiables** : polling ou proxy nécessaire ;
- **surface d'attaque supplémentaire** : une deuxième application exposée, avec sa propre authentification, ses propres sessions et ses propres sauvegardes.

Même en supposant que l'on accepte l'AGPL, ce scénario ne répond pas à « sans dupliquer la base utilisateurs ». Il déplace la duplication plutôt qu'il ne la supprime.

#### Scénario B — fork et intégration dans Presence

- on modifie Postiz pour chiffrer les jetons, signer les webhooks, mapper les organisations ;
- on l'intègre comme sous-système, éventuellement via un reverse proxy et une UI iframe.

**Avantages :** contrôle total du comportement.

**Inconvénients :**

- **AGPL** : le fork modifié et exposé en réseau doit offrir sa source correspondante ; le risque de contamination de l'œuvre combinée doit être arbitré par un avocat ;
- **double stack** : NestJS/Next.js/Temporal/Prisma à maintenir en plus de Django/React/Celery ;
- **migrations et upgrades** : chaque release Postiz peut casser le fork ;
- **UI** : l'iframe complique le SSO, le CSP, les cookies `SameSite`, et l'expérience produit ;
- **coût de maintenance** : le fork devient un produit interne à part entière.

**Verdict intégration :** possible techniquement, mais coûteuse et risquée. Le scénario A est le seul raisonnable si l'on veut utiliser Postiz sans fork ; il reste disqualifié par le stockage des jetons et l'AGPL.

### 3.6 Licence et maturité

**Licence :** la licence racine est AGPL-3.0. La section 13 dispose que si vous modifiez le programme, votre version modifiée doit offrir à tous les utilisateurs interagissant avec elle par réseau la possibilité d'obtenir la source correspondante, gratuitement, depuis un serveur réseau. Référence : [`LICENSE`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/LICENSE#L540).

Conséquences pour Presence :

- si Presence **modifie** Postiz pour corriger le chiffrement des jetons ou les webhooks, elle doit publier la source correspondante de sa version — pas seulement le module modifié, mais l'œuvre couverte par l'AGPL et, selon l'analyse, potentiellement l'œuvre combinée ;
- si Presence **appelle une instance Postiz non modifiée** via l'API, la qualification d'œuvre dérivée est débattue et l'obligation de source de la section 13 ne se déclenche pas nécessairement, car elle vise le programme modifié ; Presence doit néanmoins vérifier qu'elle ne crée pas une œuvre combinée et que l'exploitation de l'instance reste conforme ;
- l'incohérence `AGPL-3.0` (racine) / `ISC` (`apps/backend`, `apps/frontend`) doit être clarifiée par le mainteneur avant tout usage commercial ;
- l'option « Postiz Cloud » est un service commercial, pas une intégration open source : elle déplace le problème vers un vendor lock-in et ne permet pas d'auto-héberger.

**Maturité :** Postiz est un projet très visible et activement maintenu (v2.25.2 au 23 octobre 2026, releases fréquentes). La couverture fonctionnelle est réelle. En revanche :

- la stack est lourde : application, PostgreSQL, Redis, Temporal, PostgreSQL Temporal, Elasticsearch, Temporal UI ;
- aucune suite de tests unitaires n'est visible dans le snapshot ; la CI principale est un build, avec CodeQL ;
- 222 issues ouvertes et un rythme de release soutenu impliquent une veille et des upgrades réguliers ;
- les APIs des 36 fournisseurs changent en permanence : c'est Postiz qui absorbe cette complexité, mais c'est aussi une dépendance externe difficile à déboguer.

**Verdict licence/maturité :** maturité produit élevée, mais **licence incompatible avec un SaaS propriétaire qui veut modifier le code**, et **sécurité des jetons insuffisante**. Postiz reste une excellente **référence fonctionnelle** et une source d'idées, pas une dépendance de production.

### 3.7 Synthèse Postiz

| Critère | Note | Commentaire |
|---|---|---|
| Multi-tenant | 6/10 | Org-scoping applicatif correct, mais pas de RLS, pas de base par tenant, rôles moins granulaires. |
| Sécurité des jetons | 2/10 | Access/refresh tokens en clair ; CBC déterministe pour les autres secrets ; pas de KMS. |
| Intégration Django/React | 6/10 | API publique utile, mais identités dupliquées, callback externe, webhooks non fiables. |
| Licence | 2/10 | AGPL-3.0 ; fork obligatoire pour corriger les jetons, avec obligation de source. |
| Maintenance | 5/10 | Stack lourde, double runtime, upgrades fréquents. |
| Couverture fonctionnelle | 9/10 | 36 providers, analytics, calendrier, médias. |

---

## 4. Audit de Pendpost

### 4.1 Fiche technique

| Élément | Constat |
|---|---|
| Version auditée | `v2.7.0`, commit `42ac77b`, release du 14 octobre 2026 |
| Licence | **MIT** |
| Runtime | Node.js >= 20, un seul processus `server.mjs`, zéro dépendance runtime |
| Interfaces | REST `/api`, MCP `/mcp`, dashboard React, moteurs de publication dans `scripts/` |
| Données | Fichiers JSON locaux (`data/plans`, `state.json`, `config.json`), credentials dans `.env` |
| Plateformes | Une quinzaine de moteurs de publication ; Instagram, Facebook, LinkedIn, YouTube, X, Telegram, Discord, Mastodon, Nostr, WordPress, Ghost, etc. |
| Communauté | ~14 étoiles, 5 forks, **2 comptes contributeurs**, projet « early » maintenu à temps partiel |
| Tests | 392 fichiers de test, CI fournie |

Pendpost est l'opposé de Postiz : peu de code, zéro dépendance, local-first, mais une architecture volontairement mono-utilisateur. Son originalité n'est pas le scheduling, c'est **le gate d'approbation humaine** et les **garde-fous anti-bannissement**.

### 4.2 Multi-tenant : des « clients », pas des tenants

Pendpost connaît la notion de « client » :

- chaque client possède un sous-arbre `data/clients/<id>/` avec son `.env`, son `config.json`, son `state.json`, ses plans et ses médias ;
- un registre `data/clients.json` stocke le client actif ;
- les actions de création, suppression, archivage et changement de client actif sont **operator-only** et ne sont pas exposées aux agents MCP.

Références : [`multi-client.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/multi-client.mjs#L1), [`clients.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/clients.mjs#L1).

Mais ce n'est **pas** du multi-tenant au sens SaaS :

- un seul opérateur, un seul processus, un seul token bearer optionnel ;
- pas de table `User`, pas de `Membership`, pas de rôles, pas de séparation par organisation ;
- le client actif est un état global du processus ; le porteur du token peut basculer entre tous les clients ;
- les « clients » sont des dossiers sur le disque, pas des frontières d'autorisation ;
- le serveur est loopback par défaut ; si on le bind sur une interface publique, un unique `PENDPOST_AUTH_TOKEN` protège toutes les routes (sauf `/api/health`).

Références : [`server.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/server.mjs#L53), [`.env.example`](https://github.com/pendpost/pendpost/blob/v2.7.0/.env.example#L15).

**Conséquence :** pour servir N organisations Presence, il faudrait lancer N instances Pendpost, chacune avec son port, son volume, son `.env`, ses sauvegardes et ses upgrades. C'est opérationnellement linéaire, sans admin central, sans SSO, sans RBAC, sans audit consolidé. Ce n'est pas une architecture SaaS.

### 4.3 Sécurité des jetons : `.env` en clair

Pendpost assume son choix local-first : les credentials de plateformes vivent dans `.env`, qui est gitignoré. Le code `accounts.mjs` précise que les **valeurs** des tokens ne sortent pas de l'API (seuls des drapeaux de présence et les 4 derniers caractères sont exposés), mais cela ne change rien au stockage au repos : le fichier `.env` est en clair sur le disque.

Références : [`README.md`](https://github.com/pendpost/pendpost/blob/v2.7.0/README.md#L162), [`accounts.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/accounts.mjs#L1), [`.env.example`](https://github.com/pendpost/pendpost/blob/v2.7.0/.env.example#L1).

Points à noter :

- **pas de chiffrement applicatif local** : ni AES-GCM, ni enveloppe, ni KMS ;
- **pas de base de données** : les secrets sont des fichiers, donc les sauvegardes, snapshots de volume et copies de migration sont autant de copies potentielles ;
- **le cloud vault optionnel** (service 24/7 de Pendpost) stocke des jetons chiffrés, mais il est **hors du dépôt open source**, payant, et ne couvre pas l'auto-hébergement local ;
- **OAuth par CLI** : les cérémonies LinkedIn/YouTube écrivent dans `.env` via des callbacks locaux (`127.0.0.1`), pas via un callback web multi-tenant ;
- **pas de rotation de clé** ni de révocation centralisée : la révocation se fait chez le provider ou en supprimant le token du fichier.

**Verdict sécurité des jetons :** non conforme à R2 pour un SaaS. Le modèle est cohérent pour un outil local mono-utilisateur, pas pour des comptes clients hébergés.

### 4.4 Publication et gate d'approbation : la meilleure idée à reprendre

C'est la partie où Pendpost est excellent, et où Presence doit s'inspirer **conceptuellement** :

- un post créé est toujours `draft` ;
- un post sans champ d'approbation est traité comme `draft` et **ne sera pas publié** (fail-closed) ;
- seuls `approve_post` / `reject_post` peuvent changer l'état ;
- **no self-approval** : l'acteur qui a créé le post ne peut jamais l'approuver ; seul l'acteur `owner` est exempté comme autorité d'approbation ;
- un agent ne peut pas approuver son propre brouillon ;
- le hash du contenu approuvé est conservé ; une modification après approbation déclenche `editedSinceApproval` et exige une nouvelle approbation ;
- un circuit breaker Meta 368 met la voie en pause et ne reprend pas automatiquement ;
- un cadence cap et un kill switch de lane limitent les rafales.

Références : [`writes.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/writes.mjs#L8), [`writes.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/writes.mjs#L1110), [`SECURITY.md`](https://github.com/pendpost/pendpost/blob/v2.7.0/SECURITY.md#L17).

**À reprendre dans Presence :**

- état `draft → pending_approval → approved → publishing → published/failed` ;
- approbation par un acteur distinct, jamais par le créateur agent ;
- refus de publication si le contenu a changé depuis l'approbation (hash) ;
- circuit breaker par provider/connexion en cas d'erreur de type « action block » ou de quota ;
- journal d'audit avec acteur, timestamp, contenu hashé, résultat.

**À ne pas reprendre :** le stockage local, le mono-opérateur, le token bearer unique, les fichiers JSON comme source de vérité.

### 4.5 Intégration avec Django/React

Pendpost expose un REST `/api` et un serveur MCP. On pourrait :

- lancer une instance par organisation Presence ;
- appeler son API depuis Django pour créer/approuver/publier ;
- proxyfier son dashboard ou construire une UI React dédiée.

Mais :

- **pas de modèle utilisateurs/organisations** : l'API ne sait pas qui agit, seulement un acteur textuel (`owner`, `agent:claude`) ;
- **pas de RBAC** : le token bearer donne accès à tout ;
- **pas de base de données** : pas de jointures, pas de transactions, pas de reporting SQL, pas de facturation ;
- **pas de webhooks signés dans le cœur MIT** : l'API et les fichiers d'état ne remplacent pas une intégration événementielle fiable (le récepteur cloud est hors dépôt) ;
- **pas de provisioning** : créer un tenant = créer un dossier et un `.env`, pas une opération applicative ;
- **double runtime** : Node + Python, avec deux cycles de vie, deux systèmes de logs, deux stratégies de backup.

**Licence MIT :** elle autorise la réutilisation, la modification et la redistribution propriétaire. On pourrait porter les moteurs de publication en Python ou les exécuter en sidecar. Mais le coût de portage et de maintenance est élevé, et le code est optimisé pour un workspace local, pas pour une file Celery multi-tenant.

**Verdict intégration :** excellent pour un produit « single-tenant / on-premise » ou un mode « agent local » ; inadapté au SaaS multi-tenant Presence.

### 4.6 Licence et maturité

**Licence :** MIT, compatible avec un SaaS commercial. C'est son avantage majeur sur Postiz.

**Maturité :**

- ~14 étoiles, 5 forks, 2 comptes contributeurs ;
- projet explicitement « early », maintenu à temps partiel, sans LTS ;
- 392 fichiers de test et une CI sérieuse : la qualité interne est meilleure que sa popularité ne le suggère ;
- mais le bus factor est faible, et les APIs des plateformes évoluent vite ;
- pas de support commercial, pas de roadmap enterprise, pas de garantie de sécurité.

**Verdict licence/maturité :** licence compatible, mais **risque de maintenance et de continuité élevé**. On peut s'inspirer du design, pas dépendre du runtime.

### 4.7 Synthèse Pendpost

| Critère | Note | Commentaire |
|---|---|---|
| Multi-tenant | 2/10 | Mono-opérateur, clients = dossiers, pas de RBAC. |
| Sécurité des jetons | 2/10 | `.env` en clair ; vault cloud fermé et payant. |
| Intégration Django/React | 3/10 | API/MCP utilisables, mais sidecar par tenant, pas de modèle d'identité. |
| Licence | 10/10 | MIT, réutilisation propriétaire possible. |
| Maintenance | 3/10 | Early, 2 contributeurs, pas de LTS. |
| Gate d'approbation | 9/10 | Le meilleur design de la catégorie ; à reprendre conceptuellement. |

---

## 5. Développement sur mesure

### 5.1 Principe

Créer un **bounded context** `social_connectors` dans le backend Django existant, avec :

- un registre de connexions OAuth par organisation ;
- un coffre de jetons en enveloppe AES-256-GCM ;
- des adaptateurs fournisseurs (LinkedIn, Google, puis X/Meta) ;
- un workflow de publication avec gate d'approbation ;
- une collecte de statistiques normalisée ;
- une UI React dans les réglages de l'organisation.

Aucun nouveau service obligatoire : PostgreSQL, Redis, Celery et DRF existent déjà. Un KMS cloud est optionnel ; à défaut, une clé KEK injectée par secret Docker/Vault suffit pour démarrer.

### 5.2 Modèle de données proposé

```text
Organization (existant)
  └── SocialConnection
        ├── provider, external_account_id, display_name, scopes
        ├── status (connected | reauth_required | revoked | error)
        ├── token_expires_at, last_refreshed_at
        ├── created_by (User), created_at, revoked_at
        └── SocialCredential (1:1, accès restreint)
              ├── access_token_ciphertext, access_nonce
              ├── refresh_token_ciphertext, refresh_nonce
              ├── wrapped_dek, dek_nonce, key_version
              └── updated_at

SocialPost
  ├── organization, created_by, title, content, media
  ├── state (draft | pending_approval | approved | publishing | published | failed | rejected)
  ├── content_hash, approved_by, approved_at
  └── idempotency_key

SocialPostTarget
  ├── post, connection, provider_post_id, status, error_code
  └── published_at, permalink

SocialMetric
  ├── connection, metric_date, metric_key, value
  └── unique (connection, metric_date, metric_key)

SocialAuditEvent
  ├── organization, actor, action, connection/post, ip, user_agent
  └── metadata JSONB (sans jeton), created_at
```

Règles structurantes :

- `SocialConnection` est **toujours** filtré par `organization` ; l'UUID seul ne donne jamais accès ;
- `SocialCredential` n'est jamais sérialisé, ni exposé dans l'admin, ni indexé dans Elasticsearch/Sentry ;
- `external_account_id` est l'ID stable chez le provider (ex. `urn:li:organization:123`, `accounts/456`) ;
- contrainte d'unicité `(organization, provider, external_account_id)` pour éviter les doublons ;
- `SocialProfile` existant devient un objet de lecture rattaché à `organization` et, optionnellement, à `SocialConnection` ;
- `SocialMention` reçoit aussi `organization` pour supprimer le filtrage par `website__owner`.

### 5.3 Coffre de jetons : enveloppe AES-256-GCM

Le principe est simple : **une clé maîtresse (KEK) ne chiffre jamais directement les jetons**. Elle chiffre des clés de données (DEK) par connexion ; chaque DEK chiffre les jetons de cette connexion.

```text
KEK (32 octets, KMS ou secret Docker)
  └── wrap(DEK_connexion) → wrapped_dek stocké en base

DEK_connexion (32 octets, générée aléatoirement)
  ├── AESGCM(DEK).encrypt(nonce, access_token, aad)
  └── AESGCM(DEK).encrypt(nonce, refresh_token, aad)

AAD = "v1|org:<uuid>|connection:<uuid>|provider:<slug>|field:access"
```

Propriétés :

- **confidentialité et intégrité** : GCM authentifie le ciphertext ; toute altération échoue ;
- **isolation cryptographique** : un ciphertext déplacé d'une connexion à une autre échoue grâce à l'AAD ;
- **rotation** : on peut re-chiffrer les DEK avec une nouvelle KEK sans toucher aux jetons ;
- **compromission limitée** : si un DEK fuit, seule une connexion est exposée ;
- **clé hors base** : un dump SQL ne contient que des ciphertexts et des DEK emballés.

Implémentation Python avec `cryptography` (déjà présent en version 43.x) :

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def wrap_dek(kek: bytes, dek: bytes, aad: bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    return nonce, AESGCM(kek).encrypt(nonce, dek, aad)

def encrypt_token(dek: bytes, token: str, aad: bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    return nonce, AESGCM(dek).encrypt(nonce, token.encode("utf-8"), aad)

def decrypt_token(dek: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> str:
    return AESGCM(dek).decrypt(nonce, ciphertext, aad).decode("utf-8")
```

**Gestion des clés :**

- **production cloud** : AWS KMS, GCP KMS ou Vault Transit ; `GenerateDataKey` fournit un DEK en clair + un DEK chiffré ; on ne persiste que le DEK chiffré ;
- **auto-hébergement Docker** : `SOCIAL_TOKEN_KEK` injectée via Docker secret ou fichier monté, jamais dans `.env` versionné, jamais dans l'image ;
- **séparation** : ne jamais réutiliser `DJANGO_SECRET_KEY` ou `JWT_SECRET` comme KEK ;
- **rotation** : `key_version` sur chaque credential ; job de rewrap des DEK ; conserver les anciennes versions le temps de la migration ;
- **démarrage fail-closed** : si la KEK est absente ou invalide, le service de connecteurs refuse de démarrer ; pas de clé de développement par défaut en production ;
- **destruction** : zéroïser les buffers de DEK en mémoire quand c'est possible ; ne jamais logger les jetons, même en debug.

**Ce qu'il ne faut pas faire :**

- AES-CBC avec IV fixe, comme Postiz ;
- chiffrement déterministe ;
- clé dérivée d'un secret JWT ;
- token en clair dans un champ `TextField` « parce que la base est chiffrée au disque » ;
- token dans un JWT, un cookie, un localStorage ou une URL de callback.

### 5.4 Flux OAuth

```text
React (Settings > Intégrations)
  │  POST /api/organizations/{org}/social/connections/{provider}/authorize/
  ▼
Django
  ├── vérifie le rôle (owner/admin)
  ├── génère state (32 octets) + code_verifier PKCE
  ├── stocke hash(state) → {org, user, provider, redirect_uri, verifier} dans Redis (TTL 10 min)
  └── renvoie { authorization_url }
  ▼
Provider (Google / LinkedIn)
  │  consentement utilisateur
  ▼
GET /api/social/oauth/{provider}/callback?code=...&state=...
  ├── GETDEL state (usage unique)
  ├── vérifie, via le user_id scellé dans l'état, que l'utilisateur existe et est toujours membre de l'org
  ├── échange code + client_secret + code_verifier côté serveur
  ├── récupère le compte externe (ID stable, nom, scopes)
  ├── upsert SocialConnection + SocialCredential (chiffrement)
  ├── audite l'événement
  └── redirige vers /settings/integrations?connected=linkedin (sans jeton)
```

Règles :

- **state** : aléatoire, hashé en Redis, à usage unique, lié à l'utilisateur, l'organisation, le provider et l'URI de redirection ;
- **PKCE S256** : obligatoire même pour les clients confidentiels, en défense en profondeur ;
- **redirect URI** : liste blanche exacte par provider et par environnement ; jamais de wildcard ;
- **pas d'`org_id` dans le callback** : l'organisation vient de l'état, pas d'un paramètre manipulable ;
- **pas de jeton dans l'URL** : le callback ne renvoie qu'un code d'autorisation, échangé côté serveur ;
- **scopes minimaux** : demander le strict nécessaire, avec réautorisation incrémentale si besoin ;
- **refresh token** : pour Google, `access_type=offline` + `prompt=consent` ; pour LinkedIn, conserver le refresh token et les scopes associés ;
- **erreurs** : ne jamais renvoyer le code d'erreur brut du provider au frontend ; journaliser un identifiant corrélé, pas le token.

### 5.5 Publication, approbation et idempotence

**Machine à états :**

```text
draft ──submit──> pending_approval ──approve──> approved ──worker──> publishing
  ▲                    │                           │                    │
  └──── reject ────────┘                           └──── fail ────────> failed
                                                          │
                                                          └── retry ──> publishing
```

Règles :

- un post créé par un agent est toujours `draft` ;
- seul un `owner` ou `admin` peut approuver ; un `analyst` peut créer et soumettre ;
- **no self-approval** : le créateur ne peut pas approuver son propre post ; un agent ne peut jamais approuver ;
- `content_hash` calculé à l'approbation ; toute modification du contenu, des médias ou des cibles remet l'état à `draft` ;
- la publication vérifie l'état `approved` et le hash avant d'appeler le provider ;
- **idempotency_key** unique par `(post, connection)` ; si le worker réessaye, il ne duplique pas ;
- **timeout réseau** : ne pas retenter aveuglément ; vérifier chez le provider si le post existe (par `provider_post_id` ou par recherche) avant de recréer ;
- **retries** : 5 tentatives, backoff exponentiel avec jitter, `Retry-After` respecté pour 429 ;
- **401** : tenter un refresh une seule fois ; si `invalid_grant`, marquer `reauth_required` et notifier ;
- **5xx** : retenter ; **4xx métier** : échec permanent, pas de boucle ;
- **rate limit** : token bucket Redis par connexion/provider, plus un quota global par organisation ;
- **circuit breaker** : par provider/connexion, seuil d'erreurs, pause manuelle et reprise explicite ;
- **audit** : chaque transition écrit un `SocialAuditEvent` immuable.

**Webhooks :**

- entrants provider : vérifier la signature (HMAC, `X-Hub-Signature-256`, etc.), le timestamp et l'ID d'événement ; rejeter les rejeux ;
- sortants Presence → client : signer avec HMAC-SHA256 (`X-Presence-Signature`, timestamp, event ID), retry avec backoff, idempotence côté consommateur ;
- ne jamais utiliser un webhook non signé comme source de vérité.

### 5.6 Statistiques

- collecte Celery planifiée (quotidienne) par connexion ;
- normalisation en `SocialMetric` : `followers`, `impressions`, `likes`, `comments`, `shares`, `clicks`, `engagement_rate` ;
- upsert idempotent sur `(connection, metric_date, metric_key)` ;
- respect des quotas provider et du backoff ;
- conservation configurable (par défaut 24 mois) ;
- aucun jeton dans les logs ou les payloads analytics ;
- les erreurs de collecte ne doivent pas casser la publication : files séparées, priorités séparées.

### 5.7 Intégration dans le code existant

**Backend :**

- nouveau module `social_connectors/` ou extension de `social/` avec `models.py`, `services/oauth.py`, `services/vault.py`, `services/publishers/`, `tasks.py`, `views.py`, `urls.py`, `tests/` ;
- routes DRF sous `/api/organizations/<uuid:org_id>/social/...` ;
- réutilisation de `organizations.access.role_for_organization` et des ensembles `READ_ROLES` / `WRITE_ROLES` / `DELETE_ROLES` ;
- ajout de `organization` à `SocialProfile` et `SocialMention`, backfill depuis `website.organization` ou l'organisation personnelle du propriétaire ;
- remplacement des filtres `website__owner=request.user` par les helpers d'organisation ;
- conservation temporaire des jetons globaux `META_GRAPH_ACCESS_TOKEN` / `X_BEARER_TOKEN` comme fallback de lecture, sans les exposer aux nouveaux connecteurs.

**Frontend React :**

- onglet « Intégrations » dans les réglages de l'organisation ;
- bouton « Connecter LinkedIn / Google » qui ouvre une popup sur l'URL d'autorisation ;
- écoute du message de retour ou polling du statut de connexion ;
- affichage du compte, des scopes, de l'expiration et de l'état `reauth_required` ;
- bouton « Déconnecter » avec confirmation et révocation ;
- jamais de jeton dans le state React, le localStorage ou le DOM.

**API proposée :**

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/organizations/{org}/social/connections/` | Lister les connexions (métadonnées uniquement) |
| `POST` | `/api/organizations/{org}/social/connections/{provider}/authorize/` | Créer l'URL OAuth |
| `GET` | `/api/social/oauth/{provider}/callback/` | Callback public, validé par state |
| `DELETE` | `/api/organizations/{org}/social/connections/{id}/` | Révoquer et supprimer |
| `POST` | `/api/organizations/{org}/social/posts/` | Créer un brouillon |
| `POST` | `/api/organizations/{org}/social/posts/{id}/submit/` | Soumettre à approbation |
| `POST` | `/api/organizations/{org}/social/posts/{id}/approve/` | Approuver (owner/admin) |
| `GET` | `/api/organizations/{org}/social/analytics/` | Lire les métriques agrégées |

### 5.8 Matrice des rôles

| Action | Owner | Admin | Analyst | Viewer | Agent |
|---|---:|---:|---:|---:|---:|
| Voir les connexions (métadonnées) | ✅ | ✅ | ✅ | ✅ | ❌ |
| Connecter / déconnecter | ✅ | ✅ | ❌ | ❌ | ❌ |
| Créer un brouillon | ✅ | ✅ | ✅ | ❌ | ✅ |
| Soumettre à approbation | ✅ | ✅ | ✅ | ❌ | ✅ |
| Approuver / rejeter | ✅ | ✅ | ❌ | ❌ | ❌ |
| Publier | ✅ | ✅ | ❌ | ❌ | ❌ |
| Voir les analytics | ✅ | ✅ | ✅ | ✅ | ❌ |
| Voir les jetons | ❌ | ❌ | ❌ | ❌ | ❌ |

**Personne ne voit les jetons**, pas même l'owner. Seul le worker de publication les déchiffre, dans son processus, pour l'appel provider.

### 5.9 Contrôles de sécurité et tests

| Contrôle | Implémentation | Test |
|---|---|---|
| Chiffrement au repos | AES-256-GCM en enveloppe | Round-trip, mauvais AAD, ciphertext altéré |
| Clé hors base | KMS/secret Docker | Démarrage sans clé = refus |
| Rotation | `key_version` + rewrap | Ancienne et nouvelle clé coexistent |
| State OAuth | Hash Redis, TTL 10 min, GETDEL | Rejeu, état expiré, état d'une autre org |
| PKCE | S256 | Vérifier le `code_verifier` |
| Redirect URI | Allowlist exacte | URI non listée rejetée |
| Isolation | Filtre org systématique | Org B → 404 sur connexion de org A |
| RBAC | Helpers `access.py` | Chaque rôle, chaque action |
| Logs | Redaction tokens | Scanner les logs de test |
| Refresh | Lock par connexion | Deux workers simultanés |
| Publication | Idempotence | Double exécution = un seul post |
| Webhooks | HMAC + timestamp | Signature invalide/rejeu rejetés |
| Suppression | Révocation + cascade | Token révoqué, données effacées |

**Tests multi-tenant prioritaires :**

1. un utilisateur de l'organisation B ne peut pas lister, lire, supprimer ou publier sur une connexion de A, même avec l'UUID exact ;
2. un `analyst` ne peut pas connecter ni approuver ;
3. un `viewer` ne peut pas créer de brouillon ;
4. un agent ne peut pas approuver son propre brouillon ;
5. un post modifié après approbation repasse en brouillon ;
6. une connexion `reauth_required` ne peut pas publier ;
7. un jeton révoqué est rejeté et la connexion passe en `revoked` ;
8. aucune réponse API ne contient `access_token`, `refresh_token` ou `wrapped_dek`.

### 5.10 Chiffrage et coût

| Poste | Estimation |
|---|---|
| Modèles, coffre, audit, RBAC, tests | 2 à 3 semaines |
| OAuth + 2 providers (LinkedIn, Google) | 1,5 à 2 semaines |
| Publication, approbation, retries, idempotence | 1,5 à 2 semaines |
| Analytics + UI React | 1,5 à 2 semaines |
| Revue sécurité + tests | 1 semaine |
| **Total MVP 2 providers** | **6 à 9 semaines-ingénieur** |
| **Total 4 providers** | **9 à 12 semaines** |
| Maintenance courante | 0,15 à 0,25 ETP |
| Infrastructure supplémentaire | ~0 € (Postgres/Redis/Celery existants) ; KMS cloud 50–200 €/mois si utilisé |

Hypothèses : un développeur senior backend, 0,5 développeur frontend, accès aux comptes développeur Google/LinkedIn et aux environnements de test. Le chiffrage exclut l'App Review des plateformes et les délais de validation côté Google/Meta.

### 5.11 Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| APIs providers qui cassent | Élevée | Moyen | Adaptateurs isolés, tests de contrat, feature flags, surveillance |
| Compromission d'un jeton | Moyenne | Critique | Enveloppe, KMS, rotation, moindre privilège, audit |
| Fuite cross-tenant | Faible | Critique | Filtres org, tests, revue de code, RLS en phase 3 |
| Perte de la KEK | Faible | Critique | Sauvegarde KMS, procédure de break-glass, sinon reauth forcée |
| Course de refresh | Moyenne | Moyen | Verrou par connexion, mise à jour atomique |
| Double publication | Moyenne | Élevé | Clé d'idempotence, réconciliation provider |
| Rate limit / ban | Moyenne | Élevé | Backoff, quotas, circuit breaker, gate d'approbation |
| Dérive de scope | Moyenne | Moyen | Audit des scopes, reautorisation, documentation |
| Coût de maintenance | Moyenne | Moyen | Périmètre 2–4 providers, adaptateurs, tests |

---

## 6. Comparaison pondérée

Notation subjective, sur 10, pondérée selon l'importance pour Presence. Les poids reflètent les contraintes exprimées : sécurité et isolation d'abord, puis intégration, licence, maintenance, couverture.

| Critère | Poids | Postiz | Pendpost | Sur mesure |
|---|---:|---:|---:|---:|
| Isolation multi-tenant | 25 % | 6 | 2 | 9 |
| Sécurité des jetons | 25 % | 2 | 2 | 9 |
| Intégration Django/React | 15 % | 6 | 3 | 7 |
| Licence commerciale | 15 % | 2 | 10 | 10 |
| Maintenance / ops | 10 % | 5 | 3 | 8 |
| Couverture fonctionnelle | 10 % | 9 | 7 | 6 |
| **Score pondéré** | **100 %** | **4,6/10** | **3,95/10** | **8,45/10** |

**Lecture :**

- **Postiz** gagne sur la couverture, mais perd sur les deux critères les plus lourds : sécurité des jetons et licence ;
- **Pendpost** gagne sur la licence et le design d'approbation, mais perd sur l'isolation et le stockage des secrets ;
- **Sur mesure** gagne sur la sécurité, l'isolation et l'intégration, avec une couverture initiale volontairement limitée.

### 6.1 « Le plus rapide à déployer »

Il faut distinguer trois vitesses :

| Objectif | Postiz | Pendpost | Sur mesure |
|---|---|---|---|
| Démo fonctionnelle | **1 à 2 semaines** (déploiement + API) | 2 à 4 semaines (sidecar mono-tenant) | 4 à 6 semaines |
| Mise en production **conforme** | 8 à 12 semaines + validation AGPL + fork | 8+ semaines et toujours pas multi-tenant | **6 à 9 semaines** |
| Mise en production **sans dette de sécurité** | Impossible sans fork | Impossible sans réécriture | **Possible** |

Postiz est le plus rapide pour **montrer** des connecteurs. Le sur mesure est le plus rapide pour **livrer une version conforme** au modèle de sécurité et au multi-tenant de Presence. C'est ce que la Phase 2 doit optimiser.

### 6.2 « Le plus sûr »

Le sur mesure, à condition de respecter les contrôles de la section 5.9. Postiz et Pendpost stockent tous les deux les jetons en clair, à des degrés différents : base PostgreSQL pour l'un, `.env` pour l'autre. Aucun des deux ne peut être qualifié de « sûr » pour des comptes clients hébergés sans modification profonde.

### 6.3 « Le plus facile à maintenir »

Le sur mesure pour 2 à 4 providers : même langage, même ORM, même CI, mêmes logs, mêmes sauvegardes, mêmes astreintes. Postiz demande une double compétence Node/TypeScript et une stack Temporal/Redis/Postgres/Elasticsearch. Pendpost demande un processus par tenant et une gestion de fichiers `.env` par client.

---

## 7. Recommandation d'architecture

### 7.1 Décision

**Adopter le développement sur mesure d'un noyau de connecteurs OAuth dans Django, avec un coffre AES-256-GCM en enveloppe, et s'inspirer conceptuellement du gate d'approbation de Pendpost.**

Décision proposée, à formaliser en ADR :

- **Statut** : proposée ;
- **Contexte** : Phase 2, multi-tenant validé, besoins Google/LinkedIn, exigences anti-fuite ;
- **Décision** : construire `social_connectors` dans le backend existant ; ne pas déployer Postiz ni Pendpost comme dépendance runtime ;
- **Conséquences** : 6 à 9 semaines pour 2 providers ; pas de nouvelle stack ; sécurité et licence maîtrisées ; couverture fonctionnelle initiale limitée à 2–4 providers ;
- **Alternatives rejetées** : Postiz (tokens en clair + AGPL), Pendpost (mono-tenant + `.env`).

### 7.2 Ce qu'il faut reprendre de chaque projet

**De Postiz :**

- la liste des providers et les particularités OAuth par plateforme (LinkedIn Pages vs profil personnel, Google offline access, scopes) ;
- l'idée d'un adaptateur par provider avec `generateAuthUrl`, `exchangeCode`, `refresh`, `publish`, `fetchAnalytics` ;
- les workflows de refresh et de reprise ;
- la gestion des médias et des erreurs provider.

**À ne pas reprendre :** le code AGPL, le stockage des jetons, les webhooks non signés, la stack lourde. Si un extrait de code Postiz est copié, il doit être traité comme du code AGPL et validé par le conseil juridique. Une approche clean-room (spécification fonctionnelle, implémentation indépendante) est préférable.

**De Pendpost :**

- le gate d'approbation fail-closed ;
- la règle de non-auto-approbation ;
- le hash de contenu approuvé ;
- le circuit breaker par lane et le kill switch ;
- le journal d'audit avec acteur ;
- l'idée d'un « mode agent » qui ne peut que proposer, jamais approuver.

**À ne pas reprendre :** les fichiers JSON, le mono-opérateur, le token bearer global, les credentials `.env`.

### 7.3 Plan de mise en œuvre proposé

| Sprint | Durée | Contenu | Critère de sortie |
|---|---|---|---|
| 0 — Cadrage | 1 semaine | ADR, choix des 2 providers, choix KMS/secret, threat model, maquettes UI | Décision validée, périmètre gelé |
| 1 — Fondations | 2 semaines | Modèles, coffre, audit, RBAC, state OAuth, tests unitaires | Aucun jeton en clair, tests crypto et tenant au vert |
| 2 — Connexion | 2 semaines | LinkedIn + Google OAuth, refresh, UI de connexion, états d'erreur | Un compte de test connecté/déconnecté, reauth testé |
| 3 — Publication | 2 semaines | Posts, approbation, idempotence, retries, circuit breaker | Publication réelle sur compte de test, double exécution sans doublon |
| 4 — Analytics & durcissement | 1 à 2 semaines | Métriques, webhooks signés, revue sécurité, tests E2E | Rapport de sécurité, tests multi-tenant, go/no-go |

**Jalons go/no-go :**

- aucun `access_token`/`refresh_token` en clair dans PostgreSQL, les sauvegardes ou les logs ;
- tests cross-tenant au vert ;
- `state` rejoué = rejeté ;
- refresh concurrent = un seul refresh ;
- publication idempotente ;
- aucun code AGPL copié ;
- revue de sécurité indépendante.

### 7.4 Questions ouvertes

1. **Périmètre initial** : LinkedIn Pages + Google Business Profile, ou LinkedIn + YouTube ? Le choix change les scopes, l'App Review et les tests. Recommandation : LinkedIn Pages + Google Business Profile pour la présence locale ; YouTube si la vidéo est prioritaire.
2. **KMS** : cloud KMS (AWS/GCP) ou secret Docker/Vault pour le premier déploiement ? Recommandation : commencer par un secret Docker isolé, avec une interface `KeyProvider` permettant de basculer vers KMS sans migration.
3. **Approbation** : owner/admin seulement, ou admin + analyst ? Recommandation : owner/admin pour la publication, analyst pour la création/soumission.
4. **Rétention** : 24 mois de métriques, 12 mois d'audit, 30 jours de logs ? À valider avec les exigences RGPD et les contrats clients.
5. **LinkedIn** : Pages d'entreprise uniquement, ou profils personnels aussi ? Les profils personnels ajoutent des scopes et des contraintes de conformité.

### 7.5 Conclusion

Postiz est la meilleure **bibliothèque de fonctionnalités** et un bon accélérateur de démonstration, mais ce n'est pas une fondation acceptable pour un SaaS multi-tenant qui promet l'isolation et la sécurité des jetons. Pendpost est la meilleure **référence de workflow d'approbation**, mais ce n'est pas un backend SaaS.

Presence doit construire un noyau petit, propriétaire et vérifiable : un registre OAuth par organisation, un coffre AES-256-GCM en enveloppe, un gate d'approbation, des publications idempotentes et des webhooks signés. C'est l'option la plus sûre, la plus rapide à mettre en production conforme, et la plus facile à maintenir dans la stack existante.

---

## Annexe A — Preuves d'audit

### A.1 Postiz

| Constat | Preuve | Impact |
|---|---|---|
| Licence racine AGPL-3.0 | [`LICENSE`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/LICENSE#L1), [`README`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/README.md#L190) | Fork réseau = obligation de source |
| Clause réseau AGPL §13 | [`LICENSE`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/LICENSE#L540) | Offre de source aux utilisateurs réseau |
| Jetons OAuth en clair | [`schema.prisma`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/libraries/nestjs-libraries/src/database/prisma/schema.prisma#L377), [`integration.repository.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/libraries/nestjs-libraries/src/database/prisma/integrations/integration.repository.ts#L356) | Compromission de tous les comptes |
| Chiffrement CBC déterministe | [`auth.service.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/libraries/helpers/src/auth/auth.service.ts#L6) | Pas d'intégrité, IV fixe, clé JWT réutilisée |
| Isolation par `organizationId` | [`auth.middleware.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/apps/backend/src/services/auth/auth.middleware.ts#L95) | Applicative, pas de RLS |
| Rôles limités | [`schema.prisma`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/libraries/nestjs-libraries/src/database/prisma/schema.prisma#L1802) | 3 rôles, pas de viewer/analyst distincts |
| OIDC générique | [`oauth.provider.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/apps/backend/src/services/auth/providers/oauth.provider.ts#L39) | SSO possible, mais comptes locaux créés |
| Webhooks non signés | [`post.activity.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/apps/orchestrator/src/activities/post.activity.ts#L509) | Pas de source de vérité |
| API publique | [`public.integrations.controller.ts`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/apps/backend/src/public-api/routes/v1/public.integrations.controller.ts#L64) | Intégration possible, mais dépendance externe |
| Stack lourde | [`docker-compose.yaml`](https://github.com/gitroomhq/postiz-app/blob/v2.25.2/docker-compose.yaml#L2) | Postgres, Redis, Temporal, Elasticsearch |
| Incohérence de licence package | `apps/backend/package.json` déclare `ISC` | À clarifier avant usage commercial |

### A.2 Pendpost

| Constat | Preuve | Impact |
|---|---|---|
| Licence MIT | [`LICENSE`](https://github.com/pendpost/pendpost/blob/v2.7.0/LICENSE#L1) | Compatible SaaS propriétaire |
| Architecture locale | [`README`](https://github.com/pendpost/pendpost/blob/v2.7.0/README.md#L154) | Un processus Node, JSON, `.env` |
| Mono-opérateur | [`clients.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/clients.mjs#L1) | Pas de RBAC, pas de tenants |
| Clients = dossiers | [`multi-client.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/multi-client.mjs#L4) | Isolation par filesystem, pas par autorisation |
| Loopback + bearer optionnel | [`server.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/server.mjs#L53), [`.env.example`](https://github.com/pendpost/pendpost/blob/v2.7.0/.env.example#L15) | Un token pour toutes les routes |
| Tokens en `.env` | [`README`](https://github.com/pendpost/pendpost/blob/v2.7.0/README.md#L162), [`.env.example`](https://github.com/pendpost/pendpost/blob/v2.7.0/.env.example#L34) | Pas de chiffrement local |
| Gate d'approbation | [`writes.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/writes.mjs#L8), [`writes.mjs`](https://github.com/pendpost/pendpost/blob/v2.7.0/lib/writes.mjs#L1110) | Meilleur design à reprendre |
| Anti-bannissement | [`SECURITY.md`](https://github.com/pendpost/pendpost/blob/v2.7.0/SECURITY.md#L24) | Circuit breaker 368, pas d'auto-reprise |
| Projet early | [`README`](https://github.com/pendpost/pendpost/blob/v2.7.0/README.md#L188) | Risque de maintenance |

### A.3 Presence

| Constat | Preuve | Impact |
|---|---|---|
| Organisations et rôles | [`organizations/models.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/organizations/models.py#L17) | Base multi-tenant existante |
| Helpers d'accès | [`organizations/access.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/organizations/access.py#L11) | Réutilisation directe |
| `SocialProfile` non org-scopé | [`social/models.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/social/models.py#L11) | À migrer |
| Vues owner-only | [`social/views.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/social/views.py#L14) | À remplacer par les rôles org |
| Jetons globaux | [`config/settings/base.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/config/settings/base.py#L476) | Pas de connexion par tenant |
| `cryptography` disponible | [`requirements.txt`](../../SaaS_Web_Application_digitale_presenz_v2/backend/requirements.txt#L34) | AESGCM sans nouvelle dépendance |
| Infra Celery/Redis | [`docker-compose.yml`](../../docker-compose.yml#L23) | Pas de nouveau runtime |

---

## Annexe B — Séquence OAuth cible

```text
Utilisateur            React                 Django                  Redis                 Provider
    │                    │                      │                       │                       │
    │ clique Connecter   │                      │                       │                       │
    │───────────────────>│ POST authorize       │                       │                       │
    │                    │─────────────────────>│                       │                       │
    │                    │                      │ état + PKCE           │                       │
    │                    │                      │──────────────────────>│                       │
    │                    │                      │ { authorization_url } │                       │
    │                    │<─────────────────────│                       │                       │
    │<───────────────────│ ouvre la popup       │                       │                       │
    │─────────────────────────────────────────────────────────────────────────────────────────>│
    │                    │                      │                       │   consentement        │
    │<─────────────────────────────────────────────────────────────────────────────────────────│
    │                    │                      │ GET callback?code&state                       │
    │                    │                      │<──────────────────────────────────────────────│
    │                    │                      │ GETDEL state           │                       │
    │                    │                      │──────────────────────>│                       │
    │                    │                      │ échange code + PKCE   │                       │
    │                    │                      │──────────────────────────────────────────────>│
    │                    │                      │ access + refresh      │                       │
    │                    │                      │<──────────────────────────────────────────────│
    │                    │                      │ chiffre, upsert, audit │                       │
    │                    │                      │──────────────────────>│                       │
    │                    │                      │ redirect succès       │                       │
    │                    │<─────────────────────│                       │                       │
    │<───────────────────│ affiche l'état       │                       │                       │
```

---

## Annexe C — Modèle de menaces (extrait)

| Menace | Vecteur | Contre-mesure |
|---|---|---|
| Vol de jeton par dump SQL | Sauvegarde, réplica, accès support | AES-256-GCM en enveloppe, KEK hors base, AAD |
| Rejeu OAuth | Callback intercepté, state volé | State à usage unique, PKCE, TTL court, liaison user/org |
| Fuite cross-tenant | UUID deviné, filtre oublié | Filtre org systématique, tests, RLS phase 3 |
| CSRF sur callback | Requête forgée | State lié à la session, SameSite, vérification utilisateur |
| Open redirect | `redirect_uri` manipulée | Allowlist exacte, pas de wildcard |
| Double publication | Retry réseau | Idempotency key, réconciliation provider |
| Refresh concurrent | Deux workers | Verrou par connexion, `select_for_update` |
| Fuite dans les logs | Exception provider, debug | Redaction, structures de logs, tests |
| Compromission d'un DEK | Accès mémoire/process | Rotation, moindre privilège, isolation worker |
| Perte de KEK | Mauvaise configuration | Sauvegarde KMS, alerte, procédure de reauth |
| Abus de quota | Agent en boucle | Rate limit, circuit breaker, gate d'approbation |

---

## Annexe D — Sources

### Dépôts et documentation

- Postiz : <https://github.com/gitroomhq/postiz-app> (version `v2.25.2`)
- Postiz, licence : <https://github.com/gitroomhq/postiz-app/blob/v2.25.2/LICENSE>
- Postiz, README : <https://github.com/gitroomhq/postiz-app/blob/v2.25.2/README.md>
- Pendpost : <https://github.com/pendpost/pendpost> (version `v2.7.0`)
- Pendpost, licence : <https://github.com/pendpost/pendpost/blob/v2.7.0/LICENSE>
- Pendpost, sécurité : <https://github.com/pendpost/pendpost/blob/v2.7.0/SECURITY.md>
- Pendpost, documentation : <https://docs.pendpost.com>

### Fichiers Presence

- [`organizations/models.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/organizations/models.py)
- [`organizations/access.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/organizations/access.py)
- [`websites/models.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/websites/models.py)
- [`social/models.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/social/models.py)
- [`social/views.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/social/views.py)
- [`config/settings/base.py`](../../SaaS_Web_Application_digitale_presenz_v2/backend/config/settings/base.py)
- [`requirements.txt`](../../SaaS_Web_Application_digitale_presenz_v2/backend/requirements.txt)
- [`docker-compose.yml`](../../docker-compose.yml)
- [`docs/audits/PHASE_F_LIVE_VALIDATION_2026-10-24.md`](PHASE_F_LIVE_VALIDATION_2026-10-24.md)

---

## Annexe E — Glossaire

| Terme | Définition |
|---|---|
| **KEK** | Key Encryption Key : clé maîtresse qui chiffre les DEK, stockée hors base. |
| **DEK** | Data Encryption Key : clé aléatoire par connexion, chiffrée par la KEK. |
| **Enveloppe** | Schéma où la KEK chiffre des DEK, et les DEK chiffrent les données. |
| **AAD** | Additional Authenticated Data : données non chiffrées mais authentifiées par GCM (org, connexion, champ). |
| **PKCE** | Proof Key for Code Exchange : protection du flux OAuth contre l'interception du code. |
| **State** | Valeur aléatoire à usage unique qui lie le callback à la demande initiale. |
| **Idempotence** | Propriété qui garantit qu'une opération répétée ne produit pas de doublon. |
| **RLS** | Row-Level Security PostgreSQL : filtrage des lignes au niveau base. |
| **AGPL** | GNU Affero General Public License : copyleft fort, avec clause réseau. |
| **No self-approval** | Règle empêchant le créateur d'un contenu de l'approuver lui-même. |

---

*Fin du rapport. Aucun code source applicatif n'a été modifié pendant cette phase.*
