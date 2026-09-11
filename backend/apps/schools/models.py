from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import ArchivableModel, BaseModel
from apps.core.storage import school_logo_path


class RequirementCategory(BaseModel):
    """
    The grouping a checklist item appears under.

    Taken straight from the HWR Berlin tracker's own categories — Documents &
    Transcripts, Language, Visa & Relocation and so on — but stored as data so
    the agency can add categories for a new destination country without a
    developer.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon key for the frontend.")
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "name")
        verbose_name_plural = "requirement categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        super().save(*args, **kwargs)


class Country(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    iso_code = models.CharField(max_length=2, unique=True)
    is_active = models.BooleanField(default=True)
    visa_notes = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "countries"

    def __str__(self) -> str:
        return self.name


class School(BaseModel, ArchivableModel):
    """A partner or target institution students apply to."""

    class Kind(models.TextChoices):
        UNIVERSITY = "university", "University"
        COLLEGE = "college", "College"
        LANGUAGE_SCHOOL = "language_school", "Language school"
        PATHWAY = "pathway", "Pathway / foundation provider"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.UNIVERSITY)
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name="schools", null=True, blank=True
    )
    city = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to=school_logo_path, null=True, blank=True)
    description = models.TextField(blank=True)

    # Commercial terms — visible to staff only.
    is_partner = models.BooleanField(
        default=False, help_text="We hold a formal recruitment agreement with this school."
    )
    commission_notes = models.TextField(blank=True)

    # Free-form attributes captured through the admin-built school form (§3.5),
    # so new fields ('has February intake', 'accepts 3-year degrees') need no migration.
    attributes = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_schools",
    )

    class Meta:
        ordering = ("name",)
        indexes = [models.Index(fields=["is_active", "country"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:200]
        super().save(*args, **kwargs)

    @property
    def current_requirement_set(self) -> "SchoolRequirementSet | None":
        return self.requirement_sets.filter(
            status=SchoolRequirementSet.Status.PUBLISHED
        ).order_by("-version").first()


class Programme(BaseModel, ArchivableModel):
    """
    A specific course of study.

    Requirements often differ per programme (an MBA wants work experience that a
    BSc does not), so a requirement set may attach to a programme rather than
    the whole school.
    """

    class Level(models.TextChoices):
        FOUNDATION = "foundation", "Foundation / pathway"
        UNDERGRADUATE = "undergraduate", "Undergraduate"
        POSTGRADUATE = "postgraduate", "Postgraduate"
        DOCTORATE = "doctorate", "Doctorate"
        LANGUAGE = "language", "Language course"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="programmes")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.UNDERGRADUATE)
    duration_months = models.PositiveIntegerField(null=True, blank=True)
    tuition_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tuition_currency = models.CharField(max_length=3, blank=True, default="EUR")
    language_of_instruction = models.CharField(max_length=60, blank=True, default="English")
    intakes = models.JSONField(
        default=list, blank=True, help_text='e.g. ["October 2027", "April 2028"]'
    )
    application_opens = models.DateField(null=True, blank=True)
    application_deadline = models.DateField(null=True, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("school__name", "name")
        constraints = [
            models.UniqueConstraint(fields=["school", "slug"], name="uniq_programme_per_school")
        ]

    def __str__(self) -> str:
        return f"{self.school.name} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:200]
        super().save(*args, **kwargs)


class SchoolRequirementSet(BaseModel):
    """
    A named, versioned bundle of requirements (plan §4.1).

    Versioned for the same reason forms are: a student's checklist is snapshotted
    from a specific version, and changing requirements next month must not
    silently rewrite what someone who started three months ago agreed to do.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="requirement_sets", null=True, blank=True
    )
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="requirement_sets", null=True, blank=True
    )
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)

    is_template = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "A reusable starting point not tied to one school — e.g. 'UK undergraduate "
            "standard set'. Most UK universities want near-identical documents, so the "
            "admin clones a template instead of rebuilding from scratch (§4.1)."
        ),
    )
    cloned_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="clones"
    )
    notes = models.TextField(blank=True)
    change_note = models.CharField(max_length=255, blank=True)

    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_requirement_sets",
    )

    class Meta:
        ordering = ("school__name", "-version")
        indexes = [models.Index(fields=["school", "status"]), models.Index(fields=["is_template", "status"])]

    def __str__(self) -> str:
        owner = self.programme or self.school or "Template"
        return f"{owner} — {self.name} v{self.version}"

    def clean(self):
        if self.is_template and (self.school_id or self.programme_id):
            raise ValidationError("A template requirement set must not be tied to a school or programme.")
        if not self.is_template and not (self.school_id or self.programme_id):
            raise ValidationError("Attach the requirement set to a school or programme, or mark it a template.")

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.DRAFT

    @property
    def required_item_count(self) -> int:
        return self.items.filter(is_required=True, is_active=True).count()

    @transaction.atomic
    def publish(self, user=None) -> "SchoolRequirementSet":
        from apps.core import audit

        if self.status == self.Status.PUBLISHED:
            return self
        if not self.items.exists():
            raise ValidationError("A requirement set needs at least one item before publishing.")

        previous = (
            SchoolRequirementSet.objects.select_for_update()
            .filter(school=self.school, programme=self.programme, status=self.Status.PUBLISHED)
            .exclude(pk=self.pk)
            .first()
        )
        if previous:
            previous.status = self.Status.ARCHIVED
            previous.save(update_fields=["status", "updated_at"])

        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

        audit.record(
            "publish",
            target=self,
            actor=user,
            metadata={"version": self.version, "items": self.items.count()},
        )
        return self

    @transaction.atomic
    def clone(self, *, school=None, programme=None, name="", user=None) -> "SchoolRequirementSet":
        """Copy this set (and its items) as a new draft — the template flow of §4.1."""
        target_school = school or (programme.school if programme else None)
        new_set = SchoolRequirementSet.objects.create(
            school=target_school,
            programme=programme,
            name=name or self.name,
            version=1,
            status=self.Status.DRAFT,
            is_template=False,
            cloned_from=self,
            notes=self.notes,
            created_by=user,
        )
        RequirementItem.objects.bulk_create(
            [
                RequirementItem(
                    requirement_set=new_set,
                    category=item.category,
                    label=item.label,
                    description=item.description,
                    help_text=item.help_text,
                    is_required=item.is_required,
                    priority=item.priority,
                    evidence_type=item.evidence_type,
                    accepted_file_types=item.accepted_file_types,
                    max_file_size_mb=item.max_file_size_mb,
                    allow_multiple_files=item.allow_multiple_files,
                    linked_form=item.linked_form,
                    data_spec=item.data_spec,
                    is_shareable=item.is_shareable,
                    shareable_key=item.shareable_key,
                    expires_after_months=item.expires_after_months,
                    display_order=item.display_order,
                    due_offset_days=item.due_offset_days,
                )
                for item in self.items.filter(is_active=True)
            ]
        )
        return new_set

    @transaction.atomic
    def create_new_version(self, user=None, change_note: str = "") -> "SchoolRequirementSet":
        latest = (
            SchoolRequirementSet.objects.select_for_update()
            .filter(school=self.school, programme=self.programme)
            .order_by("-version")
            .first()
        )
        if latest and latest.status == self.Status.DRAFT:
            raise ValidationError(
                f"Draft v{latest.version} already exists — edit or discard it first."
            )
        new_set = self.clone(school=self.school, programme=self.programme, name=self.name, user=user)
        new_set.version = (latest.version if latest else self.version) + 1
        new_set.cloned_from = self
        new_set.change_note = change_note
        new_set.save(update_fields=["version", "cloned_from", "change_note", "updated_at"])
        return new_set


