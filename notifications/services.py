from notifications.models import Notification


def create_notification(*, user, type: str, title: str, message: str) -> Notification:
    return Notification.objects.create(user=user, type=type, title=title, message=message)
