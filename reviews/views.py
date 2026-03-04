from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from gen_hub_be.permissions import is_admin
from .models import Review
from .permissions import IsReviewOwnerOrReadOnly
from .serializers import ReviewSerializer
from .services import create_review, update_review, delete_review, get_reviews_for_babysitter


@extend_schema(tags=["Reviews"])
class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsReviewOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = Review.objects.select_related("task", "parent", "volunteer")
        if is_admin(user):
            return qs
        if user.role == "parent":
            return qs.filter(parent=user)
        if user.role == "babysitter":
            return qs.filter(volunteer=user)
        return qs.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = create_review(
            parent=request.user,
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
        review = update_review(review=instance, parent=request.user, data=serializer.validated_data)
        output = self.get_serializer(review)
        return Response(output.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_review(review=instance, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Get all reviews for a specific babysitter",
        tags=["Reviews"],
    )
    @action(detail=False, methods=["get"], url_path="babysitter/(?P<babysitter_id>[^/.]+)", pagination_class=None)
    def babysitter_reviews(self, request, babysitter_id=None):
        """Get all reviews for a specific babysitter.

        This endpoint bypasses the default queryset filtering to allow
        any authenticated user to view reviews for any babysitter.
        Returns unpaginated list of all reviews for the babysitter.
        """
        reviews = get_reviews_for_babysitter(babysitter_id)
        serializer = self.get_serializer(reviews, many=True)
        return Response(serializer.data)

    @extend_schema(
        description="Check if the current user can review a specific task",
        tags=["Reviews"],
    )
    @action(detail=False, methods=["get"], url_path="can-review/(?P<task_id>[^/.]+)")
    def can_review(self, request, task_id=None):
        """Check if the current user can review a specific task."""
        from tasks.models import Task

        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response({"can_review": False, "reason": "Task not found"})

        user = request.user

        if user.role != "parent":
            return Response({"can_review": False, "reason": "Only parents can review tasks"})

        if task.user != user:
            return Response({"can_review": False, "reason": "You can only review your own tasks"})

        if task.status != Task.COMPLETED:
            return Response({"can_review": False, "reason": "Task must be completed first"})

        if hasattr(task, "review"):
            return Response({
                "can_review": False,
                "reason": "Task already reviewed",
                "review_id": str(task.review.id),
                "is_editable": task.review.is_editable(),
            })

        return Response({
            "can_review": True,
            "volunteer_id": str(task.volunteer.id) if task.volunteer else None,
            "volunteer_name": task.volunteer.name if task.volunteer else None,
        })
