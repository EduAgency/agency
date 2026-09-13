"""
Payment orchestration.

The rule this module exists to enforce: **a payment becomes successful only when
a signature-verified webhook (or the reconciliation job) says so** — never
because a browser landed on a success page (plan §5.2).
"""

from __future__ import annotations

import hashlib
import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core import audit

from .gateways.base import GatewayError, get_gateway
from .models import Payment, PaymentGatewayConfig, Refund, WebhookEvent
from .pricing import Pricing

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------
def available_gateways(currency: str = None) -> list[PaymentGatewayConfig]:
    """What the checkout screen may offer right now (plan §5.1)."""
    return list(PaymentGatewayConfig.active_for(currency or settings.DEFAULT_CURRENCY))


@transaction.atomic
def initiate_payment(
    *,
    student,
    purpose: str = Payment.Purpose.ACCESS_FEE,
    gateway: str = None,
    amount: Decimal = None,
    currency: str = None,
    application=None,
    callback_url: str = None,
    ip_address: str = None,
) -> tuple[Payment, str]:
    """Create a pending Payment and hand back the gateway's checkout URL.

    The amount is decided here, server-side, from the `Pricing` row — never
    accepted from the client, or a student could pay ₦1 for access. It is the
    same row the checkout page and the landing page read, so the number on the
    button and the number actually charged cannot drift apart.
    """
    pricing = Pricing.load()
    currency = (currency or pricing.access_fee_currency).upper()
    if amount is None:
        if purpose != Payment.Purpose.ACCESS_FEE:
            raise ValidationError("An amount is required for this payment purpose.")
        amount = pricing.access_fee_amount

    configs = PaymentGatewayConfig.active_for(currency)
    if gateway:
        config = configs.filter(gateway=gateway).first()
        if config is None:
            raise ValidationError(f"{gateway} is not currently accepting {currency} payments.")
    else:
        config = configs.first()
        if config is None:
            raise ValidationError(
                f"No payment gateway is active for {currency}. "
                "An administrator must enable one in Payments → Gateway configuration."
            )

    if purpose == Payment.Purpose.ACCESS_FEE:
        # Read the flag from the database rather than the passed-in instance.
        # This is the check that stops a student being charged twice, and an
        # in-memory StudentProfile can be stale — `grant_platform_access`
        # updates the row through its own `select_for_update` fetch, so a
        # caller holding an older copy would see False and start a second
        # payment. Real money; a single existence query is cheap insurance.
        already_paid = type(student)._default_manager.filter(
            pk=student.pk, has_platform_access=True
        ).exists()
        if already_paid:
            raise ValidationError("This account already has platform access.")

    # Reuse a still-pending attempt rather than littering the table each time a
    # student reopens the checkout page.
    existing = Payment.objects.filter(
        student=student, purpose=purpose, status=Payment.Status.PENDING, gateway=config.gateway
    ).order_by("-created_at").first()

    payment = existing or Payment.objects.create(
        reference=Payment.generate_reference(),
        gateway=config.gateway,
        gateway_config=config,
        student=student,
        application=application,
        email=student.user.email,
        purpose=purpose,
        amount=amount,
        currency=currency,
        initiated_ip=ip_address,
        metadata={"test_mode": config.is_test_mode},
    )

    adapter = get_gateway(config)
    callback = callback_url or f"{settings.FRONTEND_BASE_URL}/payment/callback"
    try:
        session = adapter.initialize(payment, callback)
    except GatewayError as exc:
        payment.status_reason = str(exc)[:255]
        payment.save(update_fields=["status_reason", "updated_at"])
        raise ValidationError(f"Could not start the payment: {exc}") from exc

    if session.gateway_reference and session.gateway_reference != payment.gateway_reference:
        payment.gateway_reference = session.gateway_reference
        payment.save(update_fields=["gateway_reference", "updated_at"])

    audit.record(
        "create", target=payment, actor=student.user,
        metadata={"purpose": purpose, "amount": str(amount), "currency": currency, "gateway": config.gateway},
    )
    return payment, session.authorization_url


