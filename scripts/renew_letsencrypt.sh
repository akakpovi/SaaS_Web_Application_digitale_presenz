#!/usr/bin/env bash
# Renouvelle le certificat Let's Encrypt et recharge nginx sans coupure.
#
# À planifier après scripts/enable_letsencrypt.sh, par exemple chaque lundi :
#   15 4 * * 1 cd /srv/presence && bash scripts/renew_letsencrypt.sh >> /var/log/presence-certbot.log 2>&1
#
# certbot ne renouvelle réellement que si le certificat expire sous 30 jours ;
# le script est donc sans effet le reste du temps. Le rechargement nginx n'a
# lieu qu'après un `nginx -t` réussi.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p nginx/letsencrypt nginx/certbot

echo "==> Vérification du renouvellement Let's Encrypt"
docker run --rm \
  -v "$ROOT_DIR/nginx/letsencrypt:/etc/letsencrypt" \
  -v "$ROOT_DIR/nginx/certbot:/var/www/certbot" \
  certbot/certbot renew \
  --webroot -w /var/www/certbot \
  --quiet

echo "==> Validation de la configuration nginx"
docker compose exec -T frontend nginx -t

echo "==> Rechargement de nginx"
docker compose exec -T frontend nginx -s reload

echo "OK — certificat vérifié, nginx rechargé."
