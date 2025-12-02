from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import Application
from .permissions import IsApplicationOwner
from .serializers import ApplicationSerializer
from .services import cancel_application


@extend_schema(tags=["Applications"])
class ApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, IsApplicationOwner]

    def get_queryset(self):
        user = self.request.user
        qs = Application.objects.select_related("task", "volunteer", "task__category")
        if user.is_staff or user.is_superuser:
            return qs
        if user.role == "senior":
            return qs.filter(task__user=user)
        if user.role == "volunteer":
            return qs.filter(volunteer=user)
        return qs.none()

    @extend_schema(tags=["Applications"])
    @action(detail=True, methods=["delete"], permission_classes=[IsAuthenticated, IsApplicationOwner])
    def cancel(self, request, pk=None):
        application = self.get_object()
        cancel_application(task=application.task, volunteer=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
