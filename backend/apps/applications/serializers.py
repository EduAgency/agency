from rest_framework import serializers

from .models import (
    Application,
    ChecklistInstance,
    ChecklistItemInstance,
    DocumentUpload,
    StudentDocument,
)


class DocumentUploadSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentUpload
        fields = (
            "id", "version", "original_filename", "content_type", "size_bytes",
            "status", "rejection_reason", "reviewed_at", "created_at", "download_url",
        )
        read_only_fields = fields

    def get_download_url(self, obj) -> str | None:
        """A signed, short-lived URL — never a permanent public link to a passport."""
        if not obj.file:
            return None
        try:
            return obj.file.url
        except Exception:
            return None


class StudentDocumentSerializer(serializers.ModelSerializer):
    uploads = DocumentUploadSerializer(many=True, read_only=True)
    current = DocumentUploadSerializer(source="current_upload", read_only=True)
    review_status = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = StudentDocument
        fields = (
            "id", "title", "shareable_key", "category", "issued_on", "expires_on",
            "review_status", "is_expired", "current", "uploads", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ChecklistItemSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    document = StudentDocumentSerializer(read_only=True)

    class Meta:
        model = ChecklistItemInstance
        fields = (
            "id", "label", "description", "help_text", "category_name", "category_slug",
            "category_order", "is_required", "priority", "evidence_type",
            "accepted_file_types", "max_file_size_mb", "allow_multiple_files",
            "shareable_key", "due_date", "status", "status_display", "rejection_reason",
            "student_note", "data", "document", "reviewed_at", "display_order", "updated_at",
        )
        # Only staff move a status; a student changes it by uploading.
        read_only_fields = tuple(f for f in fields if f not in {"student_note", "data"})


class ChecklistSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)
    categories = serializers.SerializerMethodField()

    class Meta:
        model = ChecklistInstance
        fields = (
            "id", "progress_basis", "percent_complete", "percent_uploaded",
            "required_count", "verified_count", "uploaded_count", "source_version",
            "generated_at", "last_resynced_at", "items", "categories",
        )
        read_only_fields = fields

    def get_categories(self, obj) -> list:
        return obj.progress_by_category()


class ChecklistSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistInstance
        fields = (
            "id", "percent_complete", "percent_uploaded",
            "required_count", "verified_count", "uploaded_count",
        )
        read_only_fields = fields


class ApplicationSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    programme_name = serializers.CharField(source="programme.name", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    checklist = ChecklistSummarySerializer(read_only=True)

    class Meta:
        model = Application
        fields = (
            "id", "student", "school", "school_name", "programme", "programme_name",
            "intake", "status", "status_display", "target_submission_date",
            "submitted_at", "decision_at", "external_reference", "checklist",
            "created_at", "updated_at",
        )
        # Status moves through the dedicated endpoint so every change is audited.
        read_only_fields = ("id", "student", "status", "submitted_at", "decision_at", "created_at", "updated_at")


class StaffApplicationSerializer(ApplicationSerializer):
    student_email = serializers.CharField(source="student.user.email", read_only=True)
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)

    class Meta(ApplicationSerializer.Meta):
        fields = (*ApplicationSerializer.Meta.fields, "student_email", "student_name", "counsellor_notes")


class UploadDocumentSerializer(serializers.Serializer):
    """Upload against a checklist item.

    Either attaches an existing vault document (``document_id``) or takes a new
    ``file``. Size and type are checked against the item's own snapshot, so the
    rules a student was shown are the rules applied.
    """

    file = serializers.FileField(required=False)
    document_id = serializers.UUIDField(required=False)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    data = serializers.DictField(required=False)

    def validate(self, attrs):
        if not attrs.get("file") and not attrs.get("document_id"):
            raise serializers.ValidationError("Provide a file or an existing document to attach.")

        item: ChecklistItemInstance = self.context["item"]
        upload = attrs.get("file")
        if upload:
            max_bytes = item.max_file_size_mb * 1024 * 1024
            if upload.size > max_bytes:
                raise serializers.ValidationError(
                    {"file": [f"This file is {upload.size / 1024 / 1024:.1f}MB. The limit is {item.max_file_size_mb}MB."]}
                )
            accepted = [ext.lower() for ext in (item.accepted_file_types or [])]
            if accepted:
                extension = "." + upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else ""
                if extension not in accepted:
                    raise serializers.ValidationError(
                        {"file": [f"Accepted file types: {', '.join(accepted)}."]}
                    )
        return attrs


class ReviewItemSerializer(serializers.Serializer):
    """Staff decision on a checklist item."""

    status = serializers.ChoiceField(
        choices=[
            ChecklistItemInstance.Status.VERIFIED,
            ChecklistItemInstance.Status.REJECTED,
            ChecklistItemInstance.Status.WAIVED,
            ChecklistItemInstance.Status.NOT_APPLICABLE,
            ChecklistItemInstance.Status.PENDING_REVIEW,
        ]
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    reviewer_note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        # A rejection without a reason just becomes a support ticket (plan §10).
        if attrs["status"] == ChecklistItemInstance.Status.REJECTED and not attrs.get("reason", "").strip():
            raise serializers.ValidationError(
                {"reason": ["Tell the student what was wrong so they can fix it."]}
            )
        return attrs
