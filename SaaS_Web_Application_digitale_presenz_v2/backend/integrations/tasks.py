"""Scheduled maintenance for social connector credentials."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from integrations.models import OAuthConnection
from integrations.services.refresh import (
    REFRESH_BATCH_SIZE,
    REFRESH_WINDOW_HOURS,
    refresh_connection,
)

logger = logging.getLogger("integrations.refresh")


def _positive_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


@shared_task(name="integrations.tasks.refresh_expiring_social_tokens")
def refresh_expiring_social_tokens() -> dict:
    """Refresh LinkedIn connections expiring inside the configured window.

    The window includes already-expired access tokens: a valid refresh token
    can still recover them.  Rows are locked with ``skip_locked`` so two beat
    workers cannot refresh the same connection concurrently.  The provider
    call happens while the row is locked; that serializes refreshes for one
    account at the cost of holding the lock for the provider timeout.

    A failure on one connection never aborts the batch.  Tokens are never
    included in the returned summary or in log lines.
    """

    window_hours = _positive_int(
        "SOCIAL_TOKEN_REFRESH_WINDOW_HOURS",
        REFRESH_WINDOW_HOURS,
        720,
    )
    batch_size = _positive_int(
        "SOCIAL_TOKEN_REFRESH_BATCH_SIZE",
        REFRESH_BATCH_SIZE,
        1000,
    )
    now = timezone.now()
    deadline = now + timedelta(hours=window_hours)

    candidate_ids = list(
        OAuthConnection.objects.filter(
            provider=OAuthConnection.Provider.LINKEDIN,
            status=OAuthConnection.Status.ACTIVE,
            expires_at__isnull=False,
            expires_at__lte=deadline,
        )
        .order_by("expires_at")
        .values_list("pk", flat=True)[:batch_size]
    )

    summary = {
        "candidates": len(candidate_ids),
        "refreshed": 0,
        "skipped": 0,
        "failed": 0,
        "reasons": {},
    }

    for connection_id in candidate_ids:
        try:
            with transaction.atomic():
                connection = (
                    OAuthConnection.objects.select_for_update(skip_locked=True)
                    .filter(
                        pk=connection_id,
                        provider=OAuthConnection.Provider.LINKEDIN,
                        status=OAuthConnection.Status.ACTIVE,
                        expires_at__isnull=False,
                        expires_at__lte=deadline,
                    )
                    .first()
                )
                if connection is None:
                    # Another worker refreshed or removed it after selection.
                    summary["skipped"] += 1
                    continue
                outcome = refresh_connection(connection)
        except DatabaseError:
            summary["failed"] += 1
            summary["reasons"]["database_error"] = (
                summary["reasons"].get("database_error", 0) + 1
            )
            logger.warning(
                "oauth_refresh_database_error connection=%s",
                connection_id,
            )
            continue
        except Exception as exc:  # noqa: BLE001 - isolate one bad connection
            summary["failed"] += 1
            summary["reasons"]["unexpected_error"] = (
                summary["reasons"].get("unexpected_error", 0) + 1
            )
            logger.warning(
                "oauth_refresh_unexpected_error connection=%s error=%s",
                connection_id,
                type(exc).__name__,
            )
            continue

        summary["reasons"][outcome] = summary["reasons"].get(outcome, 0) + 1
        if outcome == "refreshed":
            summary["refreshed"] += 1
        elif outcome == "missing_refresh_token":
            summary["skipped"] += 1
        else:
            summary["failed"] += 1

    logger.info(
        "oauth_refresh_batch candidates=%s refreshed=%s skipped=%s failed=%s",
        summary["candidates"],
        summary["refreshed"],
        summary["skipped"],
        summary["failed"],
    )
    return summary
