"""Payments: a redirect never confirms money; a webhook signature does, once."""

import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.payments.gateways.base import TransactionResult
from apps.payments.gateways.paystack import PaystackGateway
from apps.payments.models import Payment, WebhookEvent
from apps.payments.services import log_webhook, mark_payment_successful, process_webhook_event


def sign(body: bytes, secret: str = "sk_test_secret") -> dict:
    return {
        "HTTP_X_PAYSTACK_SIGNATURE": hmac.new(secret.encode(), body, hashlib.sha512).hexdigest(),
        "CONTENT_TYPE": "application/json",
    }


def charge_body(reference: str, amount_kobo: int = 500000) -> bytes:
    return json.dumps(
        {
            "event": "charge.success",
            "data": {
                "reference": reference,
                "id": 998877,
                "status": "success",
                "amount": amount_kobo,
                "currency": "NGN",
                "channel": "card",
                "paid_at": "2026-09-01T10:00:00.000Z",
                "fees": 7500,
            },
        }
    ).encode()


@pytest.mark.django_db
class TestSignatureVerification:
    def test_valid_signature_is_accepted(self, gateway_config, access_fee_payment):
        body = charge_body(access_fee_payment.reference)
        event = log_webhook(gateway="paystack", body=body, headers=sign(body))
        assert event.status == WebhookEvent.Status.VERIFIED

    def test_forged_signature_is_rejected_but_still_logged(self, gateway_config, access_fee_payment):
        body = charge_body(access_fee_payment.reference)
        event = log_webhook(
            gateway="paystack", body=body, headers={"HTTP_X_PAYSTACK_SIGNATURE": "deadbeef"}
        )
        assert event.status == WebhookEvent.Status.INVALID_SIGNATURE
        assert event.payload["event"] == "charge.success"  # kept for investigation

    def test_missing_signature_is_rejected(self, gateway_config, access_fee_payment):
        body = charge_body(access_fee_payment.reference)
        event = log_webhook(gateway="paystack", body=body, headers={})
        assert event.status == WebhookEvent.Status.INVALID_SIGNATURE

    def test_body_tampering_invalidates_the_signature(self, gateway_config, access_fee_payment):
        body = charge_body(access_fee_payment.reference)
        headers = sign(body)
        tampered = charge_body(access_fee_payment.reference, amount_kobo=100)
        event = log_webhook(gateway="paystack", body=tampered, headers=headers)
        assert event.status == WebhookEvent.Status.INVALID_SIGNATURE


@pytest.mark.django_db
class TestIdempotency:
    def test_the_same_delivery_twice_creates_one_event(self, gateway_config, access_fee_payment):
        body = charge_body(access_fee_payment.reference)
        headers = sign(body)
        first = log_webhook(gateway="paystack", body=body, headers=headers)
        second = log_webhook(gateway="paystack", body=body, headers=headers)
        assert first.pk == second.pk
        assert WebhookEvent.objects.count() == 1

    def test_processing_twice_does_not_double_grant_access(self, gateway_config, access_fee_payment, student):
        body = charge_body(access_fee_payment.reference)
        event = log_webhook(gateway="paystack", body=body, headers=sign(body))

        verified = TransactionResult(
            reference=access_fee_payment.reference, gateway_reference="998877", status="successful",
            amount=Decimal("5000.00"), currency="NGN", channel="card",
        )
        with patch.object(PaystackGateway, "verify", return_value=verified):
            process_webhook_event(event)
            event.refresh_from_db()
            process_webhook_event(event)

        access_fee_payment.refresh_from_db()
        student.refresh_from_db()
        assert access_fee_payment.status == Payment.Status.SUCCESSFUL
        assert student.has_platform_access is True
        assert student.access_granted_by_payment_id == access_fee_payment.pk


@pytest.mark.django_db
class TestWebhookIsTheSourceOfTruth:
    def test_the_payload_alone_does_not_confirm_a_payment(self, gateway_config, access_fee_payment):
        """Even a correctly signed 'success' is re-verified against the API."""
        body = charge_body(access_fee_payment.reference)
        event = log_webhook(gateway="paystack", body=body, headers=sign(body))

        still_pending = TransactionResult(
            reference=access_fee_payment.reference, gateway_reference="998877",
            status="pending", amount=Decimal("5000.00"), currency="NGN",
        )
        with patch.object(PaystackGateway, "verify", return_value=still_pending) as verify:
            process_webhook_event(event)
        assert verify.called
        access_fee_payment.refresh_from_db()
        assert access_fee_payment.status == Payment.Status.PENDING

    def test_underpayment_does_not_grant_access(self, gateway_config, access_fee_payment, student):
        body = charge_body(access_fee_payment.reference, amount_kobo=100000)
        event = log_webhook(gateway="paystack", body=body, headers=sign(body))

        underpaid = TransactionResult(
            reference=access_fee_payment.reference, gateway_reference="1", status="successful",
            amount=Decimal("1000.00"), currency="NGN",
        )
        with patch.object(PaystackGateway, "verify", return_value=underpaid):
            process_webhook_event(event)

        access_fee_payment.refresh_from_db()
        student.refresh_from_db()
        assert access_fee_payment.status == Payment.Status.FAILED
        assert "Underpaid" in access_fee_payment.status_reason
        assert student.has_platform_access is False

    def test_a_later_failure_never_downgrades_a_confirmed_success(self, gateway_config, access_fee_payment):
        result = TransactionResult(
            reference=access_fee_payment.reference, gateway_reference="1", status="successful",
            amount=Decimal("5000.00"), currency="NGN",
        )
        mark_payment_successful(access_fee_payment, result)

        body = json.dumps({"event": "charge.failed", "data": {
            "reference": access_fee_payment.reference, "status": "failed", "amount": 500000,
            "currency": "NGN", "id": 2}}).encode()
        event = log_webhook(gateway="paystack", body=body, headers=sign(body))
        failed = TransactionResult(
            reference=access_fee_payment.reference, gateway_reference="2", status="failed",
            amount=Decimal("5000.00"), currency="NGN",
        )
        with patch.object(PaystackGateway, "verify", return_value=failed):
            process_webhook_event(event)

        access_fee_payment.refresh_from_db()
        assert access_fee_payment.status == Payment.Status.SUCCESSFUL

    def test_webhook_for_an_unknown_reference_is_flagged_not_swallowed(self, gateway_config):
        body = charge_body("NSR-NOT-A-REAL-REFERENCE")
        event = log_webhook(gateway="paystack", body=body, headers=sign(body))
        process_webhook_event(event)
        event.refresh_from_db()
        assert event.status == WebhookEvent.Status.FAILED
        assert "No payment found" in event.error


@pytest.mark.django_db
class TestGatewayConfig:
    def test_secret_keys_are_encrypted_at_rest(self, gateway_config):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT secret_key FROM payments_paymentgatewayconfig WHERE id = %s",
                [str(gateway_config.pk)],
            )
            stored = cursor.fetchone()[0]
        assert stored != "sk_test_secret"
        assert stored.startswith("gAAAAA")  # Fernet token
        gateway_config.refresh_from_db()
        assert gateway_config.secret_key == "sk_test_secret"

    def test_an_active_gateway_requires_a_webhook_secret(self, db):
        from django.core.exceptions import ValidationError

        from apps.payments.models import Gateway, PaymentGatewayConfig

        config = PaymentGatewayConfig(
            gateway=Gateway.FLUTTERWAVE, currency="NGN", is_active=True, secret_key="sk"
        )
        with pytest.raises(ValidationError, match="webhook secret"):
            config.clean()
