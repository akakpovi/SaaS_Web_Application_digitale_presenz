import random
from celery import shared_task
from django.utils import timezone
from social.models import SocialProfile, SocialMention
from websites.models import Website
from reviews.services.sentiment import get_analyzer

@shared_task
def sync_social_profiles(website_id: int) -> dict:
    profiles = SocialProfile.objects.filter(website_id=website_id)
    for p in profiles:
        p.followers += random.randint(-2, 30)
        p.engagement_rate = round(random.uniform(0.5, 5.0), 2)
        p.last_synced_at = timezone.now()
        p.save()
    return {"updated": profiles.count()}

@shared_task
def track_brand_mentions(website_id: int) -> dict:
    website = Website.objects.get(id=website_id)
    analyzer = get_analyzer()
    mock_mentions = [
        {"platform": "Twitter", "author": "happy_customer", "content": f"The website {website.domain} has an excellent performance!"},
        {"platform": "Reddit", "author": "critic_guy", "content": f"Had a slow loading screen on {website.domain}."}
    ]
    created_count = 0
    for m in mock_mentions:
        res = analyzer.analyze(m["content"])
        _, created = SocialMention.objects.get_or_create(
            website=website,
            content=m["content"],
            defaults={
                "platform": m["platform"],
                "author": m["author"],
                "sentiment": res.sentiment,
                "mentioned_at": timezone.now()
            }
        )
        if created:
            created_count += 1
    return {"new_mentions": created_count}
