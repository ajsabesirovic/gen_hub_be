from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import exceptions

from availability.services import is_user_available_for_task
from notifications.services import create_notification
from tasks.models import Task
from .models import Application, Invitation

User = get_user_model()


def submit_application(*, task: Task, volunteer: User) -> Application:
    if volunteer.role != "babysitter":
        raise exceptions.PermissionDenied("Only babysitters can apply to tasks.")
    if task.user == volunteer:
        raise exceptions.ValidationError("You cannot apply to your own task.")
    if task.status == Task.CLAIMED:
        raise exceptions.ValidationError("Task already claimed.")
    if task.applications.filter(volunteer=volunteer).exists():
        raise exceptions.ValidationError("You have already applied to this task.")

    application = Application.objects.create(task=task, volunteer=volunteer)

    volunteer_name = volunteer.name or volunteer.email
    create_notification(
        user=task.user,
        type="new_application",
        title="New application",
        message=f"{volunteer_name} applied for your task '{task.title}'.",
    )

    return application


def cancel_application(*, task: Task, volunteer: User) -> Application:
    application = get_object_or_404(Application, task=task, volunteer=volunteer)
    if application.status not in [Application.PENDING, Application.ACCEPTED]:
        raise exceptions.ValidationError("Only pending or accepted applications can be cancelled.")

    if application.status == Application.ACCEPTED:
        task.volunteer = None
        task.status = Task.UNCLAIMED
        task.save(update_fields=["volunteer", "status"])

        volunteer_name = volunteer.name or volunteer.email
        create_notification(
            user=task.user,
            type="application_cancelled",
            title="Babysitter cancelled",
            message=f"{volunteer_name} has cancelled their accepted application for '{task.title}'.",
        )

    application.status = Application.CANCELLED
    application.save(update_fields=["status"])
    return application


def accept_application(*, task: Task, parent: User, volunteer_id: str) -> Application:
    if task.user != parent:
        raise exceptions.PermissionDenied("You cannot manage applications for this task.")
    application = get_object_or_404(Application, task=task, volunteer__id=volunteer_id)

    if application.status == Application.ACCEPTED:
        raise exceptions.ValidationError("Babysitter already accepted.")

    existing_accepted = task.applications.filter(status=Application.ACCEPTED).exclude(id=application.id).first()
    if existing_accepted:
        raise exceptions.ValidationError("Another babysitter is already accepted for this task.")

    application.status = Application.ACCEPTED
    application.save(update_fields=["status"])

    rejected_apps = Application.objects.filter(task=task).exclude(id=application.id)
    for app in rejected_apps:
        app.status = Application.REJECTED
        app.save(update_fields=["status"])
        create_notification(
            user=app.volunteer,
            type="application_rejected",
            title="Application update",
            message=f"Your application for '{task.title}' was not selected.",
        )

    task.volunteer = application.volunteer
    task.status = Task.CLAIMED
    task.save(update_fields=["volunteer", "status"])

    create_notification(
        user=application.volunteer,
        type="application_accepted",
        title="Application accepted!",
        message=f"You have been accepted for the task '{task.title}'.",
    )

    return application


def reject_application(*, task: Task, parent: User, volunteer_id: str) -> Application:
    if task.user != parent:
        raise exceptions.PermissionDenied("You cannot manage applications for this task.")
    application = get_object_or_404(Application, task=task, volunteer__id=volunteer_id)

    if application.status == Application.REJECTED:
        raise exceptions.ValidationError("Babysitter already rejected.")
    if application.status == Application.ACCEPTED:
        raise exceptions.ValidationError("You cannot reject the babysitter that was already accepted.")

    application.status = Application.REJECTED
    application.save(update_fields=["status"])

    create_notification(
        user=application.volunteer,
        type="application_rejected",
        title="Application update",
        message=f"Your application for '{task.title}' was not selected.",
    )

    return application


def list_task_applications(*, task: Task, user: User):
    if task.user != user and user.role != "babysitter":
        raise exceptions.PermissionDenied("You cannot view these applications.")
    if user.role == "babysitter":
        return task.applications.filter(volunteer=user)
    return task.applications.select_related("volunteer")


