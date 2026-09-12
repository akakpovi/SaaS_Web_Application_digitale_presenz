#!/usr/bin/env bash

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PASS=0
FAIL=0
WARN=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() {
    printf "${GREEN}PASS${NC}  %s\n" "$1"
    PASS=$((PASS + 1))
}

fail() {
    printf "${RED}FAIL${NC}  %s\n" "$1"
    FAIL=$((FAIL + 1))
}

warn() {
    printf "${YELLOW}WARN${NC}  %s\n" "$1"
    WARN=$((WARN + 1))
}

section() {
    printf "\n${BLUE}============================================================${NC}\n"
    printf "${BLUE}%s${NC}\n" "$1"
    printf "${BLUE}============================================================${NC}\n"
}

run_check() {
    local description="$1"
    shift

    if "$@" >/tmp/presence-check.out 2>/tmp/presence-check.err; then
        pass "$description"
    else
        fail "$description"

        if [ -s /tmp/presence-check.out ]; then
            echo "--- stdout ---"
            cat /tmp/presence-check.out
        fi

        if [ -s /tmp/presence-check.err ]; then
            echo "--- stderr ---"
            cat /tmp/presence-check.err
        fi
    fi
}

PYTHON=""

section "1. PROJECT STRUCTURE"

for file in \
    manage.py \
    Dockerfile \
    docker-compose.yml \
    requirements.txt \
    config/urls.py \
    config/celery.py \
    core/security.py \
    scans/models.py \
    scans/services/scoring.py \
    scans/tasks.py \
    public_checker/__init__.py \
    public_checker/apps.py \
    public_checker/serializers.py \
    public_checker/views.py \
    public_checker/tasks.py \
    public_checker/urls.py \
    scanners/__init__.py \
    scanners/base.py \
    scanners/website.py \
    scanners/ssl.py \
    scanners/dns.py \
    scanners/email_security.py \
    scanners/security_headers.py \
    scanners/performance.py \
    scanners/uptime.py \
    scanners/reviews.py
do
    if [ -f "$file" ]; then
        pass "$file exists"
    else
        fail "$file is missing"
    fi
done


section "2. PYTHON INTERPRETER"

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
    pass "python3 available: $(python3 --version 2>&1)"
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
    pass "python available: $(python --version 2>&1)"
else
    fail "No Python interpreter found"
fi


section "3. REQUIREMENTS.TXT SANITY"

if grep -nE '^[[:space:]]*(cat .*requirements|EOF)[[:space:]]*$' requirements.txt >/tmp/presence-bad-req 2>/dev/null; then
    fail "requirements.txt contains shell/heredoc instructions"
    cat /tmp/presence-bad-req
else
    pass "requirements.txt contains no accidental cat/EOF commands"
fi

for dependency in \
    Django \
    djangorestframework \
    celery \
    redis \
    django-redis \
    requests \
    dnspython \
    gunicorn
do
    if grep -qi "^${dependency}" requirements.txt; then
        pass "Dependency declared: $dependency"
    else
        fail "Dependency missing from requirements.txt: $dependency"
    fi
done


section "4. PYTHON SYNTAX / COMPILE"

if [ -n "$PYTHON" ]; then
    run_check \
        "Python compileall succeeds" \
        "$PYTHON" -m compileall -q \
        accounts websites scans scanners core public_checker config
else
    warn "Compile check skipped because Python is unavailable"
fi


section "5. SECURITY API CONTRACT"

if grep -q 'class DomainValidationError' core/security.py; then
    pass "DomainValidationError exists"
else
    fail "DomainValidationError is missing from core/security.py"
fi

if grep -q 'def validate_domain_for_scan' core/security.py; then
    pass "validate_domain_for_scan exists"
else
    fail "validate_domain_for_scan is missing"
fi

if grep -q 'def safe_request' core/security.py; then
    pass "safe_request exists"
else
    warn "safe_request not found; verify HTTP scanners have equivalent redirect/DNS-rebinding protection"
fi

if grep -q '169\.254\.169\.254' core/security.py; then
    pass "Cloud metadata IPv4 endpoint explicitly covered"
else
    warn "169.254.169.254 not explicitly found; generic link-local blocking may still cover it"
fi

if grep -qi 'metadata\.google\.internal' core/security.py; then
    pass "Google metadata hostname covered"
else
    warn "metadata.google.internal not explicitly found"
fi

if grep -q 'is_loopback' core/security.py &&
   grep -q 'is_private' core/security.py &&
   grep -q 'is_link_local' core/security.py; then
    pass "IP classification checks found"
else
    warn "Could not confirm loopback/private/link-local IP checks"
fi


section "6. PUBLIC SERIALIZER CONTRACT"

