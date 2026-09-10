from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.accounts.permissions import HasAdminPermission, HasPlatformAccess, is_staff_user
from apps.core import audit

from .models import (
    Application,
    ChecklistItemInstance,
    DocumentUpload,
    StudentDocument,
)
from .serializers import (
    ApplicationSerializer,
    ChecklistItemSerializer,
    ChecklistSerializer,
    ReviewItemSerializer,
    StaffApplicationSerializer,
    StudentDocumentSerializer,
    UploadDocumentSerializer,
)
from .services import generate_checklist, preview_resync, resync_checklist


class ApplicationViewSet(ModelViewSet):
    """A student's applications. Checklist generation happens on create."""

    permission_classes = [IsAuthenticated, HasPlatformAccess]
    filterset_fields = ["status", "school", "intake"]
    ordering_fields = ["created_at", "target_submission_date"]

    def get_serializer_class(self):
        return StaffApplicationSerializer if is_staff_user(self.request.user) else ApplicationSerializer

    def get_queryset(self):
        qs = (
            Application.objects.select_related("school", "programme", "student__user", "checklist")
            .filter(archived_at__isnull=True)
            .order_by("-created_at")
        )
        user = self.request.user
        if is_staff_user(user):
            return qs
        if not user.is_authenticated:
            return qs.none()
        # A student sees only their own applications — enforced in the queryset,
        # so no object-level check can be forgotten on a new action.
        return qs.filter(student__user=user)

    @transaction.atomic
    def perform_create(self, serializer):
        """Create the application and snapshot its checklist in one transaction.

        ``student`` is read-only on the serializer so a student can never post
        an application onto someone else's account; staff name the student
        explicitly in the request body instead.
        """
        from rest_framework.exceptions import ValidationError as DRFValidationError

        from apps.accounts.models import StudentProfile

        user = self.request.user
        if is_staff_user(user):
            student_id = self.request.data.get("student")
            student = StudentProfile.objects.filter(pk=student_id).first() if student_id else None
            if student is None:
                raise DRFValidationError({"student": ["Name the student this application belongs to."]})
        else:
            student = user.student_profile

        application = serializer.save(student=student)
        try:
            generate_checklist(application, user=user)
        except DjangoValidationError:
            # A school with no published requirement set yet is a real state:
            # the application exists and staff generate the checklist later.
            pass

    @action(detail=True, methods=["get"])
    def checklist(self, request, pk=None):
        application = self.get_object()
        checklist = getattr(application, "checklist", None)
        if checklist is None:
            return Response(
                {"detail": "No checklist has been generated for this application yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ChecklistSerializer(checklist).data)

    @action(detail=True, methods=["post"], url_path="generate-checklist",
            permission_classes=[HasAdminPermission])
    def generate(self, request, pk=None):
        try:
            checklist = generate_checklist(self.get_object(), user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ChecklistSerializer(checklist).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="resync-checklist",
            permission_classes=[HasAdminPermission])
    def resync(self, request, pk=None):
        """GET previews the change; POST applies it.

        Re-sync is never automatic (plan §4.3) — staff see exactly what would
        change before a student's checklist moves.
        """
        checklist = getattr(self.get_object(), "checklist", None)
        if checklist is None:
            return Response({"detail": "No checklist to re-sync."}, status=status.HTTP_404_NOT_FOUND)
        try:
            if request.method == "GET":
                return Response(preview_resync(checklist).as_dict())
            report = resync_checklist(
                checklist,
                user=request.user,
                remove_obsolete=bool(request.data.get("remove_obsolete", False)),
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(report.as_dict())

    @action(detail=True, methods=["post"], url_path="status", permission_classes=[HasAdminPermission])
    def set_status(self, request, pk=None):
        application = self.get_object()
        new_status = request.data.get("status")
        if new_status not in Application.Status.values:
            return Response({"status": ["Unknown status."]}, status=status.HTTP_400_BAD_REQUEST)

        application.set_status(new_status, user=request.user, note=request.data.get("note", ""))

        from apps.notifications.services import notify_application_status

        notify_application_status(application, request.data.get("note", ""))

        # Milestone-triggered referral rewards (plan §6.1).
        if new_status in {Application.Status.OFFER, Application.Status.ENROLLED}:
            from apps.referrals.models import ReferralEvent
            from apps.referrals.services import record_milestone

            record_milestone(
                application,
                ReferralEvent.Type.OFFER
                if new_status == Application.Status.OFFER
                else ReferralEvent.Type.ENROLLED,
            )
        return Response(self.get_serializer(application).data)


class ChecklistItemViewSet(ReadOnlyModelViewSet):
    """Checklist items, plus the upload and review actions."""

    serializer_class = ChecklistItemSerializer
    permission_classes = [IsAuthenticated, HasPlatformAccess]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "category_slug", "is_required", "priority"]
    ordering_fields = ["updated_at", "due_date", "category_order"]

    def get_queryset(self):
        qs = ChecklistItemInstance.objects.filter(is_active=True).select_related(
            "checklist__application__school",
            "checklist__application__student__user",
            "document__current_upload",
        )
        user = self.request.user
        if not is_staff_user(user):
            if not user.is_authenticated:
                return qs.none()
            qs = qs.filter(checklist__application__student__user=user)
        if application_id := self.request.query_params.get("application"):
            qs = qs.filter(checklist__application_id=application_id)
        return qs.order_by("category_order", "display_order")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def upload(self, request, pk=None):
        """Attach a document to a checklist item.

        A new upload always becomes a new version of the vault document — the
        previously reviewed file is never overwritten, so a rejection dispute
        stays answerable.
        """
        item = self.get_object()
        if is_staff_user(request.user) and not request.user.is_superuser:
            return Response(
                {"detail": "Uploads are made by the student."}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = UploadDocumentSerializer(data=request.data, context={"item": item})
        serializer.is_valid(raise_exception=True)
        student = item.checklist.application.student

        if document_id := serializer.validated_data.get("document_id"):
            document = StudentDocument.objects.filter(pk=document_id, student=student).first()
            if document is None:
                return Response(
                    {"document_id": ["Document not found."]}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            upload_file = serializer.validated_data["file"]
            document = _document_for_item(item, student, serializer.validated_data.get("title", ""))
            next_version = (document.uploads.count() or 0) + 1

            DocumentUpload.objects.filter(
                document=document, status=DocumentUpload.Status.PENDING
            ).update(status=DocumentUpload.Status.SUPERSEDED)

            upload = DocumentUpload.objects.create(
                document=document,
                version=next_version,
                file=upload_file,
                original_filename=upload_file.name[:255],
                content_type=getattr(upload_file, "content_type", "")[:100],
                size_bytes=upload_file.size,
                checksum_sha256=DocumentUpload.compute_checksum(upload_file),
                uploaded_by=request.user,
            )
            document.current_upload = upload
            document.save(update_fields=["current_upload", "updated_at"])

        item.document = document
        if data := serializer.validated_data.get("data"):
            item.data = {**item.data, **data}
        item.status = ChecklistItemInstance.Status.PENDING_REVIEW
        item.rejection_reason = ""
        item.save(update_fields=["document", "data", "status", "rejection_reason", "updated_at"])
        item.checklist.recalculate()

        audit.record(
            "update", target=item, actor=request.user,
            metadata={"document_id": str(document.pk)},
            target_label=f"Upload for {item.label}",
        )
        return Response(ChecklistItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[HasAdminPermission])
    def review(self, request, pk=None):
        """Verify, reject or waive an item. The review queue's write endpoint."""
        item = self.get_object()
        serializer = ReviewItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        decision = serializer.validated_data["status"]
        reason = serializer.validated_data.get("reason", "")

        try:
            item.set_status(decision, user=request.user, reason=reason)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # The vault document carries the same verdict, so a shared document is
        # not re-reviewed for every school that asks for it.
        upload = item.document.current_upload if item.document_id else None
        if upload:
            mapping = {
                ChecklistItemInstance.Status.VERIFIED: DocumentUpload.Status.VERIFIED,
                ChecklistItemInstance.Status.REJECTED: DocumentUpload.Status.REJECTED,
            }
            if decision in mapping:
                upload.status = mapping[decision]
                upload.reviewed_by = request.user
                upload.reviewed_at = timezone.now()
                upload.rejection_reason = reason
                upload.reviewer_note = serializer.validated_data.get("reviewer_note", "")
                upload.save()

        from apps.notifications.services import notify_document_rejected, notify_document_verified

        if decision == ChecklistItemInstance.Status.REJECTED:
            notify_document_rejected(item, reason)
        elif decision == ChecklistItemInstance.Status.VERIFIED:
            notify_document_verified(item)

        return Response(ChecklistItemSerializer(item).data)


def _document_for_item(item: ChecklistItemInstance, student, title: str) -> StudentDocument:
    """Find or create the vault entry this item's upload belongs to.

    Shareable items (passport, WAEC) reuse one vault entry across every
    application; everything else gets its own.
    """
    if item.shareable_key:
        document, _ = StudentDocument.objects.get_or_create(
            student=student,
            shareable_key=item.shareable_key,
            defaults={"title": title or item.label},
        )
        return document
    if item.document_id:
        return item.document
    return StudentDocument.objects.create(student=student, title=title or item.label)


class ReviewQueueViewSet(ReadOnlyModelViewSet):
    """
    The document review queue (plan §7.4).

    A first-class, cross-student list rather than something buried inside each
    profile — this is the screen the team lives in daily.
    """

    serializer_class = ChecklistItemSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_review_documents"
    filterset_fields = ["status", "category_slug", "priority"]
    search_fields = ["label", "checklist__application__student__user__email"]
    ordering_fields = ["updated_at", "due_date", "priority"]

    def get_queryset(self):
        qs = (
            ChecklistItemInstance.objects.filter(is_active=True)
            .select_related(
                "checklist__application__student__user",
                "checklist__application__school",
                "document__current_upload",
            )
            .order_by("updated_at")  # oldest waiting first
        )
        if self.request.query_params.get("status"):
            return qs
        # Default view: what actually needs a decision.
        return qs.filter(
            Q(status=ChecklistItemInstance.Status.PENDING_REVIEW)
            | Q(status=ChecklistItemInstance.Status.UPLOADED)
        )


class StudentDocumentViewSet(ModelViewSet):
    """The student's document vault (plan §8.4)."""

    serializer_class = StudentDocumentSerializer
    permission_classes = [IsAuthenticated, HasPlatformAccess]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["shareable_key", "category"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = StudentDocument.objects.filter(archived_at__isnull=True).select_related(
            "current_upload", "student__user"
        )
        user = self.request.user
        if not is_staff_user(user):
            if not user.is_authenticated:
                return qs.none()
            qs = qs.filter(student__user=user)
        elif student_id := self.request.query_params.get("student"):
            qs = qs.filter(student_id=student_id)
        return qs.order_by("-updated_at")

    def perform_create(self, serializer):
        serializer.save(student=self.request.user.student_profile)

    def perform_destroy(self, instance):
        # Documents are archived, not deleted — they may be evidence in a
        # rejection dispute or needed for accreditation review (plan §10).
        instance.archive(reason="Removed by student")
        audit.record("archive", target=instance, actor=self.request.user)
