from rest_framework.permissions import BasePermission

from gen_hub_be.permissions import is_admin


class IsAvailabilityOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if is_admin(request.user):
            return True
        return obj.user == request.user

    def has_permission(self, request, view):
        return request.user.is_authenticated
