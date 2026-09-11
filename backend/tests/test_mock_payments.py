"""Mock payments: that they work, and that they cannot reach production.

The second half matters more than the first. A mock gateway is a switch that
gives away the product for free, so most of these tests are about it refusing
to turn on — and about the payment gate itself being untouched, so that if the
mock adapter were somehow reachable it would still have to go through
`mark_payment_successful` and leave an audit trail behind it.

See docs/enterprise-readiness.md.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.payments import services
from apps.payments.gateways import mock as mock_gateway
from apps.payments.gateways.base import get_gateway
from apps.payments.models import Gateway, Payment, PaymentGatewayConfig


@pytest.fixture
def mock_mode(settings):
    """A development configuration with mock payments switched on."""
    settings.DEBUG = True
    settings.ENVIRONMENT = "local"
    settings.PAYMENTS_MOCK_MODE = True
    return settings


@pytest.fixture
def mock_config(db, mock_mode):
    PaymentGatewayConfig.objects.filter(currency="NGN").update(is_active=False)
    return PaymentGatewayConfig.objects.create(
        gateway=Gateway.MOCK,
        currency="NGN",
        label="Demo checkout (no money moves)",
        is_active=True,
        is_test_mode=True,
    )


class TestItCannotReachProduction:
    """Three independent conditions, each sufficient on its own to refuse."""

    def test_refused_when_environment_is_production(self, settings):
        settings.DEBUG = True
        settings.ENVIRONMENT = "production"
        settings.PAYMENTS_MOCK_MODE = True

        assert mock_gateway.is_enabled() is False

    def test_refused_when_debug_is_off(self, settings):
        settings.DEBUG = False
        settings.ENVIRONMENT = "staging"
        settings.PAYMENTS_MOCK_MODE = True

        assert mock_gateway.is_enabled() is False

    def test_refused_when_the_flag_is_not_set(self, settings):
        settings.DEBUG = True
        settings.ENVIRONMENT = "local"
        settings.PAYMENTS_MOCK_MODE = False

        assert mock_gateway.is_enabled() is False

    def test_the_adapter_will_not_even_construct(self, settings, db):
        settings.DEBUG = False
        settings.ENVIRONMENT = "production"
        settings.PAYMENTS_MOCK_MODE = True
        config = PaymentGatewayConfig(gateway=Gateway.MOCK, currency="NGN")

        # Registering the adapter is safe precisely because of this.
        with pytest.raises(ImproperlyConfigured):
            get_gateway(config)

    def test_enabled_only_in_a_development_configuration(self, mock_mode):
        assert mock_gateway.is_enabled() is True


class TestItDoesNotBypassTheGate:
    def test_the_permission_class_has_no_mock_branch(self):
        """Access is granted by a confirmed payment, with no exceptions."""
        import inspect

        from apps.accounts import permissions

        source = inspect.getsource(permissions.HasPlatformAccess)
        assert "mock" not in source.lower()

    def test_granting_access_has_no_mock_branch(self):
        import inspect

        source = inspect.getsource(services.grant_platform_access)
        assert "mock" not in source.lower()

    def test_a_student_has_no_access_before_paying(self, student, mock_config):
        assert student.has_platform_access is False

    def test_the_mock_gateway_refuses_webhooks(self, mock_config):
        """Otherwise this would be an unauthenticated way to mark payments paid."""
        adapter = get_gateway(mock_config)

        verification = adapter.verify_webhook(b'{"event":"charge.success"}', {})

        assert verification.is_valid is False

    def test_reconciliation_is_told_the_truth(self, mock_config):
        """There is no remote ledger, so no transaction may be claimed to exist."""
        adapter = get_gateway(mock_config)
        assert adapter.list_transactions(None, None) == []


@pytest.mark.django_db
class TestTheFlowItself:
    def test_checkout_sends_the_student_to_the_real_callback(self, student, mock_config):
        payment, url = services.initiate_payment(student=student)

        assert payment.gateway == Gateway.MOCK
        assert payment.status == Payment.Status.PENDING
        # The app's own callback, not an invented fake card form.
        assert "/payment/callback" in url
        assert payment.reference in url

    def test_the_amount_still_comes_from_the_server(self, student, mock_config, settings):
        """A mock gateway must not become a way to pay a different amount."""
        payment, _ = services.initiate_payment(student=student)

        assert payment.amount == Decimal(settings.ACCESS_FEE_AMOUNT)

    def test_verification_approves_and_grants_access(self, student, mock_config):
        payment, _ = services.initiate_payment(student=student)

        verified = services.verify_payment(payment.reference)

        assert verified.status == Payment.Status.SUCCESSFUL
        student.refresh_from_db()
        assert student.has_platform_access is True
        assert student.access_granted_by_payment_id == verified.pk

    def test_access_is_attributed_to_a_payment_not_to_a_flag(self, student, mock_config):
        """The audit trail is the same one a real payment would leave."""
        payment, _ = services.initiate_payment(student=student)
        services.verify_payment(payment.reference)

        student.refresh_from_db()
        assert student.access_granted_at is not None
        assert student.access_granted_by_payment is not None
        assert student.access_granted_by_payment.reference == payment.reference

    def test_verifying_twice_is_idempotent(self, student, mock_config):
        payment, _ = services.initiate_payment(student=student)
        first = services.verify_payment(payment.reference)
        second = services.verify_payment(payment.reference)

        assert first.pk == second.pk
        assert Payment.objects.filter(student=student).count() == 1

    def test_a_paid_student_cannot_start_another_access_payment(self, student, mock_config):
        from django.core.exceptions import ValidationError

        payment, _ = services.initiate_payment(student=student)
        services.verify_payment(payment.reference)

        with pytest.raises(ValidationError, match="already has platform access"):
            services.initiate_payment(student=student)

    def test_the_double_charge_guard_survives_a_stale_instance(self, student, mock_config):
        """The guard reads the database, not the object it was handed.

        `grant_platform_access` updates the row through its own fetch, so any
        caller still holding an older StudentProfile sees has_platform_access
        False. If the check trusted that, the student would be charged twice.
        """
        from django.core.exceptions import ValidationError

        payment, _ = services.initiate_payment(student=student)
        services.verify_payment(payment.reference)

        assert student.has_platform_access is False, "the fixture instance is stale on purpose"
        with pytest.raises(ValidationError, match="already has platform access"):
            services.initiate_payment(student=student)

    def test_the_payment_records_that_no_money_moved(self, student, mock_config):
        payment, _ = services.initiate_payment(student=student)
        verified = services.verify_payment(payment.reference)

        # Anyone reading this row later can tell it was not real money.
        assert verified.channel == "mock"
        assert verified.gateway == Gateway.MOCK
        assert "mock" in verified.status_reason.lower()


@pytest.mark.django_db
class TestTheManagementCommand:
    def test_it_refuses_outside_a_development_configuration(self, settings):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        settings.DEBUG = False
        settings.ENVIRONMENT = "production"
        settings.PAYMENTS_MOCK_MODE = True

        with pytest.raises(CommandError, match="not available"):
            call_command("enable_mock_payments")

    def test_it_activates_exactly_one_gateway(self, mock_mode, db):
        from django.core.management import call_command

        PaymentGatewayConfig.objects.create(
            gateway=Gateway.PAYSTACK, currency="NGN", is_active=True
        )
        call_command("enable_mock_payments")

        active = PaymentGatewayConfig.objects.filter(currency="NGN", is_active=True)
        assert active.count() == 1
        assert active.first().gateway == Gateway.MOCK

    def test_off_deactivates_it_again(self, mock_mode, db):
        from django.core.management import call_command

        call_command("enable_mock_payments")
        call_command("enable_mock_payments", "--off")

        assert not PaymentGatewayConfig.objects.filter(
            gateway=Gateway.MOCK, is_active=True
        ).exists()
