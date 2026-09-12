from typing import Any
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

domain_validator = RegexValidator(
    regex=r"^(?=.{1,253}$)(?!-)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$",
    message="Enter a valid domain name without a scheme, path, or port.",
)


class Website(models.Model):
    """A domain that belongs to a Presence user or a temporary guest session."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="websites",
        null=True,
        blank=True,
    )
    domain = models.CharField(max_length=253, validators=[domain_validator])
    display_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether monitoring is active for this website."
    )
    is_guest = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this website was created by an unauthenticated guest."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["domain"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "domain"],
                condition=Q(owner__isnull=False),
                name="unique_website_domain_per_owner",
            )
        ]
        indexes = [
            models.Index(fields=["owner", "domain"]),
            models.Index(fields=["owner", "created_at"]),
            models.Index(fields=["is_guest", "created_at"]),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.domain = self.domain.strip().lower().rstrip(".")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.domain} (Guest)" if self.is_guest else self.domain
