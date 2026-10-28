# Presence — Recette SaaS complète en vue du lancement Allemagne

**Date :** 27 octobre 2026
**Périmètre :** environnement Docker local uniquement (aucun déploiement VPS, aucune migration de production, aucun paiement réel)
**Base de départ :** `PRESENCE_ADVANCED_SCANNERS_INSTALLATION_2026-10-27.md`, `PRESENCE_UI_SCANNER_VALIDATION_2026-10-27.md`, `PRESENCE_FINAL_ACCEPTANCE_2026-10-27.md`, `PRESENCE_BILLING_PAYMENTS_VALIDATION.md`, `PRESENCE_AKA_IA_FINAL_VALIDATION_2026-10-27.md`, `PRESENCE_CONTINUOUS_MONITORING_NOTIFICATIONS.md`

---

## 1. Résumé exécutif

**Statut : `READY WITH BLOCKERS` pour un lancement allemand.**

Ce qui est validé par des preuves observables : le site public DE/EN, les pages juridiques (avec marquage explicite « brouillon à valider »), le blog WordPress headless bilingue (publication / dépublication / isolation des brouillons / persistance), l'inscription + vérification d'e-mail + connexion, la surveillance opt-in (activation / pause), les quotas côté serveur, l'isolation multi-tenant, le contrôle d'accès staff, et l'honnêteté de la facturation lorsqu'elle n'est pas configurée.

Ce qui reste bloqué sur des éléments externes ou humains : **Paddle Sandbox** (clé API, secret webhook et Price IDs absents), **compte staff** pour le parcours Admin (aucun compte `is_staff` en base), **textes juridiques allemands** (Impressum, TVA, Widerrufsbelehrung, version allemande des AGB/Datenschutz) qui exigent une validation par une personne qualifiée, et **412 chaînes d'interface encore codées en dur** dans les pages authentifiées.

Aucune donnée, aucun volume, aucun service des autres projets Docker n'a été touché. Aucun paiement réel n'a été déclenché.

---

## 2. État initial constaté

| Élément | Valeur observée |
|---|---|
| Conteneurs Presence | `web` (healthy), `frontend` (healthy), `celery-worker`, `celery-beat`, `db`, `redis`, `mailpit`, `wordpress` (healthy), `wordpress-db`, `scanner-egress-guard`, `scanner-sandbox-anchor` |
| Pile isolée | `presence-validation-*` intacte (non modifiée) |
| Autres projets | `ai-platform-*`, `fingerprint/ goldbot` : non modifiés |
| Migrations | 0001→0002 monitoring appliquées ; **une migration manquait** (voir §6) |
| Base | 21 utilisateurs, 6 sites, 12 scans, 151 constats, **0 compte staff**, 4 forfaits, 21 abonnements `active` (plan gratuit) |
| Forfaits | free (1 site / 10 scans), pro 9 €, business 29 €, agency 79 € — **aucun `external_price_id`** |
| Facturation | `BILLING_PROVIDER=paddle`, `PADDLE_ENVIRONMENT=sandbox`, `PADDLE_API_URL=https://sandbox-api.paddle.com`, **`BILLING_ENABLED=false`**, `PADDLE_API_KEY` et `PADDLE_WEBHOOK_SECRET` **absents** |
| AKA IA | `AKA_AI_API_KEY` présente, `AKA_AI_BASE_URL=https://ai.elomaiapp.com`, **`AI_ADVISOR_ENABLED=false`** |
| Réseau WordPress | `127.0.0.1:8081` (loopback uniquement) + proxy public `/cms/wp-json/` et `/cms/wp-content/` |
| Disque | 234 G, 16 G libres (94 % utilisés) |
| E-mails | Mailpit local (`:8025`) — aucun envoi réel |

---

## 3. Changements réalisés dans cette itération

### 3.1 E-mails transactionnels DE/EN

