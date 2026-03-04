import logging
from datetime import timedelta
from decimal import Decimal
from typing import Optional, TypedDict

import requests
from django.conf import settings
from django.db.models import Avg, Count, Q, QuerySet
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import exceptions

from applications.models import Application
from notifications.services import create_notification
from reviews.models import Review
from users.models import User
from .models import Task

logger = logging.getLogger(__name__)


class GeocodingResult(TypedDict):
    formatted_address: str
    latitude: Decimal
    longitude: Decimal


def geocode_address(address: str) -> Optional[GeocodingResult]:
    """
    Convert an address string to coordinates using Google Geocoding API.
    Returns None if geocoding fails or API key is not configured.
    """
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key or not address:
        return None

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": api_key,
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            location = result["geometry"]["location"]
            return GeocodingResult(
                formatted_address=result.get("formatted_address", address),
                latitude=Decimal(str(location["lat"])),
                longitude=Decimal(str(location["lng"])),
            )
        else:
            logger.warning(f"Geocoding failed for address '{address}': {data.get('status')}")
            return None
    except requests.RequestException as e:
        logger.error(f"Geocoding request failed for address '{address}': {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing geocoding response for address '{address}': {e}")
        return None


def create_task(*, parent, validated_data) -> Task:
    if parent.role != "parent":
        raise exceptions.PermissionDenied("Only parents can create tasks.")

    # Only geocode if location is provided and no geocoding data from frontend
    location = validated_data.get("location")
    has_frontend_geocoding = (
        validated_data.get("latitude") is not None and
        validated_data.get("longitude") is not None
    )

    if location and not has_frontend_geocoding:
        # Fall back to server-side geocoding
        geocoding_result = geocode_address(location)
        if geocoding_result:
            validated_data["formatted_address"] = geocoding_result["formatted_address"]
            validated_data["latitude"] = geocoding_result["latitude"]
            validated_data["longitude"] = geocoding_result["longitude"]

    return Task.objects.create(user=parent, **validated_data)


