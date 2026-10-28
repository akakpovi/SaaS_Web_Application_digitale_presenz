#!/usr/bin/env bash
# Restauration RÉELLE (destructive) de PostgreSQL / Redis.
#
# Usage:
#   bash scripts/restore.sh backups/postgres-20261021T033000Z.dump --yes
#   bash scripts/restore.sh backups/redis-20261021T033000Z.rdb.gz --yes
#
# Sans --yes, le script demande une confirmation explicite : la base actuelle
# est écrasée.  Pour une simple vérification non destructive, préférez
# scripts/verify_backup_restore.sh.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FILE="${1:-}"
CONFIRM="${2:-}"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Usage: bash scripts/restore.sh <fichier.dump|fichier.rdb.gz> --yes" >&2
  exit 2
fi

echo "ATTENTION : cette opération écrase les données actuelles."
echo "Fichier : $FILE"
if [ "$CONFIRM" != "--yes" ]; then
  read -r -p "Tapez 'RESTORE' pour confirmer : " answer
  [ "$answer" = "RESTORE" ] || { echo "Annulé."; exit 1; }
fi

case "$FILE" in
  *.dump)
    echo "==> Arrêt des services applicatifs"
    docker compose stop web celery-worker celery-beat >/dev/null

    echo "==> Restauration PostgreSQL"
    docker compose exec -T db sh -c \
      'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
      < "$FILE"

    echo "==> Redémarrage"
    docker compose start web celery-worker celery-beat >/dev/null
    ;;
  *.rdb.gz)
    echo "==> Arrêt de Redis"
    docker compose stop redis >/dev/null
    CID="$(docker compose ps -a -q redis)"
    TMP="$(mktemp)"
    gzip -dc "$FILE" > "$TMP"
    docker cp "$TMP" "$CID:/data/dump.rdb"
    rm -f "$TMP"
    docker compose start redis >/dev/null
    ;;
  *)
    echo "Format non reconnu (attendu .dump ou .rdb.gz)." >&2
    exit 2
    ;;
esac

echo "OK — restauration terminée. Vérifiez /api/v1/health/ et les logs."
