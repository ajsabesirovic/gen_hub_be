from datetime import datetime, timedelta, time
from collections import defaultdict

from django.utils import timezone
from rest_framework import exceptions

from tasks.models import Task
from .models import UserAvailability


DAY_MAP = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}
DAY_MAP_REVERSE = {v: k for k, v in DAY_MAP.items()}


def create_availability(*, user, validated_data) -> UserAvailability:
    if user.role != "babysitter":
        raise exceptions.PermissionDenied("Only babysitters can manage availability.")
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


def get_aggregated_availability(user):
    """
    Fetch all availability entries for user and aggregate into frontend format.

    Returns a structure matching the frontend's AvailabilityData interface:
    {
        mode: "weekly" | "monthly",
        weeklySchedule: [{day: string, timeRanges: [{id, from, to}]}],
        monthlySchedule: [{date: string, from: string, to: string}],
        currentMonth: string
    }
    """
    availabilities = UserAvailability.objects.filter(user=user)

    weekly_by_day = defaultdict(list)
    monthly_entries = []

    weekly_whole_day = {}

    for avail in availabilities:
        if avail.type == UserAvailability.WEEKLY:
            day_name = DAY_MAP_REVERSE.get(avail.day_of_week, 'monday')

            if avail.whole_day:
                weekly_whole_day[day_name] = True
                if day_name not in weekly_by_day:
                    weekly_by_day[day_name] = []
            else:
                weekly_by_day[day_name].append({
                    'id': str(avail.id),
                    'from': avail.start_time.strftime('%H:%M') if avail.start_time else '',
                    'to': avail.end_time.strftime('%H:%M') if avail.end_time else '',
                })
        elif avail.type == UserAvailability.MONTHLY:
            date_str = avail.date.strftime('%Y-%m-%d') if avail.date else ''
            monthly_entries.append({
                'date': date_str,
                'from': avail.start_time.strftime('%H:%M') if avail.start_time and not avail.whole_day else '',
                'to': avail.end_time.strftime('%H:%M') if avail.end_time and not avail.whole_day else '',
                'whole_day': avail.whole_day,
            })

    weekly_schedule = [
        {
            'day': day,
            'timeRanges': ranges,
            'whole_day': weekly_whole_day.get(day, False)
        }
        for day, ranges in weekly_by_day.items()
    ]

    mode = 'weekly'
    if monthly_entries and not weekly_schedule:
        mode = 'monthly'

    return {
        'mode': mode,
        'weeklySchedule': weekly_schedule,
        'monthlySchedule': monthly_entries,
        'currentMonth': timezone.now().strftime('%Y-%m-%d'),
    }


