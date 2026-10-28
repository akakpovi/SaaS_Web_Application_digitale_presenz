#!/usr/bin/env bash
# Sauvegarde PostgreSQL + Redis de la pile canonique.
#
# Écrit dans ./backups :
#   postgres-<UTC>.dump    pg_dump format custom (restaurable avec pg_restore)
#   redis-<UTC>.rdb.gz     snapshot RDB compressé
#   SHA256SUMS-<UTC>       empreintes pour vérifier l'intégrité
#
# Rétention : BACKUP_RETENTION_DAYS (défaut 14 jours).
# Export externe (optionnel) : BACKUP_S3_URI=s3://mon-bucket/presence
#   → nécessite le CLI AWS configuré (ou rclone en adaptant la dernière ligne).
#
# Cron suggéré (quotidien à 03:30, heure du serveur) :
#   30 3 * * * cd /chemin/vers/le/depot && bash scripts/backup.sh >> logs/backup.log 2>&1
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

fail() {
  echo "ERREUR: $*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "docker est requis"
docker compose ps --status running --services | grep -qx db || fail "le service db n'est pas démarré"
docker compose ps --status running --services | grep -qx redis || fail "le service redis n'est pas démarré"

PG_FILE="$BACKUP_DIR/postgres-$STAMP.dump"
REDIS_FILE="$BACKUP_DIR/redis-$STAMP.rdb.gz"

echo "==> PostgreSQL → $PG_FILE"
# Les identifiants restent dans l'environnement du conteneur : rien n'est
# affiché ni écrit dans l'historique shell.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
  > "$PG_FILE"
[ -s "$PG_FILE" ] || fail "pg_dump a produit un fichier vide"

echo "==> Redis → $REDIS_FILE"
docker compose exec -T redis redis-cli SAVE >/dev/null
REDIS_CID="$(docker compose ps -q redis)"
[ -n "$REDIS_CID" ] || fail "conteneur redis introuvable"
TMP_RDB="$(mktemp)"
docker cp "$REDIS_CID:/data/dump.rdb" "$TMP_RDB"
gzip -9 -c "$TMP_RDB" > "$REDIS_FILE"
rm -f "$TMP_RDB"
[ -s "$REDIS_FILE" ] || fail "snapshot Redis vide"

echo "==> Empreintes SHA-256"
(cd "$BACKUP_DIR" && sha256sum "postgres-$STAMP.dump" "redis-$STAMP.rdb.gz" \
  > "SHA256SUMS-$STAMP")

if [ -n "${BACKUP_S3_URI:-}" ]; then
  if command -v aws >/dev/null 2>&1; then
    echo "==> Export S3 → $BACKUP_S3_URI"
    aws s3 cp "$PG_FILE" "$BACKUP_S3_URI/" --only-show-errors
    aws s3 cp "$REDIS_FILE" "$BACKUP_S3_URI/" --only-show-errors
    aws s3 cp "$BACKUP_DIR/SHA256SUMS-$STAMP" "$BACKUP_S3_URI/" --only-show-errors
  else
    echo "AVERTISSEMENT: BACKUP_S3_URI défini mais CLI aws absent — export ignoré" >&2
  fi
fi

echo "==> Rétention ($RETENTION_DAYS jours)"
find "$BACKUP_DIR" -maxdepth 1 -type f \
  \( -name 'postgres-*.dump' -o -name 'redis-*.rdb.gz' -o -name 'SHA256SUMS-*' \) \
  -mtime +"$RETENTION_DAYS" -print -delete

echo "OK — sauvegarde terminée :"
ls -lh "$PG_FILE" "$REDIS_FILE" "$BACKUP_DIR/SHA256SUMS-$STAMP"
echo
echo "Vérifier la restauration : bash scripts/verify_backup_restore.sh"
