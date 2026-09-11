from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.encryption import EncryptedTextField, fingerprint
from apps.core.models import BaseModel


class Gateway(models.TextChoices):
    PAYSTACK = "paystack", "Paystack"
    FLUTTERWAVE = "flutterwave", "Flutterwave"
    MANUAL = "manual", "Manual / bank transfer"
    # Development and demo only. The adapter refuses to load unless DEBUG is on,
    # ENVIRONMENT is not production, and PAYMENTS_MOCK_MODE is explicitly set.
    MOCK = "mock", "Mock (no money moves)"


class PaymentGatewayConfig(BaseModel):
    """
    Admin-controlled gateway credentials and on/off switch (plan §5.1).

    Secret keys are stored through EncryptedTextField, so a database dump does
    not hand over live credentials. The checkout endpoint asks this table which
    gateways are active and offers only those.
    """

    gateway = models.CharField(max_length=20, choices=Gateway.choices, db_index=True)
    label = models.CharField(max_length=100, blank=True, help_text="Shown to students at checkout.")
    is_active = models.BooleanField(default=False, db_index=True)
    is_test_mode = models.BooleanField(default=True)
    currency = models.CharField(max_length=3, default="NGN")

    public_key = models.CharField(max_length=255, blank=True)
    secret_key = EncryptedTextField(blank=True)
    encryption_key = EncryptedTextField(
        blank=True, help_text="Flutterwave's separate encryption key, where required."
    )
    webhook_secret = EncryptedTextField(
        blank=True, help_text="Paystack: the secret key. Flutterwave: the 'secret hash'."
    )
    secret_key_fingerprint = models.CharField(
        max_length=12, blank=True,
        help_text="Non-reversible identifier so staff can confirm which key is live.",
    )

    display_order = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="updated_gateway_configs",
    )

    class Meta:
        ordering = ("display_order", "gateway")
        constraints = [
            models.UniqueConstraint(
                fields=["gateway", "currency", "is_test_mode"], name="uniq_gateway_currency_mode"
            )
        ]

    def __str__(self) -> str:
        mode = "test" if self.is_test_mode else "live"
        return f"{self.get_gateway_display()} ({self.currency}, {mode})"

    def clean(self):
        if self.is_active and not self.secret_key:
            raise ValidationError({"secret_key": "An active gateway needs a secret key."})
        if self.is_active and self.gateway != Gateway.MANUAL and not self.webhook_secret:
            raise ValidationError(
                {"webhook_secret": "An active gateway needs a webhook secret — webhooks are how "
                                   "payments are confirmed."}
            )

    def save(self, *args, **kwargs):
        self.secret_key_fingerprint = fingerprint(self.secret_key or "")
        super().save(*args, **kwargs)

    @classmethod
    def active_for(cls, currency: str = "NGN", *, test_mode: bool | None = None):
        qs = cls.objects.filter(is_active=True, currency=currency.upper())
        if test_mode is not None:
            qs = qs.filter(is_test_mode=test_mode)
        return qs.order_by("display_order")


