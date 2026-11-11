from django.test import TestCase
from django.contrib.auth import get_user_model
from websites.models import Website
from advanced_security.models import SecurityIncident

User = get_user_model()


class SecurityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="sec@test.com", password="password123"
        )
        self.website = Website.objects.create(owner=self.user, domain="example.com")

    def test_incident_creation(self):
        inc = SecurityIncident.objects.create(
            website=self.website,
            incident_type=SecurityIncident.IncidentType.OPEN_PORT,
            title="Port 22 open",
            description="SSH port exposed",
        )
        self.assertEqual(inc.severity, "low")
        self.assertFalse(inc.is_resolved)