| Fichier | Changement |
|---|---|
| `backend/accounts/emails.py` (nouveau) | Catalogue explicite DE/EN pour la vérification d'adresse et la réinitialisation de mot de passe, avec repli anglais pour toute autre langue. |
| `backend/accounts/services.py` | Les deux e-mails sont rendus dans `user.language` au lieu d'une chaîne anglaise figée. |
| `backend/accounts/serializers.py` | `language` accepté à l'inscription (facultatif) : l'e-mail de vérification part dans la langue de l'inscription. |
| `frontend/src/api/types.ts`, `frontend/src/pages/Auth.tsx` | La langue de l'interface est transmise à l'inscription. |
| `backend/accounts/tests/test_email_i18n.py` (nouveau) | 10 tests : DE, EN, repli, e-mails par service et par API, langage invalide refusé. |
| `backend/accounts/tests/test_auth_api.py` | Extraction du lien de réinitialisation par expression régulière au lieu du « dernier mot du corps » (le corps est désormais traduit et signé). |
| `frontend/src/pages/Websites.tsx` + `i18n/de.json`/`en.json` | Première page authentifiée traduite intégralement (23 clés : titre, sous-titre, ajout, états vide/chargement, cartes de site, dialogue, confirmations et messages de toast). |

### 3.2 Migration manquante (bloquant de mise en production)

`python manage.py makemigrations --check --dry-run` signalait une modification non migrée :
`monitoring/migrations/0003_alter_monitoringconfig_enabled` (le modèle est passé en opt-in, `default=False`, alors que `0001_initial` créait la colonne avec `default=True`).

- migration créée : `backend/monitoring/migrations/0003_alter_monitoringconfig_enabled.py` (AlterField seul, réversible) ;
- appliquée localement : `Applying monitoring.0003_alter_monitoringconfig_enabled... OK` ;
- données inchangées après migration : 8 configurations, 2 activées (identique à avant) ;
- `makemigrations --check --dry-run` → `No changes detected`.

### 3.3 Internationalisation et pages juridiques

| Fichier | Changement |
|---|---|
| `frontend/src/pages/WithdrawalPage.tsx` (nouveau) | Page **Widerruf** (`/widerruf`) : structure explicite, bandeau « à valider », quatre sections et liste des éléments manquants. Aucun texte juridique inventé. |
| `frontend/src/components/LegalReviewNotice.tsx` (nouveau) | Bandeau réutilisable « Arbeitsentwurf – avant mise en ligne à faire vérifier » avec checklist. |
| `frontend/src/pages/TermsPage.tsx`, `PrivacyPage.tsx` | Titre localisé via `t("legal.termsTitle"/"legal.privacyTitle")`, libellé « Zuletzt aktualisiert » traduit, bandeau de revue ajouté, et **correction factuelle : Stripe → Paddle** (le prestataire réel est Paddle). |
| `frontend/src/pages/CookiesPage.tsx` | La table de stockage liste désormais les clés réellement écrites : `presence_access`, `presence_refresh`, `presence-locale`, `presence-theme`, `presence:debug-api`. |
| `frontend/src/components/SEO.tsx` | Nouvelle prop `alternates` pour les pages dont les traductions vivent sur des chemins différents. |
| `frontend/src/pages/BlogArticle.tsx` | `html lang` suit la langue **de l'article** ; `hreflang` pointe vers le **slug traduit** au lieu de `?lang=` sur le même slug. |
| `frontend/src/App.tsx`, `Landing.tsx`, `src/seo/routes.json` | Route `/widerruf`, lien de pied de page « Widerruf », entrée de pré-rendu. |
| `frontend/src/i18n/de.json`, `en.json` | +16 clés, catalogue à parité (404 / 404). |

### 3.4 Scripts et tests ajoutés

