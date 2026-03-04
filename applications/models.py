import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from tasks.models import Task


class Application(models.Model):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted"),
        (REJECTED, "Rejected"),
        (CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, related_name="applications", on_delete=models.CASCADE)
    volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="task_applications", on_delete=models.CASCADE
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("task", "volunteer")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.volunteer} -> {self.task}"


class Invitation(models.Model):
    """
    Represents an invitation sent by a parent to a babysitter for a specific task.
    """
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted"),
        (DECLINED, "Declined"),
        (EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, related_name="invitations", on_delete=models.CASCADE)
    babysitter = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="task_invitations", on_delete=models.CASCADE
    )
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("task", "babysitter")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invitation: {self.task.user} -> {self.babysitter} for {self.task}"
