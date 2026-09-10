from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class ReferralCode(BaseModel):
    """A shareable code owned by a student or an external partner (plan §6.1)."""

    class OwnerType(models.TextChoices):
        STUDENT = "student", "Student"
        PARTNER = "partner", "External partner / influencer"
        STAFF = "staff", "Agency staff"

    code = models.CharField(max_length=20, unique=True, db_index=True)
    owner_type = models.CharField(max_length=10, choices=OwnerType.choices, default=OwnerType.STUDENT)

    student = models.ForeignKey(
        "accounts.StudentProfile", null=True, blank=True,
        on_delete=models.CASCADE, related_name="referral_codes",
    )
    partner_name = models.CharField(max_length=150, blank=True)
    partner_email = models.EmailField(blank=True)
    partner_phone = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(
        null=True, blank=True, help_text="Blank means unlimited."
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            # One active code per student unless the multi-code complexity is
            # actually wanted (§6.1) — a single code is simpler to support.
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(is_active=True, owner_type="student"),
                name="uniq_active_code_per_student",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.owner_label})"

    @property
    def owner_label(self) -> str:
        if self.student_id:
            return str(self.student.user)
        return self.partner_name or "unassigned"

    @property
    def is_usable(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.max_uses is not None and self.signup_count >= self.max_uses:
            return False
        return True

    @property
    def signup_count(self) -> int:
        return self.events.filter(event_type=ReferralEvent.Type.SIGNUP).count()

    @property
    def conversion_count(self) -> int:
        return self.events.filter(event_type=ReferralEvent.Type.PAID).count()

    @property
    def total_earned(self) -> Decimal:
        total = self.rewards.exclude(status=ReferralReward.Status.VOID).aggregate(
            total=models.Sum("amount")
        )["total"]
        return total or Decimal("0.00")

    @property
    def total_paid_out(self) -> Decimal:
        total = self.rewards.filter(status=ReferralReward.Status.PAID).aggregate(
            total=models.Sum("amount")
        )["total"]
        return total or Decimal("0.00")

    @classmethod
    def generate_code(cls, seed: str = "") -> str:
        import re
        import secrets

        base = re.sub(r"[^A-Z0-9]", "", (seed or "").upper())[:6] or "NSR"
        for _ in range(10):
            candidate = f"{base}{secrets.token_hex(2).upper()}"
            if not cls.objects.filter(code=candidate).exists():
                return candidate
        return f"NSR{secrets.token_hex(4).upper()}"


class ReferralRewardRule(BaseModel):
    """
    The *rule*, stored separately from the rewards it produced (plan §6.1).

    Rewards keep a snapshot of the rule that created them, so changing the
    programme next quarter never rewrites what someone already earned.
    """

    class Trigger(models.TextChoices):
        SIGNUP = "signup", "Referred student signs up"
        PAID = "paid", "Referred student's access fee is confirmed"
        OFFER = "offer", "Referred student receives an offer"
        ENROLLED = "enrolled", "Referred student enrols"

    class Calculation(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENTAGE = "percentage", "Percentage of the referred student's payment"

    name = models.CharField(max_length=120)
    trigger = models.CharField(max_length=12, choices=Trigger.choices, db_index=True)
    calculation = models.CharField(max_length=12, choices=Calculation.choices, default=Calculation.FIXED)

    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Naira for a fixed reward; percent (e.g. 10.00) for a percentage reward.",
    )
    currency = models.CharField(max_length=3, default="NGN")
    max_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, help_text="Cap for percentage rewards."
    )

    owner_type = models.CharField(
        max_length=10, choices=ReferralCode.OwnerType.choices, blank=True,
        help_text="Blank applies the rule to every owner type.",
    )
    min_referrals = models.PositiveIntegerField(
        default=0, help_text="Tier gate: only applies from this many prior conversions onward."
    )
    max_referrals = models.PositiveIntegerField(
        null=True, blank=True, help_text="Tier ceiling, exclusive."
    )

    requires_manual_approval = models.BooleanField(
        default=False, help_text="Hold the reward for review instead of auto-approving."
    )
    auto_approve_below = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Rewards at or above this amount always wait for a human (§6.2).",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=0, help_text="Higher wins when several rules match.")

    class Meta:
        ordering = ("-priority", "trigger")

    def __str__(self) -> str:
        unit = "%" if self.calculation == self.Calculation.PERCENTAGE else self.currency
        return f"{self.name} — {self.amount}{unit} on {self.get_trigger_display()}"

    def clean(self):
        if self.calculation == self.Calculation.PERCENTAGE and not (0 < self.amount <= 100):
            raise ValidationError({"amount": "A percentage reward must be between 0 and 100."})
        if self.max_referrals is not None and self.max_referrals <= self.min_referrals:
            raise ValidationError({"max_referrals": "Must be greater than min_referrals."})

    def is_live(self, at=None) -> bool:
        at = at or timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and at < self.starts_at:
            return False
        if self.ends_at and at > self.ends_at:
            return False
        return True

    def compute_amount(self, payment_amount: Decimal | None) -> Decimal:
        if self.calculation == self.Calculation.FIXED:
            return self.amount
        base = payment_amount or Decimal("0.00")
        value = (base * self.amount / Decimal("100")).quantize(Decimal("0.01"))
        return min(value, self.max_amount) if self.max_amount else value

    def snapshot(self) -> dict:
        return {
            "rule_id": str(self.pk),
            "name": self.name,
            "trigger": self.trigger,
            "calculation": self.calculation,
            "amount": str(self.amount),
            "currency": self.currency,
            "max_amount": str(self.max_amount) if self.max_amount else None,
        }


