from rest_framework import serializers

from .models import AIRecommendation, SecurityFinding

# Mirrors ``security_advisor.MAX_QUESTION_CHARS``: the service re-checks the
# bound because it can be called outside HTTP.
MAX_QUESTION_CHARS = 2_000


class AdvisorChatRequestSerializer(serializers.Serializer):
    """Payload of ``POST /organizations/{org_id}/ai-advisor/chat/``."""

    message = serializers.CharField(
        min_length=3,
        max_length=MAX_QUESTION_CHARS,
        trim_whitespace=True,
        help_text="Operator question about the organization's open findings.",
    )
    asset_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text=(
            "Optional website id.  When provided, the advisor is restricted to "
            "that asset's open findings of this organization."
        ),
    )


class AdvisorChatResponseSerializer(serializers.Serializer):
    """Read-only answer; never echoes the prompt, evidence or any token."""

    reply = serializers.CharField()
    model = serializers.CharField()
    findings_included = serializers.IntegerField()
    context_truncated = serializers.BooleanField()
    request_id = serializers.CharField(allow_null=True)


class AssetSecurityFindingSerializer(serializers.ModelSerializer):
    """Metadata of one finding for the asset page.

    ``proof_or_payload`` is deliberately absent: raw evidence can contain
    tokens or personal data and the asset view does not need it.  The admin
    import/advisor paths keep it server-side only.
    """

    asset_id = serializers.IntegerField(read_only=True)
    has_proof = serializers.SerializerMethodField()

    class Meta:
        model = SecurityFinding
        fields = [
            "id",
            "asset_id",
            "scanner_source",
            "vulnerability_name",
            "severity",
            "status",
            "description",
            "detected_at",
            "resolved_at",
            "has_proof",
        ]
        read_only_fields = fields

    def get_has_proof(self, obj: SecurityFinding) -> bool:
        return bool(obj.proof_or_payload)


class AIRecommendationSerializer(serializers.ModelSerializer):
    check_code = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    finding_id = serializers.IntegerField(read_only=True)
    check_result_id = serializers.IntegerField(read_only=True)
    accepted_by = serializers.PrimaryKeyRelatedField(read_only=True)
    dismissed_by = serializers.PrimaryKeyRelatedField(read_only=True)
    source = serializers.SerializerMethodField()
    persisted = serializers.SerializerMethodField()

    class Meta:
        model = AIRecommendation
        fields = [
            "id",
            "title",
            "summary",
            "action",
            "effort",
            "priority",
            "confidence",
            "check_code",
            "category",
            "finding_id",
            "check_result_id",
            "status",
            "accepted_by",
            "accepted_at",
            "dismissed_by",
            "dismissed_at",
            "source",
            "persisted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_check_code(self, obj: AIRecommendation) -> str:
        if obj.finding_id is not None:
            return obj.finding.check_code
        if obj.check_result_id is not None:
            return f"{obj.check_result.category}.overall"
        return ""

    def get_category(self, obj: AIRecommendation) -> str:
        if obj.finding_id is not None:
            return obj.finding.category
        if obj.check_result_id is not None:
            return obj.check_result.category
        return ""

    def get_source(self, obj: AIRecommendation) -> str:
        return "ai"

    def get_persisted(self, obj: AIRecommendation) -> bool:
        return True