# --------------------------------------------------------------------------
# Webhook intake
# --------------------------------------------------------------------------
def log_webhook(*, gateway: str, body: bytes, headers: dict, source_ip: str = None) -> WebhookEvent:
    """Step 1 of §5.2: persist the raw payload *before* doing anything with it.

    Returns the existing row on a redelivery rather than raising, so duplicate
    deliveries are a no-op instead of an error the gateway keeps retrying.
    """
    import json

    try:
        payload = json.loads(body.decode() or "{}")
    except (ValueError, UnicodeDecodeError):
        payload = {"_unparseable": True}

    config = PaymentGatewayConfig.objects.filter(gateway=gateway, is_active=True).first()
    verification = None
    if config:
        try:
            verification = get_gateway(config).verify_webhook(body, headers)
        except GatewayError:
            logger.exception("Webhook verification blew up for %s", gateway)

    key = verification.idempotency_key if verification else f"{gateway}:{hashlib.sha256(body).hexdigest()}"

    safe_headers = {
        k: v for k, v in headers.items()
        if k.startswith("HTTP_") and k not in {"HTTP_AUTHORIZATION", "HTTP_COOKIE"}
    }

    try:
        with transaction.atomic():
            return WebhookEvent.objects.create(
                gateway=gateway,
                event_type=(verification.event_type if verification else payload.get("event", ""))[:80],
                idempotency_key=key[:128],
                payload=payload,
                headers=safe_headers,
                signature=(headers.get("HTTP_X_PAYSTACK_SIGNATURE") or headers.get("HTTP_VERIF_HASH") or "")[:255],
                source_ip=source_ip,
                status=(
                    WebhookEvent.Status.VERIFIED
                    if verification and verification.is_valid
                    else WebhookEvent.Status.INVALID_SIGNATURE
                ),
                error="" if (verification and verification.is_valid) else (
                    verification.reason if verification else "No active gateway config to verify against."
                ),
            )
    except IntegrityError:
        # Step 3 of §5.2 — same delivery twice must never double-credit.
        event = WebhookEvent.objects.get(idempotency_key=key[:128])
        if event.status not in {WebhookEvent.Status.PROCESSED, WebhookEvent.Status.FAILED}:
            event.status = WebhookEvent.Status.DUPLICATE
            event.save(update_fields=["status", "updated_at"])
        return event


@transaction.atomic
def process_webhook_event(event: WebhookEvent) -> WebhookEvent:
    """Steps 2–5 of §5.2. Idempotent: safe to call twice on the same event."""
    event.attempts += 1

    if event.status == WebhookEvent.Status.PROCESSED:
        return event
    if event.status == WebhookEvent.Status.INVALID_SIGNATURE:
        event.save(update_fields=["attempts", "updated_at"])
        return event

    config = PaymentGatewayConfig.objects.filter(gateway=event.gateway, is_active=True).first()
    if config is None:
        event.status = WebhookEvent.Status.FAILED
        event.error = "No active gateway configuration."
        event.save(update_fields=["status", "error", "attempts", "updated_at"])
        return event

    adapter = get_gateway(config)
    result = adapter.parse_webhook(event.payload)
    if result is None or not result.reference:
        event.status = WebhookEvent.Status.IGNORED
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed_at", "attempts", "updated_at"])
        return event

    payment = (
        Payment.objects.select_for_update()
        .filter(reference=result.reference)
        .first()
    )
    if payment is None:
        event.status = WebhookEvent.Status.FAILED
        event.error = f"No payment found for reference {result.reference}."
        event.save(update_fields=["status", "error", "attempts", "updated_at"])
        logger.error("Webhook for unknown payment reference %s", result.reference)
        return event

    event.payment = payment

    # Never trust the webhook body's amount/status on its own — re-verify with
    # the gateway API. Flutterwave's plain shared-hash scheme in particular is
    # not strong enough to authorise money on by itself.
    try:
        verified = adapter.verify(payment.reference)
    except GatewayError as exc:
        event.status = WebhookEvent.Status.FAILED
        event.error = f"Re-verification failed: {exc}"
        event.save(update_fields=["status", "error", "payment", "attempts", "updated_at"])
        raise  # let Celery retry

    if verified.status == "successful":
        expected = payment.amount
        if verified.amount < expected:
            # Underpayment: record it, do not grant access, and flag for a human.
            payment.status = Payment.Status.FAILED
            payment.status_reason = (
                f"Underpaid: expected {payment.currency} {expected}, received {verified.amount}."
            )
            payment.save(update_fields=["status", "status_reason", "updated_at"])
            event.status = WebhookEvent.Status.PROCESSED
            event.error = payment.status_reason
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error", "payment", "processed_at", "attempts", "updated_at"])
            audit.record("payment_status_change", target=payment, metadata={"reason": payment.status_reason})
            return event
        mark_payment_successful(payment, verified, source="webhook")
    elif verified.status in {"failed", "abandoned", "reversed"}:
        _apply_terminal_status(payment, verified)

    event.status = WebhookEvent.Status.PROCESSED
    event.processed_at = timezone.now()
    event.save(update_fields=["status", "payment", "processed_at", "attempts", "updated_at"])
    return event


def _apply_terminal_status(payment: Payment, result) -> None:
    if payment.is_successful:
        return  # a later 'failed' event never downgrades a confirmed success
    previous = payment.status
    payment.status = result.status
    payment.status_reason = (result.reason or "")[:255]
    payment.save(update_fields=["status", "status_reason", "updated_at"])
    audit.record(
        "payment_status_change", target=payment,
        changes={"status": {"from": previous, "to": payment.status}},
    )


