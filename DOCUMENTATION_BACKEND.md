## Installation rapide

### Prérequis
- Docker 24+
- Docker Compose v2+

### 1. Cloner le projet

```bash
git clone https://github.com/akakpovi/SaaS_Web_Application_digitale_presenz.git
cd SaaS_Web_Application_digitale_presenz
```

### 2. Configurer l'environnement

```bash
cp backend/.env.example backend/.env
# Éditer backend/.env avec vos valeurs
```

### 3. Démarrer

```bash
cd backend
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py create_plans
docker compose exec web python manage.py createsuperuser
```

### 4. Accéder

- Application : http://localhost:8080
- API : http://localhost:8080/api/v1/
- Documentation API : http://localhost:8080/api/docs/
- Admin Django : http://localhost:8080/admin/

---

## Variables d'environnement

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080

# Base de données
POSTGRES_DB=presence
POSTGRES_USER=presence
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
DEFAULT_FROM_EMAIL=noreply@yourapp.com

# Frontend
FRONTEND_URL=http://localhost:5173
```

---

## API Endpoints

### Authentification

```
POST   /api/v1/auth/register/
POST   /api/v1/auth/login/
POST   /api/v1/auth/logout/
POST   /api/v1/auth/refresh/
GET    /api/v1/auth/me/
POST   /api/v1/auth/password/reset/
POST   /api/v1/auth/password/reset/confirm/
```

### Public (sans authentification)

```
POST   /api/v1/public/check/
GET    /api/v1/public/check/<id>/
```

### Websites

```
GET    POST          /api/v1/websites/
GET    PUT    DELETE /api/v1/websites/<id>/
POST                 /api/v1/websites/<id>/scan/
```

### Scans

```
GET    /api/v1/scans/
GET    /api/v1/scans/<id>/
GET    /api/v1/scans/<id>/results/
```

### Monitoring

```
GET                       /api/v1/monitoring/
GET    PUT   PATCH DELETE /api/v1/monitoring/websites/<id>/
POST                      /api/v1/monitoring/websites/<id>/scan/
```

### Alertes

```
GET    /api/v1/alerts/
GET    /api/v1/alerts/<id>/
POST   /api/v1/alerts/<id>/acknowledge/
POST   /api/v1/alerts/<id>/resolve/
GET    PUT    PATCH   /api/v1/alerts/preferences/
GET    POST          /api/v1/alerts/rules/
GET    PUT    DELETE /api/v1/alerts/rules/<id>/
GET    POST          /api/v1/alerts/mute-windows/
GET    DELETE        /api/v1/alerts/mute-windows/<id>/
```

### Notifications

```
GET    POST          /api/v1/notifications/channels/
GET    PUT    DELETE /api/v1/notifications/channels/<id>/
POST                 /api/v1/notifications/channels/<id>/test/
```

### Rapports

```
GET    /api/v1/reports/
GET    /api/v1/reports/<id>/
POST   /api/v1/reports/generate/
```

### Avis clients

```
GET    POST          /api/v1/reviews/sources/
GET    PUT    DELETE /api/v1/reviews/sources/<id>/
GET    POST          /api/v1/reviews/
GET    PUT    DELETE /api/v1/reviews/<id>/
POST                 /api/v1/reviews/<id>/approve/
GET    POST          /api/v1/reviews/responses/
GET    PUT    DELETE /api/v1/reviews/responses/<id>/
```

### Abonnements

```
GET    /api/v1/subscriptions/plans/
GET    /api/v1/subscriptions/me/
POST   /api/v1/subscriptions/upgrade/
POST   /api/v1/subscriptions/cancel/
```

---

## Tests

```bash
# Tous les tests
docker compose exec web python manage.py test --verbosity=2

# Un module spécifique
docker compose exec web python manage.py test accounts.tests
docker compose exec web python manage.py test core.tests
docker compose exec web python manage.py test monitoring.tests
docker compose exec web python manage.py test alerts.tests
```

**168 tests passants**

---

## Docker

### Services

| Service | Image | Rôle |
|---------|-------|------|
| web | python:3.12-slim | Django + Gunicorn |
| db | postgres:16-alpine | Base de données |
| redis | redis:7-alpine | Cache + Broker Celery |
| celery-worker | python:3.12-slim | Tâches asynchrones |
| celery-beat | python:3.12-slim | Tâches planifiées |
| nginx | nginx:1.27-alpine | Reverse proxy |

### Commandes Docker

```bash
# Démarrer tous les services
docker compose up -d

# Voir les logs
docker compose logs -f web
docker compose logs -f celery-worker
docker compose logs -f celery-beat

# Rebuild après modification
docker compose build web
docker compose up -d

# Arrêter
docker compose down

# Arrêter et supprimer les volumes
docker compose down -v
```

---

## Tâches Celery planifiées

| Tâche | Fréquence | Description |
|-------|-----------|-------------|
| run-due-monitors | Toutes les 5 min | Lance les scans de monitoring |
| cleanup-old-alerts | Tous les jours à 2h | Supprime les alertes > 90 jours |
| generate-monthly-reports | 1er du mois à 3h | Génère les rapports mensuels |

---

## Licence

MIT — Projet open source
```

---

## DOCUMENTATION_BACKEND.md

