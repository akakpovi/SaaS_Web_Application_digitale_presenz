"""Append-only audit trail for social connector lifecycle actions."""

from __future__ import annotations

import ipaddress
import logging

from integrations.models import SocialAuditEvent

logger = logging.getLogger("integrations.audit")


def client_ip(request) -> str | None:
    """Return the client IP without trusting a browser-supplied header.

    The canonical deployment overwrites ``X-Real-IP`` at the edge proxy with
    ``$remote_addr``.  If that header is absent or malformed (for example when
    the app is reached directly during development), fall back to
    ``REMOTE_ADDR``.  ``X-Forwarded-For`` is intentionally not parsed here:
    its leftmost values are client-controlled and would let an actor forge the
    address stored in the audit trail.
    """

    if request is None:
        return None

    meta = getattr(request, "META", {}) or {}
    for key in ("HTTP_X_REAL_IP", "REMOTE_ADDR"):
        raw = str(meta.get(key) or "").strip()
        if not raw:
            continue
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            continue
    return None


def record_social_audit_event(
    *,
    organization_id,
    actor,
    action: str,
    provider: str,
    external_account_id: str,
    connection_id=None,
    request=None,
) -> SocialAuditEvent:
    """Append one immutable audit row.

    Only non-secret metadata is stored.  Call this inside the same database
    transaction as the connection mutation so a failed audit insert rolls the
    mutation back instead of leaving an unaudited change.
    """

    actor_email = ""
    actor_id = None
    if actor is not None and getattr(actor, "pk", None) is not None:
        actor_id = actor.pk
        actor_email = str(getattr(actor, "email", "") or "")

    event = SocialAuditEvent.objects.create(
        organization_id=organization_id,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        provider=provider,
        external_account_id=external_account_id,
        connection_id=connection_id,
        ip_address=client_ip(request),
    )
    logger.info(
        "social_audit_event action=%s org=%s provider=%s",
        action,
        organization_id,
        provider,
    )
    return event
