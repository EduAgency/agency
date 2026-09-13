"""The pricing endpoints.

One public read, one staff read/write. The public one is unauthenticated and
cacheable because it is what the marketing site, the checkout screen and the
share card all render from — if it needed a token, the price would end up
hardcoded again in whichever surface could not get one.

It returns both a formatted string and the raw amount. The string is what almost
every caller wants and it means the symbol and the grouping are decided once, on
the server; the raw amount is there for the one caller that cannot render a
currency symbol at all.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasAdminPermission
from apps.core import audit
from apps.core.models import AuditLog

from .pricing import UNVERIFIED_DISPLAY, CostEstimate, Pricing


class CostEstimateSerializer(serializers.ModelSerializer):
    """A cost row, as a student sees it.

    ``amount`` is `public_amount`, not the stored figure: a row nobody has
    verified inside the staleness window reports "ask us" and never leaks the old
    number. ``verified_source`` is absent by construction — it is an internal
    note.
    """

    amount = serializers.CharField(source="public_amount", read_only=True)
    is_verified = serializers.SerializerMethodField()

    class Meta:
        model = CostEstimate
        fields = ("id", "label", "amount", "note", "is_verified", "display_order")

    def get_is_verified(self, estimate) -> bool:
        return not estimate.is_stale


class AdminCostEstimateSerializer(serializers.ModelSerializer):
    """The staff view: the stored figure, the source, and whether it has gone stale."""

    public_amount = serializers.CharField(read_only=True)
    is_stale = serializers.BooleanField(read_only=True)

    class Meta:
        model = CostEstimate
        fields = (
            "id", "label", "amount_display", "note",
            "verified_on", "verified_source",
            "display_order", "is_active",
            "public_amount", "is_stale",
            "created_at", "updated_at",
        )
        read_only_fields = ("public_amount", "is_stale", "created_at", "updated_at")


class PricingSerializer(serializers.ModelSerializer):
    formatted_access_fee = serializers.CharField(read_only=True)
    ascii_access_fee = serializers.CharField(read_only=True)
    currency_symbol = serializers.CharField(read_only=True)

    class Meta:
        model = Pricing
        fields = (
            "access_fee_amount", "access_fee_currency", "access_fee_note",
            "estimate_stale_after_days",
            "formatted_access_fee", "ascii_access_fee", "currency_symbol",
            "updated_at",
        )
        read_only_fields = (
            "formatted_access_fee", "ascii_access_fee", "currency_symbol", "updated_at",
        )

    def validate(self, attrs):
        from django.core.exceptions import ValidationError as DjangoValidationError

        instance = Pricing.load()
        for field, value in attrs.items():
            setattr(instance, field, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict or {"detail": exc.messages}) from exc
        return attrs


class PublicPricingView(APIView):
    """Every price the site shows, in one response.

    Unauthenticated on purpose: this is the source of truth for the landing page,
    the checkout screen, the policy pages and the share card. A price behind a
    token is a price that gets hardcoded somewhere it cannot reach.
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: OpenApiResponse(description="Access fee and cost estimates.")})
    def get(self, request):
        pricing = Pricing.load()
        estimates = CostEstimate.objects.filter(is_active=True)
        return Response(
            {
                "access_fee": {
                    "amount": str(pricing.access_fee_amount),
                    "major_units": pricing.access_fee_major_units,
                    "currency": pricing.access_fee_currency,
                    "symbol": pricing.currency_symbol,
                    # What almost every caller should render: the symbol and the
                    # grouping decided once, here.
                    "formatted": pricing.formatted_access_fee,
                    # For the share card, whose renderer has no font outside
                    # basic Latin and silently drops the naira sign.
                    "ascii": pricing.ascii_access_fee,
                    "note": pricing.access_fee_note,
                },
                "costs": CostEstimateSerializer(estimates, many=True).data,
                "unverified_label": UNVERIFIED_DISPLAY,
            }
        )


class AdminPricingView(APIView):
    """Read and write the access fee.

    Behind ``can_manage_payment_config``: this number is what a student is
    charged, so it belongs with the people who already hold the gateway keys and
    not with everyone who can edit a page.
    """

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_manage_payment_config"
    read_admin_permission = "can_view_payments"

    @extend_schema(responses={200: PricingSerializer})
    def get(self, request):
        return Response(PricingSerializer(Pricing.load()).data)

    @extend_schema(request=PricingSerializer, responses={200: PricingSerializer})
    def patch(self, request):
        instance = Pricing.load()
        serializer = PricingSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        before = {field: str(getattr(instance, field)) for field in serializer.validated_data}
        saved = serializer.save()
        after = {field: str(getattr(saved, field)) for field in serializer.validated_data}

        # A price change is a money change. It is audited like one.
        audit.record(
            AuditLog.Action.UPDATE,
            target=saved,
            actor=request.user,
            target_label="Pricing",
            changes=audit.diff(before, after),
        )
        return Response(PricingSerializer(saved).data)


class AdminCostEstimateViewSet(viewsets.ModelViewSet):
    """The cost rows staff maintain.

    Editable by anyone who can publish content as well as by finance: these are
    marketing figures, not our prices, and the person who notices one has gone
    stale is usually the person writing about it.
    """

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_publish_content"
    read_admin_permission = "can_write_content"
    serializer_class = AdminCostEstimateSerializer
    pagination_class = None
    queryset = CostEstimate.objects.all()

    def perform_update(self, serializer):
        before = serializer.instance.amount_display
        estimate = serializer.save()
        if before != estimate.amount_display:
            audit.record(
                AuditLog.Action.UPDATE,
                target=estimate,
                actor=self.request.user,
                target_label=f"Cost estimate: {estimate.label}",
                changes={"amount_display": {"from": before, "to": estimate.amount_display}},
                metadata={"verified_on": str(estimate.verified_on or "")},
            )