```markdown
# Documentation Backend — Presence SaaS

**Version** : Phase 7 complète
**Date** : 2026
**Stack** : Django 5.1 + DRF + PostgreSQL + Redis + Celery

---

## Table des matières

1. Architecture générale
2. Modèles de données
3. Authentification
4. Scanners
5. Système de scoring
6. Protection SSRF
7. Monitoring planifié
8. Système d'alertes
9. Notifications
10. Rapports
11. Avis clients
12. Abonnements
13. Tâches Celery
14. API Reference
15. Sécurité
16. Tests

---

## 1. Architecture générale

Le backend est organisé en modules Django indépendants.
Chaque module est une application Django avec ses propres modèles,
vues, serializers, URLs et tests.

```
backend/
├── config/
│   ├── settings/
│   │   ├── base.py         # Configuration commune
│   │   ├── development.py  # Surcharge développement
│   │   └── production.py   # Surcharge production
│   ├── celery.py           # Configuration Celery
│   └── urls.py             # Routage principal
│
├── accounts/               # Authentification + User model
├── websites/               # Gestion des sites web
├── scans/                  # Scans + CheckResult + scoring
├── monitoring/             # MonitoringConfig + tâche Beat
├── alerts/                 # Alert + AlertPreference + MuteWindow
├── notifications/          # NotificationChannel + providers
├── reports/                # Report + génération asynchrone
├── reviews/                # ReviewSource + Review + ResponseDraft
├── subscriptions/          # Plan + Subscription
├── scanners/               # 7 scanners individuels
├── public_checker/         # Endpoint public sans authentification
└── core/                   # Protection SSRF + escalation
```

### Flux complet d'un scan

```
Étape 1 : L'utilisateur appelle POST /api/v1/websites/<id>/scan/
Étape 2 : La vue crée un objet Scan avec status=QUEUED
Étape 3 : La vue lance run_authenticated_scan.delay(scan_id)
Étape 4 : Celery Worker exécute les 7 scanners en séquence
Étape 5 : Chaque scanner crée ou met à jour un CheckResult
Étape 6 : Le scoring calcule le health_score (0 à 100)
Étape 7 : Le Scan passe à status=COMPLETED
Étape 8 : detect_alerts.delay(scan_id) est appelé
Étape 9 : Les alertes sont créées selon les résultats
Étape 10 : NotificationDispatcher envoie via les canaux configurés
```

---

## 2. Modèles de données

### User (accounts/models.py)

Champs principaux :
- id : UUID (clé primaire auto-générée)
- email : adresse email (unique, identifiant principal)
- full_name : nom complet
- is_active : compte actif
- is_staff : accès admin
- is_email_verified : email vérifié
- date_joined : date de création
- updated_at : date de mise à jour

Identifiant principal : email (USERNAME_FIELD = "email")

Objets créés automatiquement à la création d'un User :
- AlertPreference via signal post_save (alerts/signals.py)
- Subscription au plan Free via signal post_save (subscriptions/signals.py)

---

### Website (websites/models.py)

Champs principaux :
- owner : ForeignKey vers User
- domain : domaine normalisé en minuscules, sans slash ni port
- display_name : nom affiché dans l'interface
- is_active : monitoring actif pour ce site
- created_at, updated_at : timestamps

Contrainte : un propriétaire ne peut pas avoir deux fois le même domaine.

Objet créé automatiquement à la création d'un Website :
- MonitoringConfig via signal post_save (monitoring/signals.py)
  avec interval=24h et next_scan_at=maintenant

---

### Scan (scans/models.py)

Champs principaux :
- website : ForeignKey vers Website
- status : état du scan
- trigger : origine du scan
- health_score : score global de 0 à 100
- health_status : niveau de santé global
- failure_message : message d'erreur si échec
- started_at, completed_at, created_at : timestamps

Valeurs de status :
- pending : en attente
- queued : en file d'attente Celery
- running : en cours d'exécution
- completed : terminé avec succès
- failed : échec

Valeurs de trigger :
- manual : déclenché manuellement par l'utilisateur
- onboarding : déclenché à l'inscription
- monitoring : déclenché par la tâche Beat automatique
- public : déclenché via l'endpoint public

Machine à états (transitions autorisées) :
- pending peut aller vers queued ou failed
- queued peut aller vers running ou failed
- running peut aller vers completed ou failed
- completed est un état final
- failed est un état final

---

### CheckResult (scans/models.py)

Champs principaux :
- scan : ForeignKey vers Scan
- category : catégorie du check
- status : résultat du check
- score : score entre 0 et max_weight (null pour uptime)
- summary : message lisible par l'utilisateur
- recommendation : action recommandée
- technical_details : données JSON brutes du scanner

Valeurs de category :
- website : disponibilité du site
- ssl : certificat SSL
- dns : configuration DNS
- email_security : SPF, DKIM, DMARC
- security_headers : en-têtes de sécurité HTTP
- performance : performance et temps de réponse
- uptime : disponibilité historique (score null)

Contrainte : un seul CheckResult par catégorie par scan.

---

### MonitoringConfig (monitoring/models.py)

Champs principaux :
- website : OneToOneField vers Website
- enabled : monitoring actif ou non
- interval : fréquence de surveillance
- last_scan_at : date du dernier scan
- next_scan_at : date du prochain scan planifié
- consecutive_failures : nombre d'échecs consécutifs
- escalation_level : niveau d'escalade actuel

Valeurs d'interval :
- 5m : toutes les 5 minutes
- 15m : toutes les 15 minutes
- 30m : toutes les 30 minutes
- 1h : toutes les heures
- 6h : toutes les 6 heures
- 24h : toutes les 24 heures (valeur par défaut)

Valeurs d'escalation_level :
- 0 : tout va bien
- 1 : niveau warning
- 2 : niveau critique

Méthodes utiles :
- schedule_next_scan() : calcule et sauvegarde next_scan_at avec jitter
- record_failure() : incrémente consecutive_failures et met à jour escalation_level
- record_success() : remet consecutive_failures et escalation_level à zéro

---

### Alert (alerts/models.py)

Champs principaux :
- id : UUID (clé primaire auto-générée)
- user : ForeignKey vers User
- website : ForeignKey vers Website
- scan : ForeignKey vers Scan (nullable)
- alert_type : type d'alerte
- severity : niveau de sévérité
- status : état de l'alerte
- title : titre lisible
- message : description détaillée
- metadata : données JSON supplémentaires
- notification_channels_sent : liste des canaux via lesquels l'alerte a été envoyée
- acknowledged_at, acknowledged_by : données d'acquittement
- resolved_at : date de résolution

Valeurs d'alert_type :
- ssl_expiring : SSL expire dans moins de 30 jours
- ssl_invalid : certificat SSL invalide
- ssl_expired : SSL expire dans moins de 7 jours
- website_offline : site inaccessible
- dns_problem : problème DNS critique
- email_security : problème de configuration email
- security_headers : en-têtes de sécurité manquants
- performance : dégradation de performance
- score_drop : baisse du score de santé
- scan_failed : échec du scan
- monitoring_disabled : monitoring désactivé

Valeurs de severity :
- info : information
- warning : avertissement
- critical : critique

Valeurs de status :
- firing : alerte active
- acknowledged : acquittée par l'utilisateur
- resolved : résolue automatiquement ou manuellement

Méthodes :
- acknowledge(user) : acquitte l'alerte
- resolve() : résout l'alerte

---

### AlertPreference (alerts/models.py)

Champs principaux :
- user : OneToOneField vers User
- ssl_expiring_enabled : alertes SSL expiration activées
- ssl_invalid_enabled : alertes SSL invalide activées
- website_offline_enabled : alertes site hors ligne activées
- dns_problem_enabled : alertes DNS activées
- email_security_enabled : alertes email sécurité activées
- security_headers_enabled : alertes en-têtes sécurité activées
- performance_enabled : alertes performance activées
- score_drop_enabled : alertes baisse de score activées
- scan_failed_enabled : alertes échec scan activées
- ssl_expiry_warning_days : seuil d'avertissement SSL en jours (défaut 30)
- ssl_expiry_critical_days : seuil critique SSL en jours (défaut 7)
- score_drop_threshold : seuil de baisse de score en points (défaut 10)
- consecutive_failures_critical : nombre d'échecs avant escalade critique (défaut 3)
- digest_frequency : fréquence des résumés (immediate, hourly, daily)
- quiet_hours_start : début des heures silencieuses
- quiet_hours_end : fin des heures silencieuses

Méthode :
- is_in_quiet_hours() : retourne True si on est dans les heures silencieuses
  Gère le passage minuit (ex : 22h00 à 07h00)

---

### MuteWindow (alerts/models.py)

Champs principaux :
- user : ForeignKey vers User
- websites : ManyToManyField vers Website (vide = tous les sites)
- start_at : début de la fenêtre de silence
- end_at : fin de la fenêtre de silence
- reason : raison (maintenance, deployment, migration, other)
- note : note libre
- is_active : fenêtre active ou non

Méthode :
- is_currently_muting() : retourne True si la fenêtre est active maintenant

---

### AlertRule (alerts/models.py)

Champs principaux :
- user : ForeignKey vers User
- website : ForeignKey vers Website (null = tous les sites de l'utilisateur)
- name : nom de la règle
- metric : métrique surveillée
- operator : opérateur de comparaison
- threshold : seuil de déclenchement
- severity : sévérité déclenchée
- enabled : règle active ou non
- cooldown_minutes : délai minimum entre deux déclenchements (défaut 60)
- last_triggered_at : dernière fois que la règle s'est déclenchée

Valeurs de metric :
- health_score : score de santé global
- ssl_days_remaining : jours restants sur le certificat SSL
- load_time_ms : temps de chargement en millisecondes
- page_size_kb : taille de la page en kilooctets

Valeurs d'operator :
- gt : supérieur à
- lt : inférieur à
- gte : supérieur ou égal à
- lte : inférieur ou égal à
- eq : égal à

Méthodes :
- evaluate(value) : retourne True si la valeur déclenche la règle
- is_in_cooldown() : retourne True si la règle est en période de cooldown

---

### NotificationChannel (notifications/models.py)

Champs principaux :
- user : ForeignKey vers User
- channel_type : type de canal
- name : nom du canal
- enabled : canal actif
- config : configuration JSON spécifique au provider
- severities : liste des sévérités filtrées (vide = toutes)
- alert_types : liste des types d'alertes filtrés (vide = tous)

Valeurs de channel_type :
- email : envoi par email
- slack : webhook Slack
- discord : webhook Discord
- webhook : webhook personnalisé
- sms : SMS (provider à intégrer)

Configuration par type :
- email : {"email": "destinataire@example.com"}
- slack : {"webhook_url": "https://hooks.slack.com/..."}
- discord : {"webhook_url": "https://discord.com/api/webhooks/..."}
- webhook : {"url": "https://...", "secret": "clé-secrète-optionnelle"}

Méthode :
- matches(severity, alert_type) : retourne True si ce canal doit recevoir cette alerte

---

### Report (reports/models.py)

Champs principaux :
- id : UUID
- user : ForeignKey vers User
- website : ForeignKey vers Website
- period : période du rapport (weekly ou monthly)
- period_start, period_end : dates de début et fin
- status : état du rapport (pending, generated, failed)
- current_score : score actuel en fin de période
- previous_score : score en début de période
- score_change : différence (positif = amélioration)
- check_breakdown : score moyen par catégorie (JSON)
- improvements : liste des points positifs (JSON)
- problems : liste des problèmes détectés (JSON)
- recommendations : liste des actions recommandées (JSON)
- score_history : historique des scores sur la période (JSON)
- total_scans : nombre de scans sur la période
- generated_at : date de génération

Propriété calculée :
- score_trend : "up" si score_change > 0, "down" si < 0, "stable" si = 0, "neutral" si null

---

### ReviewSource (reviews/models.py)

Champs principaux :
- user : ForeignKey vers User
- website : ForeignKey vers Website
- provider : plateforme d'avis (google, trustpilot, tripadvisor, manual)
- name : nom de la source
- config : configuration JSON (place_id, etc.)
- enabled : source active
- last_synced_at : dernière synchronisation

---

### Review (reviews/models.py)

Champs principaux :
- id : UUID
- source : ForeignKey vers ReviewSource
- external_id : identifiant sur la plateforme externe
- author_name, author_photo : données auteur
- rating : note de 0 à 5
- text : contenu de l'avis
- sentiment : positive, neutral, negative
- is_approved : avis approuvé pour affichage
- review_date : date de l'avis sur la plateforme
- raw_data : données brutes JSON de la plateforme

---

### ResponseDraft (reviews/models.py)

Champs principaux :
- review : OneToOneField vers Review
- user : ForeignKey vers User
- content : texte du brouillon de réponse
- status : état (draft, approved, sent)
- sent_at : date d'envoi

---

### Plan (subscriptions/models.py)

Champs principaux :
- tier : free, pro ou business (unique)
- name, description
- price_monthly, price_yearly
- max_websites : nombre maximum de sites
- max_scans_per_month : scans mensuels maximum
- min_scan_interval : intervalle minimum de surveillance
- can_export_reports : export PDF possible
- can_use_api : accès API possible
- can_add_team_members : ajout de membres d'équipe
- max_team_members : nombre maximum de membres
- max_alert_channels : nombre maximum de canaux de notification
- features : liste des fonctionnalités (JSON)
- is_active : plan disponible

Plans par défaut créés par la commande create_plans :

| Plan     | Prix mensuel | Sites max | Scans/mois | Intervalle min |
|----------|-------------|-----------|------------|----------------|
| Free     | 0 EUR       | 1         | 10         | 24h            |
| Pro      | 19 EUR      | 10        | 500        | 1h             |
| Business | 49 EUR      | 50        | 5000       | 5m             |

---

### Subscription (subscriptions/models.py)

Champs principaux :
- id : UUID
- user : OneToOneField vers User
- plan : ForeignKey vers Plan
- status : état de l'abonnement
- billing_cycle : mensuel ou annuel
- started_at : date de début
- current_period_start, current_period_end : période courante
- cancelled_at : date d'annulation
- trial_end : fin de période d'essai
- external_id : ID chez le fournisseur de paiement
- billing_provider : nom du fournisseur (stripe, paddle, etc.)
- billing_metadata : données JSON libres du fournisseur

Valeurs de status :
- active : abonnement actif
- cancelled : annulé
- past_due : paiement en retard
- trialing : en période d'essai
- expired : expiré

Propriétés calculées :
- is_active : True si status est active ou trialing
- is_free : True si le plan est Free

Méthode :
- cancel() : annule l'abonnement

---

## 3. Authentification

### Mécanisme

JWT (JSON Web Tokens) via la bibliothèque djangorestframework-simplejwt.

Deux tokens sont utilisés :
- Access token : durée de vie courte, utilisé pour chaque requête API
- Refresh token : durée de vie longue, utilisé pour obtenir un nouvel access token

Le refresh token est blacklisté après rotation pour empêcher la réutilisation.

### Header requis pour les endpoints authentifiés

```
Authorization: Bearer <access_token>
```

### Endpoints d'authentification

POST /api/v1/auth/register/
Corps : { "email": "user@example.com", "password": "motdepasse12", "full_name": "Jean Dupont" }
Retour : { "access": "...", "refresh": "...", "user": { ... } }

POST /api/v1/auth/login/
Corps : { "email": "user@example.com", "password": "motdepasse12" }
Retour : { "access": "...", "refresh": "...", "user": { ... } }

POST /api/v1/auth/logout/
Corps : { "refresh": "..." }
Effet : blackliste le refresh token (déconnexion)

POST /api/v1/auth/refresh/
Corps : { "refresh": "..." }
Retour : { "access": "...", "refresh": "..." }

GET /api/v1/auth/me/
Retour : { "id": "uuid", "email": "...", "full_name": "...", ... }

POST /api/v1/auth/password/reset/
Corps : { "email": "user@example.com" }
Effet : envoie un email de réinitialisation

POST /api/v1/auth/password/reset/confirm/
Corps : { "token": "...", "password": "nouveaumotdepasse12" }
Effet : réinitialise le mot de passe

---

## 4. Scanners

Tous les scanners se trouvent dans le dossier scanners/ et héritent de scanners/base.py.

### Structure d'un ScanResult

Chaque scanner retourne un objet ScanResult avec les champs suivants :
- status : healthy, warning, critical ou neutral
- score : score numérique entre 0 et le poids maximum de la catégorie
- message : message lisible par l'utilisateur non technique
- details : dictionnaire Python avec les données techniques brutes
- recommendation : action recommandée pour améliorer le score
- duration_ms : durée d'exécution du scanner en millisecondes

### Scanner 1 — Website (scanners/website.py)

Vérifie la disponibilité HTTP et HTTPS du site web.
Contrôle les redirections (www vers non-www et inversement).
Vérifie que le code de réponse HTTP est 200.
Score maximum : 20 points

### Scanner 2 — SSL (scanners/ssl.py)

Vérifie la validité du certificat SSL/TLS.
Calcule le nombre de jours restants avant expiration.
Vérifie la chaîne de certification complète.
Score maximum : 20 points

Données techniques retournées :
- is_valid : certificat valide ou non
- days_until_expiry : jours restants
- issuer : émetteur du certificat
- subject : sujet du certificat
- expires_at : date d'expiration

### Scanner 3 — DNS (scanners/dns.py)

Vérifie les enregistrements DNS du domaine.
Contrôle les enregistrements A, AAAA, MX et NS.
Vérifie la propagation DNS.
Score maximum : 15 points

### Scanner 4 — Email Security (scanners/email_security.py)

Vérifie SPF (Sender Policy Framework) : autorise les serveurs à envoyer des emails.
Vérifie DKIM (DomainKeys Identified Mail) : signature cryptographique des emails.
Vérifie DMARC (Domain-based Message Authentication) : politique de gestion des échecs.
Score maximum : 15 points

### Scanner 5 — Security Headers (scanners/security_headers.py)

Vérifie les en-têtes HTTP de sécurité :
- Content-Security-Policy (CSP) : contrôle les ressources chargées
- Strict-Transport-Security (HSTS) : force HTTPS
- X-Frame-Options : protège contre le clickjacking
- X-Content-Type-Options : empêche le MIME sniffing
- Referrer-Policy : contrôle les informations référant

Score maximum : 15 points

### Scanner 6 — Performance (scanners/performance.py)

Mesure le temps de réponse total du serveur (load_time_ms).
Mesure la taille de la page principale (page_size_kb).
Score maximum : 15 points

Données techniques retournées :
- load_time_ms : temps de chargement en millisecondes
- page_size_kb : taille de la page en kilooctets

### Scanner 7 — Uptime (scanners/uptime.py)

Calcule le taux de disponibilité historique à partir des scans passés.
Ce scanner n'a pas de score pondéré car il suit la disponibilité dans le temps.

---

## 5. Système de scoring

### Pondération des catégories

```
website          : 20 points (20%)
ssl              : 20 points (20%)
dns              : 15 points (15%)
email_security   : 15 points (15%)
security_headers : 15 points (15%)
performance      : 15 points (15%)
uptime           : non pondéré (suivi séparé)
Total maximum    : 100 points
```

### Niveaux de santé

```
80 à 100 points : healthy (Bon, couleur verte)
60 à 79 points  : warning (Attention, couleur orange)
0 à 59 points   : critical (Critique, couleur rouge)
null            : neutral (Non mesuré, couleur grise)
```

### Calcul du score global

Le score global est calculé dans scans/services/scoring.py.
La fonction recalculate_scan_health(scan) :
1. Récupère tous les CheckResult du scan
2. Exclut la catégorie uptime
3. Additionne tous les scores non-null
4. Détermine health_status selon le total
5. Sauvegarde health_score et health_status sur le Scan

---

## 6. Protection SSRF

La protection contre les attaques SSRF (Server-Side Request Forgery) est
implémentée dans core/security.py et appliquée à tous les scanners.

### Plages d'adresses IP bloquées

```
127.0.0.0/8       # Loopback (localhost)
10.0.0.0/8        # Réseau privé (RFC 1918)
172.16.0.0/12     # Réseau privé (RFC 1918)
192.168.0.0/16    # Réseau privé (RFC 1918)
169.254.0.0/16    # Link-local (APIPA)
169.254.169.254   # Métadonnées AWS/cloud
::1               # Loopback IPv6
fe80::/10         # Link-local IPv6
fc00::/7          # Unique local IPv6
fd00:ec2::254     # Métadonnées IPv6 AWS
```

### Mesures de protection appliquées

Mesure 1 : Validation du domaine
Avant toute requête, le domaine est validé avec validate_domain_for_scan().
Les noms d'hôtes internes (localhost, metadata, etc.) sont rejetés immédiatement.

Mesure 2 : Résolution DNS et re-validation
Le domaine est résolu en adresse IP via DNS.
L'adresse IP résolue est re-validée contre la liste des plages bloquées.
Un domaine qui résout vers une IP privée est rejeté.

Mesure 3 : Transport sécurisé
urllib3 est utilisé avec vérification SNI et hostname.
La vérification du certificat est activée.

Mesure 4 : Gestion des redirections
Les redirections HTTP sont suivies manuellement (pas automatiquement).
Maximum 3 redirections autorisées.
Chaque URL de redirection est re-validée.

Mesure 5 : Ports autorisés
Seuls les ports 80 (HTTP) et 443 (HTTPS) sont autorisés.
Tout autre port est rejeté.

Mesure 6 : Schémas autorisés
Seuls les schémas http:// et https:// sont autorisés.
Les schémas file://, ftp://, etc. sont rejetés.

Mesure 7 : Timeouts
Toutes les requêtes réseau ont un timeout configuré.
Aucune requête ne peut bloquer indéfiniment.

---

## 7. Monitoring planifié

### MonitoringConfig

Un MonitoringConfig est créé automatiquement pour chaque Website
via le signal post_save dans monitoring/signals.py.

Configuration par défaut :
- enabled : True
- interval : 24h
- next_scan_at : maintenant (éligible immédiatement)

### Tâche Beat : run_due_monitors

Fréquence d'exécution : toutes les 5 minutes

Algorithme d'exécution :

```
1. Sélectionner tous les MonitoringConfig où :
   - enabled = True
   - next_scan_at <= maintenant

