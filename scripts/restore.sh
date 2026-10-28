#!/usr/bin/env bash
# Restauration RÉELLE (destructive) de PostgreSQL / Redis.
#
# Usage:
#   bash scripts/restore.sh backups/postgres-20261021T033000Z.dump
#   bash scripts/restore.sh backups/umami-20261021T033000Z.dump
#   bash scripts/restore.sh backups/redis-20261021T033000Z.rdb.gz
#
# La base cible est déduite du NOM du fichier, puis affichée avant toute
# écriture : un dump `umami-*.dump` ne part jamais dans la base applicative, et
# inversement.  La confirmation interactive exige de retaper cette cible
# (`RESTORE umami`, `RESTORE presence`, `RESTORE redis`), pour qu'une faute de
# frappe sur le chemin ne suffise pas à écraser la mauvaise base.
#
# `--yes` conserve la possibilité de restaurer sans interaction (cron, runbook),
# mais affiche lui aussi la base cible : l'automatisation n'est jamais muette.
#
# Pour une simple vérification non destructive, préférez
# scripts/verify_backup_restore.sh.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FILE="${1:-}"
CONFIRM="${2:-}"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Usage: bash scripts/restore.sh <fichier.dump|fichier.rdb.gz> [--yes]" >&2
  exit 2
fi

# --- Déduction de la cible, avant toute confirmation ------------------------
case "$FILE" in
  *.dump)
    case "$(basename "$FILE")" in
      umami-*.dump)
        TARGET_TOKEN="umami"
        TARGET_LABEL="umami — base analytique (Umami)"
        TARGET_KIND="umami"
        ;;
      *)
        TARGET_TOKEN="presence"
        TARGET_LABEL="presence — base applicative (\$POSTGRES_DB du conteneur db)"
        TARGET_KIND="app"
        ;;
    esac
    ;;
  *.rdb.gz)
    TARGET_TOKEN="redis"
    TARGET_LABEL="redis — snapshot RDB (base 0)"
    TARGET_KIND="redis"
    ;;
  *)
    echo "Format non reconnu (attendu .dump ou .rdb.gz)." >&2
    exit 2
    ;;
esac

echo "ATTENTION : cette opération écrase les données actuelles."
echo "Fichier      : $FILE"
echo "Base cible   : $TARGET_LABEL"
echo "Déduite de   : $(basename "$FILE")"

if [ "$CONFIRM" = "--yes" ]; then
  echo "Confirmation : --yes fourni, aucune saisie demandée (base cible ci-dessus)."
else
  read -r -p "Tapez 'RESTORE $TARGET_TOKEN' pour confirmer : " answer
  if [ "$answer" != "RESTORE $TARGET_TOKEN" ]; then
    echo "Annulé — la saisie ne correspond pas à la base cible."
    exit 1
  fi
fi

case "$TARGET_KIND" in
  umami)
    # pg_restore ne crée pas la base : sans ce contrôle, l'échec surviendrait
    # après l'arrêt d'Umami, en laissant le service à terre.
    if ! docker compose exec -T db sh -c \
        "psql -U \"\$POSTGRES_USER\" -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname = 'umami'\"" \
        | grep -qx 1; then
      echo "La base 'umami' n'existe pas dans le conteneur db — rien n'a été restauré." >&2
      exit 1
    fi

    echo "==> Arrêt d'Umami"
    docker compose stop umami >/dev/null 2>&1 || true

    echo "==> Restauration PostgreSQL → base analytique umami"
    docker compose exec -T db sh -c \
      'pg_restore -U "$POSTGRES_USER" -d umami --clean --if-exists --no-owner' \
      < "$FILE"

    echo "==> Redémarrage d'Umami"
    docker compose start umami >/dev/null 2>&1 || true
    ;;
  app)
    echo "==> Arrêt des services applicatifs"
    docker compose stop web celery-worker celery-beat >/dev/null

    echo "==> Restauration PostgreSQL → base applicative"
    docker compose exec -T db sh -c \
      'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
      < "$FILE"

    echo "==> Redémarrage"
    docker compose start web celery-worker celery-beat >/dev/null
    ;;
  redis)
    echo "==> Arrêt de Redis"
    docker compose stop redis >/dev/null
    CID="$(docker compose ps -a -q redis)"
    TMP="$(mktemp)"
    gzip -dc "$FILE" > "$TMP"
    docker cp "$TMP" "$CID:/data/dump.rdb"
    rm -f "$TMP"
    docker compose start redis >/dev/null
    ;;
esac

echo "OK — restauration terminée. Vérifiez /api/v1/health/ et les logs."
