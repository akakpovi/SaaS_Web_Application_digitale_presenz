"""User models for authentication."""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import validate_email
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with email as primary identifier."""

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        FRENCH = "fr", "Français"
        GERMAN = "de", "Deutsch"

    class Industry(models.TextChoices):
        RESTAURANT = "restaurant", "Restaurant / Café"
        RETAIL = "retail", "Retail"
        HOTEL = "hotel", "Hotel"
        AUTO_REPAIR = "auto_repair", "Auto Repair"
        BEAUTY = "beauty", "Beauty"
        AGENCY = "agency", "Agency"
        OTHER = "other", "Other"

    class Country(models.TextChoices):
        GERMANY = "DE", "Germany"
        FRANCE = "FR", "France"
        AUSTRIA = "AT", "Austria"
        SWITZERLAND = "CH", "Switzerland"
        OTHER = "OTHER", "Other"

    class Timezone(models.TextChoices):
        BERLIN = "Europe/Berlin", "Europe/Berlin"
        PARIS = "Europe/Paris", "Europe/Paris"
        VIENNA = "Europe/Vienna", "Europe/Vienna"
        UTC = "UTC", "UTC"

    email = models.EmailField(unique=True, validators=[validate_email])
    full_name = models.CharField(max_length=150, blank=True)
    # Profile preferences — editable through /api/v1/users/profile/.
    language = models.CharField(
        max_length=5, choices=Language.choices, default=Language.ENGLISH
    )
    business_name = models.CharField(max_length=150, blank=True)
    business_industry = models.CharField(
        max_length=20, choices=Industry.choices, blank=True
    )
    business_country = models.CharField(
        max_length=10, choices=Country.choices, blank=True
    )
    timezone = models.CharField(
        max_length=64, choices=Timezone.choices, default=Timezone.BERLIN
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        indexes = [models.Index(fields=["email"])]
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.email
