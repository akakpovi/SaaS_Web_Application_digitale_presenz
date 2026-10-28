"""Resource-bounded, isolated execution for external scanner tools.

The scan engine delegates work to external open-source tools (Lighthouse,
testssl.sh, nmap, …).  Those tools are untrusted from the orchestrator's point
of view: they consume CPU/RAM, may hang, and may spawn children.  This module
is the single choke point that guarantees a scan can never take the VPS down.

Two execution modes
-------------------
``process`` (default)
    The tool runs as a child of the Celery worker in its own session/process
    group.  The following limits are applied:

    * wall-clock timeout, enforced with ``SIGKILL`` on the whole process group;
    * ``RLIMIT_CPU`` hard CPU limit;
    * RSS watchdog sampling ``/proc`` every 250 ms, killing the group when the
      combined resident memory exceeds ``memory_mb`` (Node/Chrome reserve huge
      virtual address spaces, so an ``RLIMIT_AS`` cap would break them while an
      RSS cap measures what actually pressures the VPS);
    * ``RLIMIT_FSIZE`` / ``RLIMIT_NOFILE`` to bound disk writes and descriptors;
    * filtered environment (no secrets inherited) and output cap.

``docker``
    Each invocation is a one-shot container: ``--memory``, ``--memory-swap``,
    ``--cpus``, ``--pids-limit``, ``--read-only``, ``--cap-drop=ALL``,
    ``--security-opt=no-new-privileges``, dedicated ``/tmp`` tmpfs, no pull at
    scan time.  This gives hard kernel-enforced limits and filesystem
    isolation.  It requires the Docker CLI and socket on the worker host; the
    image must already be present locally (``pull_policy=never``).

A short-lived cross-worker concurrency gate (Redis cache) bounds how many
sandboxed tools run at the same time, so two scans cannot each start a
Chromium and exhaust the VPS.

Security boundary
-----------------
This module enforces *resource* isolation.  Target validation (SSRF) is
enforced **before** delegation by ``ScanOrchestrator._validated_target`` and
again by each network scanner.  Never call this executor with an unvalidated
user-supplied target.

Usage::

    from scanners.executors.sandbox import get_sandbox_executor

    executor = get_sandbox_executor()
    limits = executor.limits_for("lighthouse", timeout=90)
    result = executor.run(command, limits=limits, scanner_name="lighthouse")
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, replace
from typing import Any, Sequence

from django.conf import settings

from scanners.executors.command import (
    DEFAULT_MAX_OUTPUT_BYTES,
    CommandResult,
    build_child_environment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class SandboxMode:
    PROCESS = "process"
    DOCKER = "docker"


#: Sampling interval for the RSS watchdog (seconds).
_RSS_SAMPLE_INTERVAL = 0.25

#: Default Docker tmpfs size for ``/tmp`` (Chromium profiles need headroom).
_DEFAULT_TMPFS_MB = 256


class SandboxError(Exception):
    """Base class for sandbox execution failures."""


class SandboxUnavailableError(SandboxError):
    """Raised when the configured sandbox mode cannot run a command."""


class SandboxBusyError(SandboxError):
    """Raised when no sandbox slot became available before the deadline."""


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SandboxLimits:
    """Resource envelope for one external tool invocation.

    ``memory_mb=0`` disables the memory cap (only useful for tools that manage
    their own memory; Docker mode treats 0 as "no ``--memory`` flag").
    ``pids_limit=0`` disables the process-count cap.
    """

    timeout_s: int
    cpu_seconds: int
    memory_mb: int = 0
    pids_limit: int = 0
    file_size_mb: int = 64
    open_files: int = 256

    def with_timeout(self, timeout_s: int) -> "SandboxLimits":
        """Return a copy bounded by *timeout_s* (never below 1 second)."""
        return replace(self, timeout_s=max(1, int(timeout_s)))

    def clamped(self, max_timeout_s: int) -> "SandboxLimits":
        """Clamp the wall-clock and CPU budgets to *max_timeout_s*."""
        max_timeout_s = max(1, int(max_timeout_s or 1))
        return replace(
            self,
            timeout_s=min(max(1, self.timeout_s), max_timeout_s),
            cpu_seconds=min(
                max(1, self.cpu_seconds),
                max_timeout_s,
            ),
        )


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _sandbox_settings() -> dict[str, Any]:
    return getattr(settings, "SCANNER_SANDBOX", {}) or {}


def _docker_settings() -> dict[str, Any]:
    return _sandbox_settings().get("docker", {}) or {}


#: Whether the image of the last probe still exists, with the time it was seen.
_DOCKER_IMAGE_CACHE: dict[str, tuple[float, bool]] = {}
_DOCKER_IMAGE_CACHE_TTL = 60.0
_DOCKER_IMAGE_INSPECT_TIMEOUT = 15


def docker_image_present(image: str, *, binary: str = "docker") -> bool:
    """Return whether *image* exists in the local Docker image store.

    The sandbox runs with ``--pull never``: a missing image makes ``docker
    run`` fail with exit code 125, which looks like a crashed tool rather than
    an unconfigured environment.  Probing first turns that into the honest
    ``unavailable`` outcome — no scan result is fabricated either way, but the
    operator sees the real cause.  The answer is cached briefly so a scan with
    several tools does not pay one ``docker image inspect`` per step.
    """
    now = time.monotonic()
    cached = _DOCKER_IMAGE_CACHE.get(image)
    if cached is not None and now - cached[0] < _DOCKER_IMAGE_CACHE_TTL:
        return cached[1]

    present = False
    try:
        proc = subprocess.run(  # noqa: S603 - argv is built from settings
            [binary, "image", "inspect", image, "--format", "{{.Id}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=_DOCKER_IMAGE_INSPECT_TIMEOUT,
        )
        present = proc.returncode == 0 and bool(proc.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        # Fail closed: an unverifiable image is treated as absent so the
        # adapter reports the scanner as unavailable instead of guessing.
        present = False

    _DOCKER_IMAGE_CACHE[image] = (now, present)
    return present


def _scanner_settings(scanner_name: str) -> dict[str, Any]:
    return getattr(settings, "SCANNER_CONFIG", {}).get(scanner_name, {}) or {}


def _scanner_sandbox_settings(scanner_name: str) -> dict[str, Any]:
    return _scanner_settings(scanner_name).get("sandbox", {}) or {}


def docker_tmpfs_for(scanner_name: str) -> list[str]:
    """Return extra ``--tmpfs`` mounts configured for *scanner_name*.

    Some tools (ZAP) need a writable directory inside an otherwise read-only
    container.  Entries come from trusted settings, never from scan input.
    """
    raw = _scanner_sandbox_settings(scanner_name).get("tmpfs") or []
    if isinstance(raw, str):
        raw = [raw]
    mounts: list[str] = []
    for entry in raw:
        value = str(entry).strip()
        if value and value.startswith("/"):
            mounts.append(value)
    return mounts


def shared_work_dir() -> str:
    """Directory both the worker and the Docker daemon can see, or ``""``.

    A containerised worker creates its temporary files inside its own
    namespace; the daemon on the host cannot bind-mount those paths (it fails
    with "bind source path does not exist").  When the stack mounts a shared
    directory into the worker, adapters create their output files there so the
    ``docker run --mount`` reference resolves to a real host path.
    """
    raw = (
        (getattr(settings, "SCANNER_SANDBOX", {}) or {}).get("shared_work_dir")
        or ""
    )
    path = str(raw).strip()
    if not path:
        return ""
    resolved = os.path.realpath(path)
    if not os.path.isdir(resolved):
        logger.warning(
            "SCANNER_SANDBOX_SHARED_WORK_DIR=%s does not exist; falling back "
            "to %s (Docker bind mounts may fail when the worker runs in a "
            "container)",
            resolved,
            tempfile.gettempdir(),
        )
        return ""
    if not os.access(resolved, os.W_OK):
        # A root-owned 0755 directory mounted into the worker is the classic
        # failure: tempfile silently falls back to /tmp, Docker then cannot
        # bind-mount that path on the host.  Warn loudly instead.
        logger.warning(
            "SCANNER_SANDBOX_SHARED_WORK_DIR=%s is not writable by uid %s; "
            "fix its permissions (install -d -m 1777 %s)",
            resolved,
            os.getuid(),
            resolved,
        )
        return ""
    return resolved


def _allowed_bind_roots() -> list[str]:
    """Directories a sandbox bind mount may point at."""
    roots = [os.path.realpath(tempfile.gettempdir())]
    shared = shared_work_dir()
    if shared:
        roots.append(shared)
    return roots


def _validate_bind_mounts(
    mounts: Sequence[tuple[str, str]] | None,
) -> list[tuple[str, str]]:
    """Validate host bind mounts used for scanner output files.

    Only directories under the system temporary directory (or the configured
    shared work directory) may be mounted.  This keeps the sandbox API from
    becoming an arbitrary host-filesystem escape if a future adapter mishandles
    input.
    """
    if not mounts:
        return []

    roots = _allowed_bind_roots()
    validated: list[tuple[str, str]] = []
    for host_path, container_path in mounts:
        host = os.path.realpath(str(host_path))
        if not any(host == root or host.startswith(root + os.sep) for root in roots):
            raise SandboxError(
                f"Refusing bind mount outside {roots}: {host_path!r}"
            )
        if not os.path.isdir(host):
            raise SandboxError(f"Bind mount source is not a directory: {host_path!r}")

        target = str(container_path)
        if not target.startswith("/") or ".." in target.split("/"):
            raise SandboxError(f"Invalid container mount path: {container_path!r}")
        validated.append((host, target))
    return validated


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------

def _kill_process_group(pid: int) -> None:
    """Kill *pid* and every process in its group, ignoring races."""
    try:
        pgid = os.getpgid(pid)
    except (ProcessLookupError, OSError):
        pgid = pid

    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        # The process already exited or is not a group leader.
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def _process_group_rss_bytes(pgid: int) -> int:
    """Return the combined resident memory of all processes in *pgid*.

    Reads ``/proc`` directly to avoid adding a ``psutil`` dependency.  Returns
    0 when ``/proc`` is unavailable (e.g. macOS development machines).
    """
    proc_root = "/proc"
    if not os.path.isdir(proc_root):
        return 0

    total = 0
    try:
        entries = list(os.scandir(proc_root))
    except OSError:
        return 0

    for entry in entries:
        if not entry.name.isdigit():
            continue
        stat_path = os.path.join(proc_root, entry.name, "stat")
        status_path = os.path.join(proc_root, entry.name, "status")
        try:
            with open(stat_path, "r", encoding="utf-8", errors="replace") as handle:
                stat_line = handle.read()

            # Field layout: pid (comm) state ppid pgrp ...
            # ``comm`` may contain spaces and parentheses, hence rfind(")").
            close_paren = stat_line.rfind(")")
            if close_paren == -1:
                continue
            fields = stat_line[close_paren + 2:].split()
            if len(fields) < 3:
                continue
            # fields[0] = state, fields[1] = ppid, fields[2] = pgrp
            if int(fields[2]) != pgid:
                continue

            with open(status_path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.startswith("VmRSS:"):
                        total += int(line.split()[1]) * 1024
                        break
        except (OSError, ValueError, IndexError):
            continue

    return total


class _RssWatchdog(threading.Thread):
    """Kill a process group when its resident memory exceeds a limit."""

    def __init__(self, pgid: int, limit_bytes: int) -> None:
        super().__init__(name=f"scan-rss-watchdog-{pgid}", daemon=True)
        self.pgid = pgid
        self.limit_bytes = limit_bytes
        self.exceeded = False
        self.peak_bytes = 0
        self._stop_event = threading.Event()

    def run(self) -> None:  # pragma: no cover - exercised through run()
        while not self._stop_event.wait(_RSS_SAMPLE_INTERVAL):
            rss = _process_group_rss_bytes(self.pgid)
            self.peak_bytes = max(self.peak_bytes, rss)
            if rss > self.limit_bytes:
                self.exceeded = True
                logger.warning(
                    "Scanner sandbox memory limit exceeded: pgid=%d rss=%d limit=%d",
                    self.pgid,
                    rss,
                    self.limit_bytes,
                )
                _kill_process_group(self.pgid)
                return

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=2.0)


def _make_preexec(limits: SandboxLimits):
    """Return a ``preexec_fn`` applying best-effort rlimits in the child."""

    def _apply() -> None:  # pragma: no cover - runs in the forked child
        try:
            import resource

            if limits.cpu_seconds > 0:
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (limits.cpu_seconds, limits.cpu_seconds + 1),
                )
            if limits.file_size_mb > 0:
                file_bytes = int(limits.file_size_mb) * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
            if limits.open_files > 0:
                resource.setrlimit(
                    resource.RLIMIT_NOFILE,
                    (limits.open_files, limits.open_files),
                )
            if limits.pids_limit > 0:
                # RLIMIT_NPROC counts all processes of the *user*, not the
                # process tree.  Only applied when explicitly configured; the
                # Docker backend uses --pids-limit (cgroup-scoped) instead.
                resource.setrlimit(
                    resource.RLIMIT_NPROC,
                    (limits.pids_limit, limits.pids_limit),
                )
            os.umask(0o077)
        except Exception:
            # A limit that cannot be applied must not prevent the scan from
            # running; the wall-clock timeout and RSS watchdog still apply.
            pass

    return _apply


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class SandboxedCommandExecutor:
    """Executes external scanner commands under strict resource limits."""

    def __init__(
        self,
        *,
        mode: str | None = None,
        max_output_bytes: int | None = None,
    ) -> None:
        cfg = _sandbox_settings()
        self.mode = (mode or cfg.get("mode") or SandboxMode.PROCESS).strip().lower()
        if self.mode not in (SandboxMode.PROCESS, SandboxMode.DOCKER):
            logger.warning(
                "Unknown SCANNER_SANDBOX mode %r — falling back to process mode",
                self.mode,
            )
            self.mode = SandboxMode.PROCESS

        self.max_output_bytes = int(
            max_output_bytes
            if max_output_bytes is not None
            else cfg.get("max_output_bytes", DEFAULT_MAX_OUTPUT_BYTES)
        )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def docker_binary(self) -> str:
        return _docker_settings().get("binary", "docker")

    def docker_available(self) -> bool:
        return shutil.which(self.docker_binary) is not None

    def docker_image_for(self, scanner_name: str) -> str:
        images = _docker_settings().get("images", {}) or {}
        return str(images.get(scanner_name, "") or "").strip()

    def is_available(
        self,
        scanner_name: str,
        *,
        binary: str | None = None,
    ) -> bool:
        """Return whether this executor can run *scanner_name* right now.

        In Docker mode "available" means: the Docker client exists, an image is
        configured for the scanner and — because the sandbox never pulls — that
        image is already present locally.  Reporting a scanner as available
        when its image is missing would turn an unconfigured environment into a
        failed scan step; the probe keeps the honest ``unavailable`` status.
        """
        if self.mode == SandboxMode.DOCKER:
            if not self.docker_available():
                return False
            image = self.docker_image_for(scanner_name)
            if not image:
                return False
            pull_policy = str(
                _docker_settings().get("pull_policy", "never") or "never"
            ).strip().lower()
            if pull_policy != "never":
                return True
            return docker_image_present(image, binary=self.docker_binary)
        if not binary:
            return True
        return shutil.which(binary) is not None

    # ------------------------------------------------------------------
    # Limits
    # ------------------------------------------------------------------

    def limits_for(
        self,
        scanner_name: str,
        *,
        timeout: int | None = None,
    ) -> SandboxLimits:
        """Build the resource envelope for *scanner_name*.

        Precedence: per-scanner ``SCANNER_CONFIG[name]["sandbox"]`` > global
        ``SCANNER_SANDBOX`` defaults.  The result is always clamped to
        ``SCANNER_SANDBOX["max_timeout"]``.
        """
        cfg = _sandbox_settings()
        scanner_cfg = _scanner_settings(scanner_name)
        per_scanner = _scanner_sandbox_settings(scanner_name)

        default_timeout = int(cfg.get("default_timeout", 60) or 60)
        configured_timeout = int(
            timeout
            or scanner_cfg.get("timeout")
            or default_timeout
        )
        max_timeout = int(cfg.get("max_timeout", 300) or 300)

        timeout_s = max(1, min(configured_timeout, max_timeout))

        cpu_seconds = int(
            per_scanner.get("cpu_seconds")
            or timeout_s + 5
        )
        memory_mb = int(
            per_scanner.get("memory_mb", cfg.get("default_memory_mb", 512))
        )
        pids_limit = int(
            per_scanner.get("pids_limit", 0) or 0
        )
        file_size_mb = int(
            per_scanner.get("file_size_mb", cfg.get("default_file_size_mb", 64))
        )
        open_files = int(
            per_scanner.get("open_files", cfg.get("default_open_files", 256))
        )

        return SandboxLimits(
            timeout_s=timeout_s,
            cpu_seconds=cpu_seconds,
            memory_mb=max(0, memory_mb),
            pids_limit=max(0, pids_limit),
            file_size_mb=max(0, file_size_mb),
            open_files=max(0, open_files),
        ).clamped(max_timeout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        command: Sequence[str],
        *,
        limits: SandboxLimits | None = None,
        timeout: int | None = None,
        scanner_name: str = "unknown",
        env_extra: dict[str, str] | None = None,
        cwd: str | None = None,
        docker_image: str | None = None,
        mounts: Sequence[tuple[str, str]] | None = None,
        docker_tmpfs: Sequence[str] | None = None,
        docker_entrypoint: str | None = None,
        read_only: bool = True,
    ) -> CommandResult:
        """Run *command* inside the sandbox and return a result.

        ``timeout`` is a convenience shortcut for
        ``limits.with_timeout(timeout)``.  Non-zero exit codes are returned,
        never raised.  Sandbox configuration problems raise
        :class:`SandboxUnavailableError` / :class:`SandboxBusyError` so the
        orchestrator can mark the step unavailable instead of silently
        running the tool unconfined.
        """
        cmd_list = [str(part) for part in command]
        if not cmd_list:
            raise ValueError("command must not be empty")

        effective_limits = limits or self.limits_for(scanner_name)
        if timeout is not None:
            effective_limits = effective_limits.with_timeout(timeout)
        effective_limits = effective_limits.clamped(
            int(_sandbox_settings().get("max_timeout", 300) or 300)
        )

        slot_key = self._acquire_slot(
            scanner_name, effective_limits.timeout_s
        )
        try:
            if self.mode == SandboxMode.DOCKER:
                return self._run_docker(
                    cmd_list,
                    effective_limits,
                    scanner_name=scanner_name,
                    env_extra=env_extra,
                    cwd=cwd,
                    docker_image=docker_image,
                    mounts=mounts,
                    docker_tmpfs=docker_tmpfs,
                    docker_entrypoint=docker_entrypoint,
                    read_only=read_only,
                )
            return self._run_process(
                cmd_list,
                effective_limits,
                scanner_name=scanner_name,
                env_extra=env_extra,
                cwd=cwd,
            )
        finally:
            self._release_slot(slot_key)

    # ------------------------------------------------------------------
    # Concurrency gate
    # ------------------------------------------------------------------

    def _acquire_slot(self, scanner_name: str, timeout_s: int) -> str | None:
        """Reserve one of the global sandbox slots.

        Returns the cache key to release, or ``None`` when the gate is
        disabled or the cache is unreachable (fail open: a cache outage must
        not block every scan).
        """
        max_concurrency = int(
            _sandbox_settings().get("max_concurrency", 0) or 0
        )
        if max_concurrency <= 0:
            return None

        from django.core.cache import cache

        wait_seconds = min(max(5, timeout_s), 30)
        deadline = time.monotonic() + wait_seconds
        ttl = timeout_s + 120

        while time.monotonic() < deadline:
            for index in range(max_concurrency):
                key = f"scanner-sandbox-slot:{index}"
                try:
                    if cache.add(key, os.getpid(), timeout=ttl):
                        return key
                except Exception:
                    logger.warning(
                        "Scanner sandbox concurrency gate unavailable "
                        "(cache error) — running %s without a slot",
                        scanner_name,
                        exc_info=True,
                    )
                    return None
            time.sleep(0.2)

        raise SandboxBusyError(
            f"No sandbox slot available for '{scanner_name}' within "
            f"{wait_seconds}s (max_concurrency={max_concurrency})"
        )

    @staticmethod
    def _release_slot(slot_key: str | None) -> None:
        if slot_key is None:
            return
        try:
            from django.core.cache import cache

            cache.delete(slot_key)
        except Exception:
            logger.warning("Could not release scanner sandbox slot", exc_info=True)

    # ------------------------------------------------------------------
    # Process backend
    # ------------------------------------------------------------------

    def _run_process(
        self,
        command: list[str],
        limits: SandboxLimits,
        *,
        scanner_name: str,
        env_extra: dict[str, str] | None,
        cwd: str | None,
    ) -> CommandResult:
        env = build_child_environment(env_extra)
        started = time.monotonic()

        logger.info(
            "Starting sandboxed scanner command",
            extra={
                "scanner": scanner_name,
                "binary": command[0],
                "mode": SandboxMode.PROCESS,
                "timeout_s": limits.timeout_s,
                "cpu_seconds": limits.cpu_seconds,
                "memory_mb": limits.memory_mb,
            },
        )

        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=cwd,
                shell=False,
                close_fds=True,
                start_new_session=True,
                preexec_fn=_make_preexec(limits),
            )
        except FileNotFoundError:
            duration_ms = int((time.monotonic() - started) * 1000)
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=f"Binary '{command[0]}' not found",
                duration_ms=duration_ms,
                command=command,
                killed_reason="binary_not_found",
            )

        watchdog: _RssWatchdog | None = None
        if limits.memory_mb > 0:
            watchdog = _RssWatchdog(proc.pid, limits.memory_mb * 1024 * 1024)
            watchdog.start()

        timed_out = False
        killed_reason = ""
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=limits.timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            killed_reason = "timeout"
            _kill_process_group(proc.pid)
            stdout_bytes, stderr_bytes = proc.communicate()
        finally:
            if watchdog is not None:
                watchdog.stop()

        if watchdog is not None and watchdog.exceeded:
            killed_reason = "memory"

        exit_code = proc.returncode if proc.returncode is not None else -1
        duration_ms = int((time.monotonic() - started) * 1000)

        output_truncated = False
        if len(stdout_bytes) > self.max_output_bytes:
            stdout_bytes = stdout_bytes[: self.max_output_bytes]
            output_truncated = True
        if len(stderr_bytes) > self.max_output_bytes:
            stderr_bytes = stderr_bytes[: self.max_output_bytes]
            output_truncated = True

        if timed_out or killed_reason == "memory":
            logger.warning(
                "Sandboxed scanner killed",
                extra={
                    "scanner": scanner_name,
                    "reason": killed_reason,
                    "timeout_s": limits.timeout_s,
                    "duration_ms": duration_ms,
                },
            )

        return CommandResult(
            exit_code=exit_code,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_ms=duration_ms,
            command=command,
            timed_out=timed_out,
            output_truncated=output_truncated,
            memory_exceeded=killed_reason == "memory",
            killed_reason=killed_reason,
        )

    # ------------------------------------------------------------------
    # Docker backend
    # ------------------------------------------------------------------

    def build_docker_command(
        self,
        command: Sequence[str],
        limits: SandboxLimits,
        *,
        scanner_name: str,
        docker_image: str | None = None,
        name: str | None = None,
        env_extra: dict[str, str] | None = None,
        mounts: Sequence[tuple[str, str]] | None = None,
        docker_tmpfs: Sequence[str] | None = None,
        docker_entrypoint: str | None = None,
        read_only: bool = True,
    ) -> list[str]:
        """Return the hardened ``docker run`` argv for one tool invocation."""
        image = (docker_image or self.docker_image_for(scanner_name)).strip()
        if not image:
            raise SandboxUnavailableError(
                f"No Docker image configured for scanner '{scanner_name}'. "
                "Set SCANNER_SANDBOX['docker']['images'][...] "
                f"(env SCANNER_DOCKER_IMAGE_{scanner_name.upper()})."
            )

        docker = _docker_settings()
        container_name = name or f"presence-scan-{uuid.uuid4().hex[:12]}"
        network = str(docker.get("network", "bridge") or "bridge")
        cpus = str(docker.get("cpus", 1.0))
        shm_mb = int(docker.get("shm_size_mb", 256) or 256)
        pull_policy = str(docker.get("pull_policy", "never") or "never")
        pids_limit = limits.pids_limit or int(docker.get("pids_limit", 256) or 256)

        argv = [
            self.docker_binary,
            "run",
            "--rm",
            "--init",
            "--name",
            container_name,
            "--label",
            f"presence.scanner={scanner_name}",
            "--network",
            network,
            "--pull",
            pull_policy,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
        ]
        if read_only:
            argv.append("--read-only")
        # ``docker_entrypoint=""`` clears the image entrypoint so the adapter
        # can choose the exact script (ZAP images vary between tags).
        if docker_entrypoint is not None:
            argv += ["--entrypoint", docker_entrypoint]
        argv += [
            "--tmpfs",
            f"/tmp:rw,nosuid,nodev,size={_DEFAULT_TMPFS_MB}m",
            "--shm-size",
            f"{shm_mb}m",
            "--pids-limit",
            str(pids_limit),
            "--cpus",
            cpus,
            "--env",
            "HOME=/tmp",
        ]

        if limits.memory_mb > 0:
            argv += [
                "--memory",
                f"{limits.memory_mb}m",
                "--memory-swap",
                f"{limits.memory_mb}m",
            ]

        user = str(docker.get("user", "") or "").strip()
        if user:
            argv += ["--user", user]

        # Extra writable tmpfs directories (e.g. ZAP's /zap/wrk) keep the
        # root filesystem read-only while letting the tool write its state.
        tmpfs_entries = (
            docker_tmpfs if docker_tmpfs is not None else docker_tmpfs_for(scanner_name)
        )
        for entry in tmpfs_entries:
            argv += ["--tmpfs", str(entry)]

        for host_path, container_path in _validate_bind_mounts(mounts):
            argv += [
                "--mount",
                f"type=bind,src={host_path},dst={container_path}",
            ]

        if env_extra:
            for key, value in env_extra.items():
                # Only forward explicit scanner-provided values; the image
                # never inherits the worker's environment.
                argv += ["--env", f"{key}={value}"]

        argv.append(image)
        argv.extend(str(part) for part in command)
        return argv

    def _run_docker(
        self,
        command: list[str],
        limits: SandboxLimits,
        *,
        scanner_name: str,
        env_extra: dict[str, str] | None,
        cwd: str | None,
        docker_image: str | None,
        mounts: Sequence[tuple[str, str]] | None = None,
        docker_tmpfs: Sequence[str] | None = None,
        docker_entrypoint: str | None = None,
        read_only: bool = True,
    ) -> CommandResult:
        if not self.docker_available():
            raise SandboxUnavailableError(
                f"Docker binary '{self.docker_binary}' not found on PATH"
            )

        # With ``--pull never`` (the default) an image that is not already on
        # the host cannot be run.  Report that before starting a container so
        # the step is recorded as unavailable rather than as a failed scan.
        image = (docker_image or self.docker_image_for(scanner_name)).strip()
        pull_policy = str(_docker_settings().get("pull_policy", "never") or "never")
        if (
            image
            and pull_policy.strip().lower() == "never"
            and not docker_image_present(image, binary=self.docker_binary)
        ):
            raise SandboxUnavailableError(
                f"Scanner image '{image}' for '{scanner_name}' is not present "
                "in the local image store; the sandbox never pulls during a "
                "scan (build or pull the image first)"
            )

        container_name = f"presence-scan-{uuid.uuid4().hex[:12]}"
        argv = self.build_docker_command(
            command,
            limits,
            scanner_name=scanner_name,
            docker_image=docker_image,
            name=container_name,
            env_extra=env_extra,
            mounts=mounts,
            docker_tmpfs=docker_tmpfs,
            docker_entrypoint=docker_entrypoint,
            read_only=read_only,
        )

        started = time.monotonic()
        logger.info(
            "Starting sandboxed scanner container",
            extra={
                "scanner": scanner_name,
                "binary": command[0],
                "mode": SandboxMode.DOCKER,
                "timeout_s": limits.timeout_s,
                "memory_mb": limits.memory_mb,
                "cpus": _docker_settings().get("cpus"),
            },
        )

        try:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                close_fds=True,
                start_new_session=True,
                cwd=cwd,
            )
        except FileNotFoundError:
            raise SandboxUnavailableError(
                f"Docker binary '{self.docker_binary}' not found on PATH"
            ) from None

        timed_out = False
        killed_reason = ""
        try:
            # The wall-clock budget includes container startup: the configured
            # timeout is the real upper bound the orchestrator and Celery see,
            # not an extra grace period on top of it.
            stdout_bytes, stderr_bytes = proc.communicate(
                timeout=limits.timeout_s
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            killed_reason = "timeout"
            # Killing the docker client does NOT stop the container: remove it
            # explicitly, then kill the client.
            self._force_remove_container(container_name)
            try:
                proc.kill()
            except OSError:
                pass
            stdout_bytes, stderr_bytes = proc.communicate()
        finally:
            if timed_out:
                self._force_remove_container(container_name)

        exit_code = proc.returncode if proc.returncode is not None else -1
        if exit_code == 137 and not timed_out:
            killed_reason = "memory"
        elif exit_code != 0 and not killed_reason:
            killed_reason = "exit_code"

        duration_ms = int((time.monotonic() - started) * 1000)
        output_truncated = False
        if len(stdout_bytes) > self.max_output_bytes:
            stdout_bytes = stdout_bytes[: self.max_output_bytes]
            output_truncated = True
        if len(stderr_bytes) > self.max_output_bytes:
            stderr_bytes = stderr_bytes[: self.max_output_bytes]
            output_truncated = True

        return CommandResult(
            exit_code=exit_code,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_ms=duration_ms,
            command=argv,
            timed_out=timed_out,
            output_truncated=output_truncated,
            memory_exceeded=killed_reason == "memory",
            killed_reason=killed_reason,
        )

    def _force_remove_container(self, container_name: str) -> None:
        try:
            subprocess.run(
                [self.docker_binary, "rm", "-f", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except Exception:
            logger.warning(
                "Could not remove sandbox container %s", container_name
            )


def get_sandbox_executor() -> SandboxedCommandExecutor:
    """Return a sandbox executor bound to the current settings.

    A fresh instance is cheap (no state) and guarantees that
    ``override_settings`` is honoured in tests and in long-lived workers.
    """
    return SandboxedCommandExecutor()


def sandbox_status() -> dict[str, Any]:
    """Return a diagnostic snapshot for admin/health endpoints."""
    cfg = _sandbox_settings()
    docker = _docker_settings()
    return {
        "mode": cfg.get("mode", SandboxMode.PROCESS),
        "max_timeout": cfg.get("max_timeout"),
        "max_concurrency": cfg.get("max_concurrency"),
        "default_memory_mb": cfg.get("default_memory_mb"),
        "docker_available": shutil.which(docker.get("binary", "docker")) is not None,
        "docker_images": docker.get("images", {}),
        "docker_images_present": {
            name: docker_image_present(
                str(image), binary=docker.get("binary", "docker")
            )
            for name, image in (docker.get("images", {}) or {}).items()
            if str(image or "").strip()
        },
        "docker_network": docker.get("network"),
    }
