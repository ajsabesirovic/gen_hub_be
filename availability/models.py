import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserAvailability(models.Model):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    TYPE_CHOICES = [(WEEKLY, "Weekly"), (MONTHLY, "Monthly")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="availabilities"
    )
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    day_of_week = models.PositiveSmallIntegerField(null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["user", "type", "start_time"]
        verbose_name = "User availability"
        verbose_name_plural = "User availabilities"

    def __str__(self) -> str:
        return f"{self.user} - {self.type}"
