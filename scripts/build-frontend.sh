#!/usr/bin/env bash
#
# Reconstruit l'image du frontend et recrée uniquement ce service.
#
# Pourquoi ce script existe
# -------------------------
# Le pré-rendu a besoin du CMS WordPress publié sur la loopback de l'hôte :
# le build déclare donc `build.network: host` (et l'entitlement correspondant)
# dans docker-compose.yml. BuildKit refuse `network.host` tant que son
# allow-list ne l'autorise pas, et `docker compose build` n'expose aucun
# `--allow` : la commande échoue immédiatement avec
#
#   additional privileges requested: pass "--allow=network.host" ...
#
# (vérifié aussi sans `entitlements`, donc ce n'est pas la syntaxe Compose).
# `docker buildx bake` lit le *même* docker-compose.yml et accepte `--allow`,
# ce qui donne une seule commande reproductible, sans daemon reconfiguré.
#
# Quand ce script pourra disparaître : dès que le builder utilisé par Compose
# est créé avec `--buildkitd-flags '--allow-insecure-entitlement network.host'`
# (builder docker-container) ou que l'équipe accepte de publier WordPress sur
# une adresse joignable depuis le réseau de build. À ce moment-là,
# `docker compose build frontend` suffira et ce script deviendra un simple
# alias de cette commande.
#
# Usage : bash scripts/build-frontend.sh
#         VITE_BASE_URL=https://presence.example bash scripts/build-frontend.sh
#         NO_CACHE=1 bash scripts/build-frontend.sh   # cold build (CI, audit)
#
# Ne touche qu'au service `frontend` : aucun volume, aucun autre conteneur.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "[build-frontend] docker is not available" >&2
  exit 1
fi

# Nom d'image que Compose attend pour ce service (`<projet>-frontend`), lu dans
# la configuration : il suit le nom de projet Compose au lieu d'être recopié.
IMAGE="$(docker compose config --images | grep -E -- '-frontend$' | head -1)"
if [ -z "$IMAGE" ]; then
  echo "[build-frontend] could not read the frontend image name from docker compose config" >&2
  exit 1
fi

CACHE_ARGS=()
if [ "${NO_CACHE:-0}" = "1" ]; then
  CACHE_ARGS+=(--no-cache)
fi

echo "[build-frontend] building $IMAGE from docker-compose.yml (bake, --allow network.host)"
docker buildx bake \
  -f docker-compose.yml \
  --allow network.host \
  ${CACHE_ARGS[@]+"${CACHE_ARGS[@]}"} \
  --set "frontend.tags=$IMAGE" \
  frontend

echo "[build-frontend] recreating the frontend container only"
docker compose up -d --no-deps frontend

echo "[build-frontend] done — https://127.0.0.1/ now serves $IMAGE"