2. Pour chaque MonitoringConfig :

   a. Vérifier les MuteWindows actifs
      Si un MuteWindow couvre ce website :
        - Mettre next_scan_at = maintenant + 1 heure
        - Continuer au suivant

   b. Créer un Scan :
      - website = config.website
      - trigger = MONITORING
      - status = QUEUED

   c. Lancer run_authenticated_scan.delay(scan.id)

   d. Mettre à jour le planning :
      - last_scan_at = maintenant
      - next_scan_at = maintenant + interval + jitter aléatoire (0-5 min)
```

### Jitter

Un délai aléatoire de 0 à 5 minutes est ajouté à next_scan_at.
Cela évite que tous les sites configurés avec le même intervalle
se scannent exactement en même temps (pics de charge).

### Escalation automatique

Après chaque scan de monitoring :
- Si le scan est en échec : consecutive_failures++ et escalation_level mis à jour
- Si le scan réussit : consecutive_failures = 0 et escalation_level = 0

Règles d'escalation :
- 1 ou 2 échecs consécutifs : escalation_level = 1 (warning)
- 3 échecs ou plus : escalation_level = 2 (critical)

---

## 8. Système d'alertes

### Fonctionnement de detect_alerts

La tâche detect_alerts est appelée automatiquement à la fin de chaque scan
via run_authenticated_scan dans scans/tasks.py.

Étapes d'exécution :
1. Charger le Scan et ses résultats
2. Charger les AlertPreference de l'utilisateur
3. Vérifier les MuteWindows actifs (si actif, arrêter)
4. Pour chaque type d'alerte : vérifier la condition et créer si nécessaire
5. Déduplication : ne pas créer si une alerte du même type est déjà FIRING
6. Sauvegarder les nouvelles alertes et déclencher les notifications
7. Auto-résoudre les alertes dont la condition n'existe plus

### Conditions de déclenchement par type

ssl_expiring :
- Condition : days_until_expiry <= ssl_expiry_warning_days (défaut 30)
- Sévérité : WARNING

ssl_expired :
- Condition : days_until_expiry <= ssl_expiry_critical_days (défaut 7)
- Sévérité : calculée par compute_severity()

ssl_invalid :
- Condition : is_valid = False dans les détails du check SSL
- Sévérité : CRITICAL immédiat

website_offline :
- Condition : CheckResult de catégorie "website" a status = "critical"
- Sévérité : calculée par compute_severity()

dns_problem :
- Condition : CheckResult de catégorie "dns" a status = "critical"
- Sévérité : calculée par compute_severity()

security_headers :
- Condition : CheckResult de catégorie "security_headers" a status = "critical"
- Sévérité : WARNING (problème non urgent)

performance :
- Condition : CheckResult de catégorie "performance" a status = "critical"
- Sévérité : WARNING

score_drop :
- Condition : score actuel - score précédent >= score_drop_threshold (défaut 10)
- Sévérité : calculée par compute_severity()

### Logique d'escalation (core/escalation.py)

```
Fonction compute_severity(check_severity, consecutive_failures, preferences) :

