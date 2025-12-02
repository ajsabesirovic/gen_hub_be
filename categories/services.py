from rest_framework import exceptions

from .models import Category


def create_category(*, user, validated_data) -> Category:
    if not user.is_staff and not user.is_superuser:
        raise exceptions.PermissionDenied("Only administrators can create categories.")
    return Category.objects.create(**validated_data)


def update_category(*, category: Category, user, validated_data) -> Category:
    if not user.is_staff and not user.is_superuser:
        raise exceptions.PermissionDenied("Only administrators can update categories.")
    for attr, value in validated_data.items():
        setattr(category, attr, value)
    category.save()
    return category


def delete_category(*, category: Category, user) -> None:
    if not user.is_staff and not user.is_superuser:
        raise exceptions.PermissionDenied("Only administrators can delete categories.")
    category.delete()
