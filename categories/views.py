from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .models import Category
from .permissions import IsAdminOrReadOnly
from .serializers import CategorySerializer
from .services import create_category, delete_category, update_category


@extend_schema(tags=["Categories"])
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return Category.objects.all()
        return Category.objects.filter(is_active=True)

    def perform_create(self, serializer):
        category = create_category(user=self.request.user, validated_data=serializer.validated_data)
        serializer.instance = category

    def perform_update(self, serializer):
        category = update_category(
            category=self.get_object(),
            user=self.request.user,
            validated_data=serializer.validated_data,
        )
        serializer.instance = category

    def perform_destroy(self, instance):
        delete_category(category=instance, user=self.request.user)
