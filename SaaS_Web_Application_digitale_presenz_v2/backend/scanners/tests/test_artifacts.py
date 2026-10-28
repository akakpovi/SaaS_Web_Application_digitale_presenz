"""Tests for private raw scanner report archives."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from scanners.artifacts import (
    archive_report,
    prune_scan_archives,
    redact_report,
)


def _report() -> str:
    return json.dumps(
        {
            "template-id": "exposed-env-file",
            "info": {
                "name": "Exposed .env",
                "severity": "high",
                "description": "A dotfile is public.",
                "authorization": "Bearer should-not-survive",
            },
            "matched-at": (
                "https://example.com/.env?code=AUTH_CODE"
                "&state=CSRF_STATE&ordinary=kept"
            ),
            "request": (
                "GET /.env HTTP/1.1\r\n"
                "Host: example.com\r\n"
                "Cookie: session=COOKIE_SECRET\r\n"
                "Authorization: Bearer BEARER_SECRET\r\n"
                "X-Api-Key: API_KEY_SECRET\r\n"
                "\r\n"
                "email=user@example.com&token=TOKEN_SECRET"
            ),
            "extracted-results": [
                "DB_PASSWORD=PASSWORD_SECRET",
                "contact: user@example.com",
                "jwt: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature123456",
            ],
        }
    )


class RedactionTests(SimpleTestCase):
    def test_json_and_free_text_credentials_are_removed(self):
        sanitised, records, redactions = redact_report(_report())

        self.assertEqual(records, 1)
        self.assertGreaterEqual(redactions, 8)
        for secret in (
            "AUTH_CODE",
            "CSRF_STATE",
            "COOKIE_SECRET",
            "BEARER_SECRET",
            "API_KEY_SECRET",
            "TOKEN_SECRET",
            "PASSWORD_SECRET",
            "user@example.com",
            "eyJhbGciOiJIUzI1NiJ9",
            "should-not-survive",
        ):
            self.assertNotIn(secret, sanitised)
        self.assertIn("ordinary=kept", sanitised)
        self.assertIn("[REDACTED]", sanitised)
        # The sanitised line is still valid JSON.
        self.assertIsInstance(json.loads(sanitised), dict)

    def test_truncated_non_json_line_is_not_dropped(self):
        sanitised, records, _ = redact_report(
            '{"template-id":"x","matched-at":"https://example.com/?token=SECRET"}\n'
            "partial line token=SECRET"
        )
        self.assertEqual(records, 1)
        self.assertNotIn("SECRET", sanitised)
        self.assertIn("partial line", sanitised)


class ArchiveStorageTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "archives"
        self.settings = dict(
            SCANNER_ARCHIVE_ENABLED=True,
            SCANNER_ARCHIVE_DIR=str(self.root),
            SCANNER_ARCHIVE_MAX_BYTES=8 * 1024 * 1024,
            SCANNER_ARCHIVE_RETENTION_DAYS=30,
        )

    def _archive(self, **overrides):
        params = dict(
            scanner_name="nuclei",
            scan_id=3573,
            scanner_run_id=42,
            raw_report=_report(),
            report_format="nuclei-jsonl",
            diagnostics={
                "profile": "standard",
                "scan_complete": True,
                "stderr_excerpt": "Authorization: Bearer STDERR_SECRET",
            },
            complete=True,
        )
        params.update(overrides)
        with override_settings(**self.settings):
            return archive_report(**params)

    def test_complete_report_is_private_redacted_and_traceable(self):
        result = self._archive()

        self.assertEqual(result.status, "stored")
        self.assertTrue(result.ref.endswith(".jsonl"))
        self.assertEqual(result.records, 1)
        self.assertGreaterEqual(result.redactions, 1)
        self.assertFalse(result.partial)

        report_path = self.root / result.ref
        self.assertTrue(report_path.is_file())
        self.assertEqual(stat.S_IMODE(report_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(report_path.parent.stat().st_mode), 0o700)
        # Intermediate « nuclei/YYYY/MM » directories must not stay 0755:
        # they would leak archive names even though files are 0600.
        for directory in report_path.parents:
            if directory == self.root.parent:
                break
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        content = report_path.read_text(encoding="utf-8")
        self.assertNotIn("AUTH_CODE", content)
        self.assertNotIn("COOKIE_SECRET", content)
        self.assertNotIn("user@example.com", content)

        sidecars = list(self.root.rglob("*.meta.json"))
        self.assertEqual(len(sidecars), 1)
        metadata = json.loads(sidecars[0].read_text(encoding="utf-8"))
        self.assertEqual(metadata["scan_id"], 3573)
        self.assertEqual(metadata["scanner_run_id"], 42)
        self.assertEqual(metadata["diagnostics"]["profile"], "standard")
        self.assertTrue(metadata["complete"])
        self.assertFalse(metadata["partial"])
        self.assertEqual(metadata["archive_ref"], result.ref)
        self.assertNotIn("STDERR_SECRET", sidecars[0].read_text(encoding="utf-8"))

    def test_partial_report_is_archived_as_partial(self):
        result = self._archive(
            raw_report=_report().splitlines()[0],
            complete=False,
            partial_reason="timeout",
            diagnostics={"profile": "standard", "scan_complete": False},
        )

        self.assertEqual(result.status, "stored")
        self.assertTrue(result.partial)
        sidecar = next(self.root.rglob("*.meta.json"))
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        self.assertFalse(metadata["complete"])
        self.assertTrue(metadata["partial"])
        self.assertEqual(metadata["partial_reason"], "timeout")

    def test_empty_incomplete_report_is_not_fabricated(self):
        result = self._archive(raw_report="", complete=False)

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.detail, "empty_report")
        self.assertTrue(result.partial)
        self.assertFalse(any(self.root.rglob("*")))

    def test_empty_complete_report_is_a_real_zero_finding_archive(self):
        result = self._archive(raw_report="", complete=True)

        self.assertEqual(result.status, "stored")
        self.assertEqual(result.bytes, 0)
        self.assertEqual(result.lines, 0)
        self.assertEqual(result.records, 0)

    def test_retry_reuses_the_same_report_file(self):
        first = self._archive()
        second = self._archive(scanner_run_id=43)

        self.assertEqual(first.ref, second.ref)
        self.assertEqual(second.status, "reused")
        self.assertEqual(len(list(self.root.rglob("*.jsonl"))), 1)
        # Each run keeps its own diagnostic sidecar.
        self.assertEqual(len(list(self.root.rglob("*.meta.json"))), 2)

    def test_max_bytes_truncates_without_claiming_completeness(self):
        with override_settings(
            **{**self.settings, "SCANNER_ARCHIVE_MAX_BYTES": 250}
        ):
            result = archive_report(
                scanner_name="nuclei",
                scan_id=1,
                scanner_run_id=1,
                raw_report=_report(),
                complete=True,
            )

        self.assertTrue(result.truncated)
        self.assertLessEqual(result.bytes, 250)

    def test_storage_error_is_reported_not_raised(self):
        with patch(
            "scanners.artifacts._write_private",
            side_effect=OSError("disk full"),
        ):
            result = self._archive()

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.detail, "OSError")

    def test_unsafe_archive_root_is_rejected(self):
        with override_settings(
            **{**self.settings, "SCANNER_ARCHIVE_DIR": "/"}
        ):
            result = archive_report(
                scanner_name="nuclei",
                scan_id=1,
                scanner_run_id=1,
                raw_report=_report(),
            )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.detail, "unsafe_archive_dir")

    def test_retention_deletes_only_old_files(self):
        old = self.root / "nuclei" / "2026" / "01" / "01" / "old.jsonl"
        new = self.root / "nuclei" / "2026" / "10" / "26" / "new.jsonl"
        old.parent.mkdir(parents=True)
        new.parent.mkdir(parents=True)
        old.write_text("old")
        new.write_text("new")
        old_time = (datetime.now(timezone.utc) - timedelta(days=60)).timestamp()
        os.utime(old, (old_time, old_time))

        with override_settings(**self.settings):
            result = prune_scan_archives(retention_days=30)

        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["kept"], 1)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())

    def test_retention_zero_is_disabled(self):
        path = self.root / "old.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("old")
        old_time = (datetime.now(timezone.utc) - timedelta(days=60)).timestamp()
        os.utime(path, (old_time, old_time))

        with override_settings(**self.settings):
            result = prune_scan_archives(retention_days=0)

        self.assertFalse(result["enabled"])
        self.assertTrue(path.exists())
