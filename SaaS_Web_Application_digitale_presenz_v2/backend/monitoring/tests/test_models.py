from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from monitoring.models import INTERVAL_MAP, MonitoringConfig
from websites.models import Website


class IntervalMapTest(TestCase):
    def test_all_intervals_defined(self):
        expected = {"5m", "15m", "30m", "1h", "6h", "24h"}
        self.assertEqual(set(INTERVAL_MAP.keys()), expected)

    def test_24h_value(self):
        self.assertEqual(INTERVAL_MAP["24h"], timedelta(hours=24))

    def test_5m_value(self):
        self.assertEqual(INTERVAL_MAP["5m"], timedelta(minutes=5))


class MonitoringConfigSignalTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="pass1234"
        )

    def test_auto_created_on_website_creation(self):
        website = Website.objects.create(owner=self.user, domain="example.com")
        self.assertTrue(MonitoringConfig.objects.filter(website=website).exists())

    def test_auto_config_is_opt_in(self):
        """A new website is not scanned on a schedule until the owner opts in."""
        website = Website.objects.create(owner=self.user, domain="example2.com")
        config = MonitoringConfig.objects.get(website=website)
        self.assertFalse(config.enabled)
        self.assertEqual(config.interval, MonitoringConfig.Interval.TWENTY_FOUR)
        self.assertIsNone(config.next_scan_at)


class MonitoringConfigMethodsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test2@example.com", password="pass1234"
        )
        self.website = Website.objects.create(owner=self.user, domain="methods.com")
        self.config = MonitoringConfig.objects.get(website=self.website)

    def test_schedule_next_scan_no_jitter(self):
        now = timezone.now()
        self.config.schedule_next_scan(now=now, jitter_max_minutes=0)
        self.config.refresh_from_db()
        expected = now + timedelta(hours=24)
        delta = abs((self.config.next_scan_at - expected).total_seconds())
        self.assertLess(delta, 1)
        self.assertEqual(
            self.config.last_scan_at.replace(microsecond=0), now.replace(microsecond=0)
        )

    def test_record_failure_first(self):
        self.config.record_failure()
        self.config.refresh_from_db()
        self.assertEqual(self.config.consecutive_failures, 1)
        self.assertEqual(self.config.escalation_level, 1)

    def test_record_failure_escalates_to_critical(self):
        for _ in range(3):
            self.config.record_failure()
        self.config.refresh_from_db()
        self.assertEqual(self.config.consecutive_failures, 3)
        self.assertEqual(self.config.escalation_level, 2)

    def test_record_success_resets(self):
        self.config.consecutive_failures = 5
        self.config.escalation_level = 2
        self.config.save()
        self.config.record_success()
        self.config.refresh_from_db()
        self.assertEqual(self.config.consecutive_failures, 0)
        self.assertEqual(self.config.escalation_level, 0)

    def test_str(self):
        self.assertIn("methods.com", str(self.config))
