#!/usr/bin/env bash
# Bascule le TLS local (auto-signé) vers un certificat Let's Encrypt.
#
# Prérequis :
#   - un nom de domaine public qui pointe (A/AAAA) vers ce serveur ;
#   - les ports 80 et 443 ouverts ;
#   - la pile déjà démarrée (docker compose up -d).
#
# Usage :
#   bash scripts/enable_letsencrypt.sh presence.example.com admin@example.com
#
# Le certificat est obtenu en mode webroot (aucun arrêt de nginx), puis
# nginx/ssl/tls.conf est réécrit pour pointer vers /etc/letsencrypt/live/...
# et nginx est rechargé sans coupure.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${1:-}"
EMAIL="${2:-}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "Usage: bash scripts/enable_letsencrypt.sh <domain> <email>" >&2
  exit 2
fi

if ! [[ "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
  echo "Domaine invalide : $DOMAIN" >&2
  exit 2
fi

cd "$ROOT_DIR"
mkdir -p nginx/letsencrypt nginx/certbot nginx/ssl

echo "==> Émission du certificat pour $DOMAIN"
docker run --rm \
  -v "$ROOT_DIR/nginx/letsencrypt:/etc/letsencrypt" \
  -v "$ROOT_DIR/nginx/certbot:/var/www/certbot" \
  certbot/certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos --no-eff-email --non-interactive

if [ ! -f "nginx/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
  echo "Certificat introuvable — vérifiez le DNS et les ports 80/443." >&2
  exit 1
fi

cat > nginx/ssl/tls.conf <<EOF
# Certificat TLS actif — Let's Encrypt (généré le $(date -u +%Y-%m-%dT%H:%M:%SZ)).
# Renouvellement : scripts/renew_letsencrypt.sh (cron mensuel recommandé).
ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
EOF

echo "==> Rechargement de nginx"
docker compose exec -T frontend nginx -t
docker compose exec -T frontend nginx -s reload

echo "OK — https://$DOMAIN utilise maintenant Let's Encrypt."
echo "Pensez à définir VITE_BASE_URL=https://$DOMAIN puis à reconstruire le frontend"
echo "pour que canonical, sitemap et robots.txt soient absolus."
