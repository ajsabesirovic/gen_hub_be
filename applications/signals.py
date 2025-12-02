from django.db.models.signals import post_save
from django.dispatch import receiver

from notifications.services import create_notification
from .models import Application


@receiver(post_save, sender=Application)
def application_notification_handler(sender, instance: Application, created: bool, **kwargs):
    task = instance.task
    if created:
        create_notification(
            user=task.user,
            type="task_application",
            title="New volunteer application",
            message=f"{instance.volunteer} applied to '{task.title}'.",
        )
        return

    update_fields = kwargs.get('update_fields')
    if update_fields and 'status' not in update_fields:
        return

    if instance.status == Application.ACCEPTED:
        create_notification(
            user=instance.volunteer,
            type="application_accepted",
            title="Application accepted",
            message=f"Your application for '{task.title}' was accepted.",
        )
    elif instance.status == Application.REJECTED:
        create_notification(
            user=instance.volunteer,
            type="application_rejected",
            title="Application rejected",
            message=f"Your application for '{task.title}' was rejected.",
        )
