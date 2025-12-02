from rest_framework import exceptions

from tasks.models import Task
from .models import Review


def create_review(*, senior, task: Task, rating: int, comment: str = "") -> Review:
    if senior.role != "senior":
        raise exceptions.PermissionDenied("Only seniors can submit reviews.")
    if task.user != senior:
        raise exceptions.PermissionDenied("You can only review your own tasks.")
    if not task.volunteer:
        raise exceptions.ValidationError("Cannot review a task without an assigned volunteer.")
    if hasattr(task, "review"):
        raise exceptions.ValidationError("A review already exists for this task.")

    return Review.objects.create(
        task=task,
        senior=senior,
        volunteer=task.volunteer,
        rating=rating,
        comment=comment,
    )


def update_review(*, review: Review, senior, data) -> Review:
    if review.senior != senior:
        raise exceptions.PermissionDenied("You can only update your own reviews.")
    for attr, value in data.items():
        setattr(review, attr, value)
    review.save()
    return review
