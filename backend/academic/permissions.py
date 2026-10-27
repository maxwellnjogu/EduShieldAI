from rest_framework.permissions import BasePermission
from security.services import create_security_event


class IsLecturerOrAdmin(BasePermission):
    message = "Lecturer or administrator access is required."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) in ("lecturer", "admin")
        )


class IsStudentUser(BasePermission):
    message = "Student access is required."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "student"
        )


def log_unauthorized_access(request, reason, target_unit_id=None, target_student_id=None):
    """
    Log an unauthorized access attempt to the Mini SOC.
    Never logs passwords or authorization tokens.
    """
    metadata = {"reason": reason}
    if target_unit_id is not None:
        metadata["target_unit_id"] = str(target_unit_id)
    if target_student_id is not None:
        metadata["target_student_id"] = str(target_student_id)

    create_security_event(
        event_type="unauthorized_access",
        severity="HIGH",
        description=f"Unauthorized access denied: {reason}",
        user=request.user if request.user and request.user.is_authenticated else None,
        endpoint=request.path,
        request=request,
        metadata=metadata,
    )
