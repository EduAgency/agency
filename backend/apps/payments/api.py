"""
Student- and staff-facing payment endpoints.

The webhook receivers live in views.py and are intentionally separate: they are
unauthenticated, CSRF-exempt and signature-verified, and must not accidentally
inherit DRF authentication behaviour.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.accounts.permissions import HasAdminPermission, is_staff_user

from .models import Payment, PaymentGatewayConfig, ReconciliationRun, Refund, WebhookEvent
from .serializers import (
    GatewayOptionSerializer,
    InitiatePaymentSerializer,
    PaymentGatewayConfigSerializer,
    PaymentSerializer,
    ReconciliationRunSerializer,
    RefundSerializer,
    StaffPaymentSerializer,
    WebhookEventSerializer,
)
from .services import available_gateways, initiate_payment, verify_payment


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


class GatewayOptionsView(APIView):
    """Which gateways are live right now, so checkout offers only those (§5.1)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: GatewayOptionSerializer(many=True)})
    def get(self, request):
        currency = request.query_params.get("currency", "NGN")
        return Response(GatewayOptionSerializer(available_gateways(currency), many=True).data)


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InitiatePaymentSerializer,
        responses={201: OpenApiResponse(description="The pending payment plus the gateway checkout URL.")},
    )
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student = getattr(request.user, "student_profile", None)
        if student is None:
            return Response(
                {"detail": "Only students can make payments."}, status=status.HTTP_403_FORBIDDEN
            )

        application = None
        if application_id := serializer.validated_data.get("application"):
            from apps.applications.models import Application

            application = Application.objects.filter(pk=application_id, student=student).first()

        try:
            payment, checkout_url = initiate_payment(
                student=student,
                purpose=serializer.validated_data["purpose"],
                gateway=serializer.validated_data.get("gateway"),
                application=application,
                callback_url=serializer.validated_data.get("callback_url") or None,
                ip_address=_client_ip(request),
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"payment": PaymentSerializer(payment).data, "checkout_url": checkout_url},
            status=status.HTTP_201_CREATED,
        )


class VerifyPaymentView(APIView):
    """
    Called when the student returns from the gateway.

    This asks the gateway directly rather than believing the redirect, and it
    converges on the same state the webhook produces. If the webhook already
    landed, it is a no-op. A `pending`/`processing` answer here is normal and
    the UI should say "confirming your payment", not "paid".
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer("VerifyPayment", {"reference": serializers.CharField()}),
        responses={200: PaymentSerializer},
    )
    def post(self, request):
        reference = request.data.get("reference", "")
        if not reference:
            return Response({"reference": ["Required."]}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.filter(reference=reference).first()
        if payment is None:
            return Response({"detail": "Unknown payment reference."}, status=status.HTTP_404_NOT_FOUND)
        if not is_staff_user(request.user) and payment.student_id != getattr(
            getattr(request.user, "student_profile", None), "pk", None
        ):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = verify_payment(reference)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(PaymentSerializer(payment).data)


class MyPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PaymentSerializer(many=True)})
    def get(self, request):
        student = getattr(request.user, "student_profile", None)
        if student is None:
            return Response([])
        payments = Payment.objects.filter(student=student).order_by("-created_at")
        return Response(PaymentSerializer(payments, many=True).data)


class AdminPaymentViewSet(ReadOnlyModelViewSet):
    serializer_class = StaffPaymentSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_view_payments"
    filterset_fields = ["status", "gateway", "purpose", "currency", "confirmed_by_webhook"]
    search_fields = ["reference", "gateway_reference", "email", "student__user__email"]
    ordering_fields = ["created_at", "amount", "paid_at"]

    def get_queryset(self):
        return Payment.objects.select_related("student__user").order_by("-created_at")

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        from decimal import Decimal

        from .services import process_refund

        profile = getattr(request.user, "admin_profile", None)
        if not (request.user.is_superuser or (profile and profile.has("can_issue_refunds"))):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)

        payment = self.get_object()
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"reason": ["A refund must record why."]}, status=status.HTTP_400_BAD_REQUEST)

        amount = Decimal(str(request.data.get("amount", payment.amount)))
        refund = Refund(
            payment=payment, amount=amount, currency=payment.currency,
            reason=reason, requested_by=request.user,
        )
        try:
            refund.full_clean(exclude=["status"])
            refund.save()
            process_refund(refund, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if hasattr(exc, "messages") else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(RefundSerializer(refund).data)


class AdminGatewayConfigViewSet(ModelViewSet):
    """
    Gateway credentials (plan §5.1).

    Gated on ``can_manage_payment_config`` specifically, not on staff status —
    a document reviewer must never reach live API keys.
    """

    serializer_class = PaymentGatewayConfigSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_manage_payment_config"
    read_admin_permission = "can_manage_payment_config"
    queryset = PaymentGatewayConfig.objects.all().order_by("display_order")

    def perform_update(self, serializer):
        from apps.core import audit

        instance = serializer.save(updated_by=self.request.user)
        audit.record(
            "gateway_config_change",
            target=instance,
            actor=self.request.user,
            metadata={"changed_fields": list(serializer.validated_data.keys())},
        )


class AdminWebhookEventViewSet(ReadOnlyModelViewSet):
    """The raw webhook log — the answer to 'did they actually pay?' (§5.2)."""

    serializer_class = WebhookEventSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_view_payments"
    filterset_fields = ["gateway", "status", "event_type"]
    search_fields = ["idempotency_key", "payment__reference"]

    def get_queryset(self):
        return WebhookEvent.objects.select_related("payment").order_by("-created_at")

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        from .tasks import process_webhook_event_task

        process_webhook_event_task.delay(str(self.get_object().pk))
        return Response({"detail": "Queued for re-processing."})


class AdminReconciliationViewSet(ReadOnlyModelViewSet):
    serializer_class = ReconciliationRunSerializer
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_view_payments"
    filterset_fields = ["gateway"]
    queryset = ReconciliationRun.objects.all().order_by("-started_at")

    @action(detail=False, methods=["post"], url_path="run")
    def run(self, request):
        from .tasks import reconcile_all_gateways, reconcile_gateway

        gateway = request.data.get("gateway")
        if gateway:
            reconcile_gateway.delay(gateway)
        else:
            reconcile_all_gateways.delay()
        return Response({"detail": "Reconciliation queued."})