@transaction.atomic
def mark_payment_successful(payment: Payment, result, *, source: str = "webhook") -> Payment:
    """Idempotent success transition. Everything downstream hangs off this."""
    if payment.is_successful:
        return payment

    previous = payment.status
    payment.status = Payment.Status.SUCCESSFUL
    payment.gateway_reference = result.gateway_reference or payment.gateway_reference
    payment.channel = result.channel or payment.channel
    payment.authorization_code = result.authorization_code or payment.authorization_code
    payment.amount_settled = result.amount_settled
    payment.gateway_fee = result.fee
    payment.status_reason = (result.reason or "")[:255]
    payment.paid_at = (parse_datetime(result.paid_at) if result.paid_at else None) or timezone.now()
    payment.confirmed_by_webhook = source == "webhook"
    payment.confirmed_by_reconciliation = source == "reconciliation"
    payment.save()

    audit.record(
        "payment_status_change",
        target=payment,
        changes={"status": {"from": previous, "to": payment.status}},
        metadata={"source": source, "amount": str(payment.amount), "currency": payment.currency},
    )

    if payment.purpose == Payment.Purpose.ACCESS_FEE and payment.student_id:
        grant_platform_access(payment)

    # Referral rewards fire on confirmed payment, never on signup (plan §6.2).
    transaction.on_commit(lambda: _fire_referral_conversion(payment))
    transaction.on_commit(lambda: _notify_payment_success(payment))
    return payment


@transaction.atomic
def grant_platform_access(payment: Payment) -> None:
    """Unlock the student dashboard — only ever called from a confirmed payment."""
    from apps.accounts.models import StudentProfile

    student = StudentProfile.objects.select_for_update().get(pk=payment.student_id)
    if student.has_platform_access:
        return
    student.has_platform_access = True
    student.access_granted_at = timezone.now()
    student.access_granted_by_payment = payment
    student.stage = StudentProfile.Stage.PAID
    student.save(
        update_fields=[
            "has_platform_access", "access_granted_at",
            "access_granted_by_payment", "stage", "updated_at",
        ]
    )
    audit.record(
        "update", target=student, actor=None,
        changes={"has_platform_access": {"from": False, "to": True}},
        metadata={"payment_reference": payment.reference},
        target_label=f"Platform access granted to {student.user}",
    )


def _fire_referral_conversion(payment: Payment) -> None:
    try:
        from apps.referrals.services import record_conversion

        record_conversion(payment)
    except Exception:  # pragma: no cover - never let rewards break payments
        logger.exception("Referral conversion failed for payment %s", payment.reference)


def _notify_payment_success(payment: Payment) -> None:
    try:
        from apps.notifications.services import notify_payment_received

        notify_payment_received(payment)
    except Exception:  # pragma: no cover
        logger.exception("Payment notification failed for %s", payment.reference)


# --------------------------------------------------------------------------
# Verification fallback (used by the callback page)
# --------------------------------------------------------------------------
def verify_payment(reference: str) -> Payment:
    """Server-side verification triggered when a student returns from checkout.

    This is a *convenience*, not the authority: it asks the gateway directly
    rather than believing the redirect, and it converges on the same state the
    webhook would produce. If the webhook has already landed, this is a no-op.
    """
    payment = Payment.objects.filter(reference=reference).first()
    if payment is None:
        raise ValidationError("Unknown payment reference.")
    if payment.is_successful:
        return payment

    config = payment.gateway_config or PaymentGatewayConfig.objects.filter(
        gateway=payment.gateway, is_active=True
    ).first()
    if config is None:
        raise ValidationError("This gateway is no longer configured.")

    try:
        result = get_gateway(config).verify(reference)
    except GatewayError as exc:
        raise ValidationError(str(exc)) from exc

    if result.status == "successful" and result.amount >= payment.amount:
        mark_payment_successful(payment, result, source="callback_verification")
    elif result.status in {"failed", "abandoned", "reversed"}:
        _apply_terminal_status(payment, result)
    else:
        payment.status = Payment.Status.PROCESSING
        payment.save(update_fields=["status", "updated_at"])
    return payment


# --------------------------------------------------------------------------
# Refunds
# --------------------------------------------------------------------------
@transaction.atomic
def process_refund(refund: Refund, *, user=None) -> Refund:
    payment = refund.payment
    config = payment.gateway_config or PaymentGatewayConfig.objects.filter(
        gateway=payment.gateway, is_active=True
    ).first()
    if config is None:
        raise ValidationError("This gateway is no longer configured.")

    refund.status = Refund.Status.PROCESSING
    refund.approved_by = user
    refund.save(update_fields=["status", "approved_by", "updated_at"])

    try:
        response = get_gateway(config).refund(payment, refund.amount, refund.reason)
    except (GatewayError, NotImplementedError) as exc:
        refund.status = Refund.Status.FAILED
        refund.note = str(exc)[:500]
        refund.save(update_fields=["status", "note", "updated_at"])
        raise ValidationError(f"Refund failed: {exc}") from exc

    refund.status = Refund.Status.COMPLETED
    refund.completed_at = timezone.now()
    refund.gateway_reference = str(response.get("id", ""))[:128]
    refund.save(update_fields=["status", "completed_at", "gateway_reference", "updated_at"])

    payment.status = (
        Payment.Status.REFUNDED
        if payment.amount_refunded >= payment.amount
        else Payment.Status.PARTIALLY_REFUNDED
    )
    payment.save(update_fields=["status", "updated_at"])

    audit.record(
        "payment_refund", target=payment, actor=user,
        metadata={"amount": str(refund.amount), "reason": refund.reason, "refund_id": str(refund.pk)},
    )
    return refund
