from rest_framework import serializers

from .models import Website


class WebsiteSerializer(serializers.ModelSerializer[Website]):
    domain = serializers.CharField(max_length=253, trim_whitespace=True)

    class Meta:
        model = Website
        fields = ("id", "domain", "display_name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_domain(self, value: str) -> str:
        domain = value.strip().lower().rstrip(".")
        if "://" in domain or "/" in domain or ":" in domain:
            raise serializers.ValidationError("Enter only a domain name, without a scheme, path, or port.")
        return domain

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        domain = attrs.get("domain", getattr(self.instance, "domain", ""))
        owner = self.context["request"].user
        existing = Website.objects.filter(owner=owner, domain=domain)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError({"domain": "You already monitor this domain."})
        return attrs
