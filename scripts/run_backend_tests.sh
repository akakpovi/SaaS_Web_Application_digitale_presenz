#!/usr/bin/env bash
# Exécute la suite de tests Django contre l'ARBRE DE TRAVAIL (bind mount),
# et non contre le code cuit dans l'image Docker.
#
# Indispensable : l'image `web` embarque une copie du code. Sans ce montage,
# `docker exec <web> python manage.py test` teste une version périmée.
#
# Usage:
#   bash scripts/run_backend_tests.sh                  # toute la suite
#   bash scripts/run_backend_tests.sh public_checker   # une app / un module
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_DIR="$ROOT_DIR/SaaS_Web_Application_digitale_presenz_v2/backend"
TARGET="${*:-}"

# Les tests tournent avec un module de réglages dédié : le `.env` peut être
# en configuration de production (SECURE_SSL_REDIRECT=True) sans casser la
# suite, qui s'exécute ici sur du HTTP en clair.
#
# `--noinput` : une exécution interrompue laisse la base `test_presence`
# derrière elle. Sans ce drapeau, Django demande interactivement s'il faut la
# supprimer et la commande se bloque (EOF ou attente d'une frappe) au lieu de
# relancer la suite — un piège silencieux en CI comme en local.
docker compose run --rm --no-deps --user "0:0" \
  -e DJANGO_SETTINGS_MODULE=config.settings.test \
  -v "$BACKEND_DIR":/app \
  web python manage.py test --noinput $TARGET
