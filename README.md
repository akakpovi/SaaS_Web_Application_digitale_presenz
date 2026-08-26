# 🌐 Presence — Monitoring de Présence Digitale

> Surveillance de site web, SSL, DNS, sécurité email, performance et réputation en ligne — depuis un tableau de bord simple.

[![Django](https://img.shields.io/badge/Django-5.1-green)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.15-blue)](https://www.django-rest-framework.org)
[![Tests](https://img.shields.io/badge/Tests-168%20passing-brightgreen)](/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](/)

---

## Table des matières

- [Aperçu](#aperçu)
- [Stack technique](#stack-technique)
- [Architecture](#architecture)
- [Installation rapide](#installation-rapide)
- [Variables d'environnement](#variables-denvironnement)
- [API Endpoints](#api-endpoints)
- [Tests](#tests)
- [Docker](#docker)

---

## Aperçu

Presence est un SaaS de monitoring de présence digitale conçu pour les petites entreprises.
Il surveille automatiquement votre site web et vous alerte en cas de problème.

| Check | Description | Poids |
|-------|-------------|-------|
| Website | Disponibilité HTTP/HTTPS | 20 pts |
| SSL | Validité et expiration du certificat | 20 pts |
| DNS | Configuration des enregistrements | 15 pts |
| Email Security | SPF, DKIM, DMARC | 15 pts |
| Security Headers | CSP, HSTS, X-Frame-Options | 15 pts |
| Performance | Temps de chargement, taille | 15 pts |
| Uptime | Disponibilité historique | non pondéré |

**Score total : 0 à 100 points**

---

## Stack technique

### Backend
- Django 5.1 + Django REST Framework 3.15
- PostgreSQL 16 — base de données principale
- Redis 7 — broker Celery + cache
- Celery 5 — tâches asynchrones
- Celery Beat — tâches planifiées
- JWT via SimpleJWT — authentification

### Frontend
- React 18 + TypeScript
- Vite — build tool
- React Router — navigation
- Tailwind CSS — styles

### Infrastructure
- Docker Compose — orchestration
- Nginx — reverse proxy
- Gunicorn — WSGI server

---

## Architecture
presence/
├── backend/
│ ├── accounts/ # Authentification + User model
│ ├── websites/ # Gestion des sites web
│ ├── scans/ # Résultats de scans + scoring
│ ├── monitoring/ # Configuration du monitoring planifié
│ ├── alerts/ # Alertes + préférences + règles
│ ├── notifications/ # Canaux de notification (email, slack)
│ ├── reports/ # Rapports mensuels/hebdomadaires
│ ├── reviews/ # Avis clients + réponses
│ ├── subscriptions/ # Plans Free/Pro/Business
│ ├── scanners/ # 7 scanners SSRF-safe
│ ├── public_checker/ # Checker public (sans auth)
│ └── core/ # Sécurité SSRF + escalation
├── frontend/
│ └── src/
│ ├── pages/ # 14 pages React
│ └── components/ # Composants UI
└── docker-compose.yml