class ReferralEvent(BaseModel):
    """An attributable moment in a referred student's journey."""

    class Type(models.TextChoices):
        SIGNUP = "signup", "Signed up"
        PAID = "paid", "Access fee paid"
        OFFER = "offer", "Offer received"
        ENROLLED = "enrolled", "Enrolled"

    code = models.ForeignKey(ReferralCode, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=12, choices=Type.choices, db_index=True)
    referred_student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="referral_events"
    )
    payment = models.ForeignKey(
        "payments.Payment", null=True, blank=True, on_delete=models.SET_NULL, related_name="referral_events"
    )

    # Fraud signals (§6.2) — captured at the moment of the event, not inferred later.
    signup_ip = models.GenericIPAddressField(null=True, blank=True)
    device_fingerprint = models.CharField(max_length=128, blank=True)
    is_flagged = models.BooleanField(default=False, db_index=True)
    flag_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            # Each milestone counts once per referred student, whatever retries
            # or duplicate webhooks occur.
            models.UniqueConstraint(
                fields=["code", "referred_student", "event_type"], name="uniq_referral_event"
            )
        ]
        indexes = [models.Index(fields=["event_type", "is_flagged"])]

    def __str__(self) -> str:
        return f"{self.code.code} — {self.get_event_type_display()} — {self.referred_student.user}"


class ReferralReward(BaseModel):
    """What was actually earned, with the rule that produced it snapshotted in."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved for payout"
        PAID = "paid", "Paid"
        VOID = "void", "Void (fraud or reversal)"

    code = models.ForeignKey(ReferralCode, on_delete=models.CASCADE, related_name="rewards")
    event = models.OneToOneField(ReferralEvent, on_delete=models.CASCADE, related_name="reward")
    rule = models.ForeignKey(
        ReferralRewardRule, null=True, blank=True, on_delete=models.SET_NULL, related_name="rewards"
    )
    rule_snapshot = models.JSONField(
        default=dict, help_text="The rule as it stood when this reward was earned."
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="approved_referral_rewards",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    payout = models.ForeignKey(
        "referrals.ReferralPayout", null=True, blank=True, on_delete=models.SET_NULL, related_name="rewards"
    )
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.currency} {self.amount} to {self.code.code} ({self.get_status_display()})"


class ReferralPayout(BaseModel):
    """A batch payment to one referrer, covering one or more approved rewards."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        PROCESSING = "processing", "Processing"
        PAID = "paid", "Paid"
        DECLINED = "declined", "Declined"

    code = models.ForeignKey(ReferralCode, on_delete=models.PROTECT, related_name="payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED, db_index=True)

    bank_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    account_name = models.CharField(max_length=150, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="approved_payouts",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)

    def __str__(self) -> str:
        return f"Payout {self.currency} {self.amount} to {self.code.code} ({self.get_status_display()})"
