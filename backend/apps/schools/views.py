from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.accounts.permissions import HasAdminPermission, is_staff_user

from .models import (
    Country,
    Programme,
    RequirementCategory,
    RequirementItem,
    School,
    SchoolRequirementSet,
)
from .serializers import (
    CountrySerializer,
    ProgrammeSerializer,
    RequirementCategorySerializer,
    RequirementItemSerializer,
    SchoolRequirementSetSerializer,
    SchoolSerializer,
    StaffSchoolSerializer,
)


class SchoolViewSet(ModelViewSet):
    """Schools. Students read; staff with can_manage_schools write."""

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_manage_schools"
    filterset_fields = ["country", "kind", "is_active", "is_partner"]
    search_fields = ["name", "city"]
    ordering_fields = ["name", "created_at"]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_serializer_class(self):
        # Commission terms are staff-only, so the serializer differs by audience.
        return StaffSchoolSerializer if is_staff_user(self.request.user) else SchoolSerializer

    def get_queryset(self):
        qs = School.objects.select_related("country").prefetch_related("programmes")
        if not is_staff_user(self.request.user):
            qs = qs.filter(is_active=True, archived_at__isnull=True)
        return qs.order_by("name")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["get"], url_path="requirements")
    def requirements(self, request, pk=None):
        """The live requirement set — what a student would be asked for today."""
        current = self.get_object().current_requirement_set
        if current is None:
            return Response(
                {"detail": "No published requirement set for this school yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SchoolRequirementSetSerializer(current).data)


class ProgrammeViewSet(ModelViewSet):
    serializer_class = ProgrammeSerializer
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_manage_schools"
    filterset_fields = ["school", "level", "is_active"]
    search_fields = ["name", "school__name"]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        return Programme.objects.select_related("school").order_by("school__name", "name")


class RequirementCategoryViewSet(ModelViewSet):
    serializer_class = RequirementCategorySerializer
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_manage_schools"
    queryset = RequirementCategory.objects.all()

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return super().get_permissions()


class CountryViewSet(ReadOnlyModelViewSet):
    serializer_class = CountrySerializer
    permission_classes = [IsAuthenticated]
    queryset = Country.objects.filter(is_active=True)


class RequirementSetViewSet(ModelViewSet):
    """Versioned requirement sets, with publish / clone / new-version (plan §7.2)."""

    serializer_class = SchoolRequirementSetSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_manage_schools"
    filterset_fields = ["school", "programme", "status", "is_template"]
    search_fields = ["name", "school__name"]

    def get_queryset(self):
        return (
            SchoolRequirementSet.objects.select_related("school", "programme")
            .prefetch_related("items__category")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.checklist_instances.exists():
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Students' checklists were generated from this version. Archive it instead of deleting."
            )
        instance.delete()

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        try:
            requirement_set = self.get_object()
            requirement_set.publish(user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(requirement_set).data)

    @action(detail=True, methods=["post"])
    def clone(self, request, pk=None):
        """Clone a template or an existing set onto a school (plan §4.1)."""
        source = self.get_object()
        school_id = request.data.get("school")
        programme_id = request.data.get("programme")
        school = School.objects.filter(pk=school_id).first() if school_id else None
        programme = Programme.objects.filter(pk=programme_id).first() if programme_id else None
        if school is None and programme is None:
            return Response(
                {"detail": "Provide a school or a programme to clone onto."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        clone = source.clone(
            school=school, programme=programme, name=request.data.get("name", ""), user=request.user
        )
        return Response(self.get_serializer(clone).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, pk=None):
        try:
            draft = self.get_object().create_new_version(
                user=request.user, change_note=request.data.get("change_note", "")
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(draft).data, status=status.HTTP_201_CREATED)


class RequirementItemViewSet(ModelViewSet):
    serializer_class = RequirementItemSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_manage_schools"
    filterset_fields = ["requirement_set", "category", "is_required", "is_active"]

    def get_queryset(self):
        return RequirementItem.objects.select_related("category", "requirement_set").order_by(
            "category__display_order", "display_order"
        )
