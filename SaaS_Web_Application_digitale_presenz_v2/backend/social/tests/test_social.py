from django.test import TestCase
from django.contrib.auth import get_user_model
from websites.models import Website
from social.models import SocialProfile, SocialMention

User = get_user_model()


class SocialTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="social@test.com", password="password123"
        )
        self.website = Website.objects.create(owner=self.user, domain="example.com")

    def test_social_profile_creation(self):
        p = SocialProfile.objects.create(
            website=self.website, provider="twitter", handle="@example"
        )
        self.assertEqual(p.handle, "@example")
