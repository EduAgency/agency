import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import ArchivableModel, BaseModel


def document_upload_path(instance, filename: str) -> str:
    """Namespaced by student so an S3 prefix policy can be written per student,
    and so an NDPR erasure request maps to one prefix to delete."""
    student_id = instance.document.student_id
    return f"documents/{student_id}/{instance.document_id}/v{instance.version}/{filename}"


class Application(BaseModel, ArchivableModel):
    """
    One student's pursuit of one school/programme.

    Its own entity, not a field on the student, because students apply to
    several schools and each application carries its own checklist, progress and
    outcome (plan §4.4). A single global "percent complete" per student would be
    meaningless.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PREPARING = "preparing", "Preparing documents"
        READY_TO_SUBMIT = "ready_to_submit", "Ready to submit"
        SUBMITTED = "submitted", "Submitted to school"
        ADDITIONAL_INFO = "additional_info", "School requested more information"
        OFFER = "offer", "Offer received"
        CONDITIONAL_OFFER = "conditional_offer", "Conditional offer"
        REJECTED = "rejected", "Rejected by school"
        ACCEPTED_OFFER = "accepted_offer", "Offer accepted by student"
        VISA_APPLIED = "visa_applied", "Visa applied"
        VISA_GRANTED = "visa_granted", "Visa granted"
        VISA_REFUSED = "visa_refused", "Visa refused"
        ENROLLED = "enrolled", "Enrolled"
        WITHDRAWN = "withdrawn", "Withdrawn by student"

    # Terminal states keep their data (§10) but stop appearing in active queues.
    CLOSED_STATUSES = {Status.REJECTED, Status.VISA_REFUSED, Status.ENROLLED, Status.WITHDRAWN}

    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="applications"
    )
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="applications")
    programme = models.ForeignKey(
        "schools.Programme", null=True, blank=True, on_delete=models.PROTECT, related_name="applications"
    )
    intake = models.CharField(max_length=60, blank=True, help_text='e.g. "October 2027"')

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    status_changed_at = models.DateTimeField(auto_now_add=True)
    target_submission_date = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    external_reference = models.CharField(
        max_length=100, blank=True, help_text="School or uni-assist application number."
    )
    counsellor_notes = models.TextField(blank=True, help_text="Staff-only.")

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["student", "school", "programme", "intake"],
                name="uniq_application_per_intake",
            )
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student.user} → {self.school.name} ({self.get_status_display()})"

    @property
    def is_closed(self) -> bool:
        return self.status in self.CLOSED_STATUSES

    def set_status(self, status: str, *, user=None, note: str = "") -> None:
        from apps.core import audit

        previous = self.status
        if previous == status:
            return
        self.status = status
        self.status_changed_at = timezone.now()
        fields = ["status", "status_changed_at", "updated_at"]

        if status == self.Status.SUBMITTED and not self.submitted_at:
            self.submitted_at = timezone.now()
            fields.append("submitted_at")
        if status in {self.Status.OFFER, self.Status.CONDITIONAL_OFFER, self.Status.REJECTED}:
            self.decision_at = timezone.now()
            fields.append("decision_at")
        if note:
            self.decision_note = note
            fields.append("decision_note")

        self.save(update_fields=fields)
        audit.record(
            "update", target=self, actor=user,
            changes={"status": {"from": previous, "to": status}},
            metadata={"note": note},
        )


class ChecklistInstance(BaseModel):
    """
    A student's checklist for one application — a **snapshot**, not a live view
    of the school's current requirements (plan §4.3).

    Items are copied in at generation time. If the school changes its
    requirements next month, this student's checklist does not move underneath
    them; a member of staff makes that call explicitly with ``resync()``, which
    reports exactly what it added and removed.
    """

    class ProgressBasis(models.TextChoices):
        VERIFIED = "verified", "Verified documents only"
        UPLOADED = "uploaded", "Anything uploaded"

    application = models.OneToOneField(
        Application, on_delete=models.CASCADE, related_name="checklist"
    )
    source_requirement_set = models.ForeignKey(
        "schools.SchoolRequirementSet",
        null=True, blank=True, on_delete=models.SET_NULL, related_name="checklist_instances",
        help_text="The exact version this checklist was generated from.",
    )
    source_version = models.PositiveIntegerField(
        default=0, help_text="Kept even if the requirement set is later deleted."
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    last_resynced_at = models.DateTimeField(null=True, blank=True)

    # Which number the student's progress bar shows. Verified-only is the honest
    # default: it stops a student believing they are 90% done when half their
    # uploads are the wrong document (§4.2). It does mean the bar depends on
    # review turnaround, so both figures are always stored and the UI shows the
    # secondary one alongside.
    progress_basis = models.CharField(
        max_length=10, choices=ProgressBasis.choices, default=ProgressBasis.VERIFIED
    )
    percent_complete = models.PositiveIntegerField(default=0)
    percent_uploaded = models.PositiveIntegerField(default=0)
    required_count = models.PositiveIntegerField(default=0)
    verified_count = models.PositiveIntegerField(default=0)
    uploaded_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Checklist for {self.application} — {self.percent_complete}%"

    @transaction.atomic
    def recalculate(self, save: bool = True) -> dict:
        """Recompute progress from the item statuses.

        Only *required* items count toward the percentage — optional extras must
        never hold a student at 94% forever.
        """
        items = list(self.items.filter(is_active=True, is_required=True))
        total = len(items)
        verified = sum(1 for i in items if i.status == ChecklistItemInstance.Status.VERIFIED)
        uploaded = sum(
            1 for i in items
            if i.status in {
                ChecklistItemInstance.Status.UPLOADED,
                ChecklistItemInstance.Status.PENDING_REVIEW,
                ChecklistItemInstance.Status.VERIFIED,
            }
        )

        self.required_count = total
        self.verified_count = verified
        self.uploaded_count = uploaded
        self.percent_uploaded = round(uploaded / total * 100) if total else 0
        verified_pct = round(verified / total * 100) if total else 0
        self.percent_complete = (
            verified_pct if self.progress_basis == self.ProgressBasis.VERIFIED else self.percent_uploaded
        )

        if save:
            self.save(
                update_fields=[
                    "required_count", "verified_count", "uploaded_count",
                    "percent_uploaded", "percent_complete", "updated_at",
                ]
            )
        return {
            "percent_complete": self.percent_complete,
            "percent_uploaded": self.percent_uploaded,
            "verified": verified,
            "uploaded": uploaded,
            "required": total,
        }

    def progress_by_category(self) -> list[dict]:
        """Per-category breakdown, mirroring the HWR tracker's dashboard."""
        rows: dict[str, dict] = {}
        for item in self.items.filter(is_active=True).select_related():
            row = rows.setdefault(
                item.category_slug,
                {
                    "category": item.category_name,
                    "slug": item.category_slug,
                    "order": item.category_order,
                    "total": 0, "verified": 0, "uploaded": 0,
                },
            )
            row["total"] += 1
            if item.status == ChecklistItemInstance.Status.VERIFIED:
                row["verified"] += 1
            if item.status in {
                ChecklistItemInstance.Status.UPLOADED,
                ChecklistItemInstance.Status.PENDING_REVIEW,
                ChecklistItemInstance.Status.VERIFIED,
            }:
                row["uploaded"] += 1
        for row in rows.values():
            row["percent"] = round(row["verified"] / row["total"] * 100) if row["total"] else 0
        return sorted(rows.values(), key=lambda r: (r["order"], r["category"]))


