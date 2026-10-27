

from rest_framework.permissions import BasePermission


class IsEduShieldAdmin(BasePermission):
    """
    Allow access only to authenticated users
    whose EduShield role is admin.
    """

    message = "Administrator access is required."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "admin"
        )
