import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

from allauth.account.models import EmailConfirmation

from .managers import UserManager


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ROLE_CHOICES = [
        ('babysitter', 'Babysitter'),
        ('parent', 'Parent'),
    ]
    
    name = models.CharField(max_length=255, blank=True, null=True)
    age = models.CharField(max_length=50, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    profile_image = models.ImageField(
        upload_to="profile_images/",
        blank=True,
        null=True,
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)
    
    objects = UserManager()
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.username or self.email

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        previous_role = None

        if not is_new:
            try:
                old = User.objects.get(pk=self.pk)
                previous_role = old.role
            except User.DoesNotExist:
                previous_role = None

        super().save(*args, **kwargs)

        if self.is_staff or self.is_superuser:
            ParentProfile.objects.filter(user=self).delete()
            BabysitterProfile.objects.filter(user=self).delete()
            return

        if not self.role:
            return

        if previous_role is None:
            if self.role == 'parent':
                ParentProfile.objects.get_or_create(user=self)
            elif self.role == 'babysitter':
                BabysitterProfile.objects.get_or_create(user=self)


class ParentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="parent_profile",
        limit_choices_to={'role': 'parent'}
    )

    street = models.CharField(max_length=255, blank=True, null=True)
    apartment_number = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)

    # Geocoding fields
    formatted_address = models.CharField(max_length=500, blank=True, null=True, help_text="Formatted address from geocoding")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    number_of_children = models.IntegerField(blank=True, null=True)
    children_ages = models.JSONField(blank=True, default=list)
    has_special_needs = models.BooleanField(default=False)
    special_needs_description = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    preferred_babysitting_location = models.CharField(
        max_length=50,
        choices=[
            ('parents_home', 'Parents Home'),
            ('babysitters_home', 'Babysitters Home'),
            ('flexible', 'Flexible'),
        ],
        blank=True,
        null=True,
    )
    preferred_languages = models.JSONField(blank=True, default=list)
    preferred_experience_years = models.IntegerField(blank=True, null=True)
    preferred_experience_with_ages = models.JSONField(blank=True, default=list)
    smoking_allowed = models.BooleanField(default=False)
    pets_in_home = models.BooleanField(default=False)
    additional_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'parent_profiles'
        verbose_name = 'Parent Profile'
        verbose_name_plural = 'Parent Profiles'
    
    def __str__(self):
        return f"Parent Profile: {self.user.email}"


class BabysitterProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="babysitter_profile",
        limit_choices_to={'role': 'babysitter'}
    )

    description = models.TextField(blank=True, null=True)
    experience_years = models.IntegerField(blank=True, null=True)
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    education = models.CharField(max_length=255, blank=True, null=True)
    characteristics = models.JSONField(blank=True, default=list)
    drivers_license = models.BooleanField(default=False)
    car = models.BooleanField(default=False)
    has_children = models.BooleanField(default=False)
    smoker = models.BooleanField(default=False)

    street = models.CharField(max_length=255, blank=True, null=True)
    apartment_number = models.CharField(max_length=50, blank=True, null=True)

    # Geocoding fields
    formatted_address = models.CharField(max_length=500, blank=True, null=True, help_text="Formatted address from geocoding")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    preferred_babysitting_location = models.CharField(
        max_length=50,
        choices=[
            ('parents_home', 'Parents Home'),
            ('babysitters_home', 'Babysitters Home'),
            ('flexible', 'Flexible'),
        ],
        blank=True,
        null=True,
    )
    languages = models.JSONField(blank=True, default=list)
    experience_with_ages = models.JSONField(blank=True, default=list)
    background_check = models.BooleanField(default=False)
    first_aid_certified = models.BooleanField(default=False)

    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00,
        help_text="Average rating from all reviews (1-5)"
    )
    total_reviews = models.PositiveIntegerField(default=0, help_text="Total number of reviews received")

    class Meta:
        db_table = 'babysitter_profiles'
        verbose_name = 'Babysitter Profile'
        verbose_name_plural = 'Babysitter Profiles'

    def __str__(self):
        return f"Babysitter Profile: {self.user.email}"

    def update_rating(self):
        """Recalculate average rating from all reviews."""
        from django.db.models import Avg, Count
        from reviews.models import Review

        stats = Review.objects.filter(volunteer=self.user).aggregate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        self.average_rating = stats['avg_rating'] or 0.00
        self.total_reviews = stats['count'] or 0
        self.save(update_fields=['average_rating', 'total_reviews'])

    
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