Si check_severity == "critical" :
    Retourner "critical"  (critique immédiat sans condition)

Si consecutive_failures >= consecutive_failures_critical :
    Retourner "critical"  (escalade après N échecs)

Si check_severity == "warning" ou consecutive_failures >= 1 :
    Retourner "warning"

Sinon :
    Retourner "info"
```

### Auto-résolution des alertes

Après chaque scan complété, les alertes FIRING sont examinées.
Si la condition ayant déclenché l'alerte n'existe plus dans le scan actuel,
l'alerte passe automatiquement à status = RESOLVED.

Exemples :
- Alerte website_offline : résolue si le check website n'est plus "critical"
- Alerte ssl_expiring : résolue si le check ssl est "healthy" ou "warning"
- Alerte dns_problem : résolue si le check dns n'est plus "critical"

### MuteWindows

Un MuteWindow définit une fenêtre de temps pendant laquelle les alertes
sont supprimées pour un ou plusieurs sites web.

Cas d'utilisation typiques :
- Maintenance planifiée : le site sera intentionnellement indisponible
- Déploiement : des changements sont en cours, les alertes seraient du bruit
- Migration : le DNS va changer temporairement

Comportement :
- Si websites est vide : s'applique à tous les sites de l'utilisateur
- Si websites contient des sites : s'applique uniquement à ces sites
- Pendant un MuteWindow actif : aucune alerte n'est créée ni envoyée
- Le monitoring planifié reporte le scan de 1 heure si le site est muté

### Quiet hours

Les quiet hours sont configurées dans AlertPreference.
Pendant ces heures, les notifications ne sont pas envoyées.
Les alertes sont tout de même créées en base de données.
Gère les plages qui traversent minuit (ex : 22h00 à 07h00).

---

## 9. Notifications

### Architecture des providers

Tous les providers héritent de notifications/providers/base.py :

```python
class NotificationProvider(ABC):
    def send(self, alert, user) -> bool:
        # Envoie la notification
        # Retourne True si succès, False si échec

    def validate_config(self) -> list[str]:
        # Retourne la liste des erreurs de configuration
        # Liste vide = configuration valide
