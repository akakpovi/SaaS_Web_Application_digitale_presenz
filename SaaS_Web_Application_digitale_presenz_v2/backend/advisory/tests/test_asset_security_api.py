"""Asset-scoped findings API and contextual advisor chat.

The advisor page opens with an optional asset focus (``?asset=<id>``).  Both
the listing and the chat must stay inside the organization: an asset id from
another tenant answers exactly like a missing one, and no other asset's
findings may reach the prompt or the response.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from advisory.models import SecurityFinding
from advisory.tests.test_security_advisor import (
    FAKE_MODEL,
    RecordingClient,
    make_tenant,
)
from organizations.models import Membership
from websites.models import Website


def create_finding(organization, asset, name, severity, **overrides):
    payload = {
        "organization": organization,
        "asset": asset,
        "scanner_source": "nuclei",
        "vulnerability_name": name,
        "severity": severity,
        "description": f"Description for {name}",
        "proof_or_payload": "SECRET-EVIDENCE-SHOULD-NOT-LEAK",
    }
    payload.update(overrides)
    return SecurityFinding.objects.create(**payload)


class AssetFindingApiTests(APITestCase):
    def setUp(self) -> None:
        self.owner, self.organization, self.asset = make_tenant(
            "asset-owner@example.com", "asset-owner.example"
        )
        self.analyst = User.objects.create_user(
            email="asset-analyst@example.com", password="pass1234!"
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role=Membership.Role.ANALYST,
        )
        self.viewer = User.objects.create_user(
            email="asset-viewer@example.com", password="pass1234!"
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )
        self.outsider, self.other_org, self.other_asset = make_tenant(
            "asset-outsider@example.com", "asset-outsider.example"
        )
        self.second_asset = Website.objects.create(
            owner=self.owner, domain="asset-owner-second.example"
        )

        self.critical = create_finding(
            self.organization,
            self.asset,
            "Exposed .env File",
            SecurityFinding.Severity.CRITICAL,
        )
        self.low = create_finding(
            self.organization,
            self.asset,
            "Missing CSP",
            SecurityFinding.Severity.LOW,
        )
        self.resolved = create_finding(
            self.organization,
            self.asset,
            "Old TLS",
            SecurityFinding.Severity.HIGH,
            status=SecurityFinding.Status.RESOLVED,
        )
        self.other_asset_finding = create_finding(
            self.organization,
            self.second_asset,
            "Other asset finding",
            SecurityFinding.Severity.CRITICAL,
        )
        self.foreign_finding = create_finding(
            self.other_org,
            self.other_asset,
            "Foreign tenant finding",
            SecurityFinding.Severity.CRITICAL,
        )

        self.url = reverse(
            "asset-security-findings",
            kwargs={
                "organization_id": self.organization.id,
                "asset_id": self.asset.pk,
            },
        )

    def get(self, user=None, **params):
        if user is not None:
            self.client.force_authenticate(user=user)
        return self.client.get(self.url, params)

    def test_owner_sees_open_findings_most_severe_first(self):
        response = self.get(self.owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["vulnerability_name"] for row in response.data["results"]]
        self.assertEqual(names, ["Exposed .env File", "Missing CSP"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_response_never_contains_evidence(self):
        response = self.get(self.owner)
        body = str(response.data)
        self.assertNotIn("SECRET-EVIDENCE-SHOULD-NOT-LEAK", body)
        self.assertNotIn("proof_or_payload", body)
        self.assertTrue(response.data["results"][0]["has_proof"])

    def test_status_all_includes_resolved_findings(self):
        response = self.get(self.owner, status="all")
        names = {row["vulnerability_name"] for row in response.data["results"]}
        self.assertIn("Old TLS", names)
        self.assertEqual(len(names), 3)

    def test_source_and_severity_filters(self):
        create_finding(
            self.organization,
            self.asset,
            "ZAP finding",
            SecurityFinding.Severity.MEDIUM,
            scanner_source="zap",
        )
        by_source = self.get(self.owner, source="zap")
        self.assertEqual(
            [row["vulnerability_name"] for row in by_source.data["results"]],
            ["ZAP finding"],
        )

        by_severity = self.get(self.owner, severity="critical")
        self.assertEqual(
            [row["vulnerability_name"] for row in by_severity.data["results"]],
            ["Exposed .env File"],
        )

    def test_invalid_filter_is_a_400(self):
        response = self.get(self.owner, status="deleted")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_viewer_can_read_but_not_see_other_tenants(self):
        response = self.get(self.viewer)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["vulnerability_name"] for row in response.data["results"]}
        self.assertNotIn("Foreign tenant finding", names)
        self.assertNotIn("Other asset finding", names)

    def test_other_tenant_asset_is_a_404(self):
        foreign_url = reverse(
            "asset-security-findings",
            kwargs={
                "organization_id": self.organization.id,
                "asset_id": self.other_asset.pk,
            },
        )
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(foreign_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_outsider_gets_404(self):
        response = self.get(self.outsider)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(AKA_AI_MAX_PROMPT_CHARS=60_000)
class AssetScopedChatTests(APITestCase):
    def setUp(self) -> None:
        self.owner, self.organization, self.asset = make_tenant(
            "chat-asset-owner@example.com", "chat-asset-owner.example"
        )
        self.second_asset = Website.objects.create(
            owner=self.owner, domain="chat-asset-second.example"
        )
        self.outsider, self.other_org, self.other_asset = make_tenant(
            "chat-asset-outsider@example.com", "chat-asset-outsider.example"
        )

        self.finding = create_finding(
            self.organization,
            self.asset,
            "Exposed .env File",
            SecurityFinding.Severity.CRITICAL,
        )
        self.sibling = create_finding(
            self.organization,
            self.second_asset,
            "SIBLING-ASSET-FINDING",
            SecurityFinding.Severity.HIGH,
        )
        self.foreign = create_finding(
            self.other_org,
            self.other_asset,
            "FOREIGN-TENANT-FINDING",
            SecurityFinding.Severity.CRITICAL,
        )

        self.url = reverse(
            "organization-advisor-chat",
            kwargs={"organization_id": self.organization.id},
        )

    def ask(self, client, **payload):
        self.client.force_authenticate(user=self.owner)
        with patch(
            "advisory.services.security_advisor.build_aka_client",
            return_value=client,
        ):
            return self.client.post(
                self.url,
                {"message": "What should I fix first?", **payload},
                format="json",
            )

    def test_asset_context_limits_the_prompt_to_that_asset(self):
        client = RecordingClient()
        response = self.ask(client, asset_id=self.asset.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["findings_included"], 1)
        prompt = "\n".join(
            message["content"] for message in client.calls[0]["messages"]
        )
        self.assertIn("ASSET UNDER DISCUSSION: chat-asset-owner.example", prompt)
        self.assertIn("Exposed .env File", prompt)
        self.assertNotIn("SIBLING-ASSET-FINDING", prompt)
        self.assertNotIn("FOREIGN-TENANT-FINDING", prompt)

    def test_chat_without_asset_still_covers_the_organization(self):
        client = RecordingClient()
        response = self.ask(client)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prompt = "\n".join(
            message["content"] for message in client.calls[0]["messages"]
        )
        self.assertIn("Exposed .env File", prompt)
        self.assertIn("SIBLING-ASSET-FINDING", prompt)
        self.assertNotIn("ASSET UNDER DISCUSSION", prompt)

    def test_asset_from_another_tenant_is_rejected_before_any_provider_call(self):
        client = RecordingClient()
        response = self.ask(client, asset_id=self.other_asset.pk)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(client.calls, [])

    def test_unknown_asset_is_rejected(self):
        client = RecordingClient()
        response = self.ask(client, asset_id=999_999)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(client.calls, [])

    def test_oversized_asset_id_is_rejected_by_the_serializer(self):
        client = RecordingClient()
        response = self.ask(client, asset_id=0)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(client.calls, [])

    def test_asset_context_uses_the_same_model_failover(self):
        client = RecordingClient(models=(FAKE_MODEL,))
        response = self.ask(client, asset_id=self.asset.pk)

        self.assertEqual(response.data["model"], FAKE_MODEL)
        self.assertEqual(len(client.calls), 1)
