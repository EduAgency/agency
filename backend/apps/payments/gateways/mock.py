"""A gateway that approves everything, for local development and demos.

The point of this module is what it does *not* do: it does not bypass the
payment gate. There is no "if mock mode, pretend they paid" branch in the
permission class, the checkout view or `grant_platform_access`. Instead this is
a gateway adapter like Paystack and Flutterwave, and a mock payment travels the
same road a real one does — `initiate_payment`, a checkout page, a verified
result, `mark_payment_successful`, `grant_platform_access`, the referral
conversion, the receipt.

That matters for two reasons. The demo exercises the real code path, so a bug
in it shows up before production rather than after. And the invariant the whole
payments design rests on — *access is granted by a confirmed payment, never by
anything else* — stays literally true, with no exception to remember.

Turning it on is deliberately hard to do by accident:

* ``PAYMENTS_MOCK_MODE`` must be explicitly true, and
* the adapter refuses to load at all when ``ENVIRONMENT`` is production or
  ``DEBUG`` is off, whatever that flag says.

See ``tests/test_mock_payments.py``, which asserts both.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from .base import BaseGateway, CheckoutSession, TransactionResult, WebhookVerification

logger = logging.getLogger(__name__)

GATEWAY_NAME = "mock"


def is_enabled() -> bool:
    """Whether mock payments are allowed to run in this configuration at all.

    Three independent conditions, all required. A single environment variable
    left set in the wrong place should never be enough to switch off payment on
    a live site.
    """
    if getattr(settings, "ENVIRONMENT", "local") == "production":
        return False
    if not getattr(settings, "DEBUG", False):
        return False
    return bool(getattr(settings, "PAYMENTS_MOCK_MODE", False))


def assert_enabled() -> None:
    if not is_enabled():
        raise ImproperlyConfigured(
            "The mock payment gateway is not available in this configuration. "
            "It requires DEBUG=True, ENVIRONMENT other than 'production', and "
            "PAYMENTS_MOCK_MODE=True."
        )


class MockGateway(BaseGateway):
    """Approves every payment, without contacting anything."""

    name = GATEWAY_NAME

    def __init__(self, config):
        assert_enabled()
        super().__init__(config)

    def initialize(self, payment, callback_url: str) -> CheckoutSession:
        """Send the student straight to the callback the real gateways use.

        No fake card form: the checkout page belongs to the gateway, and
        inventing one here would be a screen that exists in no real deployment.
        The student lands on the app's own callback, which verifies server-side
        exactly as it would after a real redirect.
        """
        assert_enabled()
        logger.warning(
            "MOCK PAYMENT: approving %s %s for %s without contacting a gateway.",
            payment.currency,
            payment.amount,
            payment.email,
        )
        separator = "&" if "?" in callback_url else "?"
        return CheckoutSession(
            authorization_url=f"{callback_url}{separator}reference={payment.reference}&mock=1",
            gateway_reference=f"mock_{payment.reference}",
            raw={"mock": True},
        )

    def verify(self, reference: str) -> TransactionResult:
        """Always successful, for the exact amount the server recorded.

        The amount comes from the Payment row rather than being invented, so
        the `result.amount >= payment.amount` check in `verify_payment` is a
        real comparison rather than one that trivially passes.
        """
        assert_enabled()
        from apps.payments.models import Payment

        payment = Payment.objects.filter(reference=reference).first()
        amount = payment.amount if payment else Decimal("0")
        currency = payment.currency if payment else settings.ACCESS_FEE_CURRENCY

        return TransactionResult(
            reference=reference,
            gateway_reference=f"mock_{reference}",
            status="successful",
            amount=amount,
            currency=currency,
            paid_at=timezone.now().isoformat(),
            channel="mock",
            fee=Decimal("0"),
            amount_settled=amount,
            authorization_code="",
            reason="Approved by the mock gateway (no money moved).",
            raw={"mock": True},
        )

    def verify_webhook(self, body: bytes, headers: dict) -> WebhookVerification:
        """There is no real webhook to verify, and none is accepted.

        Returning "valid" here would create an unauthenticated endpoint that
        marks payments successful. Mock payments converge through callback
        verification instead.
        """
        return WebhookVerification(
            is_valid=False,
            event_type="",
            reference="",
            idempotency_key="",
            reason="The mock gateway does not accept webhooks.",
        )

    def parse_webhook(self, payload: dict) -> TransactionResult | None:
        """Unreachable: `verify_webhook` never returns valid, so nothing gets here."""
        return None

    def list_transactions(self, start, end, page: int = 1) -> list[TransactionResult]:
        """Nightly reconciliation has nothing to reconcile against.

        An empty list is correct rather than convenient: there is no remote
        ledger, so claiming any transaction exists there would be a lie that
        reconciliation would then act on.
        """
        return []

    def refund(self, payment, amount: Decimal, reason: str = ""):
        assert_enabled()
        return TransactionResult(
            reference=payment.reference,
            gateway_reference=f"mock_refund_{payment.reference}",
            status="refunded",
            amount=amount,
            currency=payment.currency,
            paid_at=timezone.now().isoformat(),
            reason=reason or "Refunded by the mock gateway.",
            raw={"mock": True},
        )
