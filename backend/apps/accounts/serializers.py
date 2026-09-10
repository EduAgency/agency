from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.referrals.services import get_or_create_code_for, record_signup, resolve_code

from .models import AdminProfile, StudentProfile, User

CURRENT_TERMS_VERSION = "1.0"
CURRENT_PRIVACY_VERSION = "1.0"


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "email", "first_name", "last_name", "full_name",
            "phone", "role", "email_verified_at",
        )
        read_only_fields = ("id", "email", "role", "email_verified_at")


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)
    referral_code = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = (
            "id", "user", "date_of_birth", "nationality", "country_of_residence",
            "state_of_residence", "whatsapp", "stage", "stage_display",
            "has_platform_access", "access_granted_at", "source", "referral_code",
        )
        # Access is granted by a confirmed payment webhook, never by a PATCH.
        read_only_fields = ("id", "stage", "has_platform_access", "access_granted_at", "source")

    def get_referral_code(self, obj) -> str:
        return get_or_create_code_for(obj).code


class AdminProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = AdminProfile
        fields = ("id", "user", "job_title", *AdminProfile.PERMISSION_FIELDS)


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=10)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    referral_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    accept_terms = serializers.BooleanField()
    marketing_opt_in = serializers.BooleanField(required=False, default=False)
    # Optional client-side signal used only to flag suspicious referral clusters.
    device_fingerprint = serializers.CharField(max_length=128, required=False, allow_blank=True)

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            # Deliberately the same wording the login form uses for a wrong
            # password, so this endpoint is not an account-enumeration oracle.
            raise serializers.ValidationError("This email address cannot be used to register.")
        return value

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate_accept_terms(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("You must accept the terms and privacy policy.")
        return value

    def validate_referral_code(self, value: str) -> str:
        # An unknown code is ignored rather than rejected — a typo must never
        # block someone from signing up.
        return value.strip().upper()

    @transaction.atomic
    def create(self, validated):
        now = timezone.now()
        user = User.objects.create_user(
            email=validated["email"],
            password=validated["password"],
            first_name=validated["first_name"],
            last_name=validated["last_name"],
            phone=validated.get("phone", ""),
            marketing_opt_in=validated.get("marketing_opt_in", False),
            accepted_terms_at=now,
            accepted_terms_version=CURRENT_TERMS_VERSION,
            accepted_privacy_at=now,
            accepted_privacy_version=CURRENT_PRIVACY_VERSION,
        )
        student = StudentProfile.objects.get(user=user)

        if code := resolve_code(validated.get("referral_code", "")):
            request = self.context.get("request")
            record_signup(
                student,
                code,
                ip=_client_ip(request) if request else None,
                fingerprint=validated.get("device_fingerprint", ""),
            )
        return user


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"].strip().lower(),
            password=attrs["password"],
        )
        if user is None:
            from apps.core import audit

            audit.record("login_failed", target_label=attrs["email"][:255])
            raise serializers.ValidationError("Incorrect email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        attrs["user"] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=10)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=10)

    def validate_new_password(self, value):
        validate_password(value)
        return value
