import logging
import re
import uuid
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone, translation
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import permissions, status

from core.security import validate_domain_for_scan, DomainValidationError, SSRFBlockedError
from scans.models import Scan, CheckResult, HealthStatus
from scans.services.scoring import PublicScorableResult, calculate_health_score
from scans.services.steps_builder import build_initial_steps, StepStatus
from websites.models import Website
from .models import PublicLead
from .throttles import PublicScanThrottle

# Imports requis pour les tâches de fond et de test
from notifications.tasks import send_public_scan_report_email
from public_checker.tasks import run_public_scan

logger = logging.getLogger(__name__)

DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def _detect_language_code(request: Request) -> str:
    language_code = translation.get_language_from_request(request, check_path=False)
    supported_languages = {code for code, _label in getattr(settings, "LANGUAGES", [("fr", "Français"), ("en", "English"), ("de", "Deutsch")])}
    if language_code not in supported_languages:
        language_code = settings.LANGUAGE_CODE.split("-")[0]
    return language_code


def _build_rich_remediation(category: str, check_status: str) -> dict:
    """
    Construit un objet de remédiation technique riche selon la catégorie de l'anomalie.
    """
    if check_status in ["healthy", "passed", "good", "online"]:
        return {}

    if category == "email_security":
        return {
            "code": "v=spf1 include:_spf.example.com ~all",
            "server_type": "generic"
        }
    elif category == "security_headers":
        return {
            "code": "add_header X-Content-Type-Options \"nosniff\" always;\nadd_header X-Frame-Options \"SAMEORIGIN\" always;\nadd_header Referrer-Policy \"strict-origin-when-cross-origin\" always;",
            "server_type": "nginx",
            "nginx": "add_header X-Content-Type-Options \"nosniff\" always;\nadd_header X-Frame-Options \"SAMEORIGIN\" always;\nadd_header Referrer-Policy \"strict-origin-when-cross-origin\" always;",
            "apache": "Header set X-Content-Type-Options \"nosniff\"\nHeader set X-Frame-Options \"SAMEORIGIN\"\nHeader set Referrer-Policy \"strict-origin-when-cross-origin\"",
            "htaccess": "Header set X-Content-Type-Options \"nosniff\"\nHeader set X-Frame-Options \"SAMEORIGIN\""
        }
    elif category == "ssl":
        return {
            "code": "sudo certbot renew --nginx",
            "server_type": "generic"
        }
    return {}


def _serialize_scan_with_rich_data(scan: Scan) -> dict:
    """
    Sérialiseur unifié produisant le schéma de données riche attendu par le frontend.
    """
    checks = {}
    for cr in scan.check_results.all():
        check_data = {
            "status": cr.status,
            "score": cr.score,
            "message": cr.summary,
            "remediation": _build_rich_remediation(cr.category, cr.status)
        }

        if cr.category == "ssl" and cr.technical_details:
            days = cr.technical_details.get("days_remaining") or cr.technical_details.get("days_left")
            if days is not None:
                check_data["days_until_expiry"] = int(days)

        if cr.category == "uptime":
            check_data["is_monitored"] = False
            check_data["is_up"] = cr.status in ["healthy", "passed", "good", "online"]

        checks[cr.category] = check_data

    critical_count = sum(1 for c in checks.values() if c["status"] == HealthStatus.CRITICAL.value)
    warning_count = sum(1 for c in checks.values() if c["status"] == HealthStatus.WARNING.value)
    passed_count = sum(1 for c in checks.values() if c["status"] in [HealthStatus.HEALTHY.value, "passed"])

    return {
        "id": str(scan.id),
        "scan_id": str(scan.id),
        "check_id": str(scan.id),
        "status": scan.status,
        "is_guest": scan.is_guest,
        "url": f"https://{scan.website.domain}",
        "domain": scan.website.domain,
        "score": scan.health_score or 0,
        "progress": scan.progress,
        "current_step": scan.current_step,
        "steps": scan.steps,
        "created_at": scan.created_at.isoformat() if scan.created_at else timezone.now().isoformat(),
        "scanned_at": scan.completed_at.isoformat() if scan.completed_at else timezone.now().isoformat(),
        "summary": {
            "critical": critical_count,
            "warnings": warning_count,
            "passed": passed_count
        },
        "checks": checks,
        "meta": {
            "total_monitored_sites": Website.objects.filter(is_guest=False).count(),
            "average_rating": None
        },
        "preview_limitations": [
            "Score history is not available in public mode",
            "Real-time alerts require a free account"
        ],
        "cta": {
            "convert_url": f"/api/v1/public/scan/{scan.id}/convert/",
            "email_report_url": f"/api/v1/public/scan/{scan.id}/email/",
            "register_url": f"/register?scan_id={scan.id}&url=https://{scan.website.domain}"
        }
    }


# ---------------------------------------------------------------------------
# Access-control helpers
# ---------------------------------------------------------------------------

#: Session key holding the guest scans created by this browser session.
#: ``django.contrib.auth.login`` rotates the session key (``cycle_key``) but
#: keeps the session payload, so this list survives a guest → account signup.
GUEST_SCANS_SESSION_KEY = "guest_scan_ids"


