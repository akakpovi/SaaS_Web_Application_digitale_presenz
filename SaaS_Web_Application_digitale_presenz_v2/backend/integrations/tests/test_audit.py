from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlparse

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from integrations.models import OAuthConnection, SocialAuditEvent
from integrations.providers.base import ExternalIdentity, OAuthTokens
from integrations.services.audit import client_ip, record_social_audit_event
from integrations.tests.utils import create_connection, make_org
from organizations.models import Membership


class SocialAuditModelTests(TestCase):
    def setUp(self) -> None:
        self.organization = make_org("Audit")
        self.actor = self.organization.billing_owner

    def _event(self, **overrides) -> SocialAuditEvent:
        values = {
            "organization_id": self.organization.id,
            "actor": self.actor,
            "action": SocialAuditEvent.Action.CONNECTED,
            "provider": OAuthConnection.Provider.LINKEDIN,
            "external_account_id": "audit-account",
            "connection_id": None,
            "request": SimpleNamespace(
                META={
                    "HTTP_X_REAL_IP": "203.0.113.10",
                    "REMOTE_ADDR": "10.0.0.1",
                }
            ),
        }
        values.update(overrides)
        return record_social_audit_event(**values)

    def test_event_persists_actor_action_ip_and_timestamp(self):
        event = self._event()

        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.actor)
        self.assertEqual(event.actor_email, self.actor.email)
        self.assertEqual(event.action, SocialAuditEvent.Action.CONNECTED)
        self.assertEqual(event.provider, OAuthConnection.Provider.LINKEDIN)
        self.assertEqual(event.external_account_id, "audit-account")
        self.assertEqual(event.ip_address, "203.0.113.10")
        self.assertIsNotNone(event.created_at)

    def test_event_is_append_only_through_model_and_queryset(self):
        event = self._event()
        original_action = event.action

        event.action = SocialAuditEvent.Action.DISCONNECTED
        with self.assertRaises(ValidationError):
            event.save()

        with self.assertRaises(ValidationError):
            event.delete()

        with self.assertRaises(ValidationError):
            SocialAuditEvent.objects.filter(pk=event.pk).update(
                action=SocialAuditEvent.Action.DISCONNECTED
            )

        with self.assertRaises(ValidationError):
            SocialAuditEvent.objects.filter(pk=event.pk).delete()

        event.refresh_from_db()
        self.assertEqual(event.action, original_action)

    def test_actor_deletion_keeps_the_audit_row_and_email_snapshot(self):
        event = self._event()
        actor_email = self.actor.email
        self.actor.delete()

        event.refresh_from_db()
        self.assertIsNone(event.actor)
        self.assertEqual(event.actor_email, actor_email)

    def test_event_does_not_store_token_material(self):
        connection = create_connection(
            self.organization,
            access_token="audit-access-token-secret",
            refresh_token="audit-refresh-token-secret",
        )
        event = self._event(
            connection_id=connection.id,
            external_account_id=connection.external_account_id,
        )

        rendered = json.dumps(
            {
                field.name: str(getattr(event, field.name))
                for field in event._meta.fields
            },
            default=str,
        )
        self.assertNotIn("audit-access-token-secret", rendered)
        self.assertNotIn("audit-refresh-token-secret", rendered)
        self.assertNotIn(connection.access_token_ciphertext, rendered)
        self.assertNotIn(connection.refresh_token_ciphertext, rendered)


class ClientIpTests(TestCase):
    def test_real_ip_is_preferred_over_remote_addr(self):
        request = SimpleNamespace(
            META={
                "HTTP_X_REAL_IP": "203.0.113.20",
                "REMOTE_ADDR": "10.0.0.20",
            }
        )
        self.assertEqual(client_ip(request), "203.0.113.20")

    def test_invalid_real_ip_falls_back_to_remote_addr(self):
        request = SimpleNamespace(
            META={
                "HTTP_X_REAL_IP": "not-an-ip",
                "REMOTE_ADDR": "198.51.100.20",
            }
        )
        self.assertEqual(client_ip(request), "198.51.100.20")

    def test_forwarded_for_is_not_trusted(self):
        request = SimpleNamespace(
            META={
                "HTTP_X_FORWARDED_FOR": "203.0.113.30",
            }
        )
        self.assertIsNone(client_ip(request))

    def test_missing_request_or_headers_yields_none(self):
        self.assertIsNone(client_ip(None))
        self.assertIsNone(client_ip(SimpleNamespace(META={})))


