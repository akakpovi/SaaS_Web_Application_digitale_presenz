# Presence — Préparation au déploiement VPS (sans déploiement)

**Date :** 27 octobre 2026
**Statut :** plan de release prêt à exécuter ; **aucune action n'a été effectuée sur le VPS** et aucune ressource distante n'a été mesurée dans cette session.

---

## 1. État de référence local dont le VPS devra partir

- Branche `main` au commit `3b2206f` ; nombreuses modifications locales non commitées (code des missions précédentes + cette session).
- Schéma : **78 migrations appliquées**, aucune en attente (`makemigrations --check` silencieux).
- Images locales reconstruites le 27/10 : `web 45e6cc6dcc76`, `celery-worker ae477d4a538d`, `celery-beat ebc2b4d5a353`, `frontend 38331c457fb9`, `scanner-tools presence-scanner-tools:2026-10-27`, plus `staticfiles` et `scanner-egress-guard`.
- Volumes : `postgres_data`, `redis_data`, `scanner_archive_data`, `media_data`, `static_data` — **aucun volume ne doit être supprimé ni recréé**.
- Services Compose : `web`, `celery-worker`, `celery-beat`, `db`, `redis`, `frontend`, `scanner-tools`, `scanner-egress-guard`, `scanner-sandbox-anchor`, `wordpress`, `wordpress-db`, `wordpress-init`, `mailpit`, `staticfiles`.

---

## 2. Préconditions à vérifier **avant** toute action

1. **Sauvegarde vérifiée** : `scripts/backup.sh` produit un dump horodaté ; la restauration est prouvée par `scripts/verify_backup_restore.sh` sur une base jetable, pas par la seule existence du fichier.
2. **Fenêtre de maintenance** annoncée, et tâches Celery en cours inventoriées (`inspect active/reserved`, files vides ou justifiées).
3. **Espace disque du VPS** : mesurer (`df -hT`, `docker system df -v`) avant de tirer des images ; prévoir ≥ 25 Go libres pour images + archives + média.
4. **Secrets de production** renseignés hors dépôt : clés de la base, `SECRET_KEY`, `ALLOWED_HOSTS`, `FRONTEND_URL`, clés Paddle (le jour où la facturation est activée), identifiants SMTP, `AKA_AI_*`. Aucune clé ne doit être copiée depuis l'environnement local de développement.
5. **Migration `0007_scan_partial_status`** incluse dans l'image déployée (elle est dans le dépôt et appliquée localement) ; les contraintes PostgreSQL de `Scan.status` acceptent `partial`.
6. **Retour arrière défini** : une simple remise à l'ancienne image ne suffit pas après migration de schéma. Le retour arrière autorise (a) le retour de code si la migration est compatible, ou (b) la restauration du dump pré-migration — décision à prendre avant d'appliquer `0007`.

---

## 3. Ordre d'exécution du release

1. **Geler** les écritures : arrêter `celery-beat`, laisser les workers terminer les tâches en cours.
2. **Sauvegarder** (`scripts/backup.sh`), vérifier l'intégrité (`pg_restore --list`), noter l'identifiant du dump.
3. **Construire** les images sur le VPS depuis le commit validé (`docker compose build web celery-worker celery-beat frontend`), noter les digests.
4. **Appliquer les migrations** : `python manage.py migrate` (dans un `web` à jour), puis `manage.py check` et `showmigrations` pour confirmer 78/78.
5. **Recréer uniquement** `web`, `celery-worker`, `celery-beat`, `frontend`, `staticfiles` (`docker compose up -d --no-deps …`) — jamais `-v`, jamais de prune global.
6. **Vérifier le worker réellement actif** : `docker inspect` du montage `scanner_archive_data:/app/scanner-archives`, permissions `0700`/`0600`, test d'écriture/lecture non sensible, puis redémarrage contrôlé du worker et relecture d'une archive.
7. **TLS** : `scripts/enable_letsencrypt.sh` (certificats, renouvellement) ; vérifier la redirection HTTP→HTTPS et `SECURE_*` via `config/settings/production.py`.

---

## 4. Tests de fumée après démarrage

| Contrôle | Commande / observation attendue |
|---|---|
| Santé API | `GET /api/v1/health/…` (ou `https://<domaine>/api/v1/subscriptions/plans/`) → 200 |
| Frontend | page d'accueil 200, assets servis, aucune erreur console |
| Base | `manage.py check`, `showmigrations` : 78/78 |
| Redis / Celery | workers `inspect ping`, file vide, beat planifié (`expire-subscriptions-daily`, `run-due-monitors`) |
| Inscription + connexion | parcours réel avec un compte de test |
| Scan de fumée | scan `health` sur une cible autorisée → statut terminal cohérent, `CheckResult` présents |
| Isolation | deux comptes, vérification 404 croisée |
| AKA IA | une question courte → 200 (ou 503 explicite si la passerelle est indisponible) |
| Facturation | si activée : checkout sandbox → activation par webhook → quota appliqué |

---

## 5. Conditions d'arrêt

- Migration en erreur ou schéma inattendu → **arrêt**, restauration du dump, aucun correctif improvisé.
- Worker monté sans le volume d'archives, ou permissions incorrectes → **arrêt** avant toute mise en service.
- Écart entre le statut d'un scan et ses artefacts (par ex. `completed` sans `CheckResult`) → arrêt et diagnostic, jamais de nouveau scan en boucle.
- Erreurs 5xx répétées ou tâches bloquées → arrêt, retour à l'image précédente si le schéma le permet.

---

## 6. Écarts connus à traiter avant ou pendant le release

| Écart | Action |
|---|---|
| Facturation non configurée (pas de clés, pas de price IDs) | Configurer et valider en sandbox **avant** d'activer `BILLING_ENABLED` en production |
| `AI_ADVISOR_ENABLED=false` | Décider l'activation et le quota IA par forfait (consommation de crédits réels) |
| Politique d'expiration des abonnements | Acter la règle (fin de période, grâce éventuelle) ; la tâche quotidienne est en place |
| Rotation/volumétrie des logs et des archives | Vérifier `LOG_ROTATION`, surveiller `csc_vpnagent` (croissance signalée lors du nettoyage) hors périmètre Presence |
| Espace disque local à 93 % | Libérer ≈12 Go récupérables côté Docker avant d'ajouter des images |
| Aucun test de charge récent | Rejouer `load/k6/presence_load_test.js` (+ `load/k6/host_sampler.py`) sur un environnement isolé |

---

## 7. Critères d'acceptation post-déploiement

- [ ] Sauvegarde pré-release vérifiée et conservée.
- [ ] Migrations appliquées sans perte, 78/78, `check` silencieux.
- [ ] `web`/`celery-worker`/`celery-beat`/`frontend` sur les images attendues (digests notés).
- [ ] Volume d'archives monté et utilisable par le worker réel.
- [ ] Scan réel `completed` avec archive persistante ; scan incomplet `partial`/`failed` sans résolution de constat.
- [ ] Isolation multi-tenant vérifiée sur les données réelles.
- [ ] TLS, redirections et en-têtes de sécurité actifs.
- [ ] Aucun secret dans les logs, l'historique ou les rapports.
- [ ] Rollback documenté et testé au moins sur la base jetable.

**Aucun déploiement réel ne doit être lancé sans validation et autorisation explicites.**