def _session_key_of(request: Request) -> str | None:
    return getattr(request.session, "session_key", None)


def _may_read_scan(request: Request, scan: Scan) -> bool:
    """Can the requester read this scan's report?

    * Guest scans are public by design: they are produced without an account,
      hold no account data, and are purged after 24 h.  They are what the
      public report page and the share flow rely on.
    * Account scans (``is_guest=False``) are private: only their owner may
      read them.  This is the IDOR that used to expose every scan by numeric
      id (including private ones) to anonymous callers.
    """
    if scan.is_guest:
        return True

    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return False
    return scan.website.owner_id == user.id


def _session_owns_scan(request: Request, scan: Scan) -> bool:
    """Is the requester the visitor/owner who *created* this scan?

    Used by the state-changing/outbound endpoints (convert, email) which must
    never act on someone else's scan:

    * guest scan → the session that created it (matched by ``session_key``,
      with a fallback on the ``guest_scan_ids`` session list so the link
      survives the session-key rotation performed at login);
    * account scan → its owner.
    """
    if not scan.is_guest:
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and scan.website.owner_id == user.id
        )

    session_key = _session_key_of(request)
    if session_key and scan.session_key == session_key:
        return True

    owned_scans = request.session.get(GUEST_SCANS_SESSION_KEY) or []
    return str(scan.id) in {str(scan_id) for scan_id in owned_scans}


