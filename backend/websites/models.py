from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

domain_validator = RegexValidator(
    regex=r"^(?=.{1,253}$)(?!-)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$",
    message="Enter a valid domain name without a scheme, path, or port.",
)


class Website(models.Model):
    """A domain that belongs to one Presence account."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="websites")
    domain = models.CharField(max_length=253, validators=[domain_validator])
    display_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True, help_text="Whether monitoring is active for this website.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["domain"]
        constraints = [models.UniqueConstraint(fields=["owner", "domain"], name="unique_website_domain_per_owner")]
        indexes = [models.Index(fields=["owner", "domain"]), models.Index(fields=["owner", "created_at"])]

    def save(self, *args: object, **kwargs: object) -> None:
        self.domain = self.domain.strip().lower().rstrip(".")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.domain