class Payment(BaseModel):
    """
    A single attempted or completed payment.

    ``status`` is moved by webhook processing and by reconciliation — never by
    the browser redirect (plan §5.2). ``reference`` is ours and unique; the
    gateway's own id is kept alongside for support conversations.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        ABANDONED = "abandoned", "Abandoned"
        REVERSED = "reversed", "Reversed"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"

    class Purpose(models.TextChoices):
        ACCESS_FEE = "access_fee", "Platform access fee"
        APPLICATION_FEE = "application_fee", "Application fee"
        SERVICE_FEE = "service_fee", "Service fee"
        TUITION_DEPOSIT = "tuition_deposit", "Tuition deposit"
        OTHER = "other", "Other"

    reference = models.CharField(
        max_length=64, unique=True, db_index=True, help_text="Our reference, sent to the gateway."
    )
    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    gateway_reference = models.CharField(max_length=128, blank=True, db_index=True)
    gateway_config = models.ForeignKey(
        PaymentGatewayConfig, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments"
    )

    student = models.ForeignKey(
        "accounts.StudentProfile", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments",
    )
    application = models.ForeignKey(
        "applications.Application", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments",
    )
    email = models.EmailField(help_text="Kept even if the student record is later removed.")

    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.ACCESS_FEE)
    # Amount + explicit currency from day one (plan §5.4) — retrofitting currency
    # onto an NGN-only assumption is painful once there are live records.
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=3, default="NGN")
    amount_settled = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    gateway_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    status_reason = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    channel = models.CharField(max_length=40, blank=True, help_text="card, bank_transfer, ussd …")
    authorization_code = models.CharField(max_length=100, blank=True)

    confirmed_by_webhook = models.BooleanField(
        default=False,
        help_text="True only when a signature-verified webhook confirmed this payment.",
    )
    confirmed_by_reconciliation = models.BooleanField(
        default=False, help_text="Set when the nightly job found a success the webhook never delivered."
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciliation_note = models.CharField(max_length=255, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    initiated_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["student", "purpose", "status"]),
            models.Index(fields=["gateway", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} — {self.currency} {self.amount} ({self.get_status_display()})"

    @property
    def is_successful(self) -> bool:
        return self.status == self.Status.SUCCESSFUL

    @property
    def amount_refunded(self) -> Decimal:
        total = self.refunds.filter(status=Refund.Status.COMPLETED).aggregate(
            total=models.Sum("amount")
        )["total"]
        return total or Decimal("0.00")

    @property
    def is_refundable(self) -> bool:
        return self.is_successful and self.amount_refunded < self.amount

    @staticmethod
    def generate_reference(prefix: str = "NSR") -> str:
        import secrets

        return f"{prefix}-{timezone.now():%Y%m%d}-{secrets.token_hex(5).upper()}"


class WebhookEvent(BaseModel):
    """
    Raw webhook log — written *before* anything is processed (plan §5.2 step 1).

    This table is the audit trail and the replay source. When a student insists
    they paid and the system disagrees, this is where the answer is.
    """

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        VERIFIED = "verified", "Signature verified"
        INVALID_SIGNATURE = "invalid_signature", "Invalid signature"
        PROCESSED = "processed", "Processed"
        DUPLICATE = "duplicate", "Duplicate — ignored"
        FAILED = "failed", "Processing failed"
        IGNORED = "ignored", "Event type not handled"

    gateway = models.CharField(max_length=20, choices=Gateway.choices, db_index=True)
    event_type = models.CharField(max_length=80, blank=True, db_index=True)
    # The gateway's own event id where it provides one; falls back to a hash of
    # the body. Unique, so the same delivery can never be processed twice
    # (plan §5.2 step 3).
    idempotency_key = models.CharField(max_length=128, unique=True, db_index=True)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict, blank=True)
    signature = models.CharField(max_length=255, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    payment = models.ForeignKey(
        Payment, null=True, blank=True, on_delete=models.SET_NULL, related_name="webhook_events"
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["gateway", "status", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.gateway}:{self.event_type} ({self.get_status_display()})"


class Refund(BaseModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        DECLINED = "declined", "Declined"

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    reason = models.TextField(help_text="Required — refunds are answerable to the refund policy (§10).")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED, db_index=True)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="requested_refunds",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="approved_refunds",
    )
    gateway_reference = models.CharField(max_length=128, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Refund {self.currency} {self.amount} on {self.payment.reference}"

    def clean(self):
        if self.amount <= 0:
            raise ValidationError({"amount": "Refund amount must be positive."})
        outstanding = self.payment.amount - self.payment.amount_refunded
        if self.amount > outstanding:
            raise ValidationError(
                {"amount": f"Only {self.payment.currency} {outstanding} remains refundable."}
            )


class ReconciliationRun(BaseModel):
    """Result of the nightly cross-check against each gateway's API (plan §5.3)."""

    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()

    transactions_checked = models.PositiveIntegerField(default=0)
    mismatches_found = models.PositiveIntegerField(default=0)
    payments_corrected = models.PositiveIntegerField(default=0)
    unknown_transactions = models.PositiveIntegerField(
        default=0, help_text="Successful at the gateway with no Payment row here — investigate."
    )
    details = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"{self.gateway} reconciliation {self.started_at:%Y-%m-%d} — {self.mismatches_found} mismatches"


# --- Module-level choice aliases -------------------------------------------
# drf-spectacular's ENUM_NAME_OVERRIDES resolves "module.attribute" only, so
# nested Model.Status.choices paths must be surfaced here. Naming these keeps
# the generated TypeScript client readable ("PaymentStatusEnum", not
# "Status399Enum").
PAYMENT_STATUS_CHOICES = Payment.Status.choices
PAYMENT_PURPOSE_CHOICES = Payment.Purpose.choices
GATEWAY_CHOICES = Gateway.choices
REFUND_STATUS_CHOICES = Refund.Status.choices
WEBHOOK_STATUS_CHOICES = WebhookEvent.Status.choices
