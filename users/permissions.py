from rest_framework import permissions


class IsParentUser(permissions.BasePermission):
    """
    Permission class that allows access only to users with role='parent'.
    Admins are explicitly denied access.
    """
    
    message = "Only parent users can access this resource."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_staff or request.user.is_superuser:
            return False
        
        return request.user.role == 'parent'


class IsVolunteerUser(permissions.BasePermission):
    """
    Permission class that allows access only to users with role='volunteer'.
    Admins are explicitly denied access.

    DEPRECATED: Use IsBabysitterUser instead. This class checks for 'volunteer' role
    which doesn't exist in the current role choices.
    """

    message = "Only volunteer users can access this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return False

        return request.user.role == 'volunteer'


class IsBabysitterUser(permissions.BasePermission):
    """
    Permission class that allows access only to users with role='babysitter'.
    Admins are explicitly denied access.
    """

    message = "Only babysitter users can access this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return False

        return request.user.role == 'babysitter'


class IsProfileOwner(permissions.BasePermission):
    """
    Permission class that ensures users can only access their own profile.
    """
    
    message = "You can only access your own profile."
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsNotAdmin(permissions.BasePermission):
    """
    Permission class that denies access to admin users.
    Used to prevent admins from accessing domain-specific resources.
    """
    
    message = "Admin users cannot access this resource."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return not (request.user.is_staff or request.user.is_superuser)

