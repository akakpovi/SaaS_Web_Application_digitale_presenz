import re
from rest_framework import serializers
from .models import Website, domain_validator
from scans.models import Scan
from scans.serializers import CheckResultSerializer


class WebsiteSerializer(serializers.ModelSerializer):
    # validators=[] empêche DRF d'exécuter le validateur de modèle sur la chaîne brute non normalisée
    domain = serializers.CharField(max_length=253, validators=[])

    class Meta:
        model = Website
        fields = ["id", "domain", "display_name", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_domain(self, value):
        raw = (value or "").strip()
        if not raw:
            raise serializers.ValidationError("Enter a valid domain name without a scheme, path, or port.")

        # Rejeter immédiatement les schémas (https://), chemins (/path) ou ports (:8080)
        if "://" in raw or "/" in raw or ":" in raw:
            raise serializers.ValidationError("Enter a valid domain name without a scheme, path, or port.")

        # Normalisation automatique (suppression du point FQDN final et passage en minuscules)
        domain = raw.rstrip(".").lower()

        # Validation via le validateur officiel du modèle sur la valeur normalisée
        domain_validator(domain)

        # Vérification d'unicité par propriétaire
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


class WebsiteDetailSerializer(WebsiteSerializer):
    health_score = serializers.SerializerMethodField()
    last_scan_id = serializers.SerializerMethodField()
    last_scan_status = serializers.SerializerMethodField()
    checks = serializers.SerializerMethodField()

    class Meta(WebsiteSerializer.Meta):
        fields = WebsiteSerializer.Meta.fields + [
            "health_score",
            "last_scan_id",
            "last_scan_status",
            "checks",
        ]

    def _get_latest_scan(self, obj):
        if not hasattr(obj, "_cached_latest_scan"):
            obj._cached_latest_scan = (
                Scan.objects.filter(website=obj)
                .order_by("-created_at")
                .prefetch_related("check_results")
                .first()
            )
        return obj._cached_latest_scan

    def get_health_score(self, obj):
        latest = self._get_latest_scan(obj)
        return latest.health_score if latest else None

    def get_last_scan_id(self, obj):
        latest = self._get_latest_scan(obj)
        return latest.id if latest else None

    def get_last_scan_status(self, obj):
        latest = self._get_latest_scan(obj)
        return latest.status if latest else None

    def get_checks(self, obj):
        latest = self._get_latest_scan(obj)
        if not latest:
            return []
        return CheckResultSerializer(latest.check_results.all(), many=True).data
