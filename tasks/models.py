import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from categories.models import Category
from gen_hub_be.db.fields import FlexibleJSONField


class Task(models.Model):
    UNCLAIMED = "unclaimed"
    CLAIMED = "claimed"
    STATUS_CHOICES = [
        (UNCLAIMED, "Unclaimed"),
        (CLAIMED, "Claimed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="created_tasks", on_delete=models.CASCADE
    )
    volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_tasks",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    category = models.ForeignKey(Category, related_name="tasks", on_delete=models.PROTECT)
    title = models.CharField(max_length=255)
    description = models.TextField()
    start = models.DateTimeField()
    end = models.DateTimeField()
    whole_day = models.BooleanField(default=False)
    color = models.CharField(max_length=32, default="#0099ff")
    location = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=UNCLAIMED)
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    extra_dates = FlexibleJSONField(blank=True, null=True, default=dict)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["start"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self) -> str:
        return self.title
