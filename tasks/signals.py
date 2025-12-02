from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from notifications.models import Notification
from notifications.services import create_notification
from .models import Task


@receiver(post_save, sender=Task)
def task_deadline_notification(sender, instance: Task, **kwargs):
    if not instance.volunteer:
        return
    
    # Only process if start time was actually updated
    update_fields = kwargs.get('update_fields')
    if update_fields and 'start' not in update_fields:
        return
    
    now = timezone.now()
    time_until_start = instance.start - now
    if time_until_start < timedelta(0) or time_until_start > timedelta(hours=24):
        return

    for user, role in ((instance.volunteer, "assigned"), (instance.user, "owner")):
        if Notification.objects.filter(
            user=user, type="task_deadline", message__icontains=str(instance.id)
        ).exists():
            continue
        create_notification(
            user=user,
            type="task_deadline",
            title="Task approaching deadline",
            message=f"Task {instance.id} ('{instance.title}') is starting soon for {role}.",
        )
