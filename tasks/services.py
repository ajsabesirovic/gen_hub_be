from datetime import timedelta

from django.db.models import Avg, Count, Q, QuerySet
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import exceptions

from applications.models import Application
from notifications.services import create_notification
from reviews.models import Review
from users.models import User
from .models import Task


def create_task(*, senior, validated_data) -> Task:
    if senior.role != "senior":
        raise exceptions.PermissionDenied("Only seniors can create tasks.")
    return Task.objects.create(user=senior, **validated_data)


def update_task(*, task: Task, user, validated_data) -> Task:
    if task.user != user:
        raise exceptions.PermissionDenied("You can only edit your own tasks.")
    for attr, value in validated_data.items():
        setattr(task, attr, value)
    task.save()
    return task


def delete_task(*, task: Task, user) -> None:
    if task.user != user:
        raise exceptions.PermissionDenied("You can only delete your own tasks.")
    task.delete()


def filter_tasks(queryset: QuerySet, params) -> QuerySet:
    category = params.get("category")
    location = params.get("location")
    date_str = params.get("date")

    if category:
        queryset = queryset.filter(category__id=category)
    if location:
        queryset = queryset.filter(location__icontains=location)
    if date_str:
        queryset = queryset.filter(start__date=date_str)

    return queryset


def get_available_tasks(user, params) -> QuerySet:
    qs = Task.objects.filter(status=Task.UNCLAIMED).exclude(user=user)
    return filter_tasks(qs, params)


def claim_task(*, task: Task, volunteer) -> Task:
    if task.user == volunteer:
        raise exceptions.ValidationError("You cannot claim your own task.")
    if task.volunteer and task.volunteer != volunteer:
        raise exceptions.ValidationError("Task already claimed by another volunteer.")

    task.volunteer = volunteer
    task.status = Task.CLAIMED
    task.save(update_fields=["volunteer", "status", "updated_at"])
    # Replace bulk update with individual saves to trigger signals
    rejected_apps = Application.objects.filter(task=task).exclude(volunteer=volunteer)
    for app in rejected_apps:
        app.status = Application.REJECTED
        app.save(update_fields=["status"])
    create_notification(
        user=task.user,
        type="task_claimed",
        title="Task claimed",
        message=f"{volunteer} has claimed your task '{task.title}'.",
    )
    return task


def release_task(*, task: Task) -> Task:
    task.volunteer = None
    task.status = Task.UNCLAIMED
    task.save(update_fields=["volunteer", "status", "updated_at"])
    return task


def tasks_for_senior(user, segment: str | None = None) -> QuerySet:
    qs = Task.objects.filter(user=user)
    if segment == "upcoming":
        qs = qs.filter(start__gte=timezone.now())
    elif segment == "active":
        now = timezone.now()
        qs = qs.filter(start__lte=now, end__gte=now)
    elif segment == "completed":
        qs = qs.filter(end__lt=timezone.now())
    return qs


def tasks_for_volunteer(user, segment: str | None = None) -> QuerySet:
    qs = Task.objects.filter(volunteer=user)
    if segment == "upcoming":
        qs = qs.filter(start__gte=timezone.now())
    elif segment == "active":
        now = timezone.now()
        qs = qs.filter(start__lte=now, end__gte=now)
    elif segment == "completed":
        qs = qs.filter(end__lt=timezone.now())
    return qs


def approaching_deadline_tasks():
    now = timezone.now()
    window = now + timedelta(hours=24)
    return Task.objects.filter(start__range=(now, window), volunteer__isnull=False)


def get_statistics():
    tasks_per_category = (
        Task.objects.values("category__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    tasks_per_month = (
        Task.objects.annotate(month=TruncMonth("start"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    role_counts = User.objects.values("role").annotate(count=Count("id"))
    admin_count = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).count()
    avg_rating = Review.objects.aggregate(avg=Avg("rating"))["avg"] or 0

    role_map = {entry["role"]: entry["count"] for entry in role_counts}

    return {
        "tasks_per_category": [
            {"category": entry["category__name"], "count": entry["count"]}
            for entry in tasks_per_category
        ],
        "tasks_per_month": [
            {"month": entry["month"].strftime("%Y-%m") if entry["month"] else None, "count": entry["count"]}
            for entry in tasks_per_month
        ],
        "user_totals": {
            "seniors": role_map.get("senior", 0),
            "volunteers": role_map.get("volunteer", 0),
            "admins": admin_count,
        },
        "average_volunteer_rating": avg_rating,
    }