def send_invitation(*, task: Task, parent: User, babysitter_id: str, message: str = None) -> Invitation:
    """Send an invitation from a parent to a babysitter for a specific task."""
    if task.user != parent:
        raise exceptions.PermissionDenied("You can only send invitations for your own tasks.")

    if task.status != Task.UNCLAIMED:
        raise exceptions.ValidationError("You can only invite babysitters to unclaimed tasks.")

    babysitter = get_object_or_404(User, id=babysitter_id)

    if babysitter.role != "babysitter":
        raise exceptions.ValidationError("You can only invite babysitters.")

    existing_invitation = Invitation.objects.filter(task=task, babysitter=babysitter).first()
    if existing_invitation:
        if existing_invitation.status == Invitation.PENDING:
            raise exceptions.ValidationError("An invitation has already been sent to this babysitter.")
        elif existing_invitation.status == Invitation.DECLINED:
            raise exceptions.ValidationError("This babysitter has already declined an invitation for this task.")
        existing_invitation.delete()

    invitation = Invitation.objects.create(
        task=task,
        babysitter=babysitter,
        message=message,
    )

    parent_name = parent.name or parent.email
    create_notification(
        user=babysitter,
        type="task_invitation",
        title="New task invitation",
        message=f"{parent_name} has invited you to their task '{task.title}'.",
    )

    return invitation


def accept_invitation(*, invitation_id: str, babysitter: User) -> Invitation:
    """Accept an invitation (babysitter only)."""
    invitation = get_object_or_404(Invitation, id=invitation_id)

    if invitation.babysitter != babysitter:
        raise exceptions.PermissionDenied("You cannot accept this invitation.")

    if invitation.status != Invitation.PENDING:
        raise exceptions.ValidationError(f"Invitation is already {invitation.status}.")

    task = invitation.task

    if task.status != Task.UNCLAIMED:
        raise exceptions.ValidationError("This task is no longer available.")

    invitation.status = Invitation.ACCEPTED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at"])

    task.volunteer = babysitter
    task.status = Task.CLAIMED
    task.save(update_fields=["volunteer", "status"])

    other_invitations = Invitation.objects.filter(task=task, status=Invitation.PENDING).exclude(id=invitation.id)
    for inv in other_invitations:
        inv.status = Invitation.EXPIRED
        inv.save(update_fields=["status"])
        create_notification(
            user=inv.babysitter,
            type="invitation_expired",
            title="Invitation expired",
            message=f"The invitation for '{task.title}' is no longer available.",
        )

    pending_applications = Application.objects.filter(task=task, status=Application.PENDING)
    for app in pending_applications:
        app.status = Application.REJECTED
        app.save(update_fields=["status"])
        create_notification(
            user=app.volunteer,
            type="application_rejected",
            title="Application update",
            message=f"Your application for '{task.title}' was not selected.",
        )

    babysitter_name = babysitter.name or babysitter.email
    create_notification(
        user=task.user,
        type="invitation_accepted",
        title="Invitation accepted!",
        message=f"{babysitter_name} has accepted your invitation for '{task.title}'.",
    )

    return invitation


def decline_invitation(*, invitation_id: str, babysitter: User) -> Invitation:
    """Decline an invitation (babysitter only)."""
    invitation = get_object_or_404(Invitation, id=invitation_id)

    if invitation.babysitter != babysitter:
        raise exceptions.PermissionDenied("You cannot decline this invitation.")

    if invitation.status != Invitation.PENDING:
        raise exceptions.ValidationError(f"Invitation is already {invitation.status}.")

    invitation.status = Invitation.DECLINED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at"])

    babysitter_name = babysitter.name or babysitter.email
    create_notification(
        user=invitation.task.user,
        type="invitation_declined",
        title="Invitation declined",
        message=f"{babysitter_name} has declined your invitation for '{invitation.task.title}'. Consider reviewing other applicants.",
    )

    return invitation


def expire_old_invitations(*, hours: int = 24) -> int:
    """
    Expire invitations that have been pending for more than the specified hours.
    Returns the number of expired invitations.
    """
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=hours)
    pending_invitations = Invitation.objects.filter(
        status=Invitation.PENDING,
        created_at__lt=cutoff,
    )

    count = 0
    for invitation in pending_invitations:
        invitation.status = Invitation.EXPIRED
        invitation.save(update_fields=["status"])

        babysitter_name = invitation.babysitter.name or invitation.babysitter.email
        create_notification(
            user=invitation.task.user,
            type="invitation_expired",
            title="Invitation expired",
            message=f"{babysitter_name} hasn't responded to your invitation for '{invitation.task.title}'. Consider reviewing other applicants.",
        )
        count += 1

    return count


def get_babysitter_invitations(*, babysitter: User):
    """Get all invitations for a babysitter."""
    return Invitation.objects.filter(babysitter=babysitter).select_related("task", "task__user", "task__category")