def update_task(*, task: Task, user, validated_data) -> Task:
    if task.user != user:
        raise exceptions.PermissionDenied("You can only edit your own tasks.")

    # Check if frontend provided geocoding data
    new_location = validated_data.get("location")
    has_frontend_geocoding = (
        validated_data.get("latitude") is not None and
        validated_data.get("longitude") is not None
    )

    # Only re-geocode if location changed and no frontend geocoding data
    if new_location and new_location != task.location and not has_frontend_geocoding:
        geocoding_result = geocode_address(new_location)
        if geocoding_result:
            validated_data["formatted_address"] = geocoding_result["formatted_address"]
            validated_data["latitude"] = geocoding_result["latitude"]
            validated_data["longitude"] = geocoding_result["longitude"]
        else:
            # Clear geocoding data if geocoding fails
            validated_data["formatted_address"] = None
            validated_data["latitude"] = None
            validated_data["longitude"] = None

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
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    if category:
        queryset = queryset.filter(category__id=category)
    if location:
        queryset = queryset.filter(location__icontains=location)
    if date_str:
        queryset = queryset.filter(start__date=date_str)
    if start_date:
        queryset = queryset.filter(start__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(start__date__lte=end_date)

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
    task.save(update_fields=["volunteer", "status"])
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
    task.save(update_fields=["volunteer", "status"])
    return task


def complete_task(*, task: Task, volunteer) -> Task:
    """Mark a task as completed by the assigned babysitter."""
    from notifications.services import notify_task_completed

    if task.volunteer != volunteer:
        raise exceptions.PermissionDenied("You can only complete tasks assigned to you.")

    if task.status == Task.COMPLETED:
        raise exceptions.ValidationError("Task is already completed.")

    if task.status != Task.CLAIMED:
        raise exceptions.ValidationError("Only claimed tasks can be marked as completed.")

    task.status = Task.COMPLETED
    task.save(update_fields=["status"])

    notify_task_completed(parent=task.user, task=task, volunteer=volunteer)

    return task


def tasks_for_parent(user, segment: str | None = None) -> QuerySet:
    qs = Task.objects.filter(user=user)
    if segment == "open":
        qs = qs.filter(status=Task.UNCLAIMED)
    elif segment == "assigned":
        qs = qs.filter(status=Task.CLAIMED)
    elif segment == "completed":
        qs = qs.filter(status=Task.COMPLETED)
    return qs.order_by('-start')


def tasks_for_volunteer(user, segment: str | None = None) -> QuerySet:
    qs = Task.objects.filter(volunteer=user)
    if segment == "upcoming":
        qs = qs.filter(start__gte=timezone.now()).exclude(
            status__in=[Task.COMPLETED, Task.CANCELLED]
        )
    elif segment == "active":
        qs = qs.filter(status=Task.CLAIMED)
    elif segment == "completed":
        qs = qs.filter(status=Task.COMPLETED)
    return qs


def approaching_deadline_tasks():
    now = timezone.now()
    window = now + timedelta(hours=24)
    return Task.objects.filter(start__range=(now, window), volunteer__isnull=False)


def get_statistics(query_params=None):
    """
    Get system statistics with optional filtering.
    
    Query params:
    - role: Filter users by role (parent, babysitter)
    - task_status: Filter tasks by status (unclaimed, claimed)
    - date_from: Filter tasks from this date (YYYY-MM-DD)
    - date_to: Filter tasks to this date (YYYY-MM-DD)
    """
    query_params = query_params or {}
    
    tasks_qs = Task.objects.all()
    users_qs = User.objects.all()
    
    task_status = query_params.get("task_status")
    if task_status:
        tasks_qs = tasks_qs.filter(status=task_status)
    
    date_from = query_params.get("date_from")
    date_to = query_params.get("date_to")
    if date_from:
        tasks_qs = tasks_qs.filter(start__gte=date_from)
    if date_to:
        tasks_qs = tasks_qs.filter(end__lte=date_to)
    
    tasks_per_category = (
        tasks_qs.values("category__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    tasks_per_month = (
        tasks_qs.annotate(month=TruncMonth("start"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    
    tasks_by_status = (
        tasks_qs.values("status")
        .annotate(count=Count("id"))
    )
    task_status_map = {entry["status"]: entry["count"] for entry in tasks_by_status}
    
    role_filter = query_params.get("role")
    if role_filter and role_filter in ["parent", "babysitter"]:
        users_qs = users_qs.filter(role=role_filter)
    
    role_counts = users_qs.values("role").annotate(count=Count("id"))
    admin_count = users_qs.filter(Q(is_staff=True) | Q(is_superuser=True)).count()

    non_admin_qs = users_qs.exclude(Q(is_staff=True) | Q(is_superuser=True))
    role_counts = role_counts.exclude(Q(is_staff=True) | Q(is_superuser=True))
    total_non_admin = non_admin_qs.count()
    active_non_admin = non_admin_qs.filter(is_active=True).count()

    role_map = {entry["role"]: entry["count"] for entry in role_counts}
    
    from applications.models import Application
    apps_qs = Application.objects.all()
    if date_from:
        apps_qs = apps_qs.filter(created_at__gte=date_from)
    if date_to:
        apps_qs = apps_qs.filter(created_at__lte=date_to)
    
    applications_by_status = (
        apps_qs.values("status")
        .annotate(count=Count("id"))
    )
    app_status_map = {entry["status"]: entry["count"] for entry in applications_by_status}
    
    reviews_qs = Review.objects.all()
    avg_rating = reviews_qs.aggregate(avg=Avg("rating"))["avg"] or 0
    total_reviews = reviews_qs.count()
    
    active_parents = User.objects.filter(
        role="parent",
        created_tasks__isnull=False
    ).distinct().count()
    
    active_babysitters = User.objects.filter(
        role="babysitter",
        task_applications__isnull=False
    ).distinct().count()

    return {
        "tasks_per_category": [
            {"category": entry["category__name"], "count": entry["count"]}
            for entry in tasks_per_category
        ],
        "tasks_per_month": [
            {"month": entry["month"].strftime("%Y-%m") if entry["month"] else None, "count": entry["count"]}
            for entry in tasks_per_month
        ],
        "tasks_by_status": {
            "unclaimed": task_status_map.get("unclaimed", 0),
            "claimed": task_status_map.get("claimed", 0),
            "total": tasks_qs.count(),
        },
        "user_totals": {
            "total": total_non_admin,
            "parents": role_map.get("parent", 0),
            "babysitters": role_map.get("babysitter", 0),
            "admins": admin_count,
            "active_total": active_non_admin,
            "active_parents": active_parents,
            "active_babysitters": active_babysitters,
        },
        "applications_by_status": {
            "pending": app_status_map.get("pending", 0),
            "accepted": app_status_map.get("accepted", 0),
            "rejected": app_status_map.get("rejected", 0),
            "total": apps_qs.count(),
        },
        "average_babysitter_rating": round(float(avg_rating), 2),
        "total_reviews": total_reviews,
    }