```

### Provider Email

Configuration requise : {"email": "destinataire@example.com"}

Format de l'email envoyé :
- Sujet : [CRITICAL] ou [WARNING] + titre de l'alerte
- Corps : message + domaine + type + sévérité

### Provider Slack

Configuration requise : {"webhook_url": "https://hooks.slack.com/..."}

Format Slack :
- Message principal avec icône selon la sévérité
- Attachment coloré (rouge pour critique, orange pour warning)
- Champs : website, type, message

### Provider Discord

Configuration requise : {"webhook_url": "https://discord.com/api/webhooks/..."}

Format Discord :
- Embed avec couleur selon la sévérité
- Champs : website, type
- Timestamp de l'alerte

### Provider Webhook

Configuration requise : {"url": "https://...", "secret": "optionnel"}

Payload JSON envoyé :
- id : UUID de l'alerte
- alert_type : type d'alerte
- severity : sévérité
- status : état
- title : titre
- message : message
- website : domaine
- created_at : timestamp

Si secret est configuré, l'en-tête X-Presence-Secret est ajouté.

### Flux du dispatcher (notifications/dispatcher.py)

```
Étape 1 : Vérifier les quiet hours de l'utilisateur
          Si on est dans les quiet hours -> arrêter (retourner [])

Étape 2 : Vérifier les MuteWindows actifs
          Si le site est muté -> arrêter (retourner [])

