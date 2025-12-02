from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from gen_hub_be.permissions import is_admin
from .models import UserAvailability
from .permissions import IsAvailabilityOwner
from .serializers import UserAvailabilitySerializer
from .services import create_availability, delete_availability, update_availability


@extend_schema(tags=["Availability"])
class UserAvailabilityViewSet(viewsets.ModelViewSet):
    serializer_class = UserAvailabilitySerializer
    permission_classes = [IsAuthenticated, IsAvailabilityOwner]

    def get_queryset(self):
        if is_admin(self.request.user):
            return UserAvailability.objects.select_related("user")
        return UserAvailability.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        availability = create_availability(user=self.request.user, validated_data=serializer.validated_data)
        serializer.instance = availability

    def perform_update(self, serializer):
        availability = update_availability(
            availability=self.get_object(),
            user=self.request.user,
            validated_data=serializer.validated_data,
        )
        serializer.instance = availability

    def perform_destroy(self, instance):
        delete_availability(availability=instance, user=self.request.user)