if grep -q 'validate_domain_for_scan' public_checker/serializers.py; then
    pass "Public serializer calls SSRF/domain validator"
else
    fail "Public serializer does not call validate_domain_for_scan"
fi

if grep -q 'DomainValidationError' public_checker/serializers.py; then
    pass "Public serializer handles DomainValidationError"
else
    fail "Public serializer does not handle DomainValidationError"
fi

for field in \
    scan_id \
    domain \
    status \
    progress \
    health_score \
    health_status \
    checks
do
    if grep -q "$field" public_checker/serializers.py; then
        pass "Public state serializer contains $field"
    else
        fail "Public state serializer appears to be missing $field"
    fi
done

if grep -q 'total_score' public_checker/serializers.py; then
    warn "Legacy field total_score is still present"
else
    pass "Legacy total_score removed"
fi

if grep -Eq 'results[[:space:]]*=' public_checker/serializers.py; then
    warn "Legacy results field may still be present"
else
    pass "Legacy results serializer field removed"
fi


section "7. PUBLIC VIEW ORCHESTRATION"

if grep -q 'run_public_scan' public_checker/views.py; then
    pass "View references run_public_scan orchestrator"
else
    fail "View does not reference run_public_scan"
fi

if grep -Eq 'run_public_scan\.delay|run_public_scan\.apply_async' public_checker/views.py; then
    pass "View asynchronously enqueues run_public_scan"
else
    fail "View does not appear to enqueue run_public_scan asynchronously"
fi

if grep -q 'from celery import chord' public_checker/views.py ||
   grep -q 'chord(' public_checker/views.py; then
    fail "View still orchestrates a Celery chord directly; orchestration belongs in tasks.py"
else
    pass "View does not build a Celery chord directly"
fi

if grep -q 'run_public_scanner\.s' public_checker/views.py; then
    fail "View still directly creates scanner task signatures"
else
    pass "View does not directly create scanner signatures"
fi

if grep -q 'throttle_scope.*public_scan_create' public_checker/views.py; then
    pass "Create endpoint has public_scan_create throttle scope"
else
    fail "Create endpoint throttle scope missing"
fi

if grep -q 'throttle_scope.*public_scan_poll' public_checker/views.py; then
    pass "Polling endpoint has public_scan_poll throttle scope"
else
    fail "Polling endpoint throttle scope missing"
fi


section "8. CELERY TASK CONTRACT"

if grep -q 'def run_public_scanner' public_checker/tasks.py; then
    pass "run_public_scanner task exists"
else
    fail "run_public_scanner task missing"
fi

if grep -q 'def run_public_scan' public_checker/tasks.py; then
    pass "run_public_scan orchestrator exists"
else
    fail "run_public_scan orchestrator missing"
fi

if grep -q 'def finalize_public_scan' public_checker/tasks.py; then
    pass "finalize_public_scan callback exists"
else
    fail "finalize_public_scan callback missing"
fi

if grep -q 'chord(' public_checker/tasks.py; then
    pass "Celery chord orchestration exists in tasks.py"
else
    fail "No Celery chord found in public_checker/tasks.py"
fi

if grep -q 'finalize_public_scan\.s(domain, scan_id)' public_checker/tasks.py; then
    pass "Chord callback argument order looks correct"
else
    warn "Could not confirm finalize_public_scan.s(domain, scan_id)"
fi

if grep -q '"error": str(exc)' public_checker/tasks.py ||
   grep -q "'error': str(exc)" public_checker/tasks.py; then
    fail "Public task exposes raw exception text"
else
    pass "No obvious raw exception leakage from public task"
fi

if grep -q 'soft_time_limit' public_checker/tasks.py; then
    pass "Per-scanner Celery soft timeout configured"
else
    warn "No task-level soft_time_limit found"
fi

if grep -q 'max_retries' public_checker/tasks.py; then
    pass "Scanner retry limit configured"
else
    warn "No explicit scanner retry limit found"
fi


section "9. SCORING CONTRACT"

if grep -q 'class PublicScorableResult' scans/services/scoring.py; then
    pass "PublicScorableResult exists"
else
    fail "PublicScorableResult missing"
fi

if grep -q 'def calculate_health_score' scans/services/scoring.py; then
    pass "Central calculate_health_score exists"
else
    fail "calculate_health_score missing"
fi

if grep -q 'PublicScorableResult' public_checker/tasks.py; then
    pass "Public task adapts results to central scoring engine"
else
    fail "Public task does not appear to use PublicScorableResult"
fi

if grep -q 'health\.score' public_checker/tasks.py &&
   grep -q 'health\.status' public_checker/tasks.py; then
    pass "Public finalizer uses HealthScore attributes"
else
    fail "Public finalizer may still treat HealthScore as a dict"
