from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from accounts.models import User
from social.models import SocialMention, SocialProfile
from social.tasks import sync_social_profiles, track_brand_mentions
from websites.models import Website


class SocialSyncTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="social@test.com", password="pass1234"
        )
        self.website = Website.objects.create(owner=self.user, domain="example.com")
        self.profile = SocialProfile.objects.create(
            website=self.website,
            provider=SocialProfile.Provider.FACEBOOK,
            handle="page-id",
            followers=100,
        )

    @override_settings(META_GRAPH_ACCESS_TOKEN="", X_BEARER_TOKEN="")
    def test_without_credentials_nothing_is_invented(self):
        result = sync_social_profiles(self.website.id)

        self.profile.refresh_from_db()
        self.assertEqual(result["updated"], 0)
        self.assertIn("facebook", result["skipped"])
        self.assertEqual(self.profile.followers, 100)
        self.assertIsNone(self.profile.last_synced_at)

    @override_settings(META_GRAPH_ACCESS_TOKEN="meta-token")
    @patch("social.tasks.requests.get")
    def test_facebook_followers_come_from_the_graph_api(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"followers_count": 4321}
        mock_get.return_value = mock_response

        result = sync_social_profiles(self.website.id)

        self.profile.refresh_from_db()
        self.assertEqual(result["updated"], 1)
        self.assertEqual(self.profile.followers, 4321)
        self.assertIsNotNone(self.profile.last_synced_at)
        url = mock_get.call_args.args[0]
        self.assertIn("graph.facebook.com", url)
        self.assertIn("page-id", url)

    @override_settings(META_GRAPH_ACCESS_TOKEN="meta-token")
    @patch("social.tasks.requests.get")
    def test_provider_failure_keeps_previous_values(self, mock_get):
        mock_get.side_effect = requests.RequestException("network down")

        result = sync_social_profiles(self.website.id)

        self.profile.refresh_from_db()
        self.assertEqual(result["updated"], 0)
        self.assertIn("facebook", result["failed"])
        self.assertEqual(self.profile.followers, 100)


class BrandMentionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="mentions@test.com", password="pass1234"
        )
        self.website = Website.objects.create(owner=self.user, domain="presence.test")

    @patch("social.tasks.requests.get")
    def test_reddit_mentions_are_real_and_deduplicated(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Anyone tried presence.test?",
                            "selftext": "Great experience so far",
                            "author": "happy_user",
                            "permalink": "/r/smallbusiness/comments/abc",
                            "created_utc": 1_760_000_000,
                        }
                    },
                    {
                        "data": {
                            "title": "Unrelated post",
                            "selftext": "Nothing to see",
                            "author": "other",
                            "permalink": "/r/other/comments/def",
                            "created_utc": 1_760_000_000,
                        }
                    },
                ]
            }
        }
        mock_get.return_value = mock_response

        first = track_brand_mentions(self.website.id)
        second = track_brand_mentions(self.website.id)

        self.assertEqual(first["new_mentions"], 1)
        self.assertEqual(second["new_mentions"], 0)
        self.assertEqual(SocialMention.objects.filter(website=self.website).count(), 1)
        mention = SocialMention.objects.get()
        self.assertEqual(mention.platform, "Reddit")
        self.assertEqual(mention.author, "happy_user")
        self.assertEqual(mention.sentiment, SocialMention.Sentiment.POSITIVE)
        self.assertIn("reddit.com", mention.url)

    @patch("social.tasks.requests.get")
    def test_reddit_outage_returns_an_error_not_fake_mentions(self, mock_get):
        mock_get.side_effect = requests.RequestException("reddit down")

        result = track_brand_mentions(self.website.id)

        self.assertEqual(result["new_mentions"], 0)
        self.assertEqual(result["error"], "reddit_unavailable")
        self.assertEqual(SocialMention.objects.count(), 0)
