from django.test import TestCase
from django.contrib.auth import get_user_model
from websites.models import Website
from seo.models import SEOAudit
from seo.scanners.technical import TechnicalSEOScanner

User = get_user_model()

class SEOTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="seo@test.com", password="password123")
        self.website = Website.objects.create(owner=self.user, domain="example.com")

    def test_seo_audit_model(self):
        audit = SEOAudit.objects.create(website=self.website, overall_score=85)
        self.assertEqual(audit.overall_score, 85)

    def test_seo_scanner_parser(self):
        scanner = TechnicalSEOScanner("example.com")
        res = {"meta_tags": {}, "technical": 100, "content": 100, "mobile": 100}
        html = "<html><head><title>My Test Site</title><meta name='description' content='Best SaaS app'></head><body><h1>Header</h1></body></html>"
        scanner._audit_html(html, res)
        self.assertEqual(res["meta_tags"]["title"], "My Test Site")
        self.assertEqual(res["meta_tags"]["description"], "Best SaaS app")
