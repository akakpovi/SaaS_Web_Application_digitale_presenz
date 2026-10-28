#!/usr/bin/env bash
# Vérifie qu'une sauvegarde PostgreSQL est réellement restaurable.
#
# La restauration se fait dans une base jetable (presence_restore_check),
# jamais dans la base de production : la preuve est ainsi sans risque.
#
# Usage:
#   bash scripts/verify_backup_restore.sh [chemin/vers/postgres-*.dump]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DUMP="${1:-$(ls -t backups/postgres-*.dump 2>/dev/null | head -1 || true)}"
[ -n "$DUMP" ] && [ -f "$DUMP" ] || {
  echo "Aucun dump PostgreSQL trouvé. Lancez scripts/backup.sh." >&2
  exit 1
}

echo "==> Dump : $DUMP"
echo "==> Empreinte locale"
(cd "$(dirname "$DUMP")" && sha256sum "$(basename "$DUMP")")

RESTORE_DB="presence_restore_check_$(date +%s)"

cleanup() {
  docker compose exec -T db sh -c "dropdb -U \"\$POSTGRES_USER\" --if-exists '$RESTORE_DB'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Création de la base jetable $RESTORE_DB"
docker compose exec -T db sh -c "createdb -U \"\$POSTGRES_USER\" '$RESTORE_DB'"

echo "==> Restauration (pg_restore)"
# --no-owner : le dump a été pris avec cette option ; les rôles locaux diffèrent.
docker compose exec -T db sh -c \
  "pg_restore -U \"\$POSTGRES_USER\" -d '$RESTORE_DB' --no-owner --exit-on-error" \
  < "$DUMP"

echo "==> Contrôles d'intégrité"
docker compose exec -T db sh -c \
  "psql -U \"\$POSTGRES_USER\" -d '$RESTORE_DB' -v ON_ERROR_STOP=1 -c \
  \"SELECT (SELECT count(*) FROM information_schema.tables WHERE table_schema='public') AS tables, \
           (SELECT count(*) FROM accounts_user) AS users, \
           (SELECT count(*) FROM websites_website) AS websites, \
           (SELECT count(*) FROM scans_scan) AS scans;\""

echo "OK — la sauvegarde se restaure sans erreur."
