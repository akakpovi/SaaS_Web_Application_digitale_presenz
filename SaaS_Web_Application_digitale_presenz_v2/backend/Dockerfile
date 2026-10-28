FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Optional performance/SEO engine (Lighthouse + Chromium).
# Disabled by default so the image stays lean and the scanner is reported as
# "unavailable" rather than silently missing. Enable it with:
#   docker compose build --build-arg INSTALL_LIGHTHOUSE=true
#
# Node 22 comes from NodeSource because the Debian base ships Node 18/20,
# which is too old for current Lighthouse 12 releases.  The install is validated at
# build time (``lighthouse --version`` / ``chromium --version``) so a broken
# browser dependency fails the image build instead of every production scan.
ARG INSTALL_LIGHTHOUSE=false
ARG INSTALL_DOCKER_CLI=false
ENV CHROME_PATH=/usr/bin/chromium
RUN if [ "$INSTALL_LIGHTHOUSE" = "true" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
            ca-certificates curl gnupg chromium fonts-liberation \
        && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
        && apt-get install -y --no-install-recommends nodejs \
        && npm install --global --no-fund --no-audit lighthouse@12 \
        && node --version \
        && npm --version \
        && lighthouse --version \
        && chromium --version \
        && npm cache clean --force \
        && rm -rf /var/lib/apt/lists/* /root/.npm; \
    fi

# Docker socket access for the Docker scanner sandbox.  Only the Celery scan
# worker sets this build arg: ZAP/Nuclei containers are launched through the
# host daemon.  The daemon itself is never started in this image.
RUN if [ "$INSTALL_DOCKER_CLI" = "true" ]; then \
        apt-get update && apt-get install -y --no-install-recommends docker-cli \
        && docker --version \
        && rm -rf /var/lib/apt/lists/*; \
    fi

COPY . ./
RUN chown -R app:app /app \
    && mkdir -p /app/scanner-archives \
    && chown app:app /app/scanner-archives

# Chromium/Lighthouse create their profile under $HOME.  The system account
# created above defaults to /nonexistent, which makes Chrome abort with
# "Failed to create headless user data directory container" and Lighthouse
# wait forever for its debugging port.  Give the runtime user a real home and
# point the XDG directories at it as well.
RUN usermod -d /home/app app \
    && mkdir -p /home/app/.cache /home/app/.config \
    && chown -R app:app /home/app
ENV HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    XDG_CONFIG_HOME=/home/app/.config

USER app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-", "--access-logformat", "%(h)s %(l)s %(u)s %(t)s \"%(m)s %(U)s %(H)s\" %(s)s %(b)s"]
