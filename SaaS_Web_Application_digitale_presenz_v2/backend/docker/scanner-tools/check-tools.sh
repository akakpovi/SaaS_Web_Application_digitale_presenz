#!/bin/sh
# Presence scanner-tools self check.
#
# Runs at image build time and as the `scanner-tools` Compose service, so a
# broken or missing tool fails loudly here instead of silently degrading every
# scan to "unavailable".
#
# Prints one "tool: version" line per tool and exits non-zero if any binary is
# missing.  It must not write outside /tmp: the sandbox mounts the root
# filesystem read-only.
set -eu

status=0

report() {
    # report <label> <binary> [args...]
    label="$1"; shift
    binary="$1"; shift

    if ! command -v "$binary" >/dev/null 2>&1; then
        printf '%-12s MISSING (%s)\n' "$label" "$binary"
        status=1
        return 0
    fi

    line="$(env HOME=/tmp TMPDIR=/tmp "$binary" "$@" 2>&1 | head -n 1)"
    printf '%-12s %s\n' "$label" "${line:-<no version output>}"
}

# Binary names are the ones the adapters invoke (Debian ships testssl.sh as
# /usr/bin/testssl; nikto is the upstream release wrapped in /usr/local/bin).
report nmap       nmap       --version
report nikto      nikto      -Version
report whatweb    whatweb    --version
report testssl.sh testssl    --version
report dnsrecon   dnsrecon   --version
report gobuster   gobuster   version

# gobuster needs no wordlist of its own, but the adapter passes the Debian dirb
# list path by default (SCANNER_GOBUSTER_WORDLIST).  A missing wordlist would
# make every directory enumeration fail, so check it here.
wordlist="${SCANNER_GOBUSTER_WORDLIST:-/usr/share/dirb/wordlists/common.txt}"
if [ -r "$wordlist" ]; then
    printf '%-12s %s (%s entries)\n' "wordlist" "$wordlist" "$(wc -l <"$wordlist" | tr -d ' ')"
else
    printf '%-12s MISSING (%s)\n' "wordlist" "$wordlist"
    status=1
fi

# Scenario-C assets are baked into the image.  A missing directory or an
# empty selection would make the stage-2 profile silently scan nothing.
for templates in /opt/scanner-templates/selected /opt/scanner-templates/presence; do
    if [ -d "$templates" ]; then
        count="$(find "$templates" -name '*.yaml' -type f | wc -l | tr -d ' ')"
        if [ "$count" -gt 0 ]; then
            printf '%-12s %s (%s templates)\n' "templates" "$templates" "$count"
        else
            printf '%-12s EMPTY (%s)\n' "templates" "$templates"
            status=1
        fi
    else
        printf '%-12s MISSING (%s)\n' "templates" "$templates"
        status=1
    fi
done

extra_wordlist="${SCANNER_GOBUSTER_EXTRA_WORDLIST:-/opt/scanner-wordlists/presence-extra.txt}"
if [ -r "$extra_wordlist" ]; then
    printf '%-12s %s (%s entries)\n' "extra-list" "$extra_wordlist" "$(grep -cv '^[[:space:]]*$' "$extra_wordlist" | tr -d ' ')"
else
    printf '%-12s MISSING (%s)\n' "extra-list" "$extra_wordlist"
    status=1
fi

if [ "$status" -ne 0 ]; then
    echo "scanner-tools-check: at least one tool is unavailable" >&2
fi
exit "$status"