class RequirementItem(BaseModel):
    """
    One thing a student must produce.

    Most items are a document upload, but not all: 'IELTS score' is a number
    *and* a file, and 'Confirm HWR's exact English B2 evidence policy' is a task
    with no artefact at all. ``evidence_type`` covers that spread so the checklist
    can represent a real application rather than only a document pile.
    """

    class Evidence(models.TextChoices):
        DOCUMENT = "document", "Document upload"
        FORM = "form", "Form response"
        DOCUMENT_AND_FORM = "document_and_form", "Document + form response"
        TASK = "task", "Task (no upload)"
        EXTERNAL = "external", "Handled outside the platform"

    class Priority(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    requirement_set = models.ForeignKey(
        SchoolRequirementSet, on_delete=models.CASCADE, related_name="items"
    )
    category = models.ForeignKey(
        RequirementCategory, on_delete=models.PROTECT, related_name="requirement_items"
    )
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    help_text = models.CharField(
        max_length=300, blank=True, help_text="Shown under the upload box — e.g. 'Certified copy, English translation'."
    )

    is_required = models.BooleanField(default=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    evidence_type = models.CharField(max_length=20, choices=Evidence.choices, default=Evidence.DOCUMENT)

    accepted_file_types = models.JSONField(default=list, blank=True, help_text='e.g. [".pdf", ".jpg"]')
    max_file_size_mb = models.PositiveIntegerField(default=20)
    allow_multiple_files = models.BooleanField(default=False)

    linked_form = models.ForeignKey(
        "forms_engine.FormDefinition", null=True, blank=True,
        on_delete=models.PROTECT, related_name="requirement_items",
        help_text="Mini-form for items needing structured data alongside the file (e.g. IELTS score).",
    )
    data_spec = models.JSONField(
        default=dict, blank=True,
        help_text="Inline field spec for simple structured data, when a full form is overkill.",
    )

    is_shareable = models.BooleanField(
        default=False,
        help_text=(
            "The same artefact satisfies this item across every application — a passport "
            "is uploaded once and reused (plan §8.4)."
        ),
    )
    shareable_key = models.SlugField(
        max_length=100, blank=True,
        help_text="Items sharing this key across schools reuse one document, e.g. 'passport'.",
    )
    expires_after_months = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Validity window — IELTS is 24 months, police clearances often 6.",
    )

    display_order = models.PositiveIntegerField(default=0, db_index=True)
    due_offset_days = models.IntegerField(
        null=True, blank=True,
        help_text="Days relative to the application deadline; negative means before it.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("category__display_order", "display_order", "label")
        indexes = [models.Index(fields=["requirement_set", "is_active"])]

    def __str__(self) -> str:
        return f"{self.label} ({self.category})"

    def clean(self):
        if self.is_shareable and not self.shareable_key:
            raise ValidationError({"shareable_key": "Shareable items need a key so they can be matched across schools."})
        if self.evidence_type in {self.Evidence.FORM, self.Evidence.DOCUMENT_AND_FORM} and not (
            self.linked_form_id or self.data_spec
        ):
            raise ValidationError("Form-based items need either a linked form or a data spec.")


# Module-level aliases for drf-spectacular's ENUM_NAME_OVERRIDES.
REQUIREMENT_SET_STATUS_CHOICES = SchoolRequirementSet.Status.choices
REQUIREMENT_EVIDENCE_CHOICES = RequirementItem.Evidence.choices
REQUIREMENT_PRIORITY_CHOICES = RequirementItem.Priority.choices
SCHOOL_KIND_CHOICES = School.Kind.choices
PROGRAMME_LEVEL_CHOICES = Programme.Level.choices
