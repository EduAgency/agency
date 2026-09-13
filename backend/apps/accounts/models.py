from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.core.models import ArchivableModel, BaseModel, TimeStampedModel

# Nigerian and international formats; kept permissive on purpose — students
# type numbers many ways and we normalise on save rather than reject at entry.
phone_validator = RegexValidator(
    regex=r"^\+?[0-9\s\-()]{7,20}$",
    message="Enter a valid phone number, e.g. +2348012345678.",
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("role", User.Role.STUDENT)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", User.Role.SUPERADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        extra.setdefault("email_verified_at", timezone.now())
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("Superuser must have is_staff and is_superuser set.")
        return self._create_user(email, password, **extra)


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """Email-first account. Both students and staff are Users; what they can do
    is decided by ``role`` plus the flags on their AdminProfile."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        COUNSELLOR = "counsellor", "Counsellor"
        REVIEWER = "reviewer", "Document reviewer"
        FINANCE = "finance", "Finance"
        ADMIN = "admin", "Admin"
        SUPERADMIN = "superadmin", "Super admin"

    STAFF_ROLES = {Role.COUNSELLOR, Role.REVIEWER, Role.FINANCE, Role.ADMIN, Role.SUPERADMIN}

    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT, db_index=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False, help_text="Can log into the Django admin backoffice."
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # NDPR (plan §10): consent is recorded, versioned and timestamped, not assumed.
    accepted_terms_at = models.DateTimeField(null=True, blank=True)
    accepted_terms_version = models.CharField(max_length=20, blank=True)
    accepted_privacy_at = models.DateTimeField(null=True, blank=True)
    accepted_privacy_version = models.CharField(max_length=20, blank=True)
    marketing_opt_in = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["role", "is_active"])]

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        super().save(*args, **kwargs)

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name or self.email.split("@")[0]

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_agency_staff(self) -> bool:
        return self.role in self.STAFF_ROLES

    @property
    def email_is_verified(self) -> bool:
        return self.email_verified_at is not None


class StudentProfile(BaseModel, ArchivableModel):
    """
    Everything about a student that the platform itself needs to reason about.

    Free-form intake answers live in FormSubmission against a versioned
    FormDefinition (plan §3) — this model holds only the fields the system has
    logic for: access state, funnel stage, assignment, source.
    """

    class Stage(models.TextChoices):
        """Funnel stage — mirrors the reporting funnel in plan §7.7."""

        REGISTERED = "registered", "Registered"
        PAID = "paid", "Access fee paid"
        PROFILE_COMPLETE = "profile_complete", "Profile complete"
        APPLYING = "applying", "Applying"
        OFFER_RECEIVED = "offer_received", "Offer received"
        VISA_STAGE = "visa_stage", "Visa stage"
        ENROLLED = "enrolled", "Enrolled"
        DORMANT = "dormant", "Dormant"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Source(models.TextChoices):
        ORGANIC = "organic", "Organic"
        REFERRAL = "referral", "Referral"
        SOCIAL = "social", "Social media"
        EVENT = "event", "Event / seminar"
        PARTNER = "partner", "Partner"
        OTHER = "other", "Other"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")

    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True, default="Nigerian")
    country_of_residence = models.CharField(max_length=100, blank=True, default="Nigeria")
    state_of_residence = models.CharField(max_length=100, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    # WhatsApp Business policy requires a recorded opt-in before the first
    # message — holding someone's number is not permission to use it.
    whatsapp_opted_in_at = models.DateTimeField(null=True, blank=True)

    # Outside these hours nothing non-urgent is delivered. Stored in the
    # agency timezone (Africa/Lagos); blank means no quiet hours.
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    stage = models.CharField(
        max_length=20, choices=Stage.choices, default=Stage.REGISTERED, db_index=True
    )
    # Access is granted by a confirmed payment webhook (§5.2), never by the
    # frontend redirect — see apps.payments.services.grant_platform_access.
    has_platform_access = models.BooleanField(default=False, db_index=True)
    access_granted_at = models.DateTimeField(null=True, blank=True)
    access_granted_by_payment = models.ForeignKey(
        "payments.Payment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="granted_access_to",
    )

    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ORGANIC)
    referred_by_code = models.ForeignKey(
        "referrals.ReferralCode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referred_students",
    )
    assigned_counsellor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_students",
        limit_choices_to={"role__in": [User.Role.COUNSELLOR, User.Role.ADMIN]},
    )
    internal_notes = models.TextField(
        blank=True, help_text="Staff-only. Never exposed on the student API."
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["stage", "has_platform_access"]),
            models.Index(fields=["assigned_counsellor", "stage"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} ({self.get_stage_display()})"

    def advance_stage(self, stage: str) -> None:
        """Move forward only. Stages are a funnel, not a state machine to walk
        backwards — a paid student who goes quiet is marked DORMANT explicitly."""
        order = [
            self.Stage.REGISTERED,
            self.Stage.PAID,
            self.Stage.PROFILE_COMPLETE,
            self.Stage.APPLYING,
            self.Stage.OFFER_RECEIVED,
            self.Stage.VISA_STAGE,
            self.Stage.ENROLLED,
        ]
        if stage in order and self.stage in order and order.index(stage) <= order.index(self.stage):
            return
        self.stage = stage
        self.save(update_fields=["stage", "updated_at"])


class AdminProfile(BaseModel):
    """
    Granular staff permissions (plan §7.8).

    Built now rather than retrofitted: a document reviewer must be able to work
    the review queue without ever seeing payment gateway keys. Role sets the
    defaults; individual flags can be tightened or loosened per person.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_profile")
    job_title = models.CharField(max_length=120, blank=True)

    can_manage_students = models.BooleanField(default=False)
    can_review_documents = models.BooleanField(default=False)
    can_manage_schools = models.BooleanField(default=False)
    can_build_forms = models.BooleanField(default=False)
    can_view_payments = models.BooleanField(default=False)
    can_manage_payment_config = models.BooleanField(
        default=False, help_text="Access to gateway API keys. Grant sparingly."
    )
    can_issue_refunds = models.BooleanField(default=False)
    can_manage_referrals = models.BooleanField(default=False)
    can_approve_payouts = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_manage_team = models.BooleanField(default=False)
    can_view_audit_log = models.BooleanField(default=False)
    can_export_data = models.BooleanField(default=False)
    # Blog. Split deliberately: a writer drafts and uses the AI assist, an
    # editor decides what goes on the public site. Publishing carries a name.
    can_write_content = models.BooleanField(default=False)
    can_publish_content = models.BooleanField(default=False)

    PERMISSION_FIELDS = [
        "can_manage_students",
        "can_review_documents",
        "can_manage_schools",
        "can_build_forms",
        "can_view_payments",
        "can_manage_payment_config",
        "can_issue_refunds",
        "can_manage_referrals",
        "can_approve_payouts",
        "can_view_reports",
        "can_manage_team",
        "can_view_audit_log",
        "can_export_data",
        "can_write_content",
        "can_publish_content",
    ]

    ROLE_DEFAULTS = {
        User.Role.COUNSELLOR: [
            "can_manage_students",
            "can_review_documents",
            "can_view_reports",
            "can_write_content",
        ],
        User.Role.REVIEWER: ["can_review_documents"],
        User.Role.FINANCE: ["can_view_payments", "can_issue_refunds", "can_approve_payouts", "can_view_reports"],
        User.Role.ADMIN: [
            "can_manage_students",
            "can_review_documents",
            "can_manage_schools",
            "can_build_forms",
            "can_view_payments",
            "can_manage_referrals",
            "can_view_reports",
            "can_view_audit_log",
            "can_write_content",
            "can_publish_content",
        ],
        User.Role.SUPERADMIN: PERMISSION_FIELDS,
    }

    class Meta:
        ordering = ("user__email",)

    def __str__(self) -> str:
        return f"{self.user} — {self.job_title or self.user.get_role_display()}"

    def apply_role_defaults(self, save: bool = True) -> None:
        granted = set(self.ROLE_DEFAULTS.get(self.user.role, []))
        for field in self.PERMISSION_FIELDS:
            setattr(self, field, field in granted)
        if save:
            self.save()

    def has(self, permission: str) -> bool:
        if self.user.role == User.Role.SUPERADMIN:
            return True
        return bool(getattr(self, permission, False))


class EmailVerificationToken(TimeStampedModel):
    """Single-use, expiring token for email confirmation and password reset."""

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify email"
        RESET_PASSWORD = "reset_password", "Reset password"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tokens")
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "used_at"])]

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


# Module-level aliases for drf-spectacular's ENUM_NAME_OVERRIDES.
USER_ROLE_CHOICES = User.Role.choices
STUDENT_STAGE_CHOICES = StudentProfile.Stage.choices
STUDENT_SOURCE_CHOICES = StudentProfile.Source.choices
