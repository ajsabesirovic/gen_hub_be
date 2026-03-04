from rest_framework.permissions import BasePermission

from gen_hub_be.permissions import is_admin


class IsApplicationOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if is_admin(request.user):
            return True
        if request.user.role == "parent":
            return obj.task.user == request.user
        if request.user.role == "babysitter":
            return obj.volunteer == request.user
        return False
