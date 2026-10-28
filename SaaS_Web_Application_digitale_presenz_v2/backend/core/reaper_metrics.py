"""Persistent-enough counters for the two Celery reapers.

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
LAST_TICK_KEY = "reaper:last_tick"
AI_LAST_TICK_KEY = "reaper:ai_last_tick"
SCANS_LAST_TICK_KEY = "reaper:scans_last_tick"

_KINDS = {"ai", "scans"}


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

    ``kind`` is ``"ai"`` or ``"scans"``.  The per-kind counter and last-tick
    timestamp are updated, plus the global last-tick timestamp used by the
    status command.
    """
    if kind not in _KINDS:
        raise ValueError(f"Unknown reaper kind: {kind!r}")
    timestamp = (now or timezone.now()).isoformat()
    try:
        if kind == "ai":
            _increment(AI_RUNS_TOTAL_KEY, int(reaped or 0))
            cache.set(AI_LAST_TICK_KEY, timestamp, timeout=None)
        else:
            _increment(SCANS_TOTAL_KEY, int(reaped or 0))
            cache.set(SCANS_LAST_TICK_KEY, timestamp, timeout=None)
        cache.set(LAST_TICK_KEY, timestamp, timeout=None)
    except Exception:  # pragma: no cover - defensive, cache outage
        logger.exception("reaper_metrics_unavailable kind=%s", kind)


def read_reaper_metrics() -> dict[str, Any]:
    """Return the counters and last-tick timestamps for the status command."""
    return {
        "ai_runs_total": int(cache.get(AI_RUNS_TOTAL_KEY) or 0),
        "scans_total": int(cache.get(SCANS_TOTAL_KEY) or 0),
        "last_tick": cache.get(LAST_TICK_KEY),
        "ai_last_tick": cache.get(AI_LAST_TICK_KEY),
        "scans_last_tick": cache.get(SCANS_LAST_TICK_KEY),
    }