Étape 3 : Charger tous les NotificationChannel de l'utilisateur (enabled=True)

Étape 4 : Pour chaque canal :
          a. channel.matches(severity, alert_type) ?
             Si non -> passer au suivant
          b. get_provider(channel) pour obtenir le provider
          c. provider.send(alert, user)
          d. Si succès -> ajouter à sent_channels

Étape 5 : Sauvegarder sent_channels dans alert.notification_channels_sent
```

---

## 10. Rapports

### Génération d'un rapport

Endpoint : POST /api/v1/reports/generate/
Corps : { "website_id": 1, "period": "monthly", "period_start": "2024-01-01" }

Traitement :
1. La vue crée un objet Report avec status=PENDING
2. La tâche Celery generate_report est lancée en asynchrone
3. La vue retourne 202 Accepted avec le rapport en attente
4. Celery génère les données et passe le rapport à status=GENERATED

### Service de génération (reports/services.py)

La fonction generate_report_data(website, period_start, period_end) :
1. Récupère tous les Scan COMPLETED sur la période
2. Calcule le score actuel (dernier scan) et précédent (premier scan)
3. Calcule le score_change
4. Calcule le check_breakdown : score moyen par catégorie
5. Identifie les improvements (checks healthy) et problems (checks critiques)
6. Compile les recommendations de tous les CheckResult
7. Construit l'historique des scores (score_history)

### Contenu du check_breakdown

Pour chaque catégorie :
- avg_score : score moyen sur la période
- critical_count : nombre de fois où le check était critique
- warning_count : nombre de fois où le check était en warning
- healthy_count : nombre de fois où le check était sain

### Tâche Beat mensuelle

Tâche : generate_monthly_reports
Fréquence : 1er de chaque mois à 3h00 UTC

Fonctionnement :
1. Calcule la période du mois précédent
2. Pour chaque Website actif :
   a. Crée un Report si il n'existe pas déjà pour cette période
   b. Lance generate_report.delay(report_id)

---

## 11. Avis clients

### Architecture provider

Inspirée du pattern Adapter/Strategy pour permettre l'ajout futur de plateformes.

```
reviews/providers/
├── base.py      # ReviewProvider (ABC)
└── manual.py    # ManualReviewProvider
```

La classe ReviewProvider définit l'interface commune :
- fetch_reviews(limit) : récupère les avis depuis la plateforme
- validate_config() : valide la configuration
- get_average_rating(reviews) : calcule la note moyenne

### ManualReviewProvider

Provider pour la saisie manuelle d'avis via l'API.
fetch_reviews() retourne une liste vide (pas de plateforme externe).
Les avis sont créés directement via POST /api/v1/reviews/.

### Ajout d'un nouveau provider

Pour ajouter Google Reviews par exemple :
1. Créer reviews/providers/google.py héritant de ReviewProvider
2. Implémenter fetch_reviews() avec l'API Google Places
3. Implémenter validate_config() pour vérifier place_id
4. Enregistrer dans reviews/providers/__init__.py

### Workflow des avis

1. Créer une ReviewSource avec le provider choisi
2. Les avis arrivent via fetch (automatique) ou via POST manuel
3. Les avis peuvent être approuvés : is_approved = True
4. Un ResponseDraft peut être créé pour préparer une réponse
5. Le draft passe par draft -> approved -> sent

---

## 12. Abonnements

### Architecture provider-independent

Le modèle Subscription ne contient aucune dépendance vers un fournisseur de paiement.
Les champs billing_provider, external_id et billing_metadata permettent
d'intégrer n'importe quel fournisseur sans modifier le modèle.

Pour intégrer Stripe :
1. Créer un webhook Stripe
2. À la réception du webhook :
   a. Mettre à jour subscription.external_id avec l'ID Stripe
   b. Mettre à jour subscription.billing_provider = "stripe"
   c. Mettre à jour subscription.status selon l'événement Stripe
   d. Sauvegarder les données Stripe dans subscription.billing_metadata

### Endpoints d'abonnement

GET /api/v1/subscriptions/plans/
Retourne tous les plans actifs. Endpoint public (sans authentification).

GET /api/v1/subscriptions/me/
Retourne l'abonnement de l'utilisateur connecté avec les détails du plan.

POST /api/v1/subscriptions/upgrade/
Corps : { "plan_tier": "pro", "billing_cycle": "monthly" }
Change le plan de l'utilisateur (sans traitement de paiement).

POST /api/v1/subscriptions/cancel/
Annule l'abonnement (status = cancelled, cancelled_at = maintenant).
Non disponible pour le plan Free.

### Signal de création automatique

À la création d'un User, un abonnement Free est créé automatiquement
si le plan Free existe en base de données.

Commande pour créer les plans : docker compose exec web python manage.py create_plans

---

## 13. Tâches Celery

### Configuration Celery (config/celery.py)

Broker : Redis (CELERY_BROKER_URL)
Backend : Redis (CELERY_RESULT_BACKEND)
Sérialisation : JSON
Timezone : UTC
Time limit : 60 secondes par tâche
Soft time limit : 45 secondes

### Beat Schedule complet

```
run-due-monitors :
  Tâche : monitoring.tasks.run_due_monitors
  Fréquence : toutes les 5 minutes
  Rôle : déclenche les scans de monitoring planifiés

