from rest_framework import exceptions

from notifications.services import notify_new_review
from tasks.models import Task
from .models import Review


def create_review(*, parent, task: Task, rating: int, comment: str = "") -> Review:
    """
    Create a review for a completed task.

    Business rules:
    - Only parents can submit reviews
    - Can only review your own tasks
    - Task must have an assigned volunteer
    - Task must be completed
    - A task can only be rated once
    """
    if parent.role != "parent":
        raise exceptions.PermissionDenied("Only parents can submit reviews.")
    if task.user != parent:
        raise exceptions.PermissionDenied("You can only review your own tasks.")
    if not task.volunteer:
        raise exceptions.ValidationError("Cannot review a task without an assigned volunteer.")
    if task.status != Task.COMPLETED:
        raise exceptions.ValidationError("You can only review completed tasks.")
    if hasattr(task, "review"):
        raise exceptions.ValidationError("A review already exists for this task.")

    review = Review.objects.create(
        task=task,
        parent=parent,
        volunteer=task.volunteer,
        rating=rating,
        comment=comment,
    )

    _update_babysitter_rating(task.volunteer)

    notify_new_review(
        volunteer=task.volunteer,
        parent=parent,
        task=task,
        rating=rating,
    )

    return review


def update_review(*, review: Review, parent, data) -> Review:
    """
    Update an existing review.

    Business rules:
    - Only the parent who created the review can update it
    - Can only update within 24 hours of creation
    """
    if review.parent != parent:
        raise exceptions.PermissionDenied("You can only update your own reviews.")

    if not review.is_editable():
        raise exceptions.ValidationError(
            "Reviews can only be edited within 24 hours of creation."
        )

    old_rating = review.rating
    for attr, value in data.items():
        if attr in ['rating', 'comment']:
            setattr(review, attr, value)
    review.save()

    if 'rating' in data and data['rating'] != old_rating:
        _update_babysitter_rating(review.volunteer)

    return review


def delete_review(*, review: Review, user) -> None:
    """
    Delete a review.

    Business rules:
    - Only admins can delete reviews (for moderation)
    - Parents can only delete within 24 hours
    """
    from gen_hub_be.permissions import is_admin

    if is_admin(user):
        volunteer = review.volunteer
        review.delete()
        _update_babysitter_rating(volunteer)
        return

    if review.parent != user:
        raise exceptions.PermissionDenied("You can only delete your own reviews.")

    if not review.is_editable():
        raise exceptions.ValidationError(
            "Reviews can only be deleted within 24 hours of creation."
        )

    volunteer = review.volunteer
    review.delete()
    _update_babysitter_rating(volunteer)


def _update_babysitter_rating(volunteer) -> None:
    """Update the babysitter's average rating after a review change."""
    try:
        profile = volunteer.babysitter_profile
        profile.update_rating()
    except Exception:
        pass


def get_reviews_for_babysitter(babysitter_id: str):
    """Get all reviews for a specific babysitter."""
    return Review.objects.filter(volunteer__id=babysitter_id).select_related(
        'parent', 'task'
    ).order_by('-created_at')
