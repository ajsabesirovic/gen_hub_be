from django.db.models.signals import post_save
from django.dispatch import receiver

from notifications.services import create_notification
from .models import Review


@receiver(post_save, sender=Review)
def review_created(sender, instance: Review, created: bool, **kwargs):
    if created:
        create_notification(
            user=instance.volunteer,
            type="review_received",
            title="New review received",
            message=f"You received a {instance.rating}-star review from {instance.senior}.",
        )
