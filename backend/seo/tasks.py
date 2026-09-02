from celery import shared_task
from seo.models import SEOAudit
from seo.scanners.technical import TechnicalSEOScanner
from websites.models import Website

@shared_task
def run_seo_audit(website_id: int) -> dict:
    website = Website.objects.get(id=website_id)
    scanner = TechnicalSEOScanner(website.domain)
    data = scanner.run()
    tech = max(data["technical"], 0)
    content = max(data["content"], 0)
    mobile = max(data["mobile"], 0)
    overall = int((tech + content + mobile) / 3)

    audit = SEOAudit.objects.create(
        website=website,
        overall_score=overall,
        technical_score=tech,
        content_score=content,
        mobile_score=mobile,
        meta_tags=data["meta_tags"],
        robots_txt=data["robots_txt"],
        sitemap=data["sitemap"],
        issues=data.get("issues", [])
    )
    return {"audit_id": str(audit.id), "score": overall}
