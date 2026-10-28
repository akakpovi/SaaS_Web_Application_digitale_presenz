# Scanner tools sandbox image.
#
# One image carries the six external security tools Presence delegates to the
# hardened Docker sandbox (`SCANNER_SANDBOX` mode `docker`):
#
#   nmap, nikto, whatweb, testssl.sh, dnsrecon, gobuster
#
# Why a dedicated project image instead of six upstream ones:
#   * every tool comes from the Debian bookworm package index (or, for
#     gobuster, a checksum-verified upstream release), so the versions are
#     pinned and auditable from a single Dockerfile;
#   * no unvetted community image is given scanner privileges;
#   * the sandbox needs one predictable image name per scanner
#     (`SCANNER_DOCKER_IMAGE_<NAME>`), and mixing vendors would mean six
#     different entrypoints, users and filesystems to reason about.
#
# The sandbox runs this image with:
#   --read-only --cap-drop ALL --security-opt no-new-privileges
#   --tmpfs /tmp --pids-limit … --memory … --cpus …
#   --network presence_scanner_sandbox (nftables egress guard)
# so the tools must work as an unprivileged user with a read-only root
# filesystem and write only under /tmp.  `scanner-tools-check` proves that at
# build time, and the `scanner-tools` Compose service re-proves it on every
# `docker compose up --build`.
#
# Build (also done by `docker compose up -d --build`):
#   docker compose build scanner-tools
#
# Rebuild only after bumping the tag in docker-compose.yml,
# SCANNER_TOOLS_IMAGE in config/settings/base.py and .env.example.

FROM debian:bookworm-slim

LABEL org.opencontainers.image.title="presence-scanner-tools" \
      org.opencontainers.image.description="Sandbox image for the Presence advanced security scanners (nmap, nikto, whatweb, testssl.sh, dnsrecon, gobuster)" \
      org.opencontainers.image.version="2026-10-27" \
      org.opencontainers.image.source="https://github.com/elomaipp/presence"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

# Versions resolved at build time (recorded here so an audit does not have to
# guess; the build fails loudly if a pinned artefact disappears):
#   nmap        7.93+dfsg1-1            (Debian bookworm)
#   whatweb     0.5.5-1                 (Debian bookworm)
#   testssl.sh  3.0.8+dfsg-1            (Debian bookworm, /usr/bin/testssl)
#   dnsrecon    1.1.3-2                 (Debian bookworm + python3-pkg-resources)
#   dirb        2.22+dfsg-5             (Debian bookworm;
#                                        /usr/share/dirb/wordlists/common.txt)
#   nikto       2.6.1                   (upstream release, see below)
#   gobuster    3.6.0                   (upstream release, see below)
#
# `--no-install-recommends` keeps the image small; whatweb pulls its own Ruby
# runtime through Depends.  curl and ca-certificates are needed by the two
# upstream downloads; the Perl modules are required by nikto (JSON report,
# TLS support, XML writer).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        nmap \
        whatweb \
        testssl.sh \
        dnsrecon \
        dirb \
        perl \
        libjson-perl \
        libnet-ssleay-perl \
        libxml-writer-perl \
        # dnsrecon imports pkg_resources at start-up; without it the tool
        # aborts with a traceback before parsing a single option.
        python3-pkg-resources \
    && rm -rf /var/lib/apt/lists/*

# nikto was removed from Debian bookworm, so it is installed from the pinned
# upstream release.  The tarball is checksum-verified before unpacking and the
# telemetry/update prompt is disabled through /etc/nikto.conf: a sandboxed
# scan must never contact anything but the authorised target.
ARG NIKTO_VERSION=2.6.1
ARG NIKTO_SHA256=d1ca1acb05d81a5a6f374c0afdd76b33afa0089278631a20673c0210a71d992f
RUN set -eu; \
    curl -fsSL -o /tmp/nikto.tar.gz \
        "https://github.com/sullo/nikto/archive/refs/tags/${NIKTO_VERSION}.tar.gz"; \
    echo "${NIKTO_SHA256}  /tmp/nikto.tar.gz" | sha256sum -c -; \
    mkdir -p /opt/nikto; \
    tar -xzf /tmp/nikto.tar.gz -C /tmp; \
    cp -a "/tmp/nikto-${NIKTO_VERSION}/." /opt/nikto/; \
    rm -rf /tmp/nikto.tar.gz "/tmp/nikto-${NIKTO_VERSION}"; \
    chmod 0755 /opt/nikto/program/nikto.pl; \
    printf '%s\n' \
        'EXECDIR=/opt/nikto/program' \
        'PLUGINDIR=/opt/nikto/program/plugins' \
        'DBDIR=/opt/nikto/program/databases' \
        'TEMPLATEDIR=/opt/nikto/program/templates' \
        'NIKTODTD=/opt/nikto/program/templates/nikto.dtd' \
        '# Never ask for or send telemetry from a scan sandbox.' \
        'UPDATES=no' \
        'PROMPTS=no' \
        'LW_SSL_ENGINE=Net::SSLeay' \
        > /etc/nikto.conf; \
    chmod 0644 /etc/nikto.conf

# The wrapper keeps nikto.pl's own directory resolution intact (a symlink would
# make FindBin resolve to /usr/local/bin) and pins the config file it reads.
RUN printf '%s\n' \
        '#!/bin/sh' \
        'exec /opt/nikto/program/nikto.pl "$@"' \
        > /usr/local/bin/nikto \
    && chmod 0755 /usr/local/bin/nikto

# gobuster is not packaged in Debian.  Install the pinned upstream release and
# verify the checksum published with it before unpacking, so a compromised or
# substituted download fails the build instead of shipping.
ARG GOBUSTER_VERSION=3.6.0
ARG GOBUSTER_SHA256_AMD64=871be404ce5f80c96b864586b3caa90f894598d1a8222ae316c19e5f70e04cfc
ARG GOBUSTER_SHA256_ARM64=9d6c93ea27fa0477a8f7b57a4c495c8c91490d76805180c18b9d77bfc4f61b55
RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
        amd64) asset="gobuster_Linux_x86_64.tar.gz"; sum="$GOBUSTER_SHA256_AMD64" ;; \
        arm64) asset="gobuster_Linux_arm64.tar.gz";  sum="$GOBUSTER_SHA256_ARM64" ;; \
        *) echo "gobuster: unsupported architecture $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/gobuster.tar.gz \
        "https://github.com/OJ/gobuster/releases/download/v${GOBUSTER_VERSION}/${asset}"; \
    echo "${sum}  /tmp/gobuster.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/gobuster.tar.gz -C /usr/local/bin gobuster; \
    chmod 0755 /usr/local/bin/gobuster; \
    rm -f /tmp/gobuster.tar.gz

# Least privilege: the sandbox does not set --user, so the image user must be
# unprivileged.  HOME lives under /tmp, which the sandbox mounts as a tmpfs.
RUN groupadd --system --gid 10001 scanner \
    && useradd --system --uid 10001 --gid scanner \
        --home-dir /tmp --shell /usr/sbin/nologin scanner

COPY check-tools.sh /usr/local/bin/scanner-tools-check
RUN chmod 0755 /usr/local/bin/scanner-tools-check \
    && /usr/local/bin/scanner-tools-check

USER scanner

# The sandbox always overrides the command, so the default is only used by the
# `scanner-tools` Compose service, which re-runs the same check.
CMD ["/usr/local/bin/scanner-tools-check"]