| Fichier | Rôle |
|---|---|
| `scripts/recette_paddle_quotas.sh` | Recette HTTP réelle : facturation non configurée, webhooks sans signature, quotas, isolation. |
| `scripts/recette_monitoring_ai.sh` | Recette HTTP réelle : opt-in, activation, pause, alertes, canaux, AKA IA. |
| `frontend/e2e/launch-readiness.spec.ts` | 5 parcours navigateur : public DE/EN + pages juridiques, responsive, blog bilingue, quota du plan gratuit (UI + serveur), accès Admin refusé. |

---

## 4. Inventaire des pages et routes

### 4.1 Public (pré-rendues : 32 routes, sitemap 27 URL)

`/` · `/pricing` · `/faq` · `/blog` · `/blog/:slug` · `/about` · `/contact` · `/privacy` · `/terms` · `/impressum` · `/widerruf` *(nouveau)* · `/cookies` · `/solutions/{small-business,freelancers,agencies,restaurants,ecommerce,local-business}` · `/features/{website-monitoring,ssl-monitoring,dns-monitoring,email-security,uptime-monitoring,website-performance,security-headers,review-monitoring}` · `/tools/{website-checker,ssl-checker,dns-checker,email-security-checker}` · `/scan/:scanId` · `/report/:publicId` (redirection héritée) · `/login` · `/register` · `/forgot-password` · `/reset-password` · `/verify-email` · `/onboarding` · 404.

### 4.2 Authentifié (`/app/*`)

`dashboard` · `websites` · `websites/:id` · `scans` · `monitoring` · `alerts` · `reports` · `reviews` · `growth` · `advisor` · `settings` · `settings/integrations` · `billing` · `*` → dashboard.

### 4.3 Administration

`/admin` (frontend, « Growth Center ») alimenté par `GET /api/v1/analytics/admin/overview/` (`IsAdminUser`) ; administration Django `/admin/` avec enregistrements dans 12 applications.

### 4.4 Vérifications par page (navigateur, 27/10)

| Page | Chargement | Langue | État vide / erreur | Permissions | Mobile |
|---|---|---|---|---|---|
| `/` `/pricing` `/faq` | ✅ | ✅ DE par défaut, bascule EN | ✅ | n/a | ✅ |
| `/blog` `/blog/:slug` | ✅ (CMS joignable) | ✅ article garde sa langue | ✅ erreur explicite si CMS indisponible | ✅ brouillons non exposés | ✅ |
| `/terms` `/privacy` `/impressum` `/widerruf` `/cookies` | ✅ | ✅ titres DE + bandeau de revue | n/a | n/a | ✅ |
| `/register` `/login` `/verify-email` | ✅ | ✅ | ✅ | n/a | ✅ |
| `/app/websites` | ✅ | ✅ DE/EN (traduit) | ✅ invitation à l'upgrade | ✅ 403 serveur | ✅ |
| `/admin` | ✅ | EN | ✅ panneau « Staff access required » | ✅ 403 non-staff | ✅ |

---

## 5. Résultats des tests

### 5.1 Tests automatisés exécutés

