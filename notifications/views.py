from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from gen_hub_be.permissions import is_admin
from .models import Notification
from .permissions import CanManageNotifications
from .serializers import NotificationSerializer
from .services import create_notification


@extend_schema(tags=["Notifications"])
class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, CanManageNotifications]

    def get_queryset(self):
        if is_admin(self.request.user):
            return Notification.objects.select_related("user")
        return Notification.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        notification = create_notification(
            user=self.request.user,
            type=serializer.validated_data.get("type", "custom"),
            title=serializer.validated_data.get("title", "Notification"),
            message=serializer.validated_data.get("message", ""),
        )
        serializer.instance = notification

    def _update_is_read(self, request, partial):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data={"is_read": request.data.get("is_read", True)}, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        return self._update_is_read(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update_is_read(request, partial=True)

    @extend_schema(tags=["Notifications"])
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
