from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import BaseModel

from .schema import SchemaError, validate_schema


class FormDefinition(BaseModel):
    """
    One version of one form.

    Versioning is the whole point (plan §3.3). A published form is immutable:
    editing it creates version N+1 and leaves N in place, still linked to every
    submission made against it. Without this, editing a school's requirement
    form after ten students have submitted silently changes what "complete"
    meant for people already halfway through.

    ``slug`` identifies the form across versions; (slug, version) is unique.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Audience(models.TextChoices):
        """Who may see and submit this form (plan §3.4). Enforced server-side."""

        PUBLIC = "public", "Public (no login required)"
        PROSPECT = "prospect", "Any logged-in student"
        PAID_STUDENT = "paid_student", "Students with platform access"
        ADMIN_ONLY = "admin_only", "Agency staff only"

    class Purpose(models.TextChoices):
        """What a submission against this form *means* downstream (plan §3.5)."""

        STUDENT_INTAKE = "student_intake", "Student intake / profile"
        SCHOOL_REQUIREMENTS = "school_requirements", "School & requirement upload"
        APPLICATION_SUPPLEMENT = "application_supplement", "Per-application supplement"
        REQUIREMENT_ITEM = "requirement_item", "Attached to a checklist item"
        CONSULTATION_LOG = "consultation_log", "Internal consultation log"
        GENERAL = "general", "General / standalone"

    slug = models.SlugField(max_length=140, db_index=True)
    version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.PROSPECT)
    purpose = models.CharField(max_length=30, choices=Purpose.choices, default=Purpose.GENERAL)

    schema = models.JSONField(
        default=dict, help_text="Sections and fields — see apps.forms_engine.schema."
    )

    allow_multiple_submissions = models.BooleanField(
        default=False, help_text="If false, one submission per subject per form slug."
    )
    allow_drafts = models.BooleanField(
        default=True, help_text="Students can save a partial answer set and return later."
    )
    submit_button_label = models.CharField(max_length=60, blank=True, default="Submit")
    success_message = models.TextField(blank=True)

    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="published_forms",
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_forms",
    )
    change_note = models.CharField(
        max_length=255, blank=True, help_text="What changed in this version, for the audit trail."
    )

    class Meta:
        ordering = ("slug", "-version")
        constraints = [
            models.UniqueConstraint(fields=["slug", "version"], name="uniq_form_slug_version"),
            # At most one live version per form. Enforced in the database, not
            # just in application code, because two published versions of the
            # same form is a data-integrity problem we could not untangle later.
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(status="published"),
                name="uniq_published_form_per_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["purpose", "status"]),
            models.Index(fields=["audience", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} v{self.version} ({self.get_status_display()})"

    def clean(self):
        if self.schema:
            try:
                validate_schema(self.schema)
            except SchemaError as exc:
                raise ValidationError({"schema": str(exc)}) from exc

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:140]
        super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        """Only drafts may be edited in place (§3.3)."""
        return self.status == self.Status.DRAFT

    @property
    def has_submissions(self) -> bool:
        return self.submissions.exists()

    @transaction.atomic
    def publish(self, user=None) -> "FormDefinition":
        """Make this version live, retiring whichever version is live now."""
        from apps.core import audit

        if self.status == self.Status.PUBLISHED:
            return self
        if self.status == self.Status.ARCHIVED:
            raise ValidationError("Archived forms cannot be republished — create a new version.")

        validate_schema(self.schema)  # never publish a schema that fails validation

        previous = (
            FormDefinition.objects.select_for_update()
            .filter(slug=self.slug, status=self.Status.PUBLISHED)
            .exclude(pk=self.pk)
            .first()
        )
        if previous:
            previous.status = self.Status.ARCHIVED
            previous.archived_at = timezone.now()
            previous.save(update_fields=["status", "archived_at", "updated_at"])

        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.published_by = user
        self.save(update_fields=["status", "published_at", "published_by", "updated_at"])

        audit.record(
            "publish",
            target=self,
            actor=user,
            metadata={"version": self.version, "replaced_version": previous.version if previous else None},
        )
        return self

    @transaction.atomic
    def create_new_version(self, user=None, change_note: str = "") -> "FormDefinition":
        """Branch a new editable draft from this version.

        Called instead of editing a published form. The old version stays exactly
        as it was for everyone who already submitted against it.
        """
        latest = (
            FormDefinition.objects.select_for_update()
            .filter(slug=self.slug)
            .order_by("-version")
            .first()
        )
        if latest and latest.status == self.Status.DRAFT:
            raise ValidationError(
                f"An unpublished draft (v{latest.version}) already exists for this form. "
                "Edit or discard it before creating another version."
            )
        return FormDefinition.objects.create(
            slug=self.slug,
            version=(latest.version if latest else self.version) + 1,
            title=self.title,
            description=self.description,
            status=self.Status.DRAFT,
            audience=self.audience,
            purpose=self.purpose,
            schema=self.schema,
            allow_multiple_submissions=self.allow_multiple_submissions,
            allow_drafts=self.allow_drafts,
            submit_button_label=self.submit_button_label,
            success_message=self.success_message,
            created_by=user,
            change_note=change_note,
        )

    @classmethod
    def live(cls, slug: str) -> "FormDefinition | None":
        return cls.objects.filter(slug=slug, status=cls.Status.PUBLISHED).first()

    def is_visible_to(self, user) -> bool:
        """Server-side audience check (§3.4)."""
        if self.status != self.Status.PUBLISHED:
            return bool(user and user.is_authenticated and user.is_agency_staff)
        if self.audience == self.Audience.PUBLIC:
            return True
        if not (user and user.is_authenticated):
            return False
        if user.is_agency_staff:
            return True
        if self.audience == self.Audience.ADMIN_ONLY:
            return False
        if self.audience == self.Audience.PAID_STUDENT:
            profile = getattr(user, "student_profile", None)
            return bool(profile and profile.has_platform_access)
        return True  # PROSPECT


class FormSubmission(BaseModel):
    """
    One filled-in form, pinned to the exact FormDefinition version it was
    answered against.

    ``form_definition`` is PROTECTed: a form version that has submissions can be
    archived but never deleted, or we would lose the meaning of the answers.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        SUPERSEDED = "superseded", "Superseded by a newer submission"

    form_definition = models.ForeignKey(
        FormDefinition, on_delete=models.PROTECT, related_name="submissions"
    )
    form_slug = models.SlugField(
        max_length=140, db_index=True,
        help_text="Denormalised from the definition so submissions group across versions.",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="form_submissions",
    )

    # Optional subjects — a submission is usually *about* something.
    student = models.ForeignKey(
        "accounts.StudentProfile", null=True, blank=True,
        on_delete=models.CASCADE, related_name="form_submissions",
    )
    school = models.ForeignKey(
        "schools.School", null=True, blank=True,
        on_delete=models.CASCADE, related_name="form_submissions",
    )
    application = models.ForeignKey(
        "applications.Application", null=True, blank=True,
        on_delete=models.CASCADE, related_name="form_submissions",
    )

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    data = models.JSONField(default=dict, help_text="Validated answers, keyed by field key.")
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["form_slug", "status"]),
            models.Index(fields=["student", "form_slug"]),
            models.Index(fields=["school", "form_slug"]),
        ]

    def __str__(self) -> str:
        subject = self.student or self.school or self.submitted_by or "anonymous"
        return f"{self.form_slug} v{self.form_definition.version} — {subject}"

    def save(self, *args, **kwargs):
        if not self.form_slug and self.form_definition_id:
            self.form_slug = self.form_definition.slug
        super().save(*args, **kwargs)

    def answer(self, key, default=None):
        return self.data.get(key, default)


# Module-level aliases for drf-spectacular's ENUM_NAME_OVERRIDES.
FORM_STATUS_CHOICES = FormDefinition.Status.choices
FORM_AUDIENCE_CHOICES = FormDefinition.Audience.choices
FORM_PURPOSE_CHOICES = FormDefinition.Purpose.choices
SUBMISSION_STATUS_CHOICES = FormSubmission.Status.choices
