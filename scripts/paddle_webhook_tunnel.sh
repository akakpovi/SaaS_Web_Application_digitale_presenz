#!/usr/bin/env bash
# Expose le webhook Paddle local sur une URL HTTPS publique.
#
# Paddle Sandbox exige une destination HTTPS publique. Deux fournisseurs sont
# supportés, sans installation locale :
#
#   - cloudflared (par défaut) : tunnel rapide, aucun compte requis ;
#   - ngrok (si installé et authentifié) : `ngrok http https://localhost --insecure`.
#
# Usage :
#   bash scripts/paddle_webhook_tunnel.sh            # cloudflared
#   bash scripts/paddle_webhook_tunnel.sh ngrok      # ngrok (authtoken requis)
#
# L'URL publique est écrite dans /tmp/presence-webhook-url.txt. Utilisez-la :
#   python manage.py create_paddle_sandbox --webhook-url "$URL/api/v1/webhooks/paddle/"
#
# Arrêtez le tunnel (Ctrl+C) après le test : l'URL est publique et éphémère.
set -euo pipefail

PROVIDER="${1:-cloudflared}"
URL_FILE="/tmp/presence-webhook-url.txt"

if [ "$PROVIDER" = "ngrok" ]; then
  if ! command -v ngrok >/dev/null 2>&1; then
    echo "ngrok introuvable. Installez-le puis configurez 'ngrok config add-authtoken'." >&2
    exit 2
  fi
  echo "==> ngrok vers https://localhost (certificat auto-signé ignoré)"
  ngrok http https://localhost --insecure --log=stdout | tee /tmp/presence-ngrok.log
  exit 0
fi

if [ "$PROVIDER" != "cloudflared" ]; then
  echo "Usage: bash scripts/paddle_webhook_tunnel.sh [cloudflared|ngrok]" >&2
  exit 2
fi

echo "==> tunnel cloudflared vers https://localhost (origine auto-signée)"
echo "    Détection automatique de l'URL publique…"

docker run --rm --network host cloudflare/cloudflared:latest \
  tunnel --no-autoupdate --no-tls-verify --url https://localhost 2>&1 |
  while IFS= read -r line; do
    printf '%s\n' "$line"
    if [[ "$line" =~ (https://[a-z0-9-]+\.trycloudflare\.com) ]]; then
      printf '%s\n' "${BASH_REMATCH[1]}" > "$URL_FILE"
      printf '\n>>> URL publique : %s\n>>> Webhook : %s/api/v1/webhooks/paddle/\n\n' \
        "${BASH_REMATCH[1]}" "${BASH_REMATCH[1]}"
    fi
  done
