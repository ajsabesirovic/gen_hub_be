from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from applications.serializers import ApplicationSerializer, InvitationSerializer
from applications.models import Application, Invitation
from applications.services import (
    accept_application,
    cancel_application,
    list_task_applications,
    reject_application,
    submit_application,
    send_invitation,
    accept_invitation,
    decline_invitation,
    get_babysitter_invitations,
)
from .models import Task
from .permissions import IsAdminUser, IsParent, IsTaskOwner, IsVolunteer
from .serializers import TaskDetailSerializer, TaskSerializer
from . import services
from gen_hub_be.permissions import is_admin

User = get_user_model()


@extend_schema(tags=["Tasks"])
class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related("user", "volunteer", "category")
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in {"retrieve"}:
            return TaskDetailSerializer
        return super().get_serializer_class()

    def get_permissions(self):
        if is_admin(self.request.user):
            return [IsAuthenticated(), IsAdminUser()]

        if self.action in {"create", "update", "partial_update", "destroy"}:
            permission_classes = [IsAuthenticated, IsParent, IsTaskOwner]
        elif self.action in {"available", "volunteer_me", "apply", "cancel_application", "complete"}:
            permission_classes = [IsAuthenticated, IsVolunteer]
        elif self.action in {"accept", "reject", "parent_me"}:
            permission_classes = [IsAuthenticated, IsParent]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        if is_admin(self.request.user):
            if self.action == "list":
                queryset = services.filter_tasks(queryset, self.request.query_params)
            return queryset
        
        if self.action == "list":
            queryset = services.filter_tasks(queryset, self.request.query_params)
        return queryset

    def perform_create(self, serializer):
        task = services.create_task(parent=self.request.user, validated_data=serializer.validated_data)
        serializer.instance = task

    def perform_update(self, serializer):
        task = self.get_object()
        if is_admin(self.request.user):
            for attr, value in serializer.validated_data.items():
                setattr(task, attr, value)
            task.save()
            serializer.instance = task
        else:
            task = services.update_task(
                task=task, user=self.request.user, validated_data=serializer.validated_data
            )
            serializer.instance = task

    def perform_destroy(self, instance):
        if is_admin(self.request.user):
            instance.delete()
        else:
            services.delete_task(task=instance, user=self.request.user)

    @action(detail=False, methods=["get"], url_path="available", pagination_class=None)
    def available(self, request):
        queryset = services.get_available_tasks(request.user, request.query_params)
        serializer = TaskSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)


    @action(detail=False, methods=["get"], url_path="parent/me", pagination_class=None)
    def parent_me(self, request):
        segment = request.query_params.get("segment")
        queryset = services.tasks_for_parent(request.user, segment)
        serializer = TaskSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="volunteer/me", pagination_class=None)
    def volunteer_me(self, request):
        segment = request.query_params.get("segment")
        queryset = services.tasks_for_volunteer(request.user, segment)
        serializer = TaskSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={201: ApplicationSerializer},
        tags=["Tasks"],
    )
    @action(detail=True, methods=["post"], url_path="apply")
    def apply(self, request, pk=None):
        task = self.get_object()
        application = submit_application(task=task, volunteer=request.user)
        serializer = ApplicationSerializer(application, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="cancel-application")
    def cancel_application(self, request, pk=None):
        task = self.get_object()
        application = cancel_application(task=task, volunteer=request.user)
        serializer = ApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="applications")
    def applications(self, request, pk=None):
        task = self.get_object()
        qs = list_task_applications(task=task, user=request.user)
        serializer = ApplicationSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="my-application")
    def my_application(self, request, pk=None):
        """Get the current user's application for this task, if any."""
        task = self.get_object()
        try:
            application = Application.objects.get(task=task, volunteer=request.user)
            serializer = ApplicationSerializer(application, context={"request": request})
            return Response(serializer.data)
        except Application.DoesNotExist:
            return Response({"applied": False}, status=status.HTTP_200_OK)

    @extend_schema(
        request=None,
        responses={200: ApplicationSerializer},
        tags=["Tasks"],
    )
    @action(detail=True, methods=["post"], url_path="accept/(?P<volunteer_id>[^/.]+)")
    def accept(self, request, pk=None, volunteer_id=None):
        task = self.get_object()
        if is_admin(request.user):
            application = get_object_or_404(Application, task=task, volunteer__id=volunteer_id)
            if application.status == Application.ACCEPTED:
                from rest_framework import exceptions
                raise exceptions.ValidationError("Application already accepted.")
            application.status = Application.ACCEPTED
            application.save(update_fields=["status"])

            other_apps = Application.objects.filter(task=task).exclude(id=application.id)
            from notifications.services import create_notification
            for app in other_apps:
                if app.status != Application.REJECTED:
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
                title="Application accepted",
                message=f"You have been accepted for the task '{task.title}'.",
            )
        else:
            application = accept_application(task=task, parent=request.user, volunteer_id=volunteer_id)
        serializer = ApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={200: ApplicationSerializer},
        tags=["Tasks"],
    )
    @action(detail=True, methods=["post"], url_path="reject/(?P<volunteer_id>[^/.]+)")
    def reject(self, request, pk=None, volunteer_id=None):
        task = self.get_object()
        if is_admin(request.user):
            application = get_object_or_404(Application, task=task, volunteer__id=volunteer_id)
            if application.status == Application.REJECTED:
                from rest_framework import exceptions
                raise exceptions.ValidationError("Babysitter already rejected.")
            if application.status == Application.ACCEPTED:
                from rest_framework import exceptions
                raise exceptions.ValidationError("You cannot reject the babysitter that was already accepted.")
            application.status = Application.REJECTED
            application.save(update_fields=["status"])
            from notifications.services import create_notification
            create_notification(
                user=application.volunteer,
                type="application_rejected",
                title="Application update",
                message=f"Your application for '{task.title}' was not selected.",
            )
        else:
            application = reject_application(task=task, parent=request.user, volunteer_id=volunteer_id)
        serializer = ApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={200: TaskSerializer},
        tags=["Tasks"],
        description="Mark a task as completed (babysitter only)",
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """Mark a task as completed by the assigned babysitter."""
        task = self.get_object()
        task = services.complete_task(task=task, volunteer=request.user)
        serializer = TaskSerializer(task, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={201: InvitationSerializer},
        tags=["Tasks"],
        description="Invite a babysitter to a task (parent only)",
    )
    @action(detail=True, methods=["post"], url_path="invite/(?P<babysitter_id>[^/.]+)")
    def invite(self, request, pk=None, babysitter_id=None):
        """Invite a babysitter to a task."""
        task = self.get_object()
        message = request.data.get("message")
        invitation = send_invitation(
            task=task,
            parent=request.user,
            babysitter_id=babysitter_id,
            message=message,
        )
        serializer = InvitationSerializer(invitation, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={200: ApplicationSerializer(many=True)},
        tags=["Tasks"],
        description="Get babysitter's applications",
    )
    @action(detail=False, methods=["get"], url_path="applications/me")
    def applications_me(self, request):
        """Get current user's (babysitter) applications."""
        applications = Application.objects.filter(volunteer=request.user).select_related(
            "task", "task__user", "task__category"
        )
        serializer = ApplicationSerializer(applications, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        responses={200: InvitationSerializer(many=True)},
        tags=["Tasks"],
        description="Get babysitter's invitations",
    )
    @action(detail=False, methods=["get"], url_path="invitations/me")
    def invitations_me(self, request):
        """Get current user's (babysitter) invitations."""
        invitations = get_babysitter_invitations(babysitter=request.user)
        serializer = InvitationSerializer(invitations, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={200: InvitationSerializer},
        tags=["Tasks"],
        description="Accept an invitation (babysitter only)",
    )
    @action(detail=False, methods=["post"], url_path="invitations/(?P<invitation_id>[^/.]+)/accept")
    def accept_invite(self, request, invitation_id=None):
        """Accept an invitation."""
        invitation = accept_invitation(invitation_id=invitation_id, babysitter=request.user)
        serializer = InvitationSerializer(invitation, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={200: InvitationSerializer},
        tags=["Tasks"],
        description="Decline an invitation (babysitter only)",
    )
    @action(detail=False, methods=["post"], url_path="invitations/(?P<invitation_id>[^/.]+)/decline")
    def decline_invite(self, request, invitation_id=None):
        """Decline an invitation."""
        invitation = decline_invitation(invitation_id=invitation_id, babysitter=request.user)
        serializer = InvitationSerializer(invitation, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        description="Admin: List all tasks with advanced filtering",
        tags=["Admin"],
    )
    @action(detail=False, methods=["get"], url_path="admin/all", permission_classes=[IsAuthenticated, IsAdminUser])
    def admin_all(self, request):
        """Admin endpoint to view all tasks with advanced filtering"""
        queryset = Task.objects.select_related("user", "volunteer", "category").all()
        
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        user_role = request.query_params.get("user_role")
        if user_role == "parent":
            queryset = queryset.exclude(user__is_staff=True, user__is_superuser=True)
        elif user_role == "volunteer":
            queryset = queryset.exclude(volunteer__isnull=True)
        
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(start__gte=start_date)
        if end_date:
            queryset = queryset.filter(end__lte=end_date)

        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__id=category)

        queryset = services.filter_tasks(queryset, request.query_params)
        
        page = self.paginate_queryset(queryset)
        serializer = TaskSerializer(page or queryset, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


@extend_schema(tags=["Statistics"])
class StatisticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request):
        """Get system statistics with optional filtering"""
        data = services.get_statistics(request.query_params)
        return Response(data)
