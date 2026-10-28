"""Secure subprocess executor for external security tools.

All external scanner binaries (Nmap, Nikto, Nuclei, …) must be launched
through this module.  Direct ``subprocess`` calls are forbidden in
individual scanner implementations.

Security rules enforced here
------------------------------
* ``shell=False`` always (prevents shell injection via user input).
* The target hostname/IP is **always** passed as a separate list element,
  never interpolated into a command string.
* Output size is capped at ``max_output_bytes`` to prevent OOM attacks.
* Execution time is bounded by ``timeout``.
* Environment variables are filtered to avoid leaking secrets.

Usage::

    from scanners.executors.command import CommandExecutor, CommandResult

    executor = CommandExecutor()
    result = executor.run(
        command=["nmap", "-sV", "--", "93.184.216.34"],
        timeout=120,
    )
    print(result.exit_code, result.stdout[:500])
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Sequence

logger = logging.getLogger(__name__)

# Default output cap: 10 MiB.  Configurable per call.
DEFAULT_MAX_OUTPUT_BYTES: int = 10 * 1024 * 1024

# Allowlist of environment variables forwarded to child processes.
# Keep this minimal to avoid leaking secrets/credentials.
_SAFE_ENV_KEYS: frozenset[str] = frozenset(
    {
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "PATH",
        "SHELL",
        "TERM",
        "TZ",
        "USER",
        "LOGNAME",
        # Nuclei needs these for template discovery
        "NUCLEI_TEMPLATES_PATH",
        # Lighthouse / Chromium: explicit browser path (no secret).
        "CHROME_PATH",
    }
)


def build_child_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return a filtered, minimal environment for a child process.

    Only allowlisted variables are forwarded so scanner tools never inherit
    Django settings, database credentials or API keys from the worker.
    """
    safe = {k: v for k, v in os.environ.items() if k in _SAFE_ENV_KEYS}
    if extra:
        safe.update(extra)
    return safe


@dataclass
class CommandResult:
    """Normalised result from an external scanner command."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    command: list[str] = field(default_factory=list)
    timed_out: bool = False
    output_truncated: bool = False
    #: Set by the sandbox executor when the RSS watchdog killed the process.
    memory_exceeded: bool = False
    #: Machine-readable reason when the process was killed
    #: (``timeout``, ``memory``, ``exit_code``, ``binary_not_found``).
    killed_reason: str = ""

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


class CommandExecutor:
    """Thread-safe, security-hardened subprocess wrapper."""

    def __init__(
        self,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self.max_output_bytes = max_output_bytes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def binary_available(self, binary: str) -> bool:
        """Return True if *binary* is found on PATH."""
        return shutil.which(binary) is not None

    def run(
        self,
        command: Sequence[str],
        *,
        timeout: int,
        cwd: str | None = None,
        env_extra: dict[str, str] | None = None,
        scanner_name: str = "unknown",
    ) -> CommandResult:
        """Execute *command* and return a :class:`CommandResult`.

        Parameters
        ----------
        command:
            Command as a list of strings.  **Never** pass a shell string.
            The target must be a separate element (e.g. ``["nmap", "--", hostname]``).
        timeout:
            Hard deadline in seconds.  The process is killed on expiry.
        cwd:
            Working directory for the child process.
        env_extra:
            Additional environment variables to expose to the child (merged
            with the filtered safe env).
        scanner_name:
            Used in log messages for context.

        Returns
        -------
        CommandResult
            Always returns a result — never raises on non-zero exit codes.
        """
        cmd_list = list(command)

        if not cmd_list:
            raise ValueError("command must not be empty")

        env = self._build_env(env_extra)
        start = time.monotonic()

        logger.info(
            "Executing scanner command",
            extra={
                "scanner": scanner_name,
                "binary": cmd_list[0],
                "timeout": timeout,
            },
        )

        timed_out = False
        output_truncated = False
        stdout_bytes = b""
        stderr_bytes = b""
        exit_code = -1

        try:
            proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=cwd,
                shell=False,  # NEVER shell=True
                close_fds=True,
            )

            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_bytes, stderr_bytes = proc.communicate()
                exit_code = proc.returncode if proc.returncode is not None else -1
                timed_out = True
                logger.warning(
                    "Scanner timed out",
                    extra={"scanner": scanner_name, "timeout": timeout},
                )

        except FileNotFoundError:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "Scanner binary not found",
                extra={"scanner": scanner_name, "binary": cmd_list[0]},
            )
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=f"Binary '{cmd_list[0]}' not found",
                duration_ms=duration_ms,
                command=cmd_list,
            )

        duration_ms = int((time.monotonic() - start) * 1000)

        # Truncate oversized output.
        if len(stdout_bytes) > self.max_output_bytes:
            stdout_bytes = stdout_bytes[: self.max_output_bytes]
            output_truncated = True
            logger.warning(
                "Scanner output truncated",
                extra={
                    "scanner": scanner_name,
                    "max_bytes": self.max_output_bytes,
                },
            )

        stdout = self._decode(stdout_bytes)
        stderr = self._decode(stderr_bytes)

        logger.info(
            "Scanner command finished",
            extra={
                "scanner": scanner_name,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "timed_out": timed_out,
            },
        )

        return CommandResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            command=cmd_list,
            timed_out=timed_out,
            output_truncated=output_truncated,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_env(self, extra: dict[str, str] | None) -> dict[str, str]:
        """Build a filtered, minimal environment for the child process."""
        return build_child_environment(extra)

    @staticmethod
    def _decode(data: bytes) -> str:
        """Decode bytes to str, replacing invalid sequences."""
        return data.decode("utf-8", errors="replace")


# Module-level default executor instance.
default_executor = CommandExecutor()
