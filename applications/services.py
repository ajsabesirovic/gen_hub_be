from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import exceptions

from availability.services import is_user_available_for_task
from tasks.models import Task
from .models import Application

User = get_user_model()


def submit_application(*, task: Task, volunteer: User) -> Application:
    if volunteer.role != "volunteer":
        raise exceptions.PermissionDenied("Only volunteers can apply to tasks.")
    if task.user == volunteer:
        raise exceptions.ValidationError("You cannot apply to your own task.")
    if task.status == Task.CLAIMED:
        raise exceptions.ValidationError("Task already claimed.")
    if task.applications.filter(volunteer=volunteer).exists():
        raise exceptions.ValidationError("You have already applied to this task.")
    # if not is_user_available_for_task(volunteer, task):
    #     raise exceptions.ValidationError("You are not available for the requested time.")

    return Application.objects.create(task=task, volunteer=volunteer)


def cancel_application(*, task: Task, volunteer: User) -> None:
    application = get_object_or_404(Application, task=task, volunteer=volunteer)
    if application.status != Application.PENDING:
        raise exceptions.ValidationError("Only pending applications can be cancelled.")
    application.delete()


def accept_application(*, task: Task, senior: User, volunteer_id: str) -> Application:
    if task.user != senior:
        raise exceptions.PermissionDenied("You cannot manage applications for this task.")
    application = get_object_or_404(Application, task=task, volunteer__id=volunteer_id)
    
    if application.status == Application.ACCEPTED:
        raise exceptions.ValidationError("Volunteer already accepted.") 
    
    existing_accepted = task.applications.filter(status=Application.ACCEPTED).exclude(id=application.id).first()
    if existing_accepted:
        raise exceptions.ValidationError("Another volunteer is already accepted for this task.")
    
    application.status = Application.ACCEPTED
    application.save(update_fields=["status"])
    rejected_apps = Application.objects.filter(task=task).exclude(id=application.id)
    for app in rejected_apps:
        app.status = Application.REJECTED
        app.save(update_fields=["status"])

    task.volunteer = application.volunteer
    task.status = Task.CLAIMED
    task.save(update_fields=["volunteer", "status", "updated_at"])
    return application


def reject_application(*, task: Task, senior: User, volunteer_id: str) -> Application:
    if task.user != senior:
        raise exceptions.PermissionDenied("You cannot manage applications for this task.")
    application = get_object_or_404(Application, task=task, volunteer__id=volunteer_id)
    
    if application.status == Application.REJECTED:
        raise exceptions.ValidationError("Volunteer already rejected.")
    if application.status == Application.ACCEPTED:
        raise exceptions.ValidationError("You cannot reject the volunteer that was already accepted.")
    
    application.status = Application.REJECTED
    application.save(update_fields=["status"])
    return application


def list_task_applications(*, task: Task, user: User):
    if task.user != user and user.role != "volunteer":
        raise exceptions.PermissionDenied("You cannot view these applications.")
    if user.role == "volunteer":
        return task.applications.filter(volunteer=user)
    return task.applications.select_related("volunteer")
