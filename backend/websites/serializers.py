import re
from rest_framework import serializers
from .models import Website
from scans.models import Scan
from scans.serializers import CheckResultSerializer

DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


class WebsiteSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(max_length=253, validators=[])
    health_score = serializers.SerializerMethodField()
    health_status = serializers.SerializerMethodField()
    last_scan_at = serializers.SerializerMethodField()
    last_scan_id = serializers.SerializerMethodField()

    class Meta:
        model = Website
        fields = [
            "id",
            "domain",
            "display_name",
            "is_active",
            "is_guest",
            "created_at",
            "updated_at",
            "health_score",
            "health_status",
            "last_scan_at",
            "last_scan_id",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_domain(self, value):
        raw = (value or "").strip()
        if not raw:
            raise serializers.ValidationError("Enter a valid domain name without a scheme, path, or port.")
        if "://" in raw or "/" in raw or ":" in raw:
            raise serializers.ValidationError("Enter a valid domain name without a scheme, path, or port.")
        domain = raw.rstrip(".").lower()
        if not DOMAIN_REGEX.match(domain):
            raise serializers.ValidationError("Enter a valid domain name without a scheme, path, or port.")
        request = self.context.get("request")
        owner = getattr(request, "user", None) if request else None
        if self.instance and self.instance.owner:
            owner = self.instance.owner
        if owner and owner.is_authenticated:
            qs = Website.objects.filter(owner=owner, domain=domain)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Un site avec ce domaine existe déjà pour cet utilisateur.")
        return domain

    def get_last_scan(self, obj):
        return Scan.objects.filter(website=obj).order_by('-created_at').first()

    def get_health_score(self, obj):
        last_scan = self.get_last_scan(obj)
        return last_scan.health_score if last_scan else None

    def get_health_status(self, obj):
        last_scan = self.get_last_scan(obj)
        return last_scan.health_status if last_scan else None

    def get_last_scan_at(self, obj):
        last_scan = self.get_last_scan(obj)
        return last_scan.completed_at if last_scan else None

    def get_last_scan_id(self, obj):
        last_scan = self.get_last_scan(obj)
        return last_scan.id if last_scan else None


class WebsiteListSerializer(WebsiteSerializer):
    class Meta(WebsiteSerializer.Meta):
        pass


class WebsiteDetailSerializer(WebsiteSerializer):
    checks = serializers.SerializerMethodField()

    class Meta(WebsiteSerializer.Meta):
        fields = WebsiteSerializer.Meta.fields + ["checks"]

    def get_checks(self, obj):
        latest = self.get_last_scan(obj)
        if not latest:
            return []
        return CheckResultSerializer(latest.check_results.all(), many=True).data
