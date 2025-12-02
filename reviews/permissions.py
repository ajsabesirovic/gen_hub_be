from rest_framework.permissions import BasePermission, SAFE_METHODS

from gen_hub_be.permissions import is_admin


class IsReviewOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if is_admin(request.user):
            return True
        return obj.senior == request.user
