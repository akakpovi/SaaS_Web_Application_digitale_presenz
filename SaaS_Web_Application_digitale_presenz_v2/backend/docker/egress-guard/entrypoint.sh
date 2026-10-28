#!/bin/sh
# Egress guard for the scanner sandbox network.
#
# The container runs in the host network namespace and installs a dedicated
# nftables table at priority -200, i.e. *before* Docker's bridge isolation and
# its filter chains.  Every packet leaving a scanner container towards a
# private, loopback, link-local, CGNAT, multicast or cloud-metadata address is
# dropped.  Public internet traffic is left untouched.
#
# This is a *network* control layered on top of the application SSRF gate:
# redirects and sub-resources followed by Chromium never pass through Django's
# URL validation, so they must be blocked at the packet level.
#
# Why nftables at priority -200: Docker's own inter-network isolation runs in
# its bridge chains and would drop scanner -> other-Docker-network traffic
# before an iptables DOCKER-USER rule ever sees it.  Hooking earlier makes the
# scanner policy independent of Docker's internal rule order, and it also
# covers the host INPUT path (scanner -> host services).
set -eu

SCANNER_SUBNET="${SCANNER_SUBNET:-172.31.240.0/24}"
LOG_DROPS="${SCANNER_EGRESS_LOG:-0}"
TABLE="presence_egress"

# The subnet is configuration, not user input, but keep the nft script
# injection-proof anyway.
case "$SCANNER_SUBNET" in
    *[!0-9./]*) echo "egress-guard: invalid SCANNER_SUBNET: $SCANNER_SUBNET" >&2; exit 1 ;;
esac

if ! command -v nft >/dev/null 2>&1; then
    echo "egress-guard: nft binary not found" >&2
    exit 1
fi

# Idempotent restart: remove the previous table if it exists.
nft delete table inet "$TABLE" 2>/dev/null || true

LOG_RULE=""
if [ "$LOG_DROPS" = "1" ]; then
    LOG_RULE='log prefix "scanner-egress-denied: " limit rate 5/minute'
fi

nft -f - <<EOF
table inet $TABLE {
    set private_nets {
        type ipv4_addr
        flags interval
        elements = {
            0.0.0.0/8,
            10.0.0.0/8,
            100.64.0.0/10,
            127.0.0.0/8,
            169.254.0.0/16,
            172.16.0.0/12,
            192.0.0.0/24,
            192.0.2.0/24,
            192.168.0.0/16,
            198.18.0.0/15,
            198.51.100.0/24,
            203.0.113.0/24,
            224.0.0.0/4,
            240.0.0.0/4
        }
    }

    chain forward {
        type filter hook forward priority -250; policy accept;
        # Metadata is part of 169.254.0.0/16; keep it first so audits can
        # assert a dedicated, visible counter.
        ip saddr $SCANNER_SUBNET ip daddr 169.254.169.254 $LOG_RULE counter drop
        ip saddr $SCANNER_SUBNET ip daddr @private_nets $LOG_RULE counter drop
    }

    chain input {
        type filter hook input priority -250; policy accept;
        ip saddr $SCANNER_SUBNET $LOG_RULE counter drop
    }
}
EOF

echo "egress-guard: nftables rules applied for ${SCANNER_SUBNET}"
nft list table inet "$TABLE"

exec "$@"
