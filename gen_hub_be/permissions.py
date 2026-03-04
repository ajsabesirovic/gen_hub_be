from rest_framework.permissions import BasePermission


def is_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


class IsParent(BasePermission):
    message = "Only parents can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "parent")


class IsVolunteer(BasePermission):
    message = "Only babysitters can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == "babysitter"
        )


class IsAdminUser(BasePermission):
    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        return is_admin(request.user)
