import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

from allauth.account.models import EmailConfirmation

from .managers import UserManager


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ROLE_CHOICES = [
        ('volunteer', 'Volunteer'),
        ('senior', 'Senior'),
    ]
    
    name = models.CharField(max_length=255, blank=True, null=True)
    age = models.CharField(max_length=50, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    house_number = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    skills = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)
    
    objects = UserManager()
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.username or self.email


class EmailVerificationAttempt(models.Model):
    """
    Tracks how many times a given email confirmation key has been attempted.

    There is exactly one attempt record per `EmailConfirmation` instance.
    This allows us to enforce a maximum number of invalid verification
    attempts per confirmation without modifying any allauth tables.
    """

    email_confirmation = models.OneToOneField(
        EmailConfirmation,
        on_delete=models.CASCADE,
        related_name="verification_attempt",
    )
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email Verification Attempt"
        verbose_name_plural = "Email Verification Attempts"

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        email = getattr(self.email_confirmation.email_address, "email", None)
        return f"Attempts for {email or 'unknown email'}: {self.attempts}"
