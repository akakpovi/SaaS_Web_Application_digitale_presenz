#!/usr/bin/env bash
# Sauvegarde préalable AVANT toute modification (Phase 1 — Stabilisation).
# - pg_dump logique de la base "presence" (pile live)
# - archive tar du volume Docker postgres_data (copie physique)
# Usage: bash scripts/backup_pre_remediation.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
mkdir -p "$BACKUP_DIR"

DB_CONTAINER="${DB_CONTAINER:-saas_web_application_digitale_presenz-db-1}"
DB_NAME="${DB_NAME:-presence}"
DB_USER="${DB_USER:-presence}"
VOLUME_NAME="${VOLUME_NAME:-saas_web_application_digitale_presenz_postgres_data}"

echo "==> 1/2  pg_dump (logique) ${DB_NAME} @ ${DB_CONTAINER}"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges \
  | gzip > "$BACKUP_DIR/presence_full_${TS}.sql.gz"
echo "    -> $BACKUP_DIR/presence_full_${TS}.sql.gz"

echo "==> 2/2  archive du volume ${VOLUME_NAME}"
docker run --rm \
  -v "${VOLUME_NAME}:/data:ro" \
  -v "${BACKUP_DIR}:/backup" \
  alpine:3.20 \
  tar czf "/backup/postgres_data_${TS}.tar.gz" -C /data .
echo "    -> $BACKUP_DIR/postgres_data_${TS}.tar.gz"

echo "==> Sauvegardes terminées : $BACKUP_DIR"
