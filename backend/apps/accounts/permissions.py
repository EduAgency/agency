"""DRF permissions.

Every rule here is enforced server-side. Hiding a button in the Next.js UI is a
usability choice, never a security boundary (plan §3.4).
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import User


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_student)


class IsAgencyStaff(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_agency_staff)


class HasPlatformAccess(BasePermission):
    """Gate the paid area of the student dashboard.

    Reads the flag set by the payment webhook — see plan §5.2. A student mid-payment
    gets 403 with a machine-readable code the frontend renders as 'processing'.
    """

    message = "Your platform access is not active yet."
    code = "access_fee_required"

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_agency_staff:
            return True
        profile = getattr(user, "student_profile", None)
        return bool(profile and profile.has_platform_access)


class HasAdminPermission(BasePermission):
    """Checks a named AdminProfile flag, e.g.::

        class SchoolViewSet(ModelViewSet):
            permission_classes = [HasAdminPermission]
            required_admin_permission = "can_manage_schools"

    Safe methods fall back to ``read_admin_permission`` when set, so a reviewer
    can read school data without being able to edit it.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_agency_staff):
            return False
        if user.role == User.Role.SUPERADMIN:
            return True
        profile = getattr(user, "admin_profile", None)
        if profile is None:
            return False
        required = getattr(view, "required_admin_permission", None)
        if request.method in SAFE_METHODS:
            required = getattr(view, "read_admin_permission", required)
        if required is None:
            return True
        return profile.has(required)


class IsOwnerOrStaff(BasePermission):
    """Object-level: students only ever touch their own records."""

    owner_field = "student__user"

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_agency_staff:
            return True
        field = getattr(view, "owner_field", self.owner_field)
        target = obj
        for part in field.split("__"):
            target = getattr(target, part, None)
            if target is None:
                return False
        return target == user
