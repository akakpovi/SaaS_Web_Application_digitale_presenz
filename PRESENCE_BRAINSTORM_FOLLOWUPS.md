# Presence — Brainstorm Follow-ups

## Lot A — Bloquants production (décisions D1–D10)
| # | Décision | Bloquant ? | Statut |
|---|---|---|---|
| D1 | Domaine public | Oui | ⏳ |
| D2 | IP VPS | Oui | ⏳ |
| D3 | Clé Paddle prod | Oui (paiement) | ⏳ |
| D4 | Secret webhook Paddle | Oui (paiement) | ⏳ |
| D5-D7 | SMTP (hôte/user/mdp) | Oui | ⏳ |
| D8-D9 | LinkedIn OAuth | Non | ⏳ |
| D10 | Activer IA | Non | ⏳ |

## Lot B — Corrections résiduelles
| # | Tâche | Effort | Priorité |
|---|---|---|---|
| B1 | Contenu blog DE (6 articles manquants) | Moyen | P2 |
| B2 | Scan Journey UI (paliers) | Élevé | P2 |
| B3 | Score exposition dans résultats | Moyen | P2 |
| B4 | Choix palier au lancement scan | Faible | P2 |
| B5 | Édition profil utilisateur | Moyen | P2 |
| B6 | Changement mot de passe | Moyen | P2 |
| B7 | Messages API localisés (DE/FR) | Moyen | P3 |
| B8 | Umami proxy /analytics/ | Faible | P3 |

## Lot C — Production readiness
| # | Tâche | Effort | Priorité |
|---|---|---|---|
| C1 | TLS Let's Encrypt | Moyen | P1 |
| C2 | Config prod (ALLOWED_HOSTS, CORS) | Moyen | P1 |
| C3 | Paddle checkout widget | Élevé | P1 |
| C4 | SMTP réel | Faible | P1 |
| C5 | Rate limiting (drf-ratelimit) | Moyen | P2 |
| C6 | Monitoring (Sentry) | Moyen | P2 |
| C7 | Backup auto (pg_dump + S3) | Moyen | P2 |
| C8 | Docker images prod (Trivy, non-root) | Moyen | P3 |

## Lot D — Fonctionnalités produit
| # | Tâche | Effort | Priorité |
|---|---|---|---|
| D1 | Scanner SERP | Élevé | P2 |
| D2 | Scanner avis (Trustpilot, Google) | Élevé | P2 |
| D3 | Scanner mentions sociales | Moyen | P3 |
| D4 | Rapport e-réputation global | Moyen | P2 |
| D5 | Alertes email (score baisse) | Moyen | P2 |
| D6 | Rapports PDF export | Moyen | P3 |
| D7 | Historique scores (graphiques) | Moyen | P3 |

## Lot E — Qualité technique
| # | Tâche | Effort | Priorité |
|---|---|---|---|
| E1 | Bandit 28 low restants | Moyen | P3 |
| E2 | Trivy scan images (security.yml) | Moyen | P2 |
| E3 | Couverture tests (pytest-cov) | Élevé | P3 |
| E4 | Load testing (k6/locust) | Moyen | P3 |
| E5 | A11y audit (axe-core E2E) | Moyen | P3 |
| E6 | Lighthouse CI | Moyen | P3 |
