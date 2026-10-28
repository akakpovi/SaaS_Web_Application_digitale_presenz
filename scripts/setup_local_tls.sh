#!/usr/bin/env bash
# Génère un certificat TLS auto-signé pour la terminaison HTTPS locale.
#
# Les fichiers sont montés dans le conteneur nginx du frontend
# (./nginx/ssl:/etc/nginx/ssl:ro) et ne sont JAMAIS versionnés (.gitignore).
#
# Usage: bash scripts/setup_local_tls.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSL_DIR="$ROOT_DIR/nginx/ssl"
CRT="$SSL_DIR/presence.crt"
KEY="$SSL_DIR/presence.key"

mkdir -p "$SSL_DIR"

if [ -f "$CRT" ] && [ -f "$KEY" ]; then
  echo "Certificat déjà présent : $CRT"
else
  echo "Génération du certificat auto-signé (CN=localhost, SAN localhost/127.0.0.1)..."
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$KEY" -out "$CRT" \
    -subj "/C=FR/ST=Local/L=Local/O=Presence/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
fi

chmod 600 "$KEY"
chmod 644 "$CRT"

# nginx inclut ce fichier (voir nginx.conf). Ne pas écraser une configuration
# Let's Encrypt déjà en place.
TLS_CONF="$SSL_DIR/tls.conf"
if [ ! -f "$TLS_CONF" ] || ! grep -q "letsencrypt" "$TLS_CONF"; then
  cat > "$TLS_CONF" <<'EOF'
# Certificat TLS actif.
#
# Local : certificat auto-signé généré par scripts/setup_local_tls.sh.
# Public : scripts/enable_letsencrypt.sh remplace ce fichier par les chemins
# Let's Encrypt (/etc/letsencrypt/live/<domaine>/fullchain.pem et privkey.pem).
ssl_certificate     /etc/nginx/ssl/presence.crt;
ssl_certificate_key /etc/nginx/ssl/presence.key;
EOF
  chmod 644 "$TLS_CONF"
fi

echo "OK : $CRT"
echo "     $KEY"
echo "     $TLS_CONF"
