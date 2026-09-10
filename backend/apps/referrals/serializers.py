from rest_framework import serializers

from .models import ReferralCode, ReferralEvent, ReferralPayout, ReferralReward, ReferralRewardRule


class ReferralRewardRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralRewardRule
        fields = (
            "id", "name", "trigger", "calculation", "amount", "currency", "max_amount",
            "owner_type", "min_referrals", "max_referrals", "requires_manual_approval",
            "auto_approve_below", "is_active", "starts_at", "ends_at", "priority",
        )
        read_only_fields = ("id",)


class ReferralEventSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = ReferralEvent
        fields = ("id", "event_type", "student_name", "is_flagged", "created_at")
        read_only_fields = fields

    def get_student_name(self, obj) -> str:
        """Only a first name and initial — a referrer is not entitled to the
        full identity of everyone who used their code."""
        user = obj.referred_student.user
        surname = user.last_name[:1].upper() + "." if user.last_name else ""
        return f"{user.first_name} {surname}".strip() or "A student"


class ReferralRewardSerializer(serializers.ModelSerializer):
    trigger = serializers.CharField(source="event.event_type", read_only=True)

    class Meta:
        model = ReferralReward
        fields = ("id", "amount", "currency", "status", "trigger", "created_at", "approved_at")
        read_only_fields = fields


class ReferralPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralPayout
        fields = (
            "id", "amount", "currency", "status", "bank_name", "account_number",
            "account_name", "requested_at", "paid_at", "payment_reference", "note",
        )
        read_only_fields = ("id", "amount", "currency", "status", "requested_at", "paid_at", "payment_reference")


class ReferralSummarySerializer(serializers.Serializer):
    """The referrer's dashboard: 'X signed up, Y paid, ₦Z earned' (plan §6.3)."""

    code = serializers.CharField()
    share_url = serializers.CharField()
    signups = serializers.IntegerField()
    conversions = serializers.IntegerField()
    total_earned = serializers.DecimalField(max_digits=12, decimal_places=2)
    available_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_paid_out = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()


class RequestPayoutSerializer(serializers.Serializer):
    bank_name = serializers.CharField(max_length=120)
    account_number = serializers.RegexField(r"^\d{10}$", error_messages={
        "invalid": "A Nigerian account number is 10 digits."
    })
    account_name = serializers.CharField(max_length=150)


class StaffReferralCodeSerializer(serializers.ModelSerializer):
    owner_label = serializers.CharField(read_only=True)
    signup_count = serializers.IntegerField(read_only=True)
    conversion_count = serializers.IntegerField(read_only=True)
    total_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ReferralCode
        fields = (
            "id", "code", "owner_type", "owner_label", "student", "partner_name",
            "partner_email", "partner_phone", "is_active", "expires_at", "max_uses",
            "signup_count", "conversion_count", "total_earned", "notes", "created_at",
        )
        read_only_fields = ("id", "created_at")
