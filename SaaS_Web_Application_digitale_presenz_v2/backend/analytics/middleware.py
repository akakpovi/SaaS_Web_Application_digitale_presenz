import hashlib
from django.utils.deprecation import MiddlewareMixin
from .models import TrafficLog

class TrafficTrackingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        path = request.path
        # Ne pas logger les fichiers statiques ou health checks
        if any(path.startswith(prefix) for prefix in ["/static/", "/media/", "/favicon.ico", "/health/"]):
            return response

        try:
            ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
            if ip:
                ip = ip.split(",")[0].strip()
            ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else ""
            
            user = request.user if request.user.is_authenticated else None
            
            TrafficLog.objects.create(
                path=path[:500],
                method=request.method,
                ip_hash=ip_hash,
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:250],
                referrer=request.META.get("HTTP_REFERER", "")[:500],
                user=user,
                status_code=response.status_code,
            )
        except Exception:
            pass
            
        return response
