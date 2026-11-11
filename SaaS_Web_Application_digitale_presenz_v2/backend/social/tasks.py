"""Synchronisation des réseaux sociaux et veille des mentions.

Aucune donnée n'est inventée : si un fournisseur n'est pas configuré ou ne
répond pas, la tâche le signale et laisse les valeurs existantes intactes.
Les mentions proviennent de la recherche publique Reddit (vraie API JSON).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from reviews.services.sentiment import get_analyzer
from social.models import SocialMention, SocialProfile
from websites.models import Website

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
GRAPH_API = "https://graph.facebook.com/v21.0"
TWITTER_API = "https://api.twitter.com/2"
REDDIT_SEARCH = "https://www.reddit.com/search.json"


def _fetch_facebook(profile: SocialProfile) -> dict | None:
    token = getattr(settings, "META_GRAPH_ACCESS_TOKEN", "")
    if not token:
        return None
    response = requests.get(
        f"{GRAPH_API}/{profile.handle}",
        params={"fields": "followers_count", "access_token": token},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if "followers_count" not in data:
        return None
    return {"followers": int(data["followers_count"])}


def _fetch_instagram(profile: SocialProfile) -> dict | None:
    token = getattr(settings, "META_GRAPH_ACCESS_TOKEN", "")
    if not token:
        return None
    # ``handle`` stores the Instagram Business account ID for this provider.
    response = requests.get(
        f"{GRAPH_API}/{profile.handle}",
        params={
            "fields": "followers_count,media_count",
            "access_token": token,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if "followers_count" not in data:
        return None
    return {"followers": int(data["followers_count"])}


def _fetch_twitter(profile: SocialProfile) -> dict | None:
    token = getattr(settings, "X_BEARER_TOKEN", "")
    if not token:
        return None
    response = requests.get(
        f"{TWITTER_API}/users/by/username/{profile.handle}",
        params={"user.fields": "public_metrics"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json().get("data") or {}
    metrics = data.get("public_metrics") or {}
    if "followers_count" not in metrics:
        return None
    return {"followers": int(metrics["followers_count"])}


FETCHERS = {
    SocialProfile.Provider.FACEBOOK: _fetch_facebook,
    SocialProfile.Provider.INSTAGRAM: _fetch_instagram,
    SocialProfile.Provider.TWITTER: _fetch_twitter,
}


@shared_task
def sync_social_profiles(website_id: int) -> dict:
    """Refresh follower counts from real APIs — never from random numbers."""
    profiles = SocialProfile.objects.filter(website_id=website_id)
    updated = 0
    skipped: list[str] = []
    failed: list[str] = []

    for profile in profiles:
        fetcher = FETCHERS.get(profile.provider)
        if fetcher is None:
            skipped.append(profile.provider)
            continue
        try:
            metrics = fetcher(profile)
        except requests.RequestException as exc:
            logger.warning(
                "Social sync failed for %s/%s: %s",
                profile.provider,
                profile.handle,
                exc,
            )
            failed.append(profile.provider)
            continue
        if metrics is None:
            skipped.append(profile.provider)
            continue

        profile.followers = metrics["followers"]
        profile.last_synced_at = timezone.now()
        profile.save(update_fields=["followers", "last_synced_at"])
        updated += 1

    return {
        "updated": updated,
        "skipped": sorted(set(skipped)),
        "failed": sorted(set(failed)),
    }


@shared_task
def track_brand_mentions(website_id: int) -> dict:
    """Find real public mentions of the domain on Reddit."""
    website = Website.objects.get(id=website_id)
    analyzer = get_analyzer()

    try:
        response = requests.get(
            REDDIT_SEARCH,
            params={
                "q": f'"{website.domain}"',
                "sort": "new",
                "t": "week",
                "limit": 25,
                "type": "link",
            },
            headers={
                "User-Agent": getattr(
                    settings,
                    "REDDIT_USER_AGENT",
                    "Presence-Monitor/1.0 (+https://presence.local)",
                )
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        children = (response.json().get("data") or {}).get("children") or []
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Reddit mention search failed for %s: %s", website.domain, exc)
        return {"new_mentions": 0, "error": "reddit_unavailable"}

    created_count = 0
    domain = website.domain.lower()

    for child in children:
        data = child.get("data") or {}
        title = data.get("title") or ""
        body = data.get("selftext") or ""
        link = data.get("url") or ""
        if domain not in f"{title} {body} {link}".lower():
            continue

        permalink = data.get("permalink") or ""
        url = f"https://www.reddit.com{permalink}" if permalink else link
        if not url:
            continue

        text = f"{title}\n\n{body}".strip()[:4000]
        analysis = analyzer.analyze(text)
        created_at = data.get("created_utc")
        mentioned_at = (
            datetime.fromtimestamp(created_at, tz=dt_timezone.utc)
            if created_at
            else timezone.now()
        )

        _, created = SocialMention.objects.update_or_create(
            website=website,
            url=url[:1000],
            defaults={
                "platform": "Reddit",
                "author": (data.get("author") or "unknown")[:255],
                "content": text,
                "sentiment": analysis.sentiment,
                "mentioned_at": mentioned_at,
            },
        )
        if created:
            created_count += 1

    return {"new_mentions": created_count, "source": "reddit"}
