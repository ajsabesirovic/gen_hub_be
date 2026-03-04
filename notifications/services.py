from django.core.mail import send_mail
from django.conf import settings
from notifications.models import Notification


def send_notification_email(user, title: str, message: str):
    """Send email notification to user if they have an email address."""
    if not user.email:
        return

    try:
        send_mail(
            subject=f"GenHub: {title}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Failed to send email notification to {user.email}: {e}")


def create_notification(
    *,
    user,
    type: str,
    title: str,
    message: str,
    related_task_id=None,
    related_user_id=None,
) -> Notification:
    """
    Create a notification and send it via email.

    Every notification is always:
    1. Saved to the database
    2. Sent via email to the user
    """
    notification = Notification.objects.create(
        user=user,
        type=type,
        title=title,
        message=message,
        related_task_id=related_task_id,
        related_user_id=related_user_id,
    )

    send_notification_email(user, title, message)

    return notification


def notify_task_completed(*, parent, task, volunteer):
    """Notify parent that a task has been completed by the babysitter."""
    return create_notification(
        user=parent,
        type=Notification.TASK_COMPLETED,
        title="Task Completed",
        message=f"{volunteer.name or volunteer.username} has marked the task '{task.title}' as completed. Please leave a review!",
        related_task_id=task.id,
        related_user_id=volunteer.id,
    )


def notify_new_review(*, volunteer, parent, task, rating):
    """Notify babysitter that they received a new review."""
    return create_notification(
        user=volunteer,
        type=Notification.NEW_REVIEW,
        title="New Review Received",
        message=f"{parent.name or parent.username} left you a {rating}-star review for the task '{task.title}'.",
        related_task_id=task.id,
        related_user_id=parent.id,
    )
