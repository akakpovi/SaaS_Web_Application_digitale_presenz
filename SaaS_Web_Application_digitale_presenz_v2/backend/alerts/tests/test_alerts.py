from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from alerts.models import Alert, AlertPreference, AlertRule, MuteWindow
from websites.models import Website


class AlertPreferenceSignalTest(TestCase):
    def test_created_on_user_creation(self):
        user = User.objects.create_user(email="pref@test.com", password="pass1234")
        self.assertTrue(AlertPreference.objects.filter(user=user).exists())

    def test_not_duplicated_on_update(self):
        user = User.objects.create_user(email="pref2@test.com", password="pass1234")
        user.full_name = "Updated"
        user.save()
        self.assertEqual(AlertPreference.objects.filter(user=user).count(), 1)


class AlertModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="a@test.com", password="pass1234")
        self.website = Website.objects.create(owner=self.user, domain="alerttest.com")
        self.alert = Alert.objects.create(
            user=self.user,
            website=self.website,
            alert_type=Alert.AlertType.WEBSITE_OFFLINE,
            severity=Alert.Severity.CRITICAL,
            title="Site is down",
            message="Unreachable",
        )

    def test_initial_status_firing(self):
        self.assertEqual(self.alert.status, Alert.Status.FIRING)

    def test_acknowledge(self):
        self.alert.acknowledge(self.user)
        self.assertEqual(self.alert.status, Alert.Status.ACKNOWLEDGED)
        self.assertIsNotNone(self.alert.acknowledged_at)
        self.assertEqual(self.alert.acknowledged_by, self.user)

    def test_resolve(self):
        self.alert.resolve()
        self.assertEqual(self.alert.status, Alert.Status.RESOLVED)
        self.assertIsNotNone(self.alert.resolved_at)

    def test_str(self):
        self.assertIn("website_offline", str(self.alert))


class MuteWindowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="mute@test.com", password="pass1234")

    def test_is_currently_muting_true(self):
        now = timezone.now()
        mute = MuteWindow.objects.create(
            user=self.user,
            start_at=now - timezone.timedelta(hours=1),
            end_at=now + timezone.timedelta(hours=1),
        )
        self.assertTrue(mute.is_currently_muting(now=now))

    def test_is_currently_muting_false_past(self):
        now = timezone.now()
        mute = MuteWindow.objects.create(
            user=self.user,
            start_at=now - timezone.timedelta(hours=2),
            end_at=now - timezone.timedelta(hours=1),
        )
        self.assertFalse(mute.is_currently_muting(now=now))

    def test_is_currently_muting_false_inactive(self):
        now = timezone.now()
        mute = MuteWindow.objects.create(
            user=self.user,
            start_at=now - timezone.timedelta(hours=1),
            end_at=now + timezone.timedelta(hours=1),
            is_active=False,
        )
        self.assertFalse(mute.is_currently_muting(now=now))


class AlertRuleEvaluateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="rule@test.com", password="pass1234")

    def _rule(self, metric, operator, threshold):
        return AlertRule(
            user=self.user,
            name="Test",
            metric=metric,
            operator=operator,
            threshold=threshold,
            severity=AlertRule.Severity.WARNING,
        )

    def test_lt_triggers(self):
        rule = self._rule("health_score", "lt", 50)
        self.assertTrue(rule.evaluate(40))
        self.assertFalse(rule.evaluate(60))

    def test_gt_triggers(self):
        rule = self._rule("load_time_ms", "gt", 3000)
        self.assertTrue(rule.evaluate(5000))
        self.assertFalse(rule.evaluate(2000))

    def test_lte_triggers(self):
        rule = self._rule("health_score", "lte", 50)
        self.assertTrue(rule.evaluate(50))
        self.assertFalse(rule.evaluate(51))

    def test_eq_triggers(self):
        rule = self._rule("health_score", "eq", 100)
        self.assertTrue(rule.evaluate(100))
        self.assertFalse(rule.evaluate(99))


class AlertPreferenceQuietHoursTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="quiet@test.com", password="pass1234"
        )
        self.pref = AlertPreference.objects.get(user=self.user)

    def test_no_quiet_hours_never_mutes(self):
        self.assertFalse(self.pref.is_in_quiet_hours())

    def test_quiet_hours_active(self):
        import datetime

        self.pref.quiet_hours_start = datetime.time(22, 0)
        self.pref.quiet_hours_end = datetime.time(23, 59)
        self.pref.save()
        mock_now = timezone.make_aware(timezone.datetime(2024, 1, 1, 22, 30))
        self.assertTrue(self.pref.is_in_quiet_hours(now=mock_now))

    def test_quiet_hours_inactive(self):
        import datetime

        self.pref.quiet_hours_start = datetime.time(22, 0)
        self.pref.quiet_hours_end = datetime.time(23, 59)
        self.pref.save()
        mock_now = timezone.make_aware(timezone.datetime(2024, 1, 1, 10, 0))
        self.assertFalse(self.pref.is_in_quiet_hours(now=mock_now))