cleanup-old-alerts :
  Tâche : alerts.tasks.cleanup_old_alerts
  Fréquence : tous les jours à 2h00 UTC
  Rôle : supprime les alertes RESOLVED de plus de 90 jours

generate-monthly-reports :
  Tâche : reports.tasks.generate_monthly_reports
  Fréquence : le 1er de chaque mois à 3h00 UTC
  Rôle : génère les rapports mensuels pour tous les sites actifs
```

### Toutes les tâches disponibles

run_authenticated_scan(scan_id) dans scans/tasks.py :
- Exécute les 7 scanners pour un scan authentifié
- Met à jour les CheckResult
- Calcule le score final
- Déclenche detect_alerts

run_due_monitors() dans monitoring/tasks.py :
- Sélectionne les MonitoringConfig dus
- Crée les Scan de monitoring
- Planifie les prochaines exécutions
- Retourne {"queued": N, "skipped": N}

detect_alerts(scan_id) dans alerts/tasks.py :
- Analyse les résultats du scan
- Crée les alertes selon les conditions
- Déduplique les alertes existantes
- Déclenche le dispatcher de notifications
- Auto-résout les alertes obsolètes
- Retourne {"created": N, "resolved": N}

cleanup_old_alerts() dans alerts/tasks.py :
- Supprime les alertes RESOLVED de plus de 90 jours
- Retourne {"deleted": N}

generate_report(report_id) dans reports/tasks.py :
- Génère les données du rapport
- Met à jour le Report
- Passe le status à GENERATED ou FAILED
- Retourne {"status": "generated", "report_id": "..."}

generate_monthly_reports() dans reports/tasks.py :
- Calcule la période du mois précédent
- Crée les Report pour tous les sites actifs
- Lance generate_report pour chacun
- Retourne {"created": N}

---

## 14. API Reference

### Codes de réponse HTTP

200 OK : Requête réussie
201 Created : Ressource créée avec succès
202 Accepted : Requête acceptée, traitement asynchrone en cours
400 Bad Request : Données invalides ou manquantes
401 Unauthorized : Token manquant ou invalide
403 Forbidden : Accès refusé (pas propriétaire de la ressource)
404 Not Found : Ressource introuvable
429 Too Many Requests : Limite de débit dépassée
500 Internal Server Error : Erreur serveur interne

### Format des erreurs

```json
{
  "detail": "Message d'erreur lisible"
}
```

Ou pour les erreurs de validation :
```json
{
  "field_name": ["Message d'erreur pour ce champ"],
  "other_field": ["Autre erreur"]
}
```

### Pagination

Toutes les listes sont paginées. Format de réponse :
```json
{
  "count": 42,
  "next": "http://localhost:8080/api/v1/alerts/?page=2",
  "previous": null,
  "results": [...]
}
```

Taille de page par défaut : 50 éléments

### Format des dates

Toutes les dates sont en ISO 8601 avec timezone UTC :
- Exemple : 2024-01-15T10:30:00Z
- Exemple avec offset : 2024-01-15T11:30:00+01:00

### Rate Limiting

Endpoint de création de scan public :
- Limite : 10 requêtes par heure par IP
- Code si dépassé : 429 Too Many Requests

Endpoint de polling scan public :
- Limite : 120 requêtes par minute par IP

### Filtres disponibles

Alertes : ?status=firing&severity=critical&alert_type=ssl_expiring&website_id=1
Rapports : ?website_id=1&period=monthly
Avis : ?source_id=1&approved=true&sentiment=negative

---

## 15. Sécurité

### Ownership Isolation

Tous les ViewSets et APIViews filtrent les données par utilisateur connecté.
Un utilisateur ne peut jamais voir, modifier ou supprimer les données d'un autre.

Exemple dans chaque vue :
```python
def get_queryset(self):
    return Website.objects.filter(owner=self.request.user)
