"""
Statistics services for the babysitting marketplace.

Provides computed statistics for:
- Parents (own booking/task data)
- Babysitters (own job/earnings data)
- Admins (global platform metrics)

All statistics are computed on-the-fly using Django ORM aggregates.
No statistics are stored in the database.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from applications.models import Application
from reviews.models import Review
from tasks.models import Task

User = get_user_model()


def get_parent_statistics(user) -> dict:
    """
    Get statistics for a parent user (their own data only).

    Returns:
    - total_bookings: Total tasks created
    - completed_bookings: Tasks that have ended
    - cancelled_bookings: Tasks with rejected/cancelled applications (assumption: no explicit cancel status)
    - upcoming_bookings: Tasks in the future
    - total_hours: Sum of all task durations
    - average_duration: Average task duration in minutes
    - most_hired_babysitter: Babysitter who completed most tasks for this parent
    - total_spent: Sum of (duration * hourly_rate) for completed tasks (if babysitter has rate)
    """
    now = timezone.now()

    tasks = Task.objects.filter(user=user)
    total_bookings = tasks.count()

    completed_bookings = tasks.filter(
        status=Task.CLAIMED,
        end__lt=now
    ).count()

    upcoming_bookings = tasks.filter(
        start__gt=now
    ).count()

    cancelled_bookings = tasks.filter(
        status=Task.UNCLAIMED,
        start__lt=now
    ).count()

    duration_stats = tasks.filter(
        status=Task.CLAIMED,
        end__lt=now,
        duration__isnull=False
    ).aggregate(
        total_minutes=Sum('duration'),
        avg_minutes=Avg('duration')
    )

    total_minutes = duration_stats['total_minutes'] or 0
    total_hours = round(total_minutes / 60, 1)
    average_duration = round(duration_stats['avg_minutes'] or 0, 0)

    most_hired = tasks.filter(
        volunteer__isnull=False
    ).values('volunteer__id', 'volunteer__name', 'volunteer__email').annotate(
        hire_count=Count('id')
    ).order_by('-hire_count').first()

    most_hired_babysitter = None
    if most_hired:
        most_hired_babysitter = {
            'id': str(most_hired['volunteer__id']),
            'name': most_hired['volunteer__name'] or most_hired['volunteer__email'],
            'hire_count': most_hired['hire_count']
        }

    total_spent = Decimal('0.00')
    completed_tasks = tasks.filter(
        status=Task.CLAIMED,
        end__lt=now,
        volunteer__isnull=False,
        duration__isnull=False
    ).select_related('volunteer__babysitter_profile')

    for task in completed_tasks:
        if hasattr(task.volunteer, 'babysitter_profile') and task.volunteer.babysitter_profile:
            hourly_rate = task.volunteer.babysitter_profile.hourly_rate or Decimal('0')
            hours = Decimal(task.duration) / Decimal('60')
            total_spent += hourly_rate * hours

    return {
        'total_bookings': total_bookings,
        'completed_bookings': completed_bookings,
        'cancelled_bookings': cancelled_bookings,
        'upcoming_bookings': upcoming_bookings,
        'total_hours': total_hours,
        'average_duration_minutes': int(average_duration),
        'most_hired_babysitter': most_hired_babysitter,
        'total_spent': float(round(total_spent, 2)),
    }


def get_parent_dashboard_statistics(user, range_days: int = 7) -> dict:
    """
    Get dashboard statistics for a parent user with time filtering.

    Args:
        user: The parent user
        range_days: Number of days to filter data (7, 14, or 30)

    Returns:
        - Core KPIs: total_posted_tasks, accepted_tasks, cancelled_tasks,
                     completed_tasks, acceptance_rate, cancellation_rate
        - Charts: tasks_posted_per_day, tasks_completed_per_day, busiest_days,
                  status_distribution, category_distribution, location_distribution
        - Babysitter analytics: total_unique_babysitters, repeat_babysitters_count,
                                repeat_rate, top_babysitters
        - Response metrics: avg_time_to_first_application, avg_time_to_acceptance,
                           tasks_without_applications_percent
        - Optional: total_hours_booked, average_task_duration, total_spent,
                   average_cost_per_task, average_rating
    """
    from django.db.models.functions import ExtractWeekDay, TruncDate

    now = timezone.now()
    start_date = now - timedelta(days=range_days)

    tasks = Task.objects.filter(user=user, created_at__gte=start_date)

    total_posted_tasks = tasks.count()
    accepted_tasks = tasks.filter(status__in=[Task.CLAIMED, Task.COMPLETED]).count()
    cancelled_tasks = tasks.filter(status=Task.CANCELLED).count()
    completed_tasks = tasks.filter(status=Task.COMPLETED).count()

    acceptance_rate = round((accepted_tasks / total_posted_tasks * 100) if total_posted_tasks > 0 else 0, 1)
    cancellation_rate = round((cancelled_tasks / total_posted_tasks * 100) if total_posted_tasks > 0 else 0, 1)

    tasks_posted_per_day_qs = tasks.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    tasks_posted_per_day = [
        {'date': item['date'].strftime('%Y-%m-%d') if item['date'] else None, 'count': item['count']}
        for item in tasks_posted_per_day_qs
    ]

    tasks_completed_per_day_qs = tasks.filter(
        status=Task.COMPLETED
    ).annotate(
        date=TruncDate('updated_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    tasks_completed_per_day = [
        {'date': item['date'].strftime('%Y-%m-%d') if item['date'] else None, 'count': item['count']}
        for item in tasks_completed_per_day_qs
    ]

    busiest_days_qs = tasks.annotate(
        weekday=ExtractWeekDay('start')
    ).values('weekday').annotate(
        count=Count('id')
    ).order_by('weekday')

    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    busiest_days = [
        {'day': day_names[item['weekday'] - 1] if item['weekday'] else 'Unknown', 'count': item['count']}
        for item in busiest_days_qs
    ]

    status_distribution_qs = tasks.values('status').annotate(count=Count('id'))
    status_distribution = [
        {'status': item['status'], 'count': item['count']}
        for item in status_distribution_qs
    ]

    category_distribution_qs = tasks.values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')

    category_distribution = [
        {'category': item['category__name'] or 'Uncategorized', 'count': item['count']}
        for item in category_distribution_qs
    ]

    location_distribution_qs = tasks.exclude(
        formatted_address__isnull=True
    ).exclude(
        formatted_address=''
    ).values('formatted_address').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    location_distribution = [
        {'location': item['formatted_address'], 'count': item['count']}
        for item in location_distribution_qs
    ]

    unique_babysitters = tasks.filter(volunteer__isnull=False).values('volunteer').distinct().count()

    repeat_babysitters_qs = tasks.filter(
        volunteer__isnull=False
    ).values('volunteer').annotate(
        job_count=Count('id')
    ).filter(job_count__gt=1)
    repeat_babysitters_count = repeat_babysitters_qs.count()

    repeat_rate = round((repeat_babysitters_count / unique_babysitters * 100) if unique_babysitters > 0 else 0, 1)

    top_babysitters_qs = tasks.filter(
        volunteer__isnull=False
    ).values('volunteer__id', 'volunteer__name', 'volunteer__email').annotate(
        task_count=Count('id')
    ).order_by('-task_count')[:5]

    top_babysitters = [
        {
            'id': str(item['volunteer__id']),
            'name': item['volunteer__name'] or item['volunteer__email'],
            'task_count': item['task_count']
        }
        for item in top_babysitters_qs
    ]

    tasks_with_apps = tasks.filter(applications__isnull=False).distinct()
    total_response_time = timedelta(0)
    tasks_with_response = 0

    for task in tasks_with_apps:
        first_app = task.applications.order_by('created_at').first()
        if first_app:
            response_time = first_app.created_at - task.created_at
            total_response_time += response_time
            tasks_with_response += 1

    avg_time_to_first_application_hours = round(
        (total_response_time.total_seconds() / 3600 / tasks_with_response) if tasks_with_response > 0 else 0, 1
    )

    accepted_apps = Application.objects.filter(
        task__user=user,
        task__created_at__gte=start_date,
        status=Application.ACCEPTED
    ).select_related('task')

    total_acceptance_time = timedelta(0)
    accepted_count = 0

    for app in accepted_apps:
        acceptance_time = app.created_at - app.task.created_at
        total_acceptance_time += acceptance_time
        accepted_count += 1

    avg_time_to_acceptance_hours = round(
        (total_acceptance_time.total_seconds() / 3600 / accepted_count) if accepted_count > 0 else 0, 1
    )

    tasks_without_apps = tasks.filter(applications__isnull=True).count()
    tasks_without_applications_percent = round(
        (tasks_without_apps / total_posted_tasks * 100) if total_posted_tasks > 0 else 0, 1
    )

    duration_stats = tasks.filter(
        duration__isnull=False
    ).aggregate(
        total_minutes=Sum('duration'),
        avg_minutes=Avg('duration')
    )

    total_minutes = duration_stats['total_minutes'] or 0
    total_hours_booked = round(total_minutes / 60, 1)
    average_task_duration = round(duration_stats['avg_minutes'] or 0, 0)

    total_spent = Decimal('0.00')
    completed_tasks_with_volunteer = tasks.filter(
        status=Task.COMPLETED,
        volunteer__isnull=False,
        duration__isnull=False
    ).select_related('volunteer__babysitter_profile')

    for task in completed_tasks_with_volunteer:
        if hasattr(task.volunteer, 'babysitter_profile') and task.volunteer.babysitter_profile:
            hourly_rate = task.volunteer.babysitter_profile.hourly_rate or Decimal('0')
            hours = Decimal(task.duration) / Decimal('60')
            total_spent += hourly_rate * hours

    average_cost_per_task = round(
        float(total_spent) / completed_tasks if completed_tasks > 0 else 0, 2
    )

    rating_stats = Review.objects.filter(
        parent=user,
        created_at__gte=start_date
    ).aggregate(
        avg_rating=Avg('rating'),
        count=Count('id')
    )
    average_rating = round(rating_stats['avg_rating'] or 0, 1)
    review_count = rating_stats['count']

    return {
        'total_posted_tasks': total_posted_tasks,
        'accepted_tasks': accepted_tasks,
        'cancelled_tasks': cancelled_tasks,
        'completed_tasks': completed_tasks,
        'acceptance_rate': acceptance_rate,
        'cancellation_rate': cancellation_rate,
        'tasks_posted_per_day': tasks_posted_per_day,
        'tasks_completed_per_day': tasks_completed_per_day,
        'busiest_days': busiest_days,
        'status_distribution': status_distribution,
        'category_distribution': category_distribution,
        'location_distribution': location_distribution,
        'total_unique_babysitters': unique_babysitters,
        'repeat_babysitters_count': repeat_babysitters_count,
        'repeat_rate': repeat_rate,
        'top_babysitters': top_babysitters,
        'avg_time_to_first_application_hours': avg_time_to_first_application_hours,
        'avg_time_to_acceptance_hours': avg_time_to_acceptance_hours,
        'tasks_without_applications_percent': tasks_without_applications_percent,
        'total_hours_booked': total_hours_booked,
        'average_task_duration': int(average_task_duration),
        'total_spent': float(round(total_spent, 2)),
        'average_cost_per_task': average_cost_per_task,
        'average_rating': average_rating,
        'review_count': review_count,
        'range_days': range_days,
    }


def get_babysitter_statistics(user) -> dict:
    """
    Get statistics for a babysitter user (their own data only).

    Returns:
    - total_jobs: Total accepted applications / assigned tasks
    - completed_jobs: Completed tasks (past end date)
    - cancelled_jobs: Rejected applications
    - total_hours: Sum of task durations for completed jobs
    - average_duration: Average job duration in minutes
    - total_earnings: Sum of (duration * own hourly_rate)
    - average_hourly_rate: From profile
    - average_rating: From reviews
    - review_count: Number of reviews received
    - repeat_parents: Number of parents who hired more than once
    - earnings_per_month: Monthly earnings breakdown
    """
    now = timezone.now()

    assigned_tasks = Task.objects.filter(volunteer=user)
    total_jobs = assigned_tasks.count()

    completed_jobs = assigned_tasks.filter(end__lt=now).count()

    cancelled_jobs = Application.objects.filter(
        volunteer=user,
        status=Application.REJECTED
    ).count()

    duration_stats = assigned_tasks.filter(
        end__lt=now,
        duration__isnull=False
    ).aggregate(
        total_minutes=Sum('duration'),
        avg_minutes=Avg('duration')
    )

    total_minutes = duration_stats['total_minutes'] or 0
    total_hours = round(total_minutes / 60, 1)
    average_duration = round(duration_stats['avg_minutes'] or 0, 0)

    hourly_rate = Decimal('0.00')
    if hasattr(user, 'babysitter_profile') and user.babysitter_profile:
        hourly_rate = user.babysitter_profile.hourly_rate or Decimal('0.00')

    total_earnings = hourly_rate * Decimal(total_minutes) / Decimal('60')

    review_stats = Review.objects.filter(volunteer=user).aggregate(
        avg_rating=Avg('rating'),
        count=Count('id')
    )
    average_rating = round(review_stats['avg_rating'] or 0, 1)
    review_count = review_stats['count']

    repeat_parents = assigned_tasks.values('user').annotate(
        job_count=Count('id')
    ).filter(job_count__gt=1).count()

    six_months_ago = now - timedelta(days=180)
    earnings_per_month = []

    monthly_tasks = assigned_tasks.filter(
        end__lt=now,
        end__gte=six_months_ago,
        duration__isnull=False
    ).annotate(
        month=TruncMonth('end')
    ).values('month').annotate(
        total_minutes=Sum('duration')
    ).order_by('month')

    for entry in monthly_tasks:
        month_earnings = hourly_rate * Decimal(entry['total_minutes']) / Decimal('60')
        earnings_per_month.append({
            'month': entry['month'].strftime('%Y-%m') if entry['month'] else None,
            'earnings': float(round(month_earnings, 2)),
            'hours': round(entry['total_minutes'] / 60, 1)
        })

    return {
        'total_jobs': total_jobs,
        'completed_jobs': completed_jobs,
        'cancelled_jobs': cancelled_jobs,
        'total_hours': total_hours,
        'average_duration_minutes': int(average_duration),
        'total_earnings': float(round(total_earnings, 2)),
        'hourly_rate': float(hourly_rate),
        'average_rating': average_rating,
        'review_count': review_count,
        'repeat_parents': repeat_parents,
        'earnings_per_month': earnings_per_month,
    }


def get_babysitter_dashboard_statistics(user, range_days: int = 30) -> dict:
    """
    Get dashboard statistics for a babysitter user with time filtering.

    Args:
        user: The babysitter user
        range_days: Number of days to filter data (7, 14, or 30)

    Returns:
        - Core KPIs: total_applications, accepted_applications, cancelled_applications,
                     completed_tasks, acceptance_rate, cancellation_rate
        - Charts: tasks_per_day, busiest_days, status_distribution, category_distribution,
                  location_distribution
        - Repeat clients: total_unique_parents, repeat_parents_count, repeat_rate
        - Optional: total_hours_worked, average_task_duration, average_rating
    """
    from django.db.models.functions import ExtractWeekDay, TruncDate

    now = timezone.now()
    start_date = now - timedelta(days=range_days)

    applications = Application.objects.filter(
        volunteer=user,
        created_at__gte=start_date
    )

    total_applications = applications.count()
    accepted_applications = applications.filter(status=Application.ACCEPTED).count()
    cancelled_applications = applications.filter(status=Application.CANCELLED).count()
    rejected_applications = applications.filter(status=Application.REJECTED).count()
    pending_applications = applications.filter(status=Application.PENDING).count()

    completed_tasks = Task.objects.filter(
        volunteer=user,
        status=Task.COMPLETED,
        start__gte=start_date
    ).count()

    acceptance_rate = round((accepted_applications / total_applications * 100) if total_applications > 0 else 0, 1)
    cancellation_rate = round((cancelled_applications / total_applications * 100) if total_applications > 0 else 0, 1)

    assigned_tasks = Task.objects.filter(
        volunteer=user,
        start__gte=start_date
    )

    tasks_per_day_qs = assigned_tasks.annotate(
        date=TruncDate('start')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    tasks_per_day = [
        {'date': item['date'].strftime('%Y-%m-%d') if item['date'] else None, 'count': item['count']}
        for item in tasks_per_day_qs
    ]

    busiest_days_qs = assigned_tasks.annotate(
        weekday=ExtractWeekDay('start')
    ).values('weekday').annotate(
        count=Count('id')
    ).order_by('weekday')

    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    busiest_days = [
        {'day': day_names[item['weekday'] - 1] if item['weekday'] else 'Unknown', 'count': item['count']}
        for item in busiest_days_qs
    ]

    status_distribution = [
        {'status': 'pending', 'count': pending_applications},
        {'status': 'accepted', 'count': accepted_applications},
        {'status': 'rejected', 'count': rejected_applications},
        {'status': 'cancelled', 'count': cancelled_applications},
    ]

    category_distribution_qs = assigned_tasks.values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')

    category_distribution = [
        {'category': item['category__name'] or 'Uncategorized', 'count': item['count']}
        for item in category_distribution_qs
    ]

    location_distribution_qs = assigned_tasks.exclude(
        formatted_address__isnull=True
    ).exclude(
        formatted_address=''
    ).values('formatted_address').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    location_distribution = [
        {'location': item['formatted_address'], 'count': item['count']}
        for item in location_distribution_qs
    ]

    unique_parents = assigned_tasks.values('user').distinct().count()

    repeat_parents_qs = assigned_tasks.values('user').annotate(
        job_count=Count('id')
    ).filter(job_count__gt=1)
    repeat_parents_count = repeat_parents_qs.count()

    repeat_rate = round((repeat_parents_count / unique_parents * 100) if unique_parents > 0 else 0, 1)

    completed_tasks_with_duration = Task.objects.filter(
        volunteer=user,
        status=Task.COMPLETED,
        duration__isnull=False,
        start__gte=start_date
    )

    duration_stats = completed_tasks_with_duration.aggregate(
        total_minutes=Sum('duration'),
        avg_minutes=Avg('duration')
    )

    total_minutes = duration_stats['total_minutes'] or 0
    total_hours_worked = round(total_minutes / 60, 1)
    average_task_duration = round(duration_stats['avg_minutes'] or 0, 0)

    review_stats = Review.objects.filter(volunteer=user).aggregate(
        avg_rating=Avg('rating'),
        count=Count('id')
    )
    average_rating = round(review_stats['avg_rating'] or 0, 1)
    review_count = review_stats['count']

    return {
        'total_applications': total_applications,
        'accepted_applications': accepted_applications,
        'cancelled_applications': cancelled_applications,
        'completed_tasks': completed_tasks,
        'acceptance_rate': acceptance_rate,
        'cancellation_rate': cancellation_rate,
        'tasks_per_day': tasks_per_day,
        'busiest_days': busiest_days,
        'status_distribution': status_distribution,
        'category_distribution': category_distribution,
        'location_distribution': location_distribution,
        'total_unique_parents': unique_parents,
        'repeat_parents_count': repeat_parents_count,
        'repeat_rate': repeat_rate,
        'total_hours_worked': total_hours_worked,
        'average_task_duration': int(average_task_duration),
        'average_rating': average_rating,
        'review_count': review_count,
        'range_days': range_days,
    }


def get_admin_statistics() -> dict:
    """
    Get global platform statistics for admins.

    Returns:
    - User metrics: total, by role, new per month
    - Booking metrics: total, by status, per month
    - Completion/cancellation rates
    - Average job duration
    - Parent to babysitter ratio
    """
    now = timezone.now()

    users = User.objects.exclude(Q(is_superuser=True) | Q(is_staff=True))
    total_users = users.count()

    parents_count = users.filter(role='parent').count()
    babysitters_count = users.filter(role='babysitter').count()
    admins_count = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).count()

    active_parents = User.objects.filter(
        role='parent',
        created_tasks__isnull=False
    ).distinct().count()

    active_babysitters = User.objects.filter(
        role='babysitter',
        task_applications__isnull=False
    ).distinct().count()

    six_months_ago = now - timedelta(days=180)
    new_users_per_month = User.objects.filter(
        date_joined__gte=six_months_ago
    ).annotate(
        month=TruncMonth('date_joined')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    new_users_monthly = [
        {
            'month': entry['month'].strftime('%Y-%m') if entry['month'] else None,
            'count': entry['count']
        }
        for entry in new_users_per_month
    ]

    tasks = Task.objects.all()
    total_bookings = tasks.count()

    claimed_count = tasks.filter(status=Task.CLAIMED).count()
    unclaimed_count = tasks.filter(status=Task.UNCLAIMED).count()
    completed_status_count = tasks.filter(status=Task.COMPLETED).count()
    cancelled_status_count = tasks.filter(status=Task.CANCELLED).count()

    completed_count = tasks.filter(status=Task.COMPLETED).count()

    bookings_per_month = tasks.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    bookings_monthly = [
        {
            'month': entry['month'].strftime('%Y-%m') if entry['month'] else None,
            'count': entry['count']
        }
        for entry in bookings_per_month
    ][-12:]

    past_tasks = tasks.filter(end__lt=now).count()
    completion_rate = round((completed_count / past_tasks * 100) if past_tasks > 0 else 0, 1)

    cancelled_count = tasks.filter(status=Task.CANCELLED).count()
    cancellation_rate = round((cancelled_count / past_tasks * 100) if past_tasks > 0 else 0, 1)

    avg_duration = tasks.filter(
        duration__isnull=False
    ).aggregate(avg=Avg('duration'))['avg'] or 0

    ratio = round(parents_count / babysitters_count, 2) if babysitters_count > 0 else 0

    applications = Application.objects.all()
    pending_apps = applications.filter(status=Application.PENDING).count()
    accepted_apps = applications.filter(status=Application.ACCEPTED).count()
    rejected_apps = applications.filter(status=Application.REJECTED).count()

    avg_rating = Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    total_reviews = Review.objects.count()

    tasks_per_category = tasks.values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')

    category_data = [
        {'category': entry['category__name'] or 'Uncategorized', 'count': entry['count']}
        for entry in tasks_per_category
    ]

    return {
        'user_totals': {
            'total': total_users,
            'parents': parents_count,
            'babysitters': babysitters_count,
            'admins': admins_count,
            'active_parents': active_parents,
            'active_babysitters': active_babysitters,
        },
        'new_users_per_month': new_users_monthly,
        'total_bookings': total_bookings,
        'bookings_per_month': bookings_monthly,
        'tasks_by_status': {
            'unclaimed': unclaimed_count,
            'claimed': claimed_count,
            'completed': completed_status_count,
            'cancelled': cancelled_status_count,
            'total': total_bookings,
        },
        'completion_rate': completion_rate,
        'cancellation_rate': cancellation_rate,
        'average_duration_minutes': round(avg_duration, 0),
        'parent_to_babysitter_ratio': ratio,
        'applications_by_status': {
            'pending': pending_apps,
            'accepted': accepted_apps,
            'rejected': rejected_apps,
            'total': applications.count(),
        },
        'average_rating': round(float(avg_rating), 1),
        'total_reviews': total_reviews,
        'tasks_per_category': category_data,
    }
