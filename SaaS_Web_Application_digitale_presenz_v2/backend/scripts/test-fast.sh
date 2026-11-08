#!/usr/bin/env bash
# Local backend test runner.
#
# Recreates the test database and shards the suite across workers. Run it
# inside the web container after the image has been rebuilt:
#
#   docker compose exec -T web ./scripts/test-fast.sh scans scanners public_checker
#
# Override the worker count with PARALLEL=8 if the host has enough CPU/RAM.
# A clean database avoids stale rows left by an interrupted --keepdb run.
set -euo pipefail

cd "$(dirname "$0")/.."

PARALLEL="${PARALLEL:-4}"
echo "[test-fast] settings=config.settings.test parallel=${PARALLEL}" >&2

exec python manage.py test \
  --settings=config.settings.test \
  --noinput \
  --parallel="${PARALLEL}" \
  "$@"
