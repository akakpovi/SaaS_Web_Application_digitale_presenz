# Presence — Décision analytics et plan d'activation

**Date :** 2026-10-28
**Périmètre :** site public bilingue (lots SSG, `/en`, redirections 301), VPS auto-hébergé.
**Statut global :** décision prise, scaffolding livré, **activation bloquée** par la finalisation juridique.

---

## 1. Décision

**Umami, auto-hébergé, une seule instance, base dédiée dans le PostgreSQL 16 déjà présent.**

Pas de Google Analytics, pas de Plausible Cloud, pas de Matomo, pas de PostHog.

### Pourquoi ce choix, pour ce produit

| Critère | Umami (retenu) | Plausible CE | Matomo |
|---|---|---|---|
| Données | Chez l'exploitant, aucune transmission à un tiers | Auto-hébergé possible, sinon UE | Auto-hébergé |
| Empreinte ops | 1 conteneur + PostgreSQL (déjà là) | 1 conteneur + PostgreSQL **+ ClickHouse** | PHP + MySQL/MariaDB + cron d'archivage |
| Cookies | Aucun par défaut | Aucun par défaut | Cookies par défaut, mode sans cookie à configurer |
| UTM / campagnes | Rapport Campagnes + Sources | Oui | Oui, le plus granulaire |
| Licence / coût | MIT, 0 € | AGPL, 0 € en CE | GPL, 0 € |
| Compatibilité pile | Réutilise le Postgres 16 existant | Ajoute ClickHouse (RAM/disque) | Ajoute PHP-FPM + une base |

Le positionnement du site — bandeau « GDPR Compliant », cible PME allemandes et européennes — impose trois choses : **aucun transfert vers un tiers**, **aucune donnée personnelle brute**, **une preuve d'hébergement européen**. Umami auto-hébergé coche les trois sans ajouter ClickHouse ni PHP sur un VPS qui fait déjà tourner Django, Celery, PostgreSQL, Redis, WordPress et nginx. Matomo serait le plus complet, mais c'est le plus lourd à maintenir et son image « outil à consentement » dessert le discours du site. Plausible CE offre les meilleurs rapports marketing, mais ClickHouse est un coût opérationnel disproportionné pour le volume attendu (site vitrine, quelques milliers de visites/mois).

Umami couvre le besoin réel : pages vues, sources, **rapport Campagnes (UTM)**, objectifs, entonnoirs, API REST, tableaux de bord partageables, travail sans cookie.

---

## 2. Prérequis juridique — porte bloquante, pas une note de bas de page

**Aucune collecte réelle ne doit être activée avant que ces six points soient levés.**

1. **Finaliser les pages Datenschutzerklärung et Cookies.** Elles portent encore `LegalReviewNotice` (brouillon). Une politique de confidentialité qui ne mentionne pas l'outil de mesure est un manquement à l'art. 13 RGPD, indépendamment du caractère cookieless.
2. **Trancher la base légale** avec un juriste : intérêt légitime (art. 6 § 1 f) pour une mesure anonyme, ou consentement. En Allemagne, le § 25 TDDDG s'applique à l'accès/stockage d'informations sur le terminal ; un script qui ne pose aucun cookie et ne lit rien sur l'appareil reste à qualifier au cas par cas. **Ce n'est pas à l'ingénierie de trancher.**
3. **Documenter la rétention** (par exemple 90 jours pour les événements bruts) et la configuration d'anonymisation de l'instance (IP non conservée en clair, pas de profilage cross-site).
4. **Vérifier les sous-traitants.** En auto-hébergement sur le VPS de l'exploitant : aucun nouveau sous-traitant. Si l'hébergement change, un contrat de sous-traitance (art. 28) devient nécessaire.
5. **Mettre à jour la politique cookies** pour dire explicitement « aucun cookie de mesure d'audience n'est déposé », ou décrire le consentement si le point 2 conclut qu'il en faut un.
6. **Validation écrite du juriste** sur les points 1 à 5.

Tant que ces points ne sont pas cochés : `VITE_ANALYTICS_ENABLED` reste absent ou `false`, **aucun script n'est chargé, aucune requête n'est émise, aucun conteneur Umami n'est démarré**. Le scaffolding ci-dessous est inerte par construction (double garde : variable de build + présence réelle du tracker).

---

## 3. Intégration dans l'architecture SSG (lots 1–3)

### 3.1 Le script vit dans le shell, pas dans React

`scripts/prerender.mjs` part de `dist/index.html` et y injecte le HTML rendu. Le marqueur `<!-- presence:analytics -->` ajouté dans `<head>` est donc présent dans **les 58 pages pré-rendues + les 8 articles**, sans qu'une seule ligne de React soit concernée.