class SocialAuditFlowAPITests(APITestCase):
    def setUp(self) -> None:
        self.organization = make_org("Audit Flow")
        self.owner = self.organization.billing_owner
        self.client.force_authenticate(user=self.owner)

    def test_connect_and_disconnect_write_immutable_actor_events(self):
        authorize = self.client.get(
            f"/api/v1/organizations/{self.organization.id}/social/connections/"
            "linkedin/authorize/"
        )
        self.assertEqual(authorize.status_code, status.HTTP_200_OK)
        raw_state = parse_qs(urlparse(authorize.data["authorization_url"]).query)[
            "state"
        ][0]

        provider_client = Mock()
        provider_client.exchange_code.return_value = OAuthTokens(
            access_token="flow-access-token-secret",
            refresh_token="flow-refresh-token-secret",
            expires_in=3600,
        )
        provider_client.fetch_identity.return_value = ExternalIdentity(
            subject="audit-flow-account",
            display_name="Audit Flow User",
        )

        callback_query = urlencode({"code": "authorization-code", "state": raw_state})
        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=provider_client,
        ):
            callback = self.client.get(
                f"/api/v1/social/oauth/linkedin/callback/?{callback_query}",
                HTTP_X_REAL_IP="203.0.113.40",
            )

        self.assertEqual(callback.status_code, status.HTTP_302_FOUND)
        connection = OAuthConnection.objects.get(
            organization=self.organization,
            provider=OAuthConnection.Provider.LINKEDIN,
            external_account_id="audit-flow-account",
        )
        connected = SocialAuditEvent.objects.get(
            action=SocialAuditEvent.Action.CONNECTED
        )
        self.assertEqual(connected.organization, self.organization)
        self.assertEqual(connected.actor, self.owner)
        self.assertEqual(connected.actor_email, self.owner.email)
        self.assertEqual(connected.provider, OAuthConnection.Provider.LINKEDIN)
        self.assertEqual(connected.external_account_id, "audit-flow-account")
        self.assertEqual(connected.connection_id, connection.id)
        self.assertEqual(connected.ip_address, "203.0.113.40")

        revoke_client = Mock()
        with patch(
            "integrations.services.connections.get_provider_client",
            return_value=revoke_client,
        ):
            deleted = self.client.delete(
                f"/api/v1/organizations/{self.organization.id}/social/connections/"
                f"{connection.id}/",
                HTTP_X_REAL_IP="203.0.113.50",
            )

        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OAuthConnection.objects.filter(pk=connection.id).exists())
        revoke_client.revoke_token.assert_called_once_with(
            access_token="flow-access-token-secret"
        )

        disconnected = SocialAuditEvent.objects.get(
            action=SocialAuditEvent.Action.DISCONNECTED
        )
        self.assertEqual(disconnected.organization, self.organization)
        self.assertEqual(disconnected.actor, self.owner)
        self.assertEqual(disconnected.actor_email, self.owner.email)
        self.assertEqual(disconnected.provider, OAuthConnection.Provider.LINKEDIN)
        self.assertEqual(disconnected.external_account_id, "audit-flow-account")
        self.assertEqual(disconnected.connection_id, connection.id)
        self.assertEqual(disconnected.ip_address, "203.0.113.50")

        rendered = json.dumps(
            [
                {
                    field.name: str(getattr(event, field.name))
                    for field in event._meta.fields
                }
                for event in (connected, disconnected)
            ],
            default=str,
        )
        self.assertNotIn("flow-access-token-secret", rendered)
        self.assertNotIn("flow-refresh-token-secret", rendered)


