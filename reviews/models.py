import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from tasks.models import Task


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(Task, related_name="review", on_delete=models.CASCADE)
    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="given_reviews", on_delete=models.CASCADE
    )
    volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="received_reviews", on_delete=models.CASCADE
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.parent} -> {self.volunteer} ({self.rating})"

    def is_editable(self) -> bool:
        """Check if review can still be edited (within 24 hours of creation)."""
        from datetime import timedelta
        return timezone.now() < self.created_at + timedelta(hours=24)
