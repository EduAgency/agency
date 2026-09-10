from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import HasAdminPermission

from .models import FormDefinition, FormSubmission
from .serializers import (
    FormDefinitionSerializer,
    FormSubmissionSerializer,
    PublicFormSerializer,
    SubmitFormSerializer,
)


class LiveFormView(APIView):
    """Fetch the currently published version of a form by slug.

    The audience check runs here, server-side, on every request — hiding a form
    in the UI is not a permission (plan §3.4).
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: PublicFormSerializer, 404: OpenApiResponse(description="Not found, or not visible to you.")})
    def get(self, request, slug: str):
        form = FormDefinition.live(slug)
        if form is None:
            return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
        if not form.is_visible_to(request.user):
            # 404, not 403: an admin-only form should not even confirm it exists.
            return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PublicFormSerializer(form).data)


class SubmitFormView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=SubmitFormSerializer, responses={201: FormSubmissionSerializer})
    @transaction.atomic
    def post(self, request, slug: str):
        form = FormDefinition.live(slug)
        if form is None or not form.is_visible_to(request.user):
            return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SubmitFormSerializer(data=request.data, context={"form": form, "request": request})
        serializer.is_valid(raise_exception=True)

        student = getattr(request.user, "student_profile", None)
        existing = None
        if not form.allow_multiple_submissions and student:
            existing = FormSubmission.objects.filter(
                form_slug=form.slug, student=student
            ).order_by("-created_at").first()
            # Only a draft may be overwritten; a completed submission is history.
            if existing and existing.status != FormSubmission.Status.DRAFT:
                if serializer.validated_data["is_draft"]:
                    return Response(
                        {"detail": "You have already submitted this form."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                existing.status = FormSubmission.Status.SUPERSEDED
                existing.save(update_fields=["status", "updated_at"])
                existing = None

        is_draft = serializer.validated_data["is_draft"]
        submission = existing or FormSubmission(
            form_definition=form, form_slug=form.slug, submitted_by=request.user, student=student
        )
        # A draft that was started against an older version keeps answering the
        # version it was started on until it is submitted.
        submission.data = serializer.validated_data["cleaned"]
        submission.status = FormSubmission.Status.DRAFT if is_draft else FormSubmission.Status.SUBMITTED
        submission.submitted_at = None if is_draft else timezone.now()
        submission.save()

        if not is_draft:
            _apply_side_effects(form, submission, request.user)

        return Response(FormSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


def _apply_side_effects(form: FormDefinition, submission: FormSubmission, user) -> None:
    """What a submission *means* downstream, decided by the form's purpose (§3.5)."""
    from apps.accounts.models import StudentProfile

    if form.purpose == FormDefinition.Purpose.STUDENT_INTAKE and submission.student_id:
        student = submission.student
        data = submission.data
        for source, target in (
            ("date_of_birth", "date_of_birth"),
            ("state_of_residence", "state_of_residence"),
            ("whatsapp", "whatsapp"),
            ("nationality", "nationality"),
        ):
            if value := data.get(source):
                setattr(student, target, value)
        student.save()
        student.advance_stage(StudentProfile.Stage.PROFILE_COMPLETE)


class MySubmissionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: FormSubmissionSerializer(many=True)})
    def get(self, request):
        student = getattr(request.user, "student_profile", None)
        if student is None:
            return Response([])
        submissions = FormSubmission.objects.filter(student=student).select_related("form_definition")
        if slug := request.query_params.get("form_slug"):
            submissions = submissions.filter(form_slug=slug)
        return Response(FormSubmissionSerializer(submissions, many=True).data)


class AdminFormViewSet(ModelViewSet):
    """The form builder's backing API (plan §7.3)."""

    serializer_class = FormDefinitionSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_build_forms"
    read_admin_permission = "can_build_forms"
    filterset_fields = ["status", "audience", "purpose", "slug"]
    search_fields = ["title", "slug"]
    ordering_fields = ["created_at", "slug", "version"]

    def get_queryset(self):
        return FormDefinition.objects.all().order_by("slug", "-version")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        # A form version with submissions is archived, never deleted — the
        # answers would lose their meaning without it.
        if instance.has_submissions:
            raise PermissionDenied(
                "This version has submissions and cannot be deleted. Archive it instead."
            )
        instance.delete()

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        form = self.get_object()
        try:
            form.publish(user=request.user)
        except (DjangoValidationError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(form).data)

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

    @action(detail=False, methods=["post"], url_path="validate-schema")
    def validate_schema_endpoint(self, request):
        """Let the builder UI check a schema before saving it."""
        from .schema import SchemaError, validate_schema

        try:
            validate_schema(request.data.get("schema", {}))
        except SchemaError as exc:
            return Response({"valid": False, "errors": str(exc).split("; ")})
        return Response({"valid": True, "errors": []})


class AdminSubmissionViewSet(ModelViewSet):
    serializer_class = FormSubmissionSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_manage_students"
    filterset_fields = ["form_slug", "status", "student", "school"]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return FormSubmission.objects.select_related("form_definition", "student__user", "school")