class PublicScanEndpointView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [PublicScanThrottle]

    def post(self, request: Request) -> Response:
        raw_input: str = (request.data.get("domain") or request.data.get("url") or "").strip()
        if not raw_input:
            return Response({"detail": "Domain or URL is required."}, status=status.HTTP_400_BAD_REQUEST)

        if "/check" in request.path and ("://" in raw_input or "/" in raw_input):
            return Response({"detail": "Invalid domain format. Protocols not allowed."}, status=status.HTTP_400_BAD_REQUEST)

        url_to_parse = raw_input if raw_input.startswith(("http://", "https://")) else f"https://{raw_input}"
        try:
            parsed = urlparse(url_to_parse)
            domain = (parsed.netloc or parsed.path.split("/")[0]).split(":")[0].lower().strip()
        except Exception:
            return Response({"detail": "Invalid URL format."}, status=status.HTTP_400_BAD_REQUEST)

        if not domain or len(domain) > 253 or not DOMAIN_REGEX.match(domain):
            return Response({"detail": "Invalid domain name format."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            domain = validate_domain_for_scan(domain)
        except (DomainValidationError, SSRFBlockedError, ValueError) as e:
            return Response({"detail": f"Restricted or unsafe domain: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Create guest session if needed
        if not request.session.session_key:
            request.session.save()
        session_key: str = request.session.session_key

        with transaction.atomic():
            website, _ = Website.objects.get_or_create(
                owner=request.user if request.user.is_authenticated else None,
                domain=domain,
                is_guest=not request.user.is_authenticated,
                defaults={"display_name": domain, "is_active": True},
            )

            # Create scan in QUEUED state with health steps
            scan = Scan.objects.create(
                website=website,
                trigger=Scan.Trigger.PUBLIC,
                status=Scan.Status.QUEUED,
                scan_type=Scan.ScanType.HEALTH,
                health_status=HealthStatus.NEUTRAL,
                is_guest=not request.user.is_authenticated,
                session_key=session_key if not request.user.is_authenticated else None,
                queued_at=timezone.now(),
            )
            # Initialize steps for health scan
            steps = build_initial_steps(Scan.ScanType.HEALTH)
            scan.steps = steps
            scan.save(update_fields=["steps", "updated_at"])

            if not request.user.is_authenticated:
                # Remember this guest scan on the visitor's session so it can
                # still be claimed after a signup (session key rotation).
                owned_scans = [
                    str(scan_id)
                    for scan_id in request.session.get(GUEST_SCANS_SESSION_KEY, [])
                    if str(scan_id) != str(scan.id)
                ]
                request.session[GUEST_SCANS_SESSION_KEY] = [str(scan.id)] + owned_scans[:19]
                request.session.modified = True

        # Enqueue the scan task
        try:
            run_public_scan.delay(scan.id)
        except Exception as e:
            logger.exception(f"Could not trigger run_public_scan for scan {scan.id}: {e}")
            # Mark scan as failed since we couldn't dispatch to Celery
            scan.transition_to(Scan.Status.FAILED, failure_message=f"Failed to queue scan task: {str(e)[:500]}")
            return Response(
                {"detail": "Failed to queue scan. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Return immediate response with scan identifier
        response_data = {
            "id": str(scan.id),
            "scan_id": str(scan.id),
            "domain": domain,
            "status": scan.status,
            "progress": scan.progress,
            "health_score": scan.health_score,
            "health_status": scan.health_status,
            "checks": [],
            "poll_url": f"/api/v1/public/scan/{scan.id}/status/",
            "steps": steps,
        }
        cache.set(f"public_scan:{scan.id}", response_data, timeout=3600)
        cache.set(f"public_check:{scan.id}", response_data, timeout=3600)
        return Response(response_data, status=status.HTTP_202_ACCEPTED)


class PublicScanStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, scan_id: str) -> Response:
        """Return a scan report.

        Security: the endpoint used to answer for *any* numeric scan id,
        including private scans owned by authenticated users.  It now returns
        404 as soon as the requester is not allowed to read the scan, so scan
        existence is not disclosed either.
        """
        lookup = str(scan_id)

        # For numeric scan IDs (DB-backed scans), always query the DB first
        # so the caller sees fresh state.
        if lookup.isdigit():
            scan = (
                Scan.objects
                .select_related("website")
                .prefetch_related("check_results")
                .filter(pk=int(lookup))
                .first()
            )
            if scan is None or not _may_read_scan(request, scan):
                return Response(
                    {"detail": "Scan not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response_data = _serialize_scan_with_rich_data(scan)
            # Update cache with fresh data
            cache.set(f"public_scan:{scan.id}", response_data, timeout=3600)
            cache.set(f"public_check:{scan.id}", response_data, timeout=3600)
            return Response(response_data, status=status.HTTP_200_OK)

        # Legacy session-key lookup: only honoured for the session that owns
        # the guest scan, so a leaked key cannot be used to enumerate scans.
        session_key = _session_key_of(request)
        if not session_key or lookup != session_key:
            return Response(
                {"detail": "Scan not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        scan = (
            Scan.objects
            .select_related("website")
            .prefetch_related("check_results")
            .filter(session_key=session_key, is_guest=True)
            .order_by("-created_at")
            .first()
        )
        if scan is None or not _may_read_scan(request, scan):
            return Response(
                {"detail": "Scan not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        response_data = _serialize_scan_with_rich_data(scan)
        return Response(response_data, status=status.HTTP_200_OK)


class PublicScanEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [PublicScanThrottle]

    def post(self, request: Request, scan_id: str) -> Response:
        email = request.data.get("email", "").strip().lower()
        if not email or "@" not in email:
            return Response({"detail": "Invalid email address."}, status=status.HTTP_400_BAD_REQUEST)

        # Security: only the visitor/owner of the scan may have its report
        # emailed — this endpoint used to accept any scan id and could be
        # abused to exfiltrate a private scan report to an arbitrary address.
        scan = (
            Scan.objects
            .select_related("website")
            .filter(pk=int(scan_id), is_guest=True)
            .first()
            if str(scan_id).isdigit()
            else None
        )
        if scan is None or not _session_owns_scan(request, scan):
            return Response({"detail": "Scan not found."}, status=status.HTTP_404_NOT_FOUND)

        lead, _ = PublicLead.objects.get_or_create(
            email=email,
            url_scanned=f"https://{scan.website.domain}",
            defaults={"scan_id": str(scan.id)},
        )

        language_code = _detect_language_code(request)

        try:
            send_public_scan_report_email.delay(
                lead_id=lead.id,
                scan_id=scan.id,
                email=email,
                language_code=language_code,
            )
        except Exception as e:
            logger.warning(f"Could not trigger celery email task: {e}")

        return Response({
            "status": "email_queued",
            "message": f"Report sent to {email}",
            "language": language_code,
        })


class PublicScanConvertView(APIView):
    """Claim a guest scan into the authenticated user's account.

    Security (IDOR): the endpoint used to accept any numeric scan id and then
    either take over its Website (``website.owner = request.user``) or attach
    the scan to a website the caller does not own.  A signed-in attacker could
    therefore steal another visitor's scan, and — worse — re-point an existing
    account's website to themselves.

    A conversion is now only possible when:

    * the scan is still a *guest* scan (``is_guest=True``) — an account scan can
      never be claimed by a third party;
    * the calling session is the visitor that created it.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, scan_id: str) -> Response:
        if not str(scan_id).isdigit():
            return Response({"detail": "Scan not found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            scan = (
                Scan.objects
                .select_for_update()
                .select_related("website")
                .filter(pk=int(scan_id), is_guest=True)
                .first()
            )
            if scan is None or not _session_owns_scan(request, scan):
                logger.warning(
                    "Rejected scan conversion: scan=%s user_id=%s "
                    "(not a guest scan of this session)",
                    scan_id,
                    request.user.pk,
                )
                return Response({"detail": "Scan not found."}, status=status.HTTP_404_NOT_FOUND)

            website = scan.website
            existing_user_site = Website.objects.filter(owner=request.user, domain=website.domain).first()
            if existing_user_site:
                scan.website = existing_user_site
                scan.is_guest = False
                scan.session_key = None
                scan.save(update_fields=["website", "is_guest", "session_key"])
                target_website = existing_user_site
            else:
                website.owner = request.user
                website.is_guest = False
                website.save(update_fields=["owner", "is_guest"])
                scan.is_guest = False
                scan.session_key = None
                scan.save(update_fields=["is_guest", "session_key"])
                target_website = website

            PublicLead.objects.filter(scan_id=str(scan.id), email=request.user.email).update(converted_to_user=request.user)

        return Response({
            "website_id": target_website.id,
            "dashboard_url": f"/app/websites/{target_website.id}",
        }, status=status.HTTP_200_OK)
