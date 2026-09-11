from rest_framework import serializers

from .models import (
    Gateway,
    Payment,
    PaymentGatewayConfig,
    ReconciliationRun,
    Refund,
    WebhookEvent,
)


class GatewayOptionSerializer(serializers.ModelSerializer):
    """What checkout may offer. Deliberately excludes every credential field."""

    class Meta:
        model = PaymentGatewayConfig
        fields = ("gateway", "label", "currency", "is_test_mode")
        read_only_fields = fields


class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
    """Staff-only. Secrets are write-only: they go in, they never come back out."""

    class Meta:
        model = PaymentGatewayConfig
        fields = (
            "id", "gateway", "label", "is_active", "is_test_mode", "currency",
            "public_key", "secret_key", "encryption_key", "webhook_secret",
            "secret_key_fingerprint", "display_order", "updated_at",
        )
        read_only_fields = ("id", "secret_key_fingerprint", "updated_at")
        extra_kwargs = {
            "secret_key": {"write_only": True, "required": False},
            "encryption_key": {"write_only": True, "required": False},
            "webhook_secret": {"write_only": True, "required": False},
        }

    def validate(self, attrs):
        merged = {**({} if self.instance is None else self.instance.__dict__), **attrs}
        if merged.get("is_active") and not merged.get("secret_key"):
            raise serializers.ValidationError({"secret_key": ["An active gateway needs a secret key."]})
        if (
            merged.get("is_active")
            and merged.get("gateway") != "manual"
            and not merged.get("webhook_secret")
        ):
            raise serializers.ValidationError(
                {"webhook_secret": ["An active gateway needs a webhook secret — webhooks confirm payments."]}
            )
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    purpose_display = serializers.CharField(source="get_purpose_display", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id", "reference", "gateway", "gateway_reference", "amount", "currency",
            "purpose", "purpose_display", "status", "status_display", "status_reason",
            "paid_at", "channel", "confirmed_by_webhook", "confirmed_by_reconciliation",
            "created_at",
        )
        read_only_fields = fields


class StaffPaymentSerializer(PaymentSerializer):
    student_email = serializers.CharField(source="student.user.email", read_only=True, default=None)

    class Meta(PaymentSerializer.Meta):
        fields = (
            *PaymentSerializer.Meta.fields,
            "student_email", "email", "amount_settled", "gateway_fee",
            "reconciled_at", "reconciliation_note",
        )
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    """Note what is absent: an amount. The server decides what things cost."""

    # Derived from the model, never hardcoded. This list was a literal
    # ["paystack", "flutterwave"], so adding a gateway made the checkout page
    # offer an option the API then rejected with a 400 — which is exactly what
    # happened when the mock gateway was added. Whether a gateway can actually
    # be used is decided by PaymentGatewayConfig.active_for(), not by this.
    gateway = serializers.ChoiceField(
        choices=[value for value, _ in Gateway.choices], required=False
    )
    purpose = serializers.ChoiceField(choices=Payment.Purpose.choices, default=Payment.Purpose.ACCESS_FEE)
    application = serializers.UUIDField(required=False, allow_null=True)
    callback_url = serializers.URLField(required=False, allow_blank=True)


class RefundSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(source="payment.reference", read_only=True)

    class Meta:
        model = Refund
        fields = (
            "id", "payment", "payment_reference", "amount", "currency", "reason",
            "status", "gateway_reference", "completed_at", "note", "created_at",
        )
        read_only_fields = ("id", "status", "gateway_reference", "completed_at", "created_at")


class WebhookEventSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(source="payment.reference", read_only=True, default=None)

    class Meta:
        model = WebhookEvent
        fields = (
            "id", "gateway", "event_type", "status", "payment", "payment_reference",
            "source_ip", "attempts", "error", "processed_at", "created_at",
        )
        read_only_fields = fields


class ReconciliationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationRun
        fields = (
            "id", "gateway", "started_at", "finished_at", "window_start", "window_end",
            "transactions_checked", "mismatches_found", "payments_corrected",
            "unknown_transactions", "details", "error",
        )
        read_only_fields = fields
