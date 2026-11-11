"""Sandbox executor tests.

These tests exercise real child processes (fast ones) to prove that timeouts,
output caps and the RSS watchdog actually work.  Docker is never required: the
container argv is validated in isolation.
"""

from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from scanners.executors.command import build_child_environment
from scanners.executors.sandbox import (
    SandboxLimits,
    SandboxMode,
    SandboxUnavailableError,
    SandboxedCommandExecutor,
    _process_group_rss_bytes,
    sandbox_status,
)

SANDBOX_SETTINGS = {
    "mode": "process",
    "default_timeout": 30,
    "max_timeout": 120,
    "default_memory_mb": 256,
    "default_file_size_mb": 16,
    "default_open_files": 128,
    "max_output_bytes": 64_000,
    "max_concurrency": 0,  # no Redis dependency in these tests
    "docker": {
        "binary": "docker",
        "network": "presence-sandbox",
        "cpus": 1.5,
        "pids_limit": 64,
        "shm_size_mb": 128,
        "user": "65534:65534",
        "pull_policy": "never",
        "start_grace_seconds": 5,
        "images": {"lighthouse": "presence/lighthouse:12"},
    },
}

SCANNER_CONFIG = {
    "lighthouse": {
        "timeout": 90,
        "sandbox": {"memory_mb": 1024, "cpu_seconds": 120},
    },
    "testssl": {"timeout": 60},
}


def _limits(**overrides) -> SandboxLimits:
    values = {
        "timeout_s": 10,
        "cpu_seconds": 10,
        "memory_mb": 0,
        "pids_limit": 0,
        "file_size_mb": 16,
        "open_files": 128,
    }
    values.update(overrides)
    return SandboxLimits(**values)


@override_settings(SCANNER_SANDBOX=SANDBOX_SETTINGS, SCANNER_CONFIG=SCANNER_CONFIG)
class SandboxLimitsTests(SimpleTestCase):
    def test_scanner_specific_limits_take_precedence(self):
        executor = SandboxedCommandExecutor()
        limits = executor.limits_for("lighthouse")
        self.assertEqual(limits.memory_mb, 1024)
        self.assertEqual(limits.cpu_seconds, 120)
        self.assertEqual(limits.timeout_s, 90)

    def test_timeout_is_clamped_to_the_maximum(self):
        executor = SandboxedCommandExecutor()
        limits = executor.limits_for("lighthouse", timeout=9999)
        self.assertEqual(limits.timeout_s, 120)
        self.assertEqual(limits.cpu_seconds, 120)

    def test_defaults_apply_to_unknown_scanners(self):
        executor = SandboxedCommandExecutor()
        limits = executor.limits_for("unknown-tool")
        self.assertEqual(limits.timeout_s, 30)
        self.assertEqual(limits.memory_mb, 256)

    def test_unknown_mode_falls_back_to_process(self):
        with override_settings(
            SCANNER_SANDBOX={**SANDBOX_SETTINGS, "mode": "firejail"}
        ):
            self.assertEqual(SandboxedCommandExecutor().mode, SandboxMode.PROCESS)

    def test_sandbox_status_reports_configuration(self):
        status = sandbox_status()
        self.assertEqual(status["mode"], "process")
        self.assertEqual(status["max_concurrency"], 0)
        self.assertIn("lighthouse", status["docker_images"])