fi

if grep -q 'health_data\.get' public_checker/tasks.py; then
    fail "Legacy health_data.get() usage remains"
else
    pass "No legacy HealthScore dict access found"
fi


section "10. SCANNER PACKAGE"

for module in \
    website \
    ssl \
    dns \
    email_security \
    security_headers \
    performance \
    uptime \
    reviews
do
    if grep -q "${module}_scanner" scanners/__init__.py; then
        pass "Scanner exported: ${module}_scanner"
    else
        fail "Scanner export missing: ${module}_scanner"
    fi
done

if grep -R \
    --include='*.py' \
    -nE 'requests\.(get|post|head|request)\(' \
    scanners/ >/tmp/presence-direct-requests 2>/dev/null; then

    warn "Direct requests calls found in scanner package; review SSRF safety:"
    cat /tmp/presence-direct-requests
else
    pass "No obvious direct requests calls found in scanners"
fi


section "11. DJANGO CONFIGURATION (SOURCE)"

if grep -R \
    -nE "['\"]public_checker['\"]" \
    config/settings >/dev/null 2>&1; then
    pass "public_checker found in Django settings"
else
    fail "public_checker missing from INSTALLED_APPS/settings"
fi

if grep -q 'public_checker.urls' config/urls.py; then
    pass "public_checker URLs included"
else
    fail "public_checker.urls missing from config/urls.py"
fi

if grep -R \
    -n 'public_scan_create' \
    config/settings >/dev/null 2>&1; then
    pass "public_scan_create throttle configured"
else
    fail "public_scan_create throttle rate not found"
fi

if grep -R \
    -n 'public_scan_poll' \
    config/settings >/dev/null 2>&1; then
    pass "public_scan_poll throttle configured"
else
    fail "public_scan_poll throttle rate not found"
fi

if grep -R \
    -n 'django_redis.cache.RedisCache' \
    config/settings >/dev/null 2>&1; then
    pass "Django Redis cache configured"
else
    fail "Django Redis cache backend not found"
fi

if grep -R \
    -n 'CELERY_RESULT_BACKEND' \
    config/settings >/dev/null 2>&1; then
    pass "Celery result backend configured"
else
    fail "CELERY_RESULT_BACKEND not found"
fi


section "12. DOCKER CONFIGURATION"

if docker compose config >/tmp/presence-compose.out 2>/tmp/presence-compose.err; then
    pass "docker compose config is valid"
else
    fail "docker-compose configuration is invalid"
    cat /tmp/presence-compose.err
fi

if grep -q '^COPY \. \./' Dockerfile ||
   grep -q '^COPY \. /app' Dockerfile ||
   grep -q '^COPY \. \.' Dockerfile; then
    pass "Dockerfile copies application source"
else
    warn "Could not confirm COPY of project source in Dockerfile"
fi

if grep -q '^WORKDIR /app' Dockerfile; then
    pass "Docker WORKDIR is /app"
else
    fail "Docker WORKDIR does not appear to be /app"
fi

if grep -qE '(^|/)(scanners|public_checker)/?$' .dockerignore 2>/dev/null; then
    fail ".dockerignore appears to exclude scanners or public_checker"
else
    pass ".dockerignore does not obviously exclude new packages"
fi


section "13. RUNNING CONTAINER CHECKS"

if docker compose ps --status running web 2>/dev/null | grep -q 'web'; then
    pass "Existing web container is running"

    run_check \
        "Django system check inside current image" \
        docker compose exec -T web python manage.py check

    run_check \
        "No model changes detected inside current image" \
        docker compose exec -T web \
        python manage.py makemigrations --check --dry-run

    run_check \
        "Public checker imports under initialized Django" \
        docker compose exec -T web \
        python manage.py shell -c \
        "from public_checker.serializers import PublicScanRequestSerializer; from public_checker.tasks import run_public_scan, run_public_scanner, finalize_public_scan; from scans.services.scoring import PublicScorableResult, calculate_health_score; print('OK')"

else
    warn "Web container is not currently running; container checks skipped"
fi


section "14. SSRF SERIALIZER TEST IN CURRENT IMAGE"

if docker compose ps --status running web 2>/dev/null | grep -q 'web'; then

docker compose exec -T web python manage.py shell <<'PY' >/tmp/presence-ssrf.out 2>/tmp/presence-ssrf.err
from public_checker.serializers import PublicScanRequestSerializer

blocked = [
    "localhost",
    "127.0.0.1",
    "10.0.0.1",
    "172.16.0.1",
    "192.168.1.1",
    "169.254.169.254",
    "metadata.google.internal",
    "http://127.0.0.1:22",
    "ftp://example.com",
    "file:///etc/passwd",
]

