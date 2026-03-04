from rest_framework.permissions import BasePermission, SAFE_METHODS

from gen_hub_be.permissions import IsParent, IsVolunteer, IsAdminUser, is_admin


class IsTaskOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.user == request.user


__all__ = ["IsParent", "IsVolunteer", "IsAdminUser", "IsTaskOwner", "is_admin"]
