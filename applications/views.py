from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.db.models import Q

from .models import Application
from .permissions import IsApplicationOwner
from .serializers import ApplicationSerializer
from .services import cancel_application
from gen_hub_be.permissions import IsAdminUser


@extend_schema(tags=["Applications"])
class ApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, IsApplicationOwner]

    def get_queryset(self):
        user = self.request.user
        qs = Application.objects.select_related("task", "volunteer", "task__category")
        if user.is_staff or user.is_superuser:
            return qs
        if user.role == "parent":
            return qs.filter(task__user=user)
        if user.role == "babysitter":
            return qs.filter(volunteer=user)
        return qs.none()

    @extend_schema(tags=["Applications"])
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsApplicationOwner])
    def cancel(self, request, pk=None):
        application = self.get_object()
        cancelled_application = cancel_application(task=application.task, volunteer=request.user)
        serializer = ApplicationSerializer(cancelled_application, context={"request": request})
        return Response(serializer.data)
    
    @extend_schema(
        description="Admin: List all applications with advanced filtering",
        tags=["Admin"],
    )
    @action(detail=False, methods=["get"], url_path="admin/all", permission_classes=[IsAuthenticated, IsAdminUser])
    def admin_all(self, request):
        """Admin endpoint to view all applications with advanced filtering"""
        queryset = Application.objects.select_related("task", "volunteer", "task__category", "task__user").all()
        
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        task_status = request.query_params.get("task_status")
        if task_status:
            queryset = queryset.filter(task__status=task_status)
        
        created_after = request.query_params.get("created_after")
        created_before = request.query_params.get("created_before")
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(task__title__icontains=search) |
                Q(volunteer__name__icontains=search) |
                Q(volunteer__email__icontains=search)
            )
        
        page = self.paginate_queryset(queryset.order_by('-created_at'))
        serializer = ApplicationSerializer(page or queryset, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
