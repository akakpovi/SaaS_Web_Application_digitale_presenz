"""Central scanner registry.

Usage::

    from scanners.registry import ScannerRegistry

    ScannerRegistry.register(NmapScanner)
    scanner = ScannerRegistry.get("nmap")

The registry is populated at application startup via
``scanners/__init__.py``.  Business logic must never do ``if scanner_name ==
'nmap': ...`` — use ``ScannerRegistry.get()`` instead.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class _ScannerRegistry:
    """Singleton registry that maps scanner names → scanner instances."""

    def __init__(self) -> None:
        self._registry: dict[str, "BaseScanner"] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, scanner: "BaseScanner") -> None:
        """Register a scanner instance.

        ``scanner.name`` is used as the key.  Registering a second scanner
        with the same name silently replaces the previous one (allows
        overrides in tests).
        """
        if scanner.name is None:
            raise ValueError(
                f"Scanner {scanner.__class__.__name__} has no 'name' attribute."
            )
        self._registry[scanner.name] = scanner
        logger.debug("Registered scanner: %s", scanner.name)

    def register_class(self, cls: type["BaseScanner"]) -> None:
        """Instantiate *cls* and register it.

        Convenience shortcut so callers can pass a class rather than an
        instance.
        """
        self.register(cls())

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> "BaseScanner":
        """Return the scanner registered under *name*.

        Raises ``KeyError`` if the scanner is unknown.
        """
        try:
            return self._registry[name]
        except KeyError:
            available = ", ".join(sorted(self._registry)) or "<none>"
            raise KeyError(
                f"No scanner registered under '{name}'. Available scanners: {available}"
            ) from None

    def get_or_none(self, name: str) -> "BaseScanner | None":
        """Return the scanner or *None* if not registered."""
        return self._registry.get(name)

    def is_registered(self, name: str) -> bool:
        return name in self._registry

    def is_available(self, name: str) -> bool:
        """Return True if the scanner is registered *and* available.

        Availability is determined by the scanner's own ``is_available()``
        method (e.g. checking that the binary exists on disk).
        """
        scanner = self._registry.get(name)
        if scanner is None:
            return False
        return scanner.is_available()

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def all(self) -> list["BaseScanner"]:
        """Return all registered scanners."""
        return list(self._registry.values())

    def names(self) -> list[str]:
        """Return the names of all registered scanners."""
        return sorted(self._registry)

    def available(self) -> list["BaseScanner"]:
        """Return only scanners that report themselves as available."""
        return [s for s in self._registry.values() if s.is_available()]

    def __iter__(self) -> Iterator["BaseScanner"]:
        return iter(self._registry.values())

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, name: object) -> bool:
        return name in self._registry

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def status_report(self) -> dict[str, dict]:
        """Return a dict of scanner name → availability info (for admin/debug)."""
        report: dict[str, dict] = {}
        for name, scanner in self._registry.items():
            report[name] = {
                "available": scanner.is_available(),
                "scanner_type": scanner.scanner_type,
                "version": scanner.scanner_version,
                "timeout": scanner.timeout,
            }
        return report


# Module-level singleton — the single source of truth for all scanners.
ScannerRegistry = _ScannerRegistry()