| Commande | Résultat |
|---|---|
| `bash scripts/run_backend_tests.sh accounts` | **37 tests — OK** (dont 10 nouveaux d'i18n e-mail) |
| `bash scripts/run_backend_tests.sh analytics subscriptions` | **57 tests — OK** |
| `bash scripts/run_backend_tests.sh monitoring` | **39 tests — OK** |
| `bash scripts/run_backend_tests.sh advisory` | **non terminé** : suite trop longue pour la fenêtre d'exécution. Deux lancements ont été suivis — environ **108 tests exécutés, 0 échec observé** — avant arrêt volontaire. Aucun résultat global ne peut être revendiqué : voir §10 |
| `npx tsc --noEmit` (frontend) | **exit 0** (avant et après la traduction de la page Sites) |
| `npm run build` (frontend) | **succès** — 32 routes pré-rendues, sitemap 27 URL, 3,64 s |
| `npx playwright test` | **7 / 7 réussis** — exécution finale après l'ensemble des modifications (5 nouveaux parcours + 2 existants), 2,1 min |
| `python manage.py check` | `System check identified no issues (0 silenced)` |
| `python manage.py makemigrations --check --dry-run` | après correctif : `No changes detected` |
| `docker compose config --quiet` | exit 0 |
| `node scripts/check-i18n.mjs` | parité **427 / 427** clés ✅ · **401 chaînes en dur** dans 44 fichiers ⚠️ (412 avant traduction de la page Sites) |

### 5.2 Recettes HTTP réelles

`bash scripts/recette_paddle_quotas.sh` — **tous les contrôles réussis**

```
health 200 · websites sans jeton 401 · abonnement sans jeton 401
plans 200 — free 1 site/10 scans · pro 9 €/10/500 · business 29 €/50/5000 · agency 79 €/200/20000
inscription A/B 201 · connexion 200
checkout pro → 503 code=billing_not_configured « Checkout is disabled. »
upgrade direct → 503 code=billing_not_configured · offre après tentative = free
webhook sans signature → 503 billing_not_configured
webhook signature invalide → 503 billing_not_configured
dépassement du quota de sites → 403 code=website_limit_reached
site d'un autre compte → 404 · scans étrangers dans la réponse → 0
```

`bash scripts/recette_monitoring_ai.sh` — **tous les contrôles réussis**

```
surveillance par défaut : enabled=False, next_scan_at=None (aucun scan planifié)
activation explicite : enabled=True, next_scan_at renseigné immédiatement
pause explicite : enabled=False, planification effacée
alertes : préférences 200 · règles 200 · liste 200
canaux de notification : ['email'] (créé automatiquement à l'inscription)
recommandations sans scan_id → 400 « scan_id is required. »
recommandations d'un scan étranger → 404
chat IA sur une organisation inconnue → 404
surveillance d'un site étranger → 404
```

`bash scripts/validate_wordpress_blog.sh` — **12 réussis / 0 échec**

```
GET /cms/wp-json/wp/v2/posts → 200 · articles DE: 2, EN: 6
brouillon non exposé par l'API publique
publication → visible en allemand · pas de fuite dans la liste anglaise · dépublication → retiré
liens de traduction réciproques (de-was-ist-website-monitoring ↔ what-is-website-monitoring)
wp-login.php via l'origine publique → 404 · admin en loopback 127.0.0.1:8081 → 200 (local uniquement)
articles et volume conservés après redémarrage contrôlé du CMS
```

### 5.3 Parcours navigateur (Playwright)

Exécution finale, après l'ensemble des modifications décrites au §3 (y compris la traduction de la page Sites) :

```
✓ public journey: German by default, English switch, legal pages     (12,1 s)
✓ mobile layout stays inside the viewport                            (5,5 s)
✓ blog: German article, translated slug, published posts only         (3,2 s)
✓ free plan: first website is accepted, the second is refused         (9,7 s)
✓ admin surface is staff-only                                         (7,4 s)
✓ public scan → real report → shared link → lead capture              (8,8 s)
✓ registration → e-mail link → verified account → login              (20,5 s)
```

---

## 6. Résultats DE/EN

**Validé :** bascule DE/EN visible et persistante (rechargement compris), allemand par défaut, titres et libellés des pages juridiques dans la bonne langue, e-mails de compte en allemand pour un compte `language="de"`, articles de blog conservant leur langue propre, `hreflang` pointant vers le slug traduit.

**Traduit dans cette itération :** inscription (langue transmise au backend), pages juridiques (titres AGB/Datenschutz localisés), page **Sites** entièrement bilingue (23 clés, première étape d'onboarding).

**Restant (mesuré) :** `node scripts/check-i18n.mjs` → **401 chaînes visibles codées en dur dans 44 fichiers**, principalement dans les pages authentifiées :

| Fichier | Chaînes |
|---|---|
| `pages/PrivacyPage.tsx` (corps du texte, volontairement non traduit) | 39 |
| `pages/Reviews.tsx` | 38 |
| `pages/Alerts.tsx` | 35 |
| `pages/Settings.tsx` | 29 |
| `pages/Monitoring.tsx` | 25 |
| `pages/Scans.tsx` | 23 |
| `pages/Growth.tsx` | 18 |
| `pages/Dashboard.tsx` | 15 |
| `pages/Integrations.tsx` | 15 |

Aucune clé technique (`billing.checkout.error`) n'apparaît à l'écran, et le rapporteur affiche un avertissement console en développement plutôt qu'une clé brute.

---

## 7. WordPress (blog headless)

- Conteneurs **conservés** : `wordpress` + `wordpress-db`, volumes et base dédiée intacts ; aucun service recréé.
- Publication, visibilité, modification et dépublication vérifiées par script (`validate_wordpress_blog.sh`) et par navigateur (article allemand, `canonical`, `hreflang` anglais).
- Sécurité : `/cms/wp-admin/` et `/cms/wp-login.php` → **404** via l'origine publique (seuls `/cms/wp-json/` et `/cms/wp-content/` sont proxifiés) ; l'admin n'est joignable qu'en loopback `127.0.0.1:8081`.
- Rendu sûr : le HTML du CMS passe par **DOMPurify** avant insertion (`components/BlogBody.tsx`).
- Persistance : articles conservés après redémarrage contrôlé du CMS.
- Identifiants : uniquement dans des fichiers d'environnement ignorés par Git ; le frontend ne reçoit que l'URL de l'API publique, aucun identifiant d'administration.

**Point ouvert (P2) :** `/wp-json/wp/v2/users` est **publiquement lisible** (énumération des auteurs WordPress). Recommandation : désactiver cette route côté mu-plugin ou restreindre l'API aux types de contenu nécessaires.

---

## 8. Espace Admin et contrôles d'accès

| Contrôle | Résultat | Preuve |
|---|---|---|
| Endpoint d'analytique staff | `IsAdminUser` uniquement | `analytics/views.py:36` |
| Accès anonyme | **401** | `curl → 401` |
| Accès utilisateur non staff | **403** + panneau « Staff access required », aucune métrique affichée | test E2E `admin surface is staff-only` |
| Test automatisé dédié | présent | `analytics/tests/test_admin_overview.py::test_non_staff_is_forbidden` |
| Escalade de privilèges | non observée : un utilisateur ne peut pas s'octroyer un plan payant (checkout/upgrade refusés, abonnement inchangé) | `recette_paddle_quotas.sh` |
| Admin Django | `/admin/` derrière authentification Django, modèles enregistrés dans 12 applications | `config/urls.py`, `*/admin.py` |

**Bloqué (P1) :** aucun compte `is_staff` n'existe en base (0 / 21). Le parcours Admin complet (consulter utilisateurs, abonnements, webhooks, journaux) n'a donc **pas** été exécuté. Procédure à exécuter par une personne habilitée :

```bash
docker compose exec web python manage.py createsuperuser   # mot de passe saisi interactivement, jamais écrit ici
```

---

## 9. Paddle — distinction explicite des niveaux de test

| Niveau | État |
|---|---|
| **Tests unitaires / fixtures** (signature, idempotence, cycle de vie, quotas) | ✅ exécutés — `subscriptions` inclus dans les 57 tests OK (`test_billing.py::test_missing_signature_is_rejected`, `test_invalid_signature_is_rejected`, `test_duplicate_event_is_idempotent`, `test_unknown_price_fails_loudly`, quotas, clés API) |
| **Simulations HTTP locales** (aucun appel à Paddle) | ✅ `recette_paddle_quotas.sh` — checkout/upgrade/webhook refusent honnêtement, aucun droit payant accordé |
| **Opérations Sandbox réelles** (création de checkout, session de paiement, webhook signé par Paddle) | ❌ **BLOQUÉ** — identifiants et Price IDs absents |
| **Paiement réel** | ❌ jamais déclenché (interdit) |

Codes observés lorsque la facturation n'est pas configurée : `503 billing_not_configured` pour `/subscriptions/checkout/`, `/subscriptions/upgrade/` et `/webhooks/paddle/` (aucune signature n'est « acceptée par défaut » : le refus est conservateur).

**Variables et données nécessaires pour débloquer la recette Sandbox :**

1. `BILLING_ENABLED=true`
2. `PADDLE_API_KEY` (clé Sandbox, préfixe `pdl_sdbx_…`)
3. `PADDLE_WEBHOOK_SECRET` (secret de notification Sandbox)
4. `PADDLE_ENVIRONMENT=sandbox` et `PADDLE_API_URL=https://sandbox-api.paddle.com` *(déjà en place)*
5. `Plan.external_price_id_monthly` et `Plan.external_price_id_yearly` renseignés pour `pro`, `business`, `agency` (via `python manage.py create_paddle_sandbox` ou l'admin)
6. un tunnel HTTPS public pour recevoir les webhooks (`scripts/paddle_webhook_tunnel.sh`)

---

## 10. AKA IA, surveillance, notifications et quotas

| Fonction | Résultat |
|---|---|
| Surveillance continue opt-in | ✅ désactivée à la création, aucun scan planifié ; activation → premier contrôle immédiat ; pause → planification effacée |
| Alertes et préférences | ✅ `/alerts/preferences/`, `/alerts/rules/`, `/alerts/` répondent 200 pour le propriétaire, 401 en anonyme |
| Canal de notification | ✅ canal `email` créé automatiquement à l'inscription |
| Quotas serveur | ✅ site supplémentaire refusé en **403 `website_limit_reached`** (et non par simple masquage d'un bouton) |
| Isolation multi-tenant | ✅ site d'un autre compte → 404, aucune ligne étrangère dans les listes, surveillance étrangère → 404 |
| Contrôle d'accès AKA IA | ✅ `/advisory/recommendations/` et chat IA → 401 en anonyme ; organisation inconnue → 404 ; scan étranger → 404 |
| Recommandations | nécessite `scan_id` (400 sinon) — contrat d'API confirmé |
| **Analyse IA automatique après scan** | ❌ **désactivée** dans la pile active (`AI_ADVISOR_ENABLED=false`) : aucune explication IA n'est produite automatiquement |
| Session de chat IA réelle | ⚠️ **non exécutée volontairement** : l'endpoint interactif n'est pas conditionné par `AI_ADVISOR_ENABLED` (seule l'analyse automatique l'est) et un appel réel consommerait des crédits de la passerelle AKA IA. |
| Suite de tests `advisory` | ⚠️ **non terminée** : environ 108 tests exécutés sans échec observé, puis arrêt volontaire faute de temps (la suite enchaîne des tests de résilience avec temporisations réelles). Ne pas la présenter comme réussie : la commande doit être relancée et son résumé (`Ran N tests / OK`) conservé avant toute décision de mise en production. |

Conséquences pour le lancement : l'interface ne doit pas promettre d'explications IA tant que `AI_ADVISOR_ENABLED=false`, et le garde-fou « un scan `partial` n'est pas une analyse exhaustive » doit être maintenu dans les textes.

---

## 11. Sécurité, confidentialité, conformité

### 11.1 Vérifié

- **Isolation multi-tenant** sur sites, scans, surveillance et recommandations (§10).
- **Autorisations côté serveur** : masquer un bouton ne suffit pas — refus 403 vérifié pour le quota, 403/401 pour l'admin, 404 pour les ressources d'autrui.
- **Webhooks** : signature obligatoire, rejet des signatures invalides et des horodatages expirés, idempotence par `(provider, event_id)` (table `BillingEvent`), journalisation sans secret.
- **Aucun traceur tiers** : aucun `gtag`, `analytics.js`, Umami, PostHog, Plausible, Matomo, Hotjar ou pixel réseau dans le code ; aucun cookie publicitaire.
- **Stockage navigateur** documenté et exact (jetons dans `localStorage`, langue, thème) ; **aucun bandeau de consentement n'est affiché, et c'est justifié** puisqu'il n'existe ni cookie non essentiel ni traceur tiers. Ce point est une décision à assumer explicitement.
- **Pages juridiques** : marquées comme brouillons non validés (Impressum, AGB, Datenschutz, Widerruf), avec la liste des éléments à compléter. Prestataire de paiement corrigé (Paddle).
- **WordPress** : admin non exposé publiquement, brouillons non exposés, HTML assaini (DOMPurify).
- **Secrets** : aucun secret affiché, journalisé ni versionné ; valeurs lues uniquement sous forme de noms de variables.

### 11.2 Points ouverts

| Priorité | Point | Détail |
|---|---|---|
| P1 | Textes juridiques | Impressum (identité, adresse, registre, TVA), Widerrufsbelehrung + Muster-Widerrufsformular, version allemande des AGB/Datenschutz, obligation de rétractation selon B2B/B2C. **Aucune de ces informations n'existe dans le dépôt ; elles exigent une validation professionnelle.** |
| P1 | Rétractation dans le tunnel d'achat | L'accord explicite au commencement immédiat de la prestation (perte du droit de rétractation) **n'est pas implémenté** dans le checkout. |
| P2 | `TrafficLog.ip_hash` | SHA-256 tronqué à 64 bits d'une adresse IP : pseudonymisation faible (force brute IPv4 triviale). À saler/hmac-er et à assortir d'une durée de conservation documentée. |
| P2 | API REST WordPress `users` | publique → énumération des auteurs. |
| P2 | Rendu des e-mails | vérifié via Mailpit uniquement ; aucun test sur un vrai client de messagerie ni sur un serveur SMTP réel. |
| P2 | Disque | 94 % utilisé (16 Go libres) : un scan approfondi + archives peut remplir la machine. |
| P3 | Accessibilité | vérifications limitées au débordement horizontal mobile et aux rôles ARIA présents ; aucun audit complet (contraste, navigation clavier, lecteur d'écran). |
| P3 | Performance | scripts `load/k6/` présents mais **non exécutés** dans cette itération. |
| P3 | `/admin` côté client | la route n'est pas gardée côté client (le 403 serveur et le panneau explicite font foi) ; une redirection pourrait éviter le chargement inutile. |

---

## 12. Variables et accès nécessaires pour lever les blocages

| Blocage | Ce qu'il faut fournir |
|---|---|
| Recette Paddle Sandbox | `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`, `BILLING_ENABLED=true`, Price IDs des 3 forfaits payants, tunnel HTTPS public |
| Parcours Admin | création d'un superutilisateur (`createsuperuser`) ou promotion explicite d'un compte de test |
| Analyse IA automatique | `AI_ADVISOR_ENABLED=true` (et confirmation que les crédits de la passerelle peuvent être consommés par les tests) |
| Pré-rendu SEO de production | `VITE_BASE_URL` exporté **et** `VITE_WP_API_URL` en URL absolue *au moment du build*, sinon canonicals/sitemap restent en `http://localhost:8443` et les articles de blog sont rendus côté client |
| Conformité allemande | identité juridique, adresse, registre, TVA, décision B2B/B2C, textes validés par une personne qualifiée |

---

## 13. Checklist de mise en production

| # | Point | Statut |
|---|---|---|
| 1 | Migrations cohérentes (`makemigrations --check` propre) | **VALIDÉ** (migration 0003 créée et appliquée localement) |
| 2 | `manage.py check` sans erreur | **VALIDÉ** |
| 3 | Configuration Compose valide | **VALIDÉ** (`docker compose config --quiet`) |
| 4 | Build frontend + pré-rendu | **VALIDÉ** (32 routes, 27 URL de sitemap) |
| 5 | Suite E2E navigateur (7 parcours) | **VALIDÉ** |
| 6 | Tests backend des zones touchées (accounts, monitoring, analytics, subscriptions) | **VALIDÉ** (133 tests) |
| 7 | Détection DE/EN, bascule et persistance de la langue | **VALIDÉ** |
| 8 | Pages juridiques présentes et marquées comme non validées | **VALIDÉ** (structure) / **À VALIDER MANUELLEMENT** (contenu juridique) |
| 9 | E-mails de compte DE/EN | **VALIDÉ** (Mailpit) / **À VALIDER MANUELLEMENT** (rendu client réel) |
| 10 | Blog WordPress : publication, dépublication, langues, persistance, admin non exposé | **VALIDÉ** |
| 11 | Surveillance opt-in, activation, pause | **VALIDÉ** |
| 12 | Notifications : canal par défaut + préférences | **VALIDÉ** (interne) / **À VALIDER MANUELLEMENT** (SMTP réel) |
| 13 | Quotas et limites de plan appliqués côté serveur | **VALIDÉ** |
| 14 | Isolation multi-tenant sur les API sensibles | **VALIDÉ** (sites, scans, surveillance, recommandations) |
| 15 | Contrôle d'accès Admin (non-staff refusé) | **VALIDÉ** |
| 16 | Parcours Admin complet (utilisateurs, abonnements, webhooks, journaux) | **BLOQUÉ** (aucun compte staff) |
| 17 | Checkout Paddle Sandbox réel + webhook signé | **BLOQUÉ** (clé, secret, Price IDs) |
| 18 | Cycle d'abonnement Sandbox (activation, échec, `past_due`, annulation, expiration) | **BLOQUÉ** (dépend du point 17) / couvert par tests unitaires |
| 19 | Analyse IA automatique après scan | **BLOQUÉ** (`AI_ADVISOR_ENABLED=false`) |
| 20 | Traduction complète de l'interface authentifiée | **ÉCHEC partiel** (401 chaînes en dur restantes ; DE/EN complets sur le public, l'authentification, les pages juridiques et la page Sites) |
| 21 | Textes juridiques allemands validés (Impressum, AGB, Datenschutz, Widerruf, TVA) | **À VALIDER MANUELLEMENT** |
| 22 | Rétractation / commencement immédiat de la prestation dans le checkout | **ÉCHEC** (non implémenté) |
| 23 | Durée de conservation et base légale des journaux de trafic | **À VALIDER MANUELLEMENT** |
| 24 | Audit d'accessibilité et tests de charge | **À VALIDER MANUELLEMENT** (non exécutés) |
| 25 | Pré-rendu SEO avec l'origine publique de production | **BLOQUÉ** (`VITE_BASE_URL`, `VITE_WP_API_URL`) |

**Aucun déploiement VPS n'a été effectué. Aucune donnée historique n'a été réécrite. Aucun volume, service ou projet Docker tiers n'a été supprimé ou modifié.**

---

## 14. Actions prioritaires suivantes

1. **P1 — Créer un compte staff** et dérouler le parcours Admin de bout en bout (utilisateurs, abonnements, événements webhook, état des tâches).
2. **P1 — Configurer Paddle Sandbox** (5 variables + Price IDs) et exécuter la recette réelle : checkout, webhook signé, `past_due`, annulation, expiration.
3. **P1 — Faire valider les textes juridiques allemands** et implémenter l'accord explicite au commencement immédiat de la prestation dans le checkout.
4. **P2 — Traduire les pages authentifiées prioritaires** (`Dashboard`, `Scans`, `Monitoring`, `Alerts`, `Settings`) pour éliminer le reste des 401 chaînes en dur ; la page `Websites` est faite.
5. **P2 — Corriger les points de sécurité/conformité** : `ip_hash` des journaux de trafic, route `wp/v2/users` publique.
6. **P2 — Préparer le build de production** avec `VITE_BASE_URL` et `VITE_WP_API_URL` absolus afin de pré-rendre les articles de blog.