class SocialAuditAPITests(APITestCase):
    def setUp(self) -> None:
        self.organization = make_org("Audit API")
        self.owner = self.organization.billing_owner
        self.admin = User.objects.create_user(
            "audit-api-admin@example.com",
            "Password123!",
        )
        self.analyst = User.objects.create_user(
            "audit-api-analyst@example.com",
            "Password123!",
        )
        self.viewer = User.objects.create_user(
            "audit-api-viewer@example.com",
            "Password123!",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.admin,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role=Membership.Role.ANALYST,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )

        self.other_organization = make_org("Audit Other")
        self.outsider = self.other_organization.billing_owner

        request = SimpleNamespace(META={"HTTP_X_REAL_IP": "203.0.113.60"})
        self.connected = record_social_audit_event(
            organization_id=self.organization.id,
            actor=self.owner,
            action=SocialAuditEvent.Action.CONNECTED,
            provider=OAuthConnection.Provider.LINKEDIN,
            external_account_id="audit-api-linkedin",
            request=request,
        )
        self.disconnected = record_social_audit_event(
            organization_id=self.organization.id,
            actor=self.admin,
            action=SocialAuditEvent.Action.DISCONNECTED,
            provider=OAuthConnection.Provider.GOOGLE,
            external_account_id="audit-api-google",
            request=request,
        )
        record_social_audit_event(
            organization_id=self.other_organization.id,
            actor=self.outsider,
            action=SocialAuditEvent.Action.CONNECTED,
            provider=OAuthConnection.Provider.LINKEDIN,
            external_account_id="audit-api-other-tenant",
            request=request,
        )

    def _url(self, organization=None) -> str:
        organization = organization or self.organization
        return f"/api/v1/organizations/{organization.id}/social/audit/"

    def _auth(self, user) -> None:
        self.client.force_authenticate(user=user)

    def test_owner_and_admin_can_list_paginated_tenant_events(self):
        self._auth(self.owner)
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response.data["count"], 2)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(
            {item["id"] for item in results},
            {str(self.connected.id), str(self.disconnected.id)},
        )
        expected_order = [
            str(event_id)
            for event_id in SocialAuditEvent.objects.filter(
                organization=self.organization
            )
            .order_by("-created_at")
            .values_list("id", flat=True)
        ]
        self.assertEqual([item["id"] for item in results], expected_order)
        self.assertNotIn(
            str(self.other_organization.id),
            {item["organization"] for item in results},
        )
        for item in results:
            self.assertEqual(
                set(item),
                {
                    "id",
                    "organization",
                    "actor",
                    "actor_email",
                    "action",
                    "provider",
                    "external_account_id",
                    "connection_id",
                    "ip_address",
                    "created_at",
                },
            )
            self.assertEqual(item["ip_address"], "203.0.113.60")
            rendered_item = json.dumps(item, default=str)
            self.assertNotIn("access_token", rendered_item)
            self.assertNotIn("refresh_token", rendered_item)

        rendered = json.dumps(results, default=str)
        self.assertNotIn("audit-api-other-tenant", rendered)

        self._auth(self.admin)
        admin_response = self.client.get(self._url())
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.data["count"], 2)

    def test_analyst_viewer_outsider_and_anonymous_are_rejected(self):
        for user in (self.analyst, self.viewer):
            self._auth(user)
            response = self.client.get(self._url())
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self._auth(self.outsider)
        outsider_response = self.client.get(self._url())
        self.assertEqual(
            outsider_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self._auth(None)
        anonymous_response = self.client.get(self._url())
        self.assertEqual(
            anonymous_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_action_and_provider_filters_are_scoped(self):
        self._auth(self.owner)

        action_response = self.client.get(self._url(), {"action": "disconnected"})
        self.assertEqual(action_response.status_code, status.HTTP_200_OK)
        self.assertEqual(action_response.data["count"], 1)
        self.assertEqual(
            action_response.data["results"][0]["id"],
            str(self.disconnected.id),
        )

        provider_response = self.client.get(self._url(), {"provider": "linkedin"})
        self.assertEqual(provider_response.status_code, status.HTTP_200_OK)
        self.assertEqual(provider_response.data["count"], 1)
        self.assertEqual(
            provider_response.data["results"][0]["id"],
            str(self.connected.id),
        )

        combined = self.client.get(
            self._url(),
            {"action": "connected", "provider": "linkedin"},
        )
        self.assertEqual(combined.status_code, status.HTTP_200_OK)
        self.assertEqual(combined.data["count"], 1)

    def test_invalid_filters_are_rejected(self):
        self._auth(self.owner)

        action_response = self.client.get(self._url(), {"action": "deleted"})
        self.assertEqual(
            action_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        provider_response = self.client.get(
            self._url(),
            {"provider": "myspace"},
        )
        self.assertEqual(
            provider_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
