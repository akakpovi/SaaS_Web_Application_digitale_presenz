#!/bin/sh
# Healthcheck: prove the anti-SSRF nftables policy is still installed.
#
# If the guard is unhealthy, Compose keeps the Celery worker down instead of
# letting it launch scanner containers on an unprotected network.
set -eu

rules=$(nft list table inet presence_egress 2>/dev/null) || {
    echo "presence_egress table missing" >&2
    exit 1
}

echo "$rules" | grep -q 'hook forward priority -250' \
    || { echo "forward hook missing" >&2; exit 1; }
echo "$rules" | grep -q 'hook input priority -250' \
    || { echo "input hook missing" >&2; exit 1; }
echo "$rules" | grep -q '10.0.0.0/8' \
    || { echo "RFC1918 drop rule missing" >&2; exit 1; }
echo "$rules" | grep -q '169.254.169.254' \
    || { echo "metadata drop rule missing" >&2; exit 1; }

exit 0
