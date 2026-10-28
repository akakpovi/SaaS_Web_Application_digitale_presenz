#!/usr/bin/env bash
# Configure le SMTP local (Mailpit) dans backend/.env.
#
# Remplace uniquement les clés EMAIL_* ; les autres secrets (PostgreSQL,
# Django, Paddle…) ne sont ni lus ni affichés.  Mailpit capture réellement les
# messages : http://localhost:8025
#
# Pour un test cloud, remplacer ensuite par les identifiants Mailtrap :
#   EMAIL_HOST=sandbox.smtp.mailtrap.io
#   EMAIL_PORT=587
#   EMAIL_USE_TLS=true
#   EMAIL_HOST_USER=<user>
#   EMAIL_HOST_PASSWORD=<password>
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/SaaS_Web_Application_digitale_presenz_v2/backend/.env"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT_DIR/SaaS_Web_Application_digitale_presenz_v2/backend/.env.example" "$ENV_FILE"
  echo "Créé à partir de .env.example : $ENV_FILE"
fi

set_env() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  if grep -q "^${key}=" "$ENV_FILE"; then
    # Use a literal replacement without interpreting value characters.
    KEY="$key" VALUE="$value" awk '
      BEGIN { key = ENVIRON["KEY"]; value = ENVIRON["VALUE"] }
      index($0, key "=") == 1 { print key "=" value; next }
      { print }
    ' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
    rm -f "$tmp"
  fi
}

set_env EMAIL_BACKEND "django.core.mail.backends.smtp.EmailBackend"
set_env EMAIL_HOST "mailpit"
set_env EMAIL_PORT "1025"
set_env EMAIL_USE_TLS "false"
set_env EMAIL_USE_SSL "false"
set_env EMAIL_HOST_USER ""
set_env EMAIL_HOST_PASSWORD ""
set_env DEFAULT_FROM_EMAIL "noreply@presence.local"
set_env SERVER_EMAIL "noreply@presence.local"

chmod 600 "$ENV_FILE"
echo "SMTP local configuré dans $ENV_FILE (Mailpit, port 1025)."
echo "Interface : http://localhost:8025"