À l'activation, `prerender.mjs` remplacera ce marqueur par :

```html
<script defer src="/stats/script.js" data-website-id="<id>"></script>
```

- `defer` : téléchargé en parallèle du parse, exécuté après le DOM, **aucun impact sur le LCP** ni sur l'hydratation.
- Une seule balise par page : `check-seo-build.mjs` doit asserter `count === 1` quand c'est activé, `count === 0` sinon. C'est le garde-fou anti-double-injection lors des rebuilds.
- Ne **pas** monter le script via un composant React : il s'exécuterait après hydratation, raterait les visiteurs sans JS et introduirait un décalage entre le HTML crawlé et le HTML mesuré.

### 3.2 Same-origin, comme le CMS

```nginx
location /stats/ {
    proxy_pass http://umami:3000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
    expires 1h;
}
```

Avantages : pas de domaine tiers (donc pas d'ouverture CSP, pas de blocage par les bloqueurs qui ciblent `umami.is`), pas de préflight CORS, et le `log_format presence_access` existant ne journalise déjà pas la query string.

### 3.3 Navigation SPA

Umami compte la page au chargement. Sans hook, une navigation React Router ne produirait aucune page vue. À l'activation : un `useEffect` sur `location.pathname + location.search` appelle `trackPageview(...)`, déjà écrit et inerte dans `src/lib/analytics.ts`.

### 3.4 Ce que le SSG ne doit pas casser

- `canonical`, `hreflang`, `og:locale`, sitemap : **inchangés**. Le script n'ajoute aucune URL canonique.
- Les 5 routes `noindex` restent `noindex` ; elles peuvent être mesurées sans être indexées.
- Le HTML pré-rendu doit rester identique à l'octet près quand l'analytics est désactivé — un test de non-régression doit comparer un hash de `dist/index.html` avant/après l'ajout du marqueur (le marqueur est un commentaire, il n'apparaît pas dans le rendu visible mais reste dans le source ; l'asserter explicitement évite les surprises).

---

## 4. Exploitation des UTM préservés par les 301 (lot 3)

Le lot 3 garantit qu'un paramètre de campagne survit à la redirection :

```
/pricing?lang=en&utm_source=newsletter&utm_medium=email&utm_campaign=2026-q4
  → 301 → /en/pricing?utm_source=newsletter&utm_medium=email&utm_campaign=2026-q4
```

Umami enregistre l'URL complète de la page vue et en extrait `utm_source`, `utm_medium`, `utm_campaign` (et `utm_content`, `utm_term` si présents). Conséquences concrètes :

| Rapport Umami | Question à laquelle il répond | Exemple |
|---|---|---|
| **Campagnes** | Quelle campagne amène du trafic ? | `2026-q4` : 412 visites, 3,4 % d'inscription |
| **Sources** | Par quel canal ? | `newsletter` / `email`, `linkedin` / `social` |
| **Pages** | Quelle page d'atterrissage convertit ? | `/en/pricing` vs `/pricing` |
| **Objectifs** | Quel événement est déclenché ? | `signup_completed`, `pricing_cta_clicked` |
| **Entonnoirs** | Où le parcours casse-t-il ? | arrivée → pricing → inscription |

### Convention de nommage à imposer dès la première campagne

| Paramètre | Format | Exemples |
|---|---|---|
| `utm_source` | minuscules, tirets | `newsletter`, `linkedin`, `google`, `partner-x` |
| `utm_medium` | liste fermée | `email`, `social`, `cpc`, `referral`, `print` |
| `utm_campaign` | `AAAA-trimestre-sujet` | `2026-q4-launch-de`, `2026-q4-launch-en` |
| `utm_content` | variante créative | `header-cta`, `footer-link` |

### Deux points d'attention

1. **Les liens internes conservent aujourd'hui la query** (`localizeTo` préserve `search`). Cliquer « Features » depuis `/en/pricing?utm_source=x` propage donc l'UTM à `/en/features`. Pour l'attribution de session, Umami ne regarde que la page d'atterrissage, donc l'effet est cosmétique — mais il pollue les rapports « Pages ». Recommandation : retirer `utm_*` des liens internes après l'atterrissage (petite fonction dans `LocaleLink`), à faire au moment de l'activation, pas avant.
2. **Les 301 ne doivent jamais être modifiés pour « nettoyer » la query.** Toute normalisation qui supprime `utm_*` casserait la mesure. Le test Playwright `locale-redirects-dist.spec.ts` (Location exact avec UTM) est le garde-fou.

---

## 5. Plan d'implémentation, étape par étape

### Étape 0 — Scaffolding inerte (FAIT dans cette session)

- [x] `src/lib/analytics.ts` : `isAnalyticsEnabled()`, `trackEvent()`, `trackPageview()`, double garde (build + `window.umami`), no-op en SSR.
- [x] `.env.example` : `VITE_ANALYTICS_ENABLED=false`, `VITE_ANALYTICS_WEBSITE_ID=`, `VITE_ANALYTICS_SCRIPT_URL=/stats/script.js`.
- [x] `index.html` : marqueur `<!-- presence:analytics -->` dans `<head>`, aucun script.
- [x] Ce document.

**Rien de tout cela ne collecte, ne charge ou ne contacte quoi que ce soit.**

### Étape 1 — Porte juridique (BLOQUANTE)

Cocher les six points de la section 2. Sans validation écrite, on s'arrête ici.

### Étape 2 — Service Umami

- Ajouter au `docker-compose.yml` un service `umami` (`ghcr.io/umami-software/umami:postgresql-latest`), sans port publié, sur le réseau interne.
- Créer une base et un rôle dédiés dans le PostgreSQL existant (`umami` / `umami_app`), plutôt qu'un second serveur : une base séparée isole les données et les droits sans ajouter un conteneur de plus. Prévoir `max_connections` et une limite mémoire.
- Admin accessible uniquement en loopback (`127.0.0.1:3000`) ou via tunnel SSH — jamais publié.

### Étape 3 — Injection conditionnelle

- `scripts/prerender.mjs` : remplacer le marqueur par la balise si `VITE_ANALYTICS_ENABLED === "true"` **et** `VITE_ANALYTICS_WEBSITE_ID` non vide ; sinon laisser le commentaire.
- `scripts/check-seo-build.mjs` : assertion `0` balise désactivé, `1` balise activé, et aucune balise sur les routes `noindex` si l'on décide de ne pas les mesurer.
- `vite.config.ts` : exposer `VITE_ANALYTICS_*` au build Docker (aucun secret, uniquement un identifiant public).

### Étape 4 — Proxy nginx

- Ajouter le bloc `/stats/` (section 3.2), le tester avec `scripts/verify-nginx.sh` (une vérification `200` + `content-type: application/javascript`).
- Ne pas toucher aux blocs `/cms/` ni aux redirections `?lang=`.

### Étape 5 — Mesure des conversions

- `src/pages/Auth.tsx` : `signup_started`, `signup_completed`.
- `src/pages/Pricing.tsx` : `pricing_cta_clicked` avec `plan` et `locale` en propriétés.
- `src/pages/ToolPage.tsx` : `scan_started`.
- `src/pages/Billing.tsx` : `checkout_started`.
- Aucune donnée personnelle dans les propriétés (pas d'e-mail, pas d'identifiant de compte).

### Étape 6 — Tests

- E2E : avec `VITE_ANALYTICS_ENABLED=false`, **zéro** requête vers `/stats/` (interception réseau Playwright).
- E2E : build de test activé → exactement une balise, `data-website-id` non vide.
- E2E : `/pricing?lang=en&utm_source=…&utm_medium=…` → la page finale reçoit bien la query conservée, et l'appel de page vue contient ces paramètres.
- Non-régression : les 50 tests Playwright existants restent verts.

### Étape 7 — Déploiement progressif

1. Preview uniquement, avec une propriété de test.
2. Vérifier dans Umami : une visite, une campagne, un objectif.
3. Contrôler la taille du HTML (+ ~90 octets) et l'absence de requête avant interaction.
4. Seulement ensuite, production.

---

## 6. Statut

| Élément | Statut |
|---|---|
| Choix de l'outil | **VALIDÉ TECHNIQUEMENT** (décision documentée) |
| Scaffolding inerte | **VALIDÉ TECHNIQUEMENT** (compilé, aucune collecte) |
| Porte juridique | **BLOQUÉ** — pages Datenschutz/Cookies en brouillon |
| Service Umami | **À IMPLÉMENTER** — après levée du blocage |
| Proxy nginx `/stats/` | **À IMPLÉMENTER** |
| Injection build + tests | **À IMPLÉMENTER** |
| Conformité RGPD/TDDDG | **À VÉRIFIER PAR UN JURISTE** — aucun test technique ne peut la valider |

---

## 7. Ce qui n'a pas été fait, volontairement

- Aucun script analytics n'est chargé, ni en local, ni dans `dist/`.
- Aucun conteneur Umami n'a été créé ou démarré.
- Aucun événement n'est instrumenté dans les pages.
- Aucune variable d'environnement réelle (`VITE_ANALYTICS_WEBSITE_ID`) n'a été créée.
- Aucune modification des pages juridiques, des redirections ou du sitemap.