@override_settings(SCANNER_SANDBOX=SANDBOX_SETTINGS, SCANNER_CONFIG=SCANNER_CONFIG)
class SandboxProcessTests(SimpleTestCase):
    def setUp(self):
        self.executor = SandboxedCommandExecutor(max_output_bytes=64_000)

    def test_runs_a_command_and_captures_output(self):
        result = self.executor.run(
            [sys.executable, "-c", "print('sandbox-ok')"],
            limits=_limits(),
            scanner_name="test",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("sandbox-ok", result.stdout)
        self.assertFalse(result.timed_out)
        self.assertFalse(result.memory_exceeded)
        self.assertGreaterEqual(result.duration_ms, 0)

    def test_timeout_kills_the_process_group(self):
        result = self.executor.run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            limits=_limits(timeout_s=1, cpu_seconds=2),
            scanner_name="test",
        )
        self.assertTrue(result.timed_out)
        self.assertEqual(result.killed_reason, "timeout")
        self.assertLess(result.duration_ms, 5_000)

    def test_output_is_truncated(self):
        executor = SandboxedCommandExecutor(max_output_bytes=64)
        result = executor.run(
            [sys.executable, "-c", "print('x' * 10_000)"],
            limits=_limits(),
            scanner_name="test",
        )
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.stdout), 64)

    @unittest.skipUnless(os.path.isdir("/proc"), "RSS watchdog requires Linux /proc")
    def test_memory_watchdog_kills_the_process(self):
        result = self.executor.run(
            [
                sys.executable,
                "-c",
                "payload = bytearray(150 * 1024 * 1024); import time; time.sleep(10)",
            ],
            limits=_limits(timeout_s=3, memory_mb=48),
            scanner_name="test",
        )
        self.assertTrue(result.memory_exceeded)
        self.assertEqual(result.killed_reason, "memory")

    @unittest.skipUnless(os.path.isdir("/proc"), "RSS watchdog requires Linux /proc")
    def test_process_group_rss_is_readable(self):
        self.assertGreater(_process_group_rss_bytes(os.getpgrp()), 0)

    def test_missing_binary_returns_error_without_raising(self):
        result = self.executor.run(
            ["definitely-not-a-real-binary-xyz"],
            limits=_limits(),
            scanner_name="test",
        )
        self.assertEqual(result.killed_reason, "binary_not_found")
        self.assertEqual(result.exit_code, -1)

    def test_child_environment_excludes_secrets(self):
        with patch.dict(
            os.environ,
            {
                "PATH": "/usr/bin",
                "DJANGO_SECRET_KEY": "super-secret",
                "POSTGRES_PASSWORD": "db-secret",
                "OPENAI_API_KEY": "sk-secret",
                "CHROME_PATH": "/usr/bin/chromium",
            },
            clear=False,
        ):
            env = build_child_environment()
        self.assertNotIn("DJANGO_SECRET_KEY", env)
        self.assertNotIn("POSTGRES_PASSWORD", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertEqual(env.get("CHROME_PATH"), "/usr/bin/chromium")


@override_settings(SCANNER_SANDBOX=SANDBOX_SETTINGS, SCANNER_CONFIG=SCANNER_CONFIG)
class SandboxDockerTests(SimpleTestCase):
    def setUp(self):
        self.executor = SandboxedCommandExecutor(mode=SandboxMode.DOCKER)

    def test_docker_command_is_hardened(self):
        argv = self.executor.build_docker_command(
            ["lighthouse", "https://example.com"],
            _limits(memory_mb=1024),
            scanner_name="lighthouse",
        )
        joined = " ".join(argv)

        self.assertEqual(argv[0], "docker")
        self.assertIn("run", argv)
        self.assertIn("--rm", argv)
        self.assertIn("--read-only", argv)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("--security-opt no-new-privileges", joined)
        self.assertIn("--memory 1024m", joined)
        self.assertIn("--memory-swap 1024m", joined)
        self.assertIn("--cpus 1.5", joined)
        self.assertIn("--pids-limit 64", joined)
        self.assertIn("--network presence-sandbox", joined)
        self.assertIn("--pull never", joined)
        self.assertIn("--user 65534:65534", joined)
        self.assertIn("presence/lighthouse:12", argv)
        # The target is never interpolated into a shell string.
        self.assertEqual(argv[-2:], ["lighthouse", "https://example.com"])

    def test_docker_requires_an_image(self):
        with self.assertRaises(SandboxUnavailableError):
            self.executor.build_docker_command(
                ["nmap", "example.com"],
                _limits(),
                scanner_name="nmap",
            )

    def test_docker_missing_binary_fails_closed(self):
        with patch("scanners.executors.sandbox.shutil.which", return_value=None):
            with self.assertRaises(SandboxUnavailableError):
                self.executor.run(
                    ["lighthouse", "https://example.com"],
                    limits=_limits(),
                    scanner_name="lighthouse",
                )

    def test_docker_availability_requires_image_and_binary(self):
        """Docker mode needs the client, a configured image *and* that image."""
        with patch(
            "scanners.executors.sandbox.shutil.which", return_value="/usr/bin/docker"
        ):
            with patch(
                "scanners.executors.sandbox.docker_image_present", return_value=True
            ):
                self.assertTrue(self.executor.is_available("lighthouse"))
            # No image configured for nmap in SANDBOX_SETTINGS.
            self.assertFalse(self.executor.is_available("nmap"))

    def test_docker_availability_false_when_image_is_missing(self):
        """--pull never: a missing image must not be reported as available."""
        with patch(
            "scanners.executors.sandbox.shutil.which", return_value="/usr/bin/docker"
        ):
            with patch(
                "scanners.executors.sandbox.docker_image_present", return_value=False
            ) as probe:
                self.assertFalse(self.executor.is_available("lighthouse"))
                probe.assert_called_once()

    def test_docker_image_present_uses_docker_cli(self):
        """The probe asks Docker directly and fails closed on errors."""
        from scanners.executors import sandbox as sandbox_module

        sandbox_module._DOCKER_IMAGE_CACHE.clear()
        with patch("scanners.executors.sandbox.subprocess.run") as run_mock:
            run_mock.return_value = SimpleNamespace(
                returncode=0, stdout=b"sha256:deadbeef", stderr=b""
            )
            self.assertTrue(sandbox_module.docker_image_present("presence/x:1"))
            self.assertEqual(
                run_mock.call_args[0][0][:3], ["docker", "image", "inspect"]
            )

        sandbox_module._DOCKER_IMAGE_CACHE.clear()
        with patch(
            "scanners.executors.sandbox.subprocess.run",
            side_effect=OSError("no docker"),
        ):
            self.assertFalse(sandbox_module.docker_image_present("presence/x:1"))
        sandbox_module._DOCKER_IMAGE_CACHE.clear()
