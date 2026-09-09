import json
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
from scanners import (
    website_scanner,
    ssl_scanner,
    dns_scanner,
    email_security_scanner,
    security_headers_scanner,
    performance_scanner,
    uptime_scanner,
)
from scans.models import Scan, CheckResult, HealthStatus
from scans.services.scoring import PublicScorableResult, calculate_health_score
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
        "url": f"https://{scan.website.domain}",
        "domain": scan.website.domain,
        "score": scan.health_score or 0,
        "created_at": scan.created_at.isoformat() if scan.created_at else timezone.now().isoformat(),
        "scanned_at": scan.completed_at.isoformat() if scan.completed_at else timezone.now().isoformat(),
        "summary": {
            "critical": critical_count,
            "warnings": warning_count,
            "passed": passed_count
        },
        "checks": checks,
        "meta": {
            "total_monitored_sites": Website.objects.count() or 2847,
            "average_rating": 4.8
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

        if "/check" in request.path:
            scan_id = str(uuid.uuid4())
            data = {
                "id": scan_id,
                "scan_id": scan_id,
                "domain": domain,
                "status": "queued",
                "progress": 0,
                "health_score": None,
                "health_status": None,
                "checks": [],
                "poll_url": f"/api/v1/public/check/{scan_id}/",
            }
            cache.set(f"public_scan:{scan_id}", data, timeout=3600)
            cache.set(f"public_check:{scan_id}", data, timeout=3600)
            try:
                run_public_scan.delay(domain, scan_id)
            except Exception as e:
                logger.warning(f"Could not trigger run_public_scan: {e}")
            return Response(data, status=status.HTTP_202_ACCEPTED)

        if not request.session.session_key:
            request.session.save()
        session_key: str = request.session.session_key

        scanners = {
            "website": website_scanner,
            "ssl": ssl_scanner,
            "dns": dns_scanner,
            "email_security": email_security_scanner,
            "security_headers": security_headers_scanner,
            "performance": performance_scanner,
            "uptime": uptime_scanner,
        }

        scanner_outputs: dict[str, Any] = {}
        for name, scanner_module in scanners.items():
            try:
                res = scanner_module.scan(domain)
                score = getattr(res, "score", 0)
                res_status = str(getattr(res, "status", "critical")).lower()
                if hasattr(res_status, "value"):
                    res_status = res_status.value
                elif "." in str(res_status):
                    res_status = str(res_status).split(".")[-1].lower()

                message = getattr(res, "message", "") or getattr(res, "recommendation", "") or f"{name} check completed."
                recommendation = getattr(res, "recommendation", "")
                details = getattr(res, "details", {})
                duration_ms = getattr(res, "duration_ms", 0)

                scanner_outputs[name] = {
                    "score": int(score) if score is not None else 0,
                    "status": res_status,
                    "summary": str(message),
                    "recommendation": str(recommendation),
                    "technical_details": {**details, "duration_ms": duration_ms},
                }
            except Exception as ex:
                logger.exception(f"Error running {name} scanner for domain {domain}")
                scanner_outputs[name] = {
                    "score": 0,
                    "status": "critical",
                    "summary": "Scanner failed unexpectedly.",
                    "recommendation": "",
                    "technical_details": {"error": str(ex)},
                }

        scorable_results = [
            PublicScorableResult(category=cat, score=out["score"], status=out["status"])
            for cat, out in scanner_outputs.items()
        ]

        try:
            calc = calculate_health_score(scorable_results)
            health_score: int = getattr(calc, "score", 70)
            health_status_val: str = getattr(calc, "status", HealthStatus.HEALTHY)
            if hasattr(health_status_val, "value"):
                health_status_val = health_status_val.value
        except Exception:
            health_score = int(sum(d["score"] for d in scanner_outputs.values()) / max(1, len(scanner_outputs)))
            health_status_val = HealthStatus.HEALTHY if health_score >= 80 else HealthStatus.WARNING

        with transaction.atomic():
            website, _ = Website.objects.get_or_create(
                owner=request.user if request.user.is_authenticated else None,
                domain=domain,
                is_guest=not request.user.is_authenticated,
                defaults={"display_name": domain, "is_active": True},
            )

            scan = Scan.objects.create(
                website=website,
                trigger=Scan.Trigger.PUBLIC,
                status=Scan.Status.COMPLETED,
                health_score=health_score,
                health_status=health_status_val,
                is_guest=not request.user.is_authenticated,
                session_key=session_key if not request.user.is_authenticated else None,
                started_at=timezone.now(),
                completed_at=timezone.now(),
            )

            for category, out in scanner_outputs.items():
                status_mapped = out["status"]
                if status_mapped not in [s.value for s in HealthStatus]:
                    status_mapped = HealthStatus.NEUTRAL.value

                CheckResult.objects.create(
                    scan=scan,
                    category=category,
                    status=status_mapped,
                    score=out["score"] if category != "uptime" else None,
                    summary=out["summary"],
                    recommendation=out["recommendation"],
                    technical_details=out["technical_details"],
                )

        response_data = _serialize_scan_with_rich_data(scan)
        cache.set(f"public_check:{scan.id}", response_data, timeout=3600)
        cache.set(f"public_scan:{scan.id}", response_data, timeout=3600)
        return Response(response_data, status=status.HTTP_200_OK)


class PublicScanStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, scan_id: str) -> Response:
        cached = cache.get(f"public_scan:{scan_id}") or cache.get(f"public_check:{scan_id}")
        if cached:
            if isinstance(cached, str):
                try:
                    cached = json.loads(cached)
                except Exception:
                    pass
            if isinstance(cached, dict):
                return Response(cached, status=status.HTTP_200_OK)

        scan = None
        if str(scan_id).isdigit():
            scan = (
                Scan.objects
                .select_related("website")
                .prefetch_related("check_results")
                .filter(pk=int(scan_id))
                .first()
            )

        if not scan:
            scan = (
                Scan.objects
                .select_related("website")
                .prefetch_related("check_results")
                .filter(session_key=str(scan_id))
                .first()
            )

        if not scan:
            return Response({"detail": "Scan not found."}, status=status.HTTP_404_NOT_FOUND)

        response_data = _serialize_scan_with_rich_data(scan)
        return Response(response_data, status=status.HTTP_200_OK)


class PublicScanEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [PublicScanThrottle]

    def post(self, request: Request, scan_id: str) -> Response:
        email = request.data.get("email", "").strip().lower()
        if not email or "@" not in email:
            return Response({"detail": "Invalid email address."}, status=status.HTTP_400_BAD_REQUEST)

        scan = Scan.objects.select_related("website").filter(pk=int(scan_id)).first() if str(scan_id).isdigit() else None
        if not scan:
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
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, scan_id: str) -> Response:
        scan = Scan.objects.select_related("website").filter(pk=int(scan_id)).first() if str(scan_id).isdigit() else None
        if not scan:
            return Response({"detail": "Scan not found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
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