```

Cela s'applique à : websites, scans, monitoring configs, alerts, reports,
reviews, subscriptions, notification channels, mute windows, alert rules.

### JWT Blacklist

À la déconnexion, le refresh token est ajouté à la blacklist.
Un token blacklisté ne peut plus être utilisé pour obtenir un nouvel access token.
Cela simule une vraie déconnexion malgré la nature stateless du JWT.

### Validation des domaines

Les domaines sont validés avec une regex stricte avant tout traitement.
Format autorisé : lettres, chiffres, tirets, points uniquement.
Longueur maximum : 253 caractères (RFC 1035).
Pas de schéma (http://), pas de chemin (/page), pas de port (:8080).

### Validation des mots de passe

Longueur minimum : 12 caractères
Vérification de similarité avec le nom d'utilisateur
Liste des mots de passe communs bloqués
Mots de passe entièrement numériques refusés

### Variables d'environnement

Aucun secret n'est codé en dur dans le code source.
Tous les secrets utilisent des variables d'environnement.
Le fichier .env est dans .gitignore.
Un fichier .env.example documente les variables requises.

---

## 16. Tests

### Résumé de la couverture

Total : 168 tests passants

| Module | Nombre de tests | Ce qui est testé |
|--------|----------------|------------------|
| accounts | ~20 | Register, login, logout, JWT, password reset |
| websites | ~15 | CRUD, ownership isolation |
| scans | ~15 | Scoring, state machine, permissions |
| core | 26 | Protection SSRF (toutes les plages IP) |
| monitoring | 8 | Signal, schedule, escalation, méthodes |
| alerts | 26 | Models, signals, quiet hours, règles |
| reports | 8 | Models, service, contrainte unique |
| reviews | 5 | Source, review, draft |
| subscriptions | 11 | Plans, signal, cancel, propriétés |

### Lancer les tests

```bash
# Tous les tests avec détails
docker compose exec web python manage.py test --verbosity=2

# Un seul module
docker compose exec web python manage.py test accounts.tests --verbosity=2

# Plusieurs modules
docker compose exec web python manage.py test monitoring.tests alerts.tests --verbosity=2

# Vérification Django avant les tests
docker compose exec web python manage.py check
```

### Stratégie de test

Tests unitaires :
- Méthodes des modèles (acknowledge, resolve, evaluate, is_in_cooldown, etc.)
- Services (generate_report_data, compute_severity, should_create_alert)
- Providers de notification (validate_config, send)

Tests d'intégration :
- Endpoints API avec base de données réelle
- Signaux Django (création automatique d'objets liés)
- Contraintes de base de données

Tests de sécurité :
- Protection SSRF (26 cas de test couvrant toutes les plages IP)
- Ownership isolation (un utilisateur ne peut pas accéder aux données d'un autre)
- Permissions (endpoints authentifiés refusent les requêtes sans token)

### Exemple de test d'ownership

```python
def test_ownership_isolation(self):
    # User A ne peut pas voir les sites de User B
    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_user_b}")
    response = self.client.get(f"/api/v1/websites/{site_user_a.pk}/")
    self.assertEqual(response.status_code, 404)
    # 404 et non 403 pour ne pas révéler l'existence de la ressource
```

---

## Annexe — Commandes utiles

```bash
# Créer les plans d'abonnement (requis au premier démarrage)
docker compose exec web python manage.py create_plans

# Créer un compte administrateur
docker compose exec web python manage.py createsuperuser

# Générer les migrations après modification d'un modèle
docker compose exec web python manage.py makemigrations

# Appliquer les migrations
docker compose exec web python manage.py migrate

# Vérifier la configuration Django
docker compose exec web python manage.py check

# Accéder au shell Python Django
docker compose exec web python manage.py shell

# Voir tous les endpoints disponibles
docker compose exec web python manage.py shell -c "
from django.urls import get_resolver
def list_urls(r, prefix=''):
    for p in r.url_patterns:
        if hasattr(p, 'url_patterns'):
            list_urls(p, prefix + str(p.pattern))
        else:
            print(prefix + str(p.pattern))
list_urls(get_resolver())
" | grep api | sort

# Logs en temps réel
docker compose logs -f web
docker compose logs -f celery-worker
docker compose logs -f celery-beat

# Rebuild et redémarrage complet
docker compose build web
docker compose up -d