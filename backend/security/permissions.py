

from rest_framework.permissions import BasePermission


class IsEduShieldAdmin(BasePermission):
    message = "Administrator access is required."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "admin"
        )