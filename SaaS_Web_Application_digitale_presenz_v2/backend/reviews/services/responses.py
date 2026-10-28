"""Drafting of review responses.

The platform has no LLM dependency for this feature, so the assistant is
honest about what it does: it composes a reply from a small set of
intent-aware templates using the *real* review (author, rating, sentiment).
The draft is persisted as a ``ResponseDraft`` so it can be reviewed, edited
and tracked — it is never auto-published to the review platform.
"""

from __future__ import annotations

import secrets

from reviews.models import ResponseDraft, Review

NEGATIVE_OPENERS = [
    "Thank you for taking the time to share this, {name}. We are sorry that your experience fell short of what you expected.",
    "We appreciate the honest feedback, {name}. We are sorry we did not get this right for you.",
]

NEUTRAL_OPENERS = [
    "Thank you for your feedback, {name}. We are glad you shared both the good points and what we can improve.",
    "Thanks for the detailed review, {name}. Your comments help us see where we can do better.",
]

POSITIVE_OPENERS = [
    "Thank you very much for this great feedback, {name}! We are delighted that you enjoyed your experience.",
    "We really appreciate your kind words, {name}. Thank you for recommending us.",
]

NEGATIVE_CLOSERS = [
    "We would like the opportunity to make things right. Please contact us directly so we can look into what happened.",
    "Your experience matters to us. Please reach out to us directly so we can address your concerns personally.",
]

NEUTRAL_CLOSERS = [
    "We have noted your suggestions and will use them to improve. We hope to welcome you again soon.",
    "Your feedback has been shared with the team. Do not hesitate to tell us more about what would have made your visit better.",
]

POSITIVE_CLOSERS = [
    "We look forward to welcoming you again soon.",
    "Thank you again for your trust — we hope to see you again very soon.",
]


def _first_name(review: Review) -> str:
    name = (review.author_name or "").strip()
    return name.split()[0] if name else "there"


def _tone(review: Review) -> str:
    if review.sentiment == Review.Sentiment.NEGATIVE:
        return "negative"
    if review.sentiment == Review.Sentiment.POSITIVE:
        return "positive"
    rating = float(review.rating) if review.rating is not None else None
    if rating is None:
        return "neutral"
    if rating <= 2:
        return "negative"
    if rating >= 4:
        return "positive"
    return "neutral"


def compose_response(review: Review) -> str:
    tone = _tone(review)
    pool = {
        "negative": (NEGATIVE_OPENERS, NEGATIVE_CLOSERS),
        "neutral": (NEUTRAL_OPENERS, NEUTRAL_CLOSERS),
        "positive": (POSITIVE_OPENERS, POSITIVE_CLOSERS),
    }[tone]
    opener = secrets.choice(pool[0]).format(name=_first_name(review))
    closer = secrets.choice(pool[1])

    detail = ""
    snippet = " ".join((review.text or "").split())
    if snippet:
        detail = f" You mentioned: “{snippet[:180]}{'…' if len(snippet) > 180 else ''}”"
    return f"{opener}{detail} {closer}"


def generate_draft(review: Review) -> ResponseDraft:
    """Create or refresh the single draft attached to *review*."""
    content = compose_response(review)
    draft = ResponseDraft.objects.filter(review=review).first()
    if draft is None:
        return ResponseDraft.objects.create(
            review=review,
            user=review.source.user,
            content=content,
        )
    draft.content = content
    draft.status = ResponseDraft.Status.DRAFT
    draft.sent_at = None
    draft.save(update_fields=["content", "status", "sent_at", "updated_at"])
    return draft
