from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import HasAdminPermission

from .models import ReferralCode, ReferralPayout, ReferralReward, ReferralRewardRule
from .serializers import (
    ReferralEventSerializer,
    ReferralPayoutSerializer,
    ReferralRewardRuleSerializer,
    ReferralRewardSerializer,
    ReferralSummarySerializer,
    RequestPayoutSerializer,
    StaffReferralCodeSerializer,
)
from .services import (
    approve_reward,
    available_balance,
    get_or_create_code_for,
    mark_payout_paid,
    request_payout,
    resolve_code,
    void_reward,
)


class CheckReferralCodeView(APIView):
    """Public: lets the signup form confirm a code before submitting.

    Returns only whether the code works — never who owns it.
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: OpenApiResponse(description="{valid: bool, referrer_first_name: str}")})
    def get(self, request):
        code = resolve_code(request.query_params.get("code", ""))
        if code is None or not code.is_usable:
            return Response({"valid": False})
        return Response({"valid": True, "referrer_first_name": _first_name(code)})


def _first_name(code: ReferralCode) -> str:
    if code.student_id:
        return code.student.user.first_name
    return code.partner_name.split(" ")[0] if code.partner_name else ""


class MyReferralsView(APIView):
    """The referrer's own dashboard (plan §6.3)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Summary, events, rewards and payouts for the caller's code.")})
    def get(self, request):
        student = getattr(request.user, "student_profile", None)
        if student is None:
            return Response({"detail": "Referrals are for student accounts."}, status=status.HTTP_403_FORBIDDEN)

        code = get_or_create_code_for(student)
        summary = {
            "code": code.code,
            "share_url": f"{settings.FRONTEND_BASE_URL}/signup?ref={code.code}",
            "signups": code.signup_count,
            "conversions": code.conversion_count,
            "total_earned": code.total_earned,
            "available_balance": available_balance(code),
            "total_paid_out": code.total_paid_out,
            "currency": settings.DEFAULT_CURRENCY,
        }
        return Response(
            {
                "summary": ReferralSummarySerializer(summary).data,
                "events": ReferralEventSerializer(
                    code.events.select_related("referred_student__user").order_by("-created_at")[:50],
                    many=True,
                ).data,
                # A referrer sees their own rewards, including any held for review.
                "rewards": ReferralRewardSerializer(
                    code.rewards.select_related("event").order_by("-created_at")[:50], many=True
                ).data,
                "payouts": ReferralPayoutSerializer(
                    code.payouts.order_by("-requested_at")[:20], many=True
                ).data,
            }
        )


class RequestPayoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=RequestPayoutSerializer, responses={201: ReferralPayoutSerializer})
    def post(self, request):
        student = getattr(request.user, "student_profile", None)
        if student is None:
            return Response({"detail": "Referrals are for student accounts."}, status=status.HTTP_403_FORBIDDEN)

        serializer = RequestPayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = get_or_create_code_for(student)
        try:
            payout = request_payout(code, **serializer.validated_data)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ReferralPayoutSerializer(payout).data, status=status.HTTP_201_CREATED)


class AdminReferralCodeViewSet(ModelViewSet):
    serializer_class = StaffReferralCodeSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_manage_referrals"
    filterset_fields = ["owner_type", "is_active"]
    search_fields = ["code", "partner_name", "partner_email", "student__user__email"]

    def get_queryset(self):
        return ReferralCode.objects.select_related("student__user").order_by("-created_at")


class AdminRewardRuleViewSet(ModelViewSet):
    serializer_class = ReferralRewardRuleSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_manage_referrals"
    queryset = ReferralRewardRule.objects.all().order_by("-priority")


class AdminRewardViewSet(ModelViewSet):
    """Reward approval queue, including anything the fraud checks flagged."""

    serializer_class = ReferralRewardSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_manage_referrals"
    filterset_fields = ["status", "code"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = ReferralReward.objects.select_related("code", "event__referred_student__user")
        if self.request.query_params.get("flagged") == "true":
            qs = qs.filter(event__is_flagged=True)
        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        try:
            reward = approve_reward(self.get_object(), user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(reward).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        try:
            reward = void_reward(
                self.get_object(), user=request.user, reason=request.data.get("reason", "")
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(reward).data)


class AdminPayoutViewSet(ModelViewSet):
    serializer_class = ReferralPayoutSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_approve_payouts"
    filterset_fields = ["status", "code"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return ReferralPayout.objects.select_related("code").order_by("-requested_at")

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        payout = mark_payout_paid(
            self.get_object(), user=request.user, reference=request.data.get("reference", "")
        )
        return Response(self.get_serializer(payout).data)
