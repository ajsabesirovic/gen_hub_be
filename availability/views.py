from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from gen_hub_be.permissions import is_admin
from .models import UserAvailability
from .permissions import IsAvailabilityOwner
from .serializers import UserAvailabilitySerializer, AggregatedAvailabilitySerializer
from .services import (
    create_availability,
    delete_availability,
    update_availability,
    get_aggregated_availability,
    save_aggregated_availability,
)


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


@extend_schema(tags=["Availability"])
class AggregatedAvailabilityView(APIView):
    """
    Aggregate endpoint for availability that matches frontend data structure.

    GET: Returns all availability in aggregated format (weekly schedule + monthly schedule)
    POST: Accepts aggregated format and saves as individual database rows

    This endpoint is only accessible to users with role='babysitter'.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: AggregatedAvailabilitySerializer},
        description="Get aggregated availability for the current user"
    )
    def get(self, request):
        """Get all availability entries in aggregated format."""
        if request.user.role != 'babysitter':
            return Response(
                {'detail': 'Only babysitters can access availability.'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = get_aggregated_availability(request.user)
        return Response(data)

    @extend_schema(
        request=AggregatedAvailabilitySerializer,
        responses={200: dict},
        description="Save aggregated availability data"
    )
    def post(self, request):
        """Save availability from aggregated format."""
        if request.user.role != 'babysitter':
            return Response(
                {'detail': 'Only babysitters can manage availability.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = AggregatedAvailabilitySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = save_aggregated_availability(request.user, serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)
