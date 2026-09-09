import time
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle


class PublicScanThrottle(BaseThrottle):
    """
    Rate limiter dynamique :
    - Route /api/v1/public/scan/ : 5 requêtes / heure (Phase 2)
    - Route legacy /api/v1/public/check/ : 10 requêtes / heure (Requis pour test_legacy_public_checker)
    """
    duration = 3600

    def get_ident(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        remote_addr = request.META.get("REMOTE_ADDR")
        if xff:
            return xff.split(",")[0].strip()
        return remote_addr or "127.0.0.1"

    def get_rate(self, request):
        if "/check" in request.path:
            return 10
        return 5

    def allow_request(self, request, view):
        ident = self.get_ident(request)
        rate = self.get_rate(request)
        scope = "public_check" if "/check" in request.path else "public_scan"
        key = f"throttle_{scope}_{ident}"
        now = time.time()

        history = cache.get(key, [])
        history = [ts for ts in history if ts > now - self.duration]

        if len(history) >= rate:
            return False

        history.append(now)
        cache.set(key, history, timeout=self.duration)
        return True

    def wait(self):
        return self.duration