def save_aggregated_availability(user, data):
    """
    Receive aggregated frontend format and save as individual database rows.

    This function uses the 'mode' field to determine which schedule type is being updated.
    Only the schedule type matching the mode is replaced; the other type is preserved.
    This allows users to edit weekly and monthly schedules independently.
    """
    if user.role != 'babysitter':
        raise exceptions.PermissionDenied("Only babysitters can manage availability.")

    mode = data.get('mode', 'weekly')
    weekly_schedule = data.get('weeklySchedule', [])
    monthly_schedule = data.get('monthlySchedule', [])

    if mode == 'weekly':
        UserAvailability.objects.filter(user=user, type=UserAvailability.WEEKLY).delete()
        
        for day_entry in weekly_schedule:
            day_name = day_entry.get('day', '').lower()
            day_of_week = DAY_MAP.get(day_name)

            if day_of_week is None:
                continue

            time_ranges = day_entry.get('timeRanges', [])
            is_whole_day = day_entry.get('whole_day', False)

            if is_whole_day:
                UserAvailability.objects.create(
                    user=user,
                    type=UserAvailability.WEEKLY,
                    day_of_week=day_of_week,
                    start_time=timezone.make_aware(datetime.combine(datetime.today(), time(0, 0))),
                    end_time=timezone.make_aware(datetime.combine(datetime.today(), time(23, 59))),
                    whole_day=True,
                )
            elif not time_ranges:
                continue
            else:
                for tr in time_ranges:
                    from_str = tr.get('from', '')
                    to_str = tr.get('to', '')

                    if from_str and to_str:
                        try:
                            start_time = datetime.strptime(from_str, '%H:%M').time()
                            end_time = datetime.strptime(to_str, '%H:%M').time()

                            UserAvailability.objects.create(
                                user=user,
                                type=UserAvailability.WEEKLY,
                                day_of_week=day_of_week,
                                start_time=timezone.make_aware(datetime.combine(datetime.today(), start_time)),
                                end_time=timezone.make_aware(datetime.combine(datetime.today(), end_time)),
                                whole_day=False,
                            )
                        except ValueError:
                            continue

    elif mode == 'monthly':
        UserAvailability.objects.filter(user=user, type=UserAvailability.MONTHLY).delete()

        for entry in monthly_schedule:
            date_str = entry.get('date', '')
            from_str = entry.get('from', '')
            to_str = entry.get('to', '')
            is_whole_day = entry.get('whole_day', False)

            if not date_str:
                continue

            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                continue

            if is_whole_day:
                start_dt = datetime.combine(date_obj.date(), time(0, 0))
                end_dt = datetime.combine(date_obj.date(), time(23, 59))
                UserAvailability.objects.create(
                    user=user,
                    type=UserAvailability.MONTHLY,
                    date=timezone.make_aware(date_obj),
                    start_time=timezone.make_aware(start_dt),
                    end_time=timezone.make_aware(end_dt),
                    whole_day=True,
                )
            elif from_str and to_str:
                try:
                    start_time = datetime.strptime(from_str, '%H:%M').time()
                    end_time = datetime.strptime(to_str, '%H:%M').time()
                    start_dt = datetime.combine(date_obj.date(), start_time)
                    end_dt = datetime.combine(date_obj.date(), end_time)
                except ValueError:
                    start_dt = datetime.combine(date_obj.date(), time(0, 0))
                    end_dt = datetime.combine(date_obj.date(), time(23, 59))
                UserAvailability.objects.create(
                    user=user,
                    type=UserAvailability.MONTHLY,
                    date=timezone.make_aware(date_obj),
                    start_time=timezone.make_aware(start_dt),
                    end_time=timezone.make_aware(end_dt),
                    whole_day=False,
                )
            else:
                start_dt = datetime.combine(date_obj.date(), time(0, 0))
                end_dt = datetime.combine(date_obj.date(), time(23, 59))
                UserAvailability.objects.create(
                    user=user,
                    type=UserAvailability.MONTHLY,
                    date=timezone.make_aware(date_obj),
                    start_time=timezone.make_aware(start_dt),
                    end_time=timezone.make_aware(end_dt),
                    whole_day=False,
                )

    return {'detail': 'Availability saved successfully'}


def get_availability_for_date(user, target_date):
    """
    Get availability for a specific date, applying priority rules.

    Priority: Monthly availability takes precedence over weekly availability
    for the same calendar day.

    Returns list of time slots available on that date.
    """
    day_of_week = target_date.weekday()

    monthly_avails = UserAvailability.objects.filter(
        user=user,
        type=UserAvailability.MONTHLY,
        date__date=target_date
    )

    if monthly_avails.exists():
        return [
            {
                'from': avail.start_time.strftime('%H:%M') if avail.start_time else '',
                'to': avail.end_time.strftime('%H:%M') if avail.end_time else '',
            }
            for avail in monthly_avails
        ]

    weekly_avails = UserAvailability.objects.filter(
        user=user,
        type=UserAvailability.WEEKLY,
        day_of_week=day_of_week
    )

    return [
        {
            'from': avail.start_time.strftime('%H:%M') if avail.start_time else '',
            'to': avail.end_time.strftime('%H:%M') if avail.end_time else '',
        }
        for avail in weekly_avails
    ]
