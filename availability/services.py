from datetime import timedelta

from rest_framework import exceptions

from tasks.models import Task
from .models import UserAvailability


def create_availability(*, user, validated_data) -> UserAvailability:
    if user.role != "volunteer":
        raise exceptions.PermissionDenied("Only volunteers can manage availability.")
    return UserAvailability.objects.create(user=user, **validated_data)


def update_availability(*, availability: UserAvailability, user, validated_data) -> UserAvailability:
    if availability.user != user:
        raise exceptions.PermissionDenied("You can only update your own availability.")
    for attr, value in validated_data.items():
        setattr(availability, attr, value)
    availability.save()
    return availability


def delete_availability(*, availability: UserAvailability, user) -> None:
    if availability.user != user:
        raise exceptions.PermissionDenied("You can only delete your own availability.")
    availability.delete()


def _overlaps(start_a, end_a, start_b, end_b) -> bool:
    return max(start_a, start_b) < min(end_a, end_b)


def _overlaps_datetime(start_a, end_a, start_b, end_b) -> bool:
    """Compare full datetime objects to handle edge cases like midnight-spanning windows."""
    return max(start_a, start_b) < min(end_a, end_b)


def is_user_available_for_task(user, task: Task) -> bool:
    availabilities = UserAvailability.objects.filter(user=user)
    task_day = task.start.weekday()
    task_date = task.start.date()
    task_start = task.start
    task_end = task.end 

    for availability in availabilities:
        avail_start = availability.start_time
        avail_end = availability.end_time 
        
        if availability.type == UserAvailability.WEEKLY:
            if availability.day_of_week != task_day:
                continue
            avail_start_on_task_date = task_start.replace(
                hour=avail_start.hour,
                minute=avail_start.minute,
                second=avail_start.second,
                microsecond=avail_start.microsecond
            )
            avail_end_on_task_date = task_start.replace(
                hour=avail_end.hour,
                minute=avail_end.minute,
                second=avail_end.second,
                microsecond=avail_end.microsecond
            )
            if avail_end_on_task_date < avail_start_on_task_date:
                avail_end_on_task_date += timedelta(days=1)
            if _overlaps_datetime(avail_start_on_task_date, avail_end_on_task_date, task_start, task_end):
                return True
        elif availability.type == UserAvailability.MONTHLY:
            if availability.date.date() != task_date:
                continue
            avail_start_on_task_date = task_start.replace(
                hour=avail_start.hour,
                minute=avail_start.minute,
                second=avail_start.second,
                microsecond=avail_start.microsecond
            )
            avail_end_on_task_date = task_start.replace(
                hour=avail_end.hour,
                minute=avail_end.minute,
                second=avail_end.second,
                microsecond=avail_end.microsecond
            )
            if avail_end_on_task_date < avail_start_on_task_date:
                avail_end_on_task_date += timedelta(days=1)
            if _overlaps_datetime(avail_start_on_task_date, avail_end_on_task_date, task_start, task_end):
                return True
    return False
