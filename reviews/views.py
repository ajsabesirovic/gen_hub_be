from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from gen_hub_be.permissions import is_admin
from .models import Review
from .permissions import IsReviewOwnerOrReadOnly
from .serializers import ReviewSerializer
from .services import create_review, update_review


@extend_schema(tags=["Reviews"])
class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsReviewOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = Review.objects.select_related("task", "senior", "volunteer")
        if is_admin(user):
            return qs
        if user.role == "senior":
            return qs.filter(senior=user)
        if user.role == "volunteer":
            return qs.filter(volunteer=user)
        return qs.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = create_review(
            senior=request.user,
            task=serializer.validated_data["task"],
            rating=serializer.validated_data["rating"],
            comment=serializer.validated_data.get("comment", ""),
        )
        output = self.get_serializer(review)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        review = update_review(review=instance, senior=request.user, data=serializer.validated_data)
        output = self.get_serializer(review)
        return Response(output.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)
