"""User models for authentication."""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import validate_email
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with email as primary identifier."""

    email = models.EmailField(unique=True, validators=[validate_email])
    full_name = models.CharField(max_length=150, blank=True)
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
