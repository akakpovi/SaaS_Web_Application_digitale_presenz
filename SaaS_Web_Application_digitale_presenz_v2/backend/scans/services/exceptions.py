"""Domain exceptions for progressive scan journeys.

These errors are raised by :mod:`scans.services.journey_service`.  They are
deliberately independent of DRF: the service is a backend-only layer and must
stay callable from Celery tasks and plain Python code.  Lot D maps them to
HTTP status codes (409, 410, 403, 429).
"""

from __future__ import annotations


class JourneyError(Exception):
    """Base class for every journey orchestration error."""


class JourneyConflictError(JourneyError):
    """Another journey or a classic scan conflicts with the operation."""


class JourneyStateError(JourneyError):
    """The journey state does not allow the requested operation."""


class JourneyExpiredError(JourneyError):
    """The journey's confirmation window has expired."""


class QuotaExceededError(JourneyError):
    """The organization has exhausted its monthly scan quota."""


__all__ = (
    "JourneyError",
    "JourneyConflictError",
    "JourneyStateError",
    "JourneyExpiredError",
    "QuotaExceededError",
)
