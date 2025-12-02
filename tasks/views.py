from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from applications.serializers import ApplicationSerializer
from applications.services import (
    accept_application,
    cancel_application,
    list_task_applications,
    reject_application,
    submit_application,
)
from .models import Task
from .permissions import IsAdminUser, IsSenior, IsTaskOwner, IsVolunteer
from .serializers import TaskDetailSerializer, TaskSerializer
from . import services

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
        if self.action in {"create", "update", "partial_update", "destroy"}:
            permission_classes = [IsAuthenticated, IsSenior, IsTaskOwner]
        elif self.action in {"available", "volunteer_me", "apply", "cancel_application"}:
            permission_classes = [IsAuthenticated, IsVolunteer]
        elif self.action in {"accept", "reject", "senior_me"}:
            permission_classes = [IsAuthenticated, IsSenior]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            queryset = services.filter_tasks(queryset, self.request.query_params)
        return queryset

    def perform_create(self, serializer):
        task = services.create_task(senior=self.request.user, validated_data=serializer.validated_data)
        serializer.instance = task

    def perform_update(self, serializer):
        task = services.update_task(
            task=self.get_object(), user=self.request.user, validated_data=serializer.validated_data
        )
        serializer.instance = task

    def perform_destroy(self, instance):
        services.delete_task(task=instance, user=self.request.user)

    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        queryset = services.get_available_tasks(request.user, request.query_params)
        page = self.paginate_queryset(queryset)
        serializer = TaskSerializer(page or queryset, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


    @action(detail=False, methods=["get"], url_path="senior/me")
    def senior_me(self, request):
        segment = request.query_params.get("segment")
        queryset = services.tasks_for_senior(request.user, segment)
        page = self.paginate_queryset(queryset)
        serializer = TaskSerializer(page or queryset, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="volunteer/me")
    def volunteer_me(self, request):
        segment = request.query_params.get("segment")
        queryset = services.tasks_for_volunteer(request.user, segment)
        page = self.paginate_queryset(queryset)
        serializer = TaskSerializer(page or queryset, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
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

    @action(detail=True, methods=["delete"], url_path="cancel-application")
    def cancel_application(self, request, pk=None):
        task = self.get_object()
        cancel_application(task=task, volunteer=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="applications")
    def applications(self, request, pk=None):
        task = self.get_object()
        qs = list_task_applications(task=task, user=request.user)
        serializer = ApplicationSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={200: ApplicationSerializer},
        tags=["Tasks"],
    )
    @action(detail=True, methods=["post"], url_path="accept/(?P<volunteer_id>[^/.]+)")
    def accept(self, request, pk=None, volunteer_id=None):
        task = self.get_object()
        application = accept_application(task=task, senior=request.user, volunteer_id=volunteer_id)
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
        application = reject_application(task=task, senior=request.user, volunteer_id=volunteer_id)
        serializer = ApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)


@extend_schema(tags=["Statistics"])
class StatisticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request):
        data = services.get_statistics()
        return Response(data)
