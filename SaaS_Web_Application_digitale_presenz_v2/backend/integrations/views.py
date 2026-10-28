"""OAuth authorize and callback endpoints."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.access import (
    DELETE_ROLES,
    MANAGE_MEMBER_ROLES,
    READ_ROLES,
    WRITE_ROLES,
    role_for_organization,
)
from organizations.models import Organization

from .models import OAuthConnection, SocialAuditEvent
from .serializers import OAuthConnectionSerializer, SocialAuditEventSerializer
from .services.connections import disconnect_connection
from .services.oauth import (
    OAuthFlowError,
    complete_oauth_flow,
    start_oauth_flow,
)

OAUTH_REDIRECT_ERROR = "auth_failed"

# Only the application's own error identifiers may reach the React app.  A
# provider-controlled string, an exception message or an arbitrary query
# value must never be reflected into the redirect.
OAUTH_REDIRECT_ERRORS = frozenset(
    {
        OAUTH_REDIRECT_ERROR,
        "forbidden",
        "invalid_request",
        "invalid_state",
        "oauth_exchange_failed",
        "oauth_identity_failed",
        "oauth_storage_failed",
        "provider_not_configured",
        "unsupported_provider",
    }
)


def _frontend_base_url() -> str:
    """Return a fixed frontend origin, or a safe same-origin fallback.

    ``FRONTEND_URL`` is the only source of truth.  Request headers such as
    ``Host`` or ``Referer`` are deliberately ignored: trusting them would turn
    the callback into an open redirect.  If the setting is empty or malformed,
    a relative ``/`` keeps the browser on the API origin and cannot redirect
    to a third-party site.
    """

    base = str(getattr(settings, "FRONTEND_URL", "") or "").strip()
    parts = urlsplit(base)
    if parts.scheme in {"http", "https"} and parts.netloc:
        return base
    return "/"


def _frontend_callback_url(provider: str, *, error: str | None = None) -> str:
    """Build the fixed-origin React return URL without leaking OAuth data.

    Only a whitelisted integration name and a fixed status/error value are
    appended.  The provider ``code``, ``state``, verifier and provider error
    description never leave the callback URL.
    """

    parts = urlsplit(_frontend_base_url())

    normalized_provider = (provider or "").strip().lower()
    integration = (
        "linkedin" if normalized_provider == "linkedin" else "unknown"
    )
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["integration"] = integration
    if error:
        query["error"] = (
            error if error in OAUTH_REDIRECT_ERRORS else OAUTH_REDIRECT_ERROR
        )
        query.pop("status", None)
    else:
        query["status"] = "success"
        query.pop("error", None)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path or "/",
            urlencode(query),
            parts.fragment,
        )
    )


def _redirect_to_frontend(
    provider: str,
    *,
    error: str | None = None,
) -> HttpResponseRedirect:
    response = HttpResponseRedirect(
        _frontend_callback_url(provider, error=error)
    )
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    # Do not send the callback URL (which contains code/state) as a Referer
    # to the React application or any of its subresources.
    response["Referrer-Policy"] = "no-referrer"
    return response


def _oauth_error(error: OAuthFlowError) -> Response:
    response = Response(
        {"error": error.code, "detail": error.message},
        status=error.status_code,
    )
    response["Cache-Control"] = "no-store"
    return response


def _organization_with_role(
    request: Request,
    organization_id,
    allowed_roles,
    denied_message: str,
):
    organization = get_object_or_404(Organization, pk=organization_id)
    role = role_for_organization(request.user, organization)
    if role is None:
        # Do not reveal the existence of another tenant's organization.
        raise NotFound("Organization not found.")
    if role not in allowed_roles:
        raise PermissionDenied(denied_message)
    return organization


def _organization_for_authorization(request: Request, organization_id):
    return _organization_with_role(
        request,
        organization_id,
        WRITE_ROLES,
        "Your organization role does not allow connecting social accounts.",
    )


def _organization_for_read(request: Request, organization_id):
    return _organization_with_role(
        request,
        organization_id,
        READ_ROLES,
        "Your organization role does not allow viewing social connections.",
    )


def _organization_for_delete(request: Request, organization_id):
    return _organization_with_role(
        request,
        organization_id,
        DELETE_ROLES,
        "Your organization role does not allow disconnecting social accounts.",
    )


def _organization_for_audit(request: Request, organization_id):
    return _organization_with_role(
        request,
        organization_id,
        MANAGE_MEMBER_ROLES,
        "Your organization role does not allow viewing the social audit trail.",
    )


class SocialAuditEventListView(generics.ListAPIView):
    """GET /api/v1/organizations/<org>/social/audit/.

    Read-only, owner/admin only.  The global DRF pagination applies and the
    default ordering is newest-first.  ``action`` and ``provider`` accept only
    the model's declared choices so a caller cannot probe arbitrary columns.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SocialAuditEventSerializer

    def get_queryset(self):
        organization = _organization_for_audit(
            self.request,
            self.kwargs["organization_id"],
        )
        queryset = SocialAuditEvent.objects.filter(organization=organization)

        action = str(
            self.request.query_params.get("action") or ""
        ).strip().lower()
        if action:
            if action not in SocialAuditEvent.Action.values:
                raise ValidationError({"action": "Invalid audit action."})
            queryset = queryset.filter(action=action)

        provider = str(
            self.request.query_params.get("provider") or ""
        ).strip().lower()
        if provider:
            if provider not in OAuthConnection.Provider.values:
                raise ValidationError({"provider": "Invalid provider."})
            queryset = queryset.filter(provider=provider)

        return queryset.order_by("-created_at")

    def list(self, request: Request, *args, **kwargs) -> Response:
        response = super().list(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class OAuthConnectionListView(generics.ListAPIView):
    """GET /api/v1/organizations/<org>/social/connections/.

    Metadata only: the serializer never exposes ciphertext or plaintext.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OAuthConnectionSerializer

    def get_queryset(self):
        organization = _organization_for_read(
            self.request,
            self.kwargs["organization_id"],
        )
        return OAuthConnection.objects.filter(organization=organization)

    def list(self, request: Request, *args, **kwargs) -> Response:
        response = super().list(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class OAuthConnectionDetailView(APIView):
    """DELETE /api/v1/organizations/<org>/social/connections/<id>/."""

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, organization_id, connection_id) -> Response:
        organization = _organization_for_delete(request, organization_id)
        connection = get_object_or_404(
            OAuthConnection,
            pk=connection_id,
            organization=organization,
        )
        try:
            disconnect_connection(
                connection,
                actor=request.user,
                request=request,
            )
        except OAuthFlowError as error:
            return _oauth_error(error)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        response["Cache-Control"] = "no-store"
        return response


class OAuthAuthorizeView(APIView):
    """GET /api/v1/organizations/<org>/social/connections/<provider>/authorize/."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, organization_id, provider: str) -> Response:
        organization = _organization_for_authorization(request, organization_id)
        try:
            authorization = start_oauth_flow(
                organization,
                request.user,
                provider,
            )
        except OAuthFlowError as error:
            return _oauth_error(error)

        response = Response(
            {
                "provider": authorization.provider,
                "authorization_url": authorization.authorization_url,
                "expires_at": authorization.expires_at,
            },
            status=status.HTTP_200_OK,
        )
        response["Cache-Control"] = "no-store"
        return response


class OAuthCallbackView(APIView):
    """GET /api/v1/social/oauth/<provider>/callback/.

    This endpoint is public by design: the provider redirects the browser here
    without the application's JWT header.  The single-use, tenant-bound state
    row authenticates the flow; ``complete_oauth_flow`` never trusts the
    request user.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request: Request, provider: str) -> HttpResponseRedirect:
        if request.query_params.get("error"):
            return _redirect_to_frontend(
                provider,
                error=OAUTH_REDIRECT_ERROR,
            )

        try:
            connection = complete_oauth_flow(
                provider,
                request.query_params.get("code"),
                request.query_params.get("state"),
                request=request,
            )
        except OAuthFlowError as error:
            return _redirect_to_frontend(
                provider,
                error=error.code,
            )

        return _redirect_to_frontend(connection.provider)
