import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    TASK_COMPLETED = "task_completed"
    NEW_REVIEW = "new_review"
    APPLICATION_ACCEPTED = "application_accepted"
    APPLICATION_REJECTED = "application_rejected"
    NEW_APPLICATION = "new_application"
    CUSTOM = "custom"

    TYPE_CHOICES = [
        (TASK_COMPLETED, "Task Completed"),
        (NEW_REVIEW, "New Review"),
        (APPLICATION_ACCEPTED, "Application Accepted"),
        (APPLICATION_REJECTED, "Application Rejected"),
        (NEW_APPLICATION, "New Application"),
        (CUSTOM, "Custom"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="notifications", on_delete=models.CASCADE
    )
    type = models.CharField(max_length=64, choices=TYPE_CHOICES, default=CUSTOM)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    related_task_id = models.UUIDField(null=True, blank=True)
    related_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} - {self.title}"
