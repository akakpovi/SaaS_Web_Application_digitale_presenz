"""Persistent-enough counters for the Celery reapers.

The reapers normally only emit logs.  An operator should be able to answer
"is beat alive, and how many rows did the last ticks close?" without grepping
container logs.  The counters live in the shared cache (Redis in normal
deployments, locmem in tests) and have no expiry; the last-tick timestamps are
written on every run, including runs that reaped nothing.

Metric failures must never break a reaper: a cache outage is logged and the
database sweep continues.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

AI_RUNS_TOTAL_KEY = "reaper:ai_runs_total"
SCANS_TOTAL_KEY = "reaper:scans_total"
JOURNEYS_TOTAL_KEY = "reaper:journeys_total"
LAST_TICK_KEY = "reaper:last_tick"
AI_LAST_TICK_KEY = "reaper:ai_last_tick"
SCANS_LAST_TICK_KEY = "reaper:scans_last_tick"
JOURNEYS_LAST_TICK_KEY = "reaper:journeys_last_tick"
JOURNEYS_EXPIRED_TOTAL_KEY = "reaper:journeys_expired_total"
JOURNEYS_RECONCILED_TOTAL_KEY = "reaper:journeys_reconciled_total"
JOURNEYS_ORPHANS_TOTAL_KEY = "reaper:journeys_orphans_total"
JOURNEYS_ACTIVE_COUNT_KEY = "reaper:journeys_active_count"
JOURNEYS_AWAITING_COUNT_KEY = "reaper:journeys_awaiting_count"

_KINDS = {"ai", "scans", "journeys"}


def _increment(key: str, amount: int) -> None:
    """Atomically add *amount* to a counter, creating it at zero first."""
    if amount <= 0:
        return
    cache.add(key, 0, timeout=None)
    try:
        cache.incr(key, amount)
    except ValueError:
        # The key expired or was evicted between add() and incr().
        cache.set(key, amount, timeout=None)


def record_reaper_tick(
    *,
    kind: str,
    reaped: int = 0,
    now: Any | None = None,
) -> None:
    """Record one completed reaper tick.

    ``kind`` is ``"ai"``, ``"scans"`` or ``"journeys"``.  The per-kind counter
    and last-tick timestamp are updated, plus the global last-tick timestamp
    used by the status command.  The journey breakdown and gauges are recorded
    separately by :func:`record_journey_reaper_tick`.
    """
    if kind not in _KINDS:
        raise ValueError(f"Unknown reaper kind: {kind!r}")
    timestamp = (now or timezone.now()).isoformat()
    try:
        if kind == "ai":
            _increment(AI_RUNS_TOTAL_KEY, int(reaped or 0))
            cache.set(AI_LAST_TICK_KEY, timestamp, timeout=None)
        elif kind == "scans":
            _increment(SCANS_TOTAL_KEY, int(reaped or 0))
            cache.set(SCANS_LAST_TICK_KEY, timestamp, timeout=None)
        else:
            _increment(JOURNEYS_TOTAL_KEY, int(reaped or 0))
            cache.set(JOURNEYS_LAST_TICK_KEY, timestamp, timeout=None)
        cache.set(LAST_TICK_KEY, timestamp, timeout=None)
    except Exception:  # pragma: no cover - defensive, cache outage
        logger.exception("reaper_metrics_unavailable kind=%s", kind)


def record_journey_reaper_tick(
    *,
    expired: int = 0,
    reconciled: int = 0,
    orphans: int = 0,
    active: int = 0,
    awaiting: int = 0,
    now: Any | None = None,
) -> None:
    """Record a journey tick with its per-outcome counters and gauges.

    ``journeys_total``/``journeys_last_tick`` come from
    :func:`record_reaper_tick`; this function adds the breakdown needed to
    tell an expiry wave from a reconciliation wave, plus the current number
    of active and awaiting journeys.
    """
    timestamp_dt = now or timezone.now()
    record_reaper_tick(
        kind="journeys",
        reaped=expired + reconciled + orphans,
        now=timestamp_dt,
    )

    timestamp = timestamp_dt.isoformat()
    try:
        _increment(JOURNEYS_EXPIRED_TOTAL_KEY, int(expired or 0))
        _increment(JOURNEYS_RECONCILED_TOTAL_KEY, int(reconciled or 0))
        _increment(JOURNEYS_ORPHANS_TOTAL_KEY, int(orphans or 0))
        cache.set(JOURNEYS_ACTIVE_COUNT_KEY, int(active or 0), timeout=None)
        cache.set(JOURNEYS_AWAITING_COUNT_KEY, int(awaiting or 0), timeout=None)
        cache.set(JOURNEYS_LAST_TICK_KEY, timestamp, timeout=None)
    except Exception:  # pragma: no cover - defensive, cache outage
        logger.exception("reaper_metrics_unavailable kind=journeys detail")


def read_reaper_metrics() -> dict[str, Any]:
    """Return the counters and last-tick timestamps for the status command."""
    return {
        "ai_runs_total": int(cache.get(AI_RUNS_TOTAL_KEY) or 0),
        "scans_total": int(cache.get(SCANS_TOTAL_KEY) or 0),
        "journeys_total": int(cache.get(JOURNEYS_TOTAL_KEY) or 0),
        "last_tick": cache.get(LAST_TICK_KEY),
        "ai_last_tick": cache.get(AI_LAST_TICK_KEY),
        "scans_last_tick": cache.get(SCANS_LAST_TICK_KEY),
        "journeys_last_tick": cache.get(JOURNEYS_LAST_TICK_KEY),
        "journeys_expired_total": int(
            cache.get(JOURNEYS_EXPIRED_TOTAL_KEY) or 0
        ),
        "journeys_reconciled_total": int(
            cache.get(JOURNEYS_RECONCILED_TOTAL_KEY) or 0
        ),
        "journeys_orphans_total": int(
            cache.get(JOURNEYS_ORPHANS_TOTAL_KEY) or 0
        ),
        "journeys_active_count": int(cache.get(JOURNEYS_ACTIVE_COUNT_KEY) or 0),
        "journeys_awaiting_count": int(
            cache.get(JOURNEYS_AWAITING_COUNT_KEY) or 0
        ),
    }
