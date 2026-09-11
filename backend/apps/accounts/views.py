from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.core import audit

from . import mfa
from .models import EmailVerificationToken, StudentProfile, User
from .permissions import HasAdminPermission
from .serializers import (
    AdminProfileSerializer,
    LoginSerializer,
    MfaCodeSerializer,
    MfaStatusSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SignupSerializer,
    StudentProfileSerializer,
    UserSerializer,
)
from .services import consume_token, issue_jwt, send_password_reset, send_verification_email


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


class SignupView(APIView):
    """Public registration. Rate-limited — an unprotected public signup form
    gets scraped and spammed (plan §10)."""

    permission_classes = [AllowAny]
    throttle_scope = "signup"

    @extend_schema(request=SignupSerializer, responses={201: UserSerializer})
    def post(self, request):
        serializer = SignupSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user)
        audit.record("create", target=user, actor=user, target_label=f"Signup: {user.email}")
        return Response(
            {"user": UserSerializer(user).data, "tokens": issue_jwt(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Second factor, checked only once the password is already correct — so
        # this never reveals whether an account exists or has MFA switched on.
        if mfa.has_mfa(user):
            code = serializer.validated_data.get("otp", "")
            if not code:
                return Response(
                    {
                        "detail": "Enter the code from your authenticator app.",
                        "code": "mfa_required",
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if not mfa.verify(user, code):
                audit.record("mfa_failed", target=user, actor=user)
                return Response(
                    {
                        "detail": "That code is not right or has already been used.",
                        "code": "mfa_invalid",
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        elif mfa.is_required_for(user):
            # A staff account with no second factor can still sign in, but only
            # to reach the enrolment screen. The permission class does the rest.
            audit.record("mfa_missing_on_staff_login", target=user, actor=user)

        user.last_login = timezone.now()
        user.last_login_ip = _client_ip(request)
        user.save(update_fields=["last_login", "last_login_ip"])
        audit.record("login", target=user, actor=user)

        return Response({"user": UserSerializer(user).data, "tokens": issue_jwt(user)})


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=inline_serializer("VerifyEmail", {"token": serializers.CharField()}),
        responses={200: OpenApiResponse(description="Email confirmed.")},
    )
    def post(self, request):
        user = consume_token(
            request.data.get("token", ""), EmailVerificationToken.Purpose.VERIFY_EMAIL
        )
        if user is None:
            return Response(
                {"detail": "This link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not user.email_verified_at:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
        return Response({"detail": "Email confirmed."})


class ResendVerificationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "password_reset"

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Confirmation email sent.")})
    def post(self, request):
        if request.user.email_is_verified:
            return Response({"detail": "Your email is already confirmed."})
        send_verification_email(request.user)
        return Response({"detail": "Confirmation email sent."})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: OpenApiResponse(description="Always the same answer, whether or not the account exists.")},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email=serializer.validated_data["email"].lower()).first()
        if user and user.is_active:
            send_password_reset(user)
        # Always the same answer, whether or not the address exists.
        return Response({"detail": "If that address has an account, a reset link is on its way."})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: OpenApiResponse(description="Password updated.")})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = consume_token(
            serializer.validated_data["token"], EmailVerificationToken.Purpose.RESET_PASSWORD
        )
        if user is None:
            return Response(
                {"detail": "This link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        audit.record("update", target=user, actor=user, target_label="Password reset")
        return Response({"detail": "Password updated. You can sign in now."})


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses={200: OpenApiResponse(description="Password updated.")})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        audit.record("update", target=request.user, actor=request.user, target_label="Password changed")
        return Response({"detail": "Password updated."})


class MeView(APIView):
    """The signed-in user, plus whichever profile their role carries."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="User plus student or admin profile.")})
    def get(self, request):
        user = request.user
        data = {"user": UserSerializer(user).data}
        if user.is_student:
            data["student"] = StudentProfileSerializer(user.student_profile).data
        elif profile := getattr(user, "admin_profile", None):
            data["admin"] = AdminProfileSerializer(profile).data
        return Response(data)

    @extend_schema(request=UserSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class StudentProfileView(APIView):
    """The student's own profile. Staff use the admin viewset instead."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: StudentProfileSerializer})
    def get(self, request):
        return Response(StudentProfileSerializer(request.user.student_profile).data)

    @extend_schema(request=StudentProfileSerializer, responses={200: StudentProfileSerializer})
    def patch(self, request):
        serializer = StudentProfileSerializer(
            request.user.student_profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminStudentViewSet(ModelViewSet):
    """Staff-facing student directory (plan §7.1)."""

    serializer_class = StudentProfileSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_manage_students"
    filterset_fields = ["stage", "has_platform_access", "assigned_counsellor", "source"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "user__phone"]
    ordering_fields = ["created_at", "stage"]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        return (
            StudentProfile.objects.select_related("user", "assigned_counsellor")
            .prefetch_related("applications")
            .order_by("-created_at")
        )

    @action(detail=True, methods=["post"], url_path="erase")
    def erase(self, request, pk=None):
        """NDPR erasure request. Irreversible, restricted, and audited."""
        from .services import erase_student

        profile = getattr(request.user, "admin_profile", None)
        if not (request.user.is_superuser or (profile and profile.has("can_export_data"))):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response(
                {"reason": ["An erasure must record why it was carried out."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = erase_student(self.get_object(), user=request.user, reason=reason)
        return Response(result)


# ---------------------------------------------------------------------------
# Two-factor authentication
# ---------------------------------------------------------------------------


class MfaStatusView(APIView):
    """What this account's second factor looks like right now."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MfaStatusSerializer})
    def get(self, request):
        return Response(
            {
                "enabled": mfa.has_mfa(request.user),
                "required": mfa.is_required_for(request.user),
                "recovery_codes_remaining": mfa.unused_recovery_code_count(request.user),
            }
        )


class MfaEnrolView(APIView):
    """Step one: hand back a secret for the authenticator app.

    Nothing is switched on here. The device stays unconfirmed until the user
    proves they can generate a code from it, so a mistyped secret is caught now
    rather than at the next sign-in.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "mfa"

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Enrolment secret.")})
    def post(self, request):
        try:
            return Response(mfa.begin_enrolment(request.user))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class MfaConfirmView(APIView):
    """Step two: verify the first code, then return the recovery codes once."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "mfa"

    @extend_schema(
        request=MfaCodeSerializer,
        responses={200: OpenApiResponse(description="Recovery codes, shown once.")},
    )
    def post(self, request):
        serializer = MfaCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            codes = mfa.confirm_enrolment(request.user, serializer.validated_data["code"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"recovery_codes": codes})


class MfaRecoveryCodesView(APIView):
    """Mint a fresh set, invalidating the old one. Requires a current code."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "mfa"

    @extend_schema(request=MfaCodeSerializer, responses={200: OpenApiResponse(description="New codes.")})
    def post(self, request):
        serializer = MfaCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not mfa.has_mfa(request.user):
            return Response(
                {"detail": "Two-factor authentication is not switched on."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not mfa.verify(request.user, serializer.validated_data["code"]):
            return Response({"detail": "That code is not right."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"recovery_codes": mfa.regenerate_recovery_codes(request.user)})


class MfaDisableView(APIView):
    """Switch MFA off. Requires a current code, and staff may not."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "mfa"

    @extend_schema(request=MfaCodeSerializer, responses={200: OpenApiResponse(description="Disabled.")})
    def post(self, request):
        serializer = MfaCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if mfa.is_required_for(request.user):
            # Otherwise the requirement is advisory: anyone could turn it off
            # the moment it became inconvenient.
            return Response(
                {"detail": "Staff accounts must keep two-factor authentication switched on."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not mfa.has_mfa(request.user):
            return Response({"detail": "It is already off."}, status=status.HTTP_400_BAD_REQUEST)
        if not mfa.verify(request.user, serializer.validated_data["code"]):
            return Response({"detail": "That code is not right."}, status=status.HTTP_400_BAD_REQUEST)

        mfa.disable(request.user)
        return Response({"detail": "Two-factor authentication is off."})