class ChecklistItemInstance(BaseModel):
    """
    One line on a student's checklist.

    Requirement text is **copied** here, not joined to RequirementItem, so the
    wording a student was shown is the wording preserved in their record even
    after the school's set is edited or deleted. ``source_requirement_item`` is
    a nullable back-pointer used only for re-sync matching.
    """

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        UPLOADED = "uploaded", "Uploaded"
        PENDING_REVIEW = "pending_review", "In review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        WAIVED = "waived", "Waived by agency"
        NOT_APPLICABLE = "not_applicable", "Not applicable"

    OPEN_STATUSES = {Status.NOT_STARTED, Status.IN_PROGRESS, Status.REJECTED}

    checklist = models.ForeignKey(ChecklistInstance, on_delete=models.CASCADE, related_name="items")
    source_requirement_item = models.ForeignKey(
        "schools.RequirementItem", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="instances",
    )

    # --- snapshotted requirement definition ---
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    help_text = models.CharField(max_length=300, blank=True)
    category_name = models.CharField(max_length=100)
    category_slug = models.SlugField(max_length=100)
    category_order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    priority = models.CharField(max_length=10, default="medium")
    evidence_type = models.CharField(max_length=20, default="document")
    accepted_file_types = models.JSONField(default=list, blank=True)
    max_file_size_mb = models.PositiveIntegerField(default=20)
    allow_multiple_files = models.BooleanField(default=False)
    shareable_key = models.SlugField(max_length=100, blank=True, db_index=True)
    expires_after_months = models.PositiveIntegerField(null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)

    # --- live state ---
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NOT_STARTED, db_index=True
    )
    document = models.ForeignKey(
        "applications.StudentDocument", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="checklist_items",
    )
    form_submission = models.ForeignKey(
        "forms_engine.FormSubmission", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="checklist_items",
    )
    data = models.JSONField(default=dict, blank=True, help_text="Inline structured answers (e.g. {'ielts_overall': 6.5}).")

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_checklist_items",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(
        blank=True,
        help_text="Required when rejecting (§10) — 'rejected' with no explanation just creates a support ticket.",
    )
    student_note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("category_order", "display_order", "label")
        indexes = [
            models.Index(fields=["checklist", "status"]),
            models.Index(fields=["status", "-updated_at"]),
            models.Index(fields=["shareable_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.label} — {self.get_status_display()}"

    def clean(self):
        if self.status == self.Status.REJECTED and not self.rejection_reason.strip():
            raise ValidationError({"rejection_reason": "A rejection must say why."})

    @transaction.atomic
    def set_status(self, status: str, *, user=None, reason: str = "") -> None:
        from apps.core import audit

        if status == self.Status.REJECTED and not reason.strip():
            raise ValidationError({"rejection_reason": "A rejection must say why."})

        previous = self.status
        self.status = status
        fields = ["status", "updated_at"]

        if status in {self.Status.VERIFIED, self.Status.REJECTED, self.Status.WAIVED}:
            self.reviewed_by = user
            self.reviewed_at = timezone.now()
            fields += ["reviewed_by", "reviewed_at"]
        if status == self.Status.REJECTED:
            self.rejection_reason = reason
            fields.append("rejection_reason")
        elif previous == self.Status.REJECTED:
            self.rejection_reason = ""
            fields.append("rejection_reason")

        self.save(update_fields=fields)
        self.checklist.recalculate()

        action = {
            self.Status.VERIFIED: "document_verify",
            self.Status.REJECTED: "document_reject",
        }.get(status, "update")
        audit.record(
            action, target=self, actor=user,
            changes={"status": {"from": previous, "to": status}},
            metadata={"reason": reason, "application_id": str(self.checklist.application_id)},
        )


class StudentDocument(BaseModel, ArchivableModel):
    """
    An entry in the student's document vault (plan §8.4).

    One artefact — a passport, a WAEC certificate — uploaded once and reusable
    across every application that asks for it. Version history hangs off it, so
    a re-upload after a rejection does not destroy what was reviewed before.
    """

    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=200)
    shareable_key = models.SlugField(
        max_length=100, blank=True, db_index=True,
        help_text="Matches RequirementItem.shareable_key so the same file satisfies many checklists.",
    )
    category = models.ForeignKey(
        "schools.RequirementCategory", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="student_documents",
    )
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(
        null=True, blank=True, help_text="Passport expiry, IELTS validity — drives renewal reminders."
    )
    current_upload = models.ForeignKey(
        "applications.DocumentUpload", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        ordering = ("-updated_at",)
        indexes = [models.Index(fields=["student", "shareable_key"])]

    def __str__(self) -> str:
        return f"{self.title} — {self.student.user}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_on and self.expires_on < timezone.localdate())

    @property
    def review_status(self) -> str:
        return self.current_upload.status if self.current_upload else DocumentUpload.Status.PENDING


class DocumentUpload(BaseModel):
    """
    One uploaded version of a StudentDocument.

    Never overwritten. A rejected passport scan stays on the record next to the
    replacement, which is what makes a rejection dispute answerable months later.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Superseded by a newer version"

    document = models.ForeignKey(StudentDocument, on_delete=models.CASCADE, related_name="uploads")
    version = models.PositiveIntegerField(default=1)
    file = models.FileField(upload_to=document_upload_path, max_length=500)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    checksum_sha256 = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text="Detects a student re-uploading the identical file after a rejection.",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="document_uploads",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_uploads",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    reviewer_note = models.TextField(blank=True, help_text="Internal note, not shown to the student.")

    virus_scanned_at = models.DateTimeField(null=True, blank=True)
    virus_scan_result = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(fields=["document", "version"], name="uniq_upload_version")
        ]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.document.title} v{self.version} ({self.get_status_display()})"

    @staticmethod
    def compute_checksum(file_obj) -> str:
        digest = hashlib.sha256()
        for chunk in file_obj.chunks():
            digest.update(chunk)
        file_obj.seek(0)
        return digest.hexdigest()


# Module-level aliases for drf-spectacular's ENUM_NAME_OVERRIDES — see the note
# in apps/payments/models.py.
APPLICATION_STATUS_CHOICES = Application.Status.choices
CHECKLIST_ITEM_STATUS_CHOICES = ChecklistItemInstance.Status.choices
DOCUMENT_UPLOAD_STATUS_CHOICES = DocumentUpload.Status.choices