failed = []

for value in blocked:
    serializer = PublicScanRequestSerializer(
        data={"domain": value}
    )

    if serializer.is_valid():
        print("UNSAFE ACCEPTED:", value, serializer.validated_data)
        failed.append(value)
    else:
        print("BLOCKED:", value)

if failed:
    raise SystemExit(
        "SSRF validation failure: " + ", ".join(failed)
    )

print("SSRF SERIALIZER CHECK OK")
PY

    if [ $? -eq 0 ]; then
        pass "Dangerous SSRF inputs rejected by serializer"
        cat /tmp/presence-ssrf.out
    else
        fail "One or more SSRF inputs were accepted"
        cat /tmp/presence-ssrf.out
        cat /tmp/presence-ssrf.err
    fi

else
    warn "SSRF runtime serializer test skipped"
fi


section "15. SCORING RUNTIME TEST"

if docker compose ps --status running web 2>/dev/null | grep -q 'web'; then

docker compose exec -T web python manage.py shell <<'PY' >/tmp/presence-score.out 2>/tmp/presence-score.err
from scans.services.scoring import (
    PublicScorableResult,
    calculate_health_score,
)

results = [
    PublicScorableResult("website", 20, "healthy"),
    PublicScorableResult("ssl", 20, "healthy"),
    PublicScorableResult("dns", 15, "healthy"),
    PublicScorableResult("email_security", 15, "healthy"),
    PublicScorableResult("security_headers", 15, "healthy"),
    PublicScorableResult("performance", 15, "healthy"),
    PublicScorableResult("uptime", 100, "healthy"),
]

health = calculate_health_score(results)

print("score:", health.score)
print("status:", health.status)

assert health.score == 100
assert health.status == "healthy"

print("SCORING CHECK OK")
PY

    if [ $? -eq 0 ]; then
        pass "Central scoring runtime test succeeds"
        cat /tmp/presence-score.out
    else
        fail "Central scoring runtime test failed"
        cat /tmp/presence-score.out
        cat /tmp/presence-score.err
    fi

else
    warn "Scoring runtime test skipped"
fi


section "16. CELERY CURRENT IMAGE"

if docker compose ps --status running celery-worker 2>/dev/null |
   grep -q 'celery-worker'; then

    if docker compose exec -T celery-worker \
        celery -A config inspect registered \
        >/tmp/presence-celery.out 2>/tmp/presence-celery.err; then

        for task in \
            public_checker.tasks.run_public_scan \
            public_checker.tasks.run_public_scanner \
            public_checker.tasks.finalize_public_scan \
            scans.tasks.run_authenticated_scan
        do
            if grep -q "$task" /tmp/presence-celery.out; then
                pass "Celery task registered: $task"
            else
                fail "Celery task missing: $task"
            fi
        done
    else
        fail "Could not inspect Celery registered tasks"
        cat /tmp/presence-celery.err
    fi

else
    warn "Celery worker not running; registration check skipped"
fi


section "17. GIT / SECRET SANITY"

if [ -f .env ]; then
    if git check-ignore .env >/dev/null 2>&1; then
        pass ".env is ignored by Git"
    else
        warn ".env does not appear to be ignored by Git"
    fi
fi

if [ -f .env.example ]; then
    pass ".env.example exists"
else
    warn ".env.example missing"
fi


section "18. SUMMARY"

TOTAL=$((PASS + FAIL + WARN))

echo
echo "Total checks : $TOTAL"
printf "${GREEN}PASS         : %d${NC}\n" "$PASS"
printf "${RED}FAIL         : %d${NC}\n" "$FAIL"
printf "${YELLOW}WARN         : %d${NC}\n" "$WARN"
echo

rm -f \
    /tmp/presence-check.out \
    /tmp/presence-check.err \
    /tmp/presence-bad-req \
    /tmp/presence-direct-requests \
    /tmp/presence-compose.out \
    /tmp/presence-compose.err \
    /tmp/presence-ssrf.out \
    /tmp/presence-ssrf.err \
    /tmp/presence-score.out \
    /tmp/presence-score.err \
    /tmp/presence-celery.out \
    /tmp/presence-celery.err

if [ "$FAIL" -gt 0 ]; then
    printf "${RED}PRE-BUILD CHECK FAILED.${NC}\n"
    echo "Do NOT rebuild yet. Fix the failures above first."
    exit 1
fi

printf "${GREEN}PRE-BUILD CHECK PASSED.${NC}\n"

if [ "$WARN" -gt 0 ]; then
    echo "Review the warnings before production deployment."
fi

echo
echo "You can now rebuild:"
echo "  docker compose build web celery-worker"
echo "  docker compose up -d --force-recreate web celery-worker nginx"

exit 0
