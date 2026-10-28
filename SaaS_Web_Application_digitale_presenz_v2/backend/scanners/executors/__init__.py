"""Executors package for the Scanner Engine.

``command`` is the low-level subprocess wrapper.  ``sandbox`` is the hardened
layer that every external tool must use: it applies CPU/RAM/time limits and
supports one-shot Docker containers.
"""

from scanners.executors.sandbox import (
    SandboxBusyError,
    SandboxError,
    SandboxLimits,
    SandboxMode,
    SandboxUnavailableError,
    get_sandbox_executor,
    sandbox_status,
)

__all__ = [
    "SandboxBusyError",
    "SandboxError",
    "SandboxLimits",
    "SandboxMode",
    "SandboxUnavailableError",
    "get_sandbox_executor",
    "sandbox_status",
]
