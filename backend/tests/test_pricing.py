"""Prices come from one place, and everything reads it.

The bug this file exists to prevent is specific and was real: the environment
charged ₦50,000 while every frontend page had ₦5,000 typed into it. A student
would have clicked "Pay ₦5,000" and seen a bank alert for ten times that.

So the tests here are mostly about *agreement* — that the gateway, the public
API, the marketing copy and the blog's own house-style scan all move together
when the number changes.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.pricing import UNVERIFIED_DISPLAY, CostEstimate, Pricing


@pytest.fixture(autouse=True)
def fresh_pricing(db):
    """A clean pricing row per test.

    `Pricing.load()` caches, and the cache outlives a transaction rollback — so
    without this, a test that raises the fee raises it for everything after it.
    """
    cache.delete("payments:pricing")
    row = Pricing.load()
    row.access_fee_amount = Decimal("5000.00")
    row.access_fee_currency = "NGN"
    row.save()
    yield row
    cache.delete("payments:pricing")


# ---------------------------------------------------------------------------
# The singleton
# ---------------------------------------------------------------------------


def test_there_is_only_ever_one_pricing_row(db, fresh_pricing):
    second = Pricing(access_fee_amount=Decimal("9999.00"))
    second.save()
    assert Pricing.objects.count() == 1
    assert Pricing.load().access_fee_amount == Decimal("9999.00")


def test_the_pricing_row_cannot_be_deleted(fresh_pricing):
    with pytest.raises(RuntimeError):
        fresh_pricing.delete()


def test_a_zero_fee_is_refused(fresh_pricing):
    fresh_pricing.access_fee_amount = Decimal("0")
    with pytest.raises(ValidationError) as exc:
        fresh_pricing.clean()
    assert "access_fee_amount" in exc.value.message_dict


def test_the_currency_has_to_be_a_code(fresh_pricing):
    fresh_pricing.access_fee_currency = "Naira"
    with pytest.raises(ValidationError) as exc:
        fresh_pricing.clean()
    assert "access_fee_currency" in exc.value.message_dict


def test_saving_clears_the_cache(fresh_pricing):
    assert Pricing.load().access_fee_amount == Decimal("5000.00")
    fresh_pricing.access_fee_amount = Decimal("7500.00")
    fresh_pricing.save()
    assert Pricing.load().access_fee_amount == Decimal("7500.00")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def test_a_round_fee_loses_its_trailing_zeros(fresh_pricing):
    """"₦5,000.00" in marketing copy reads like a receipt."""
    assert fresh_pricing.formatted_access_fee == "₦5,000"
    assert fresh_pricing.ascii_access_fee == "NGN 5,000"


def test_a_fee_with_kobo_keeps_them(fresh_pricing):
    fresh_pricing.access_fee_amount = Decimal("5000.50")
    fresh_pricing.save()
    assert "5,000.50" in fresh_pricing.formatted_access_fee


def test_an_unknown_currency_falls_back_to_its_code(fresh_pricing):
    fresh_pricing.access_fee_currency = "XOF"
    fresh_pricing.save()
    # Correct, if less pretty than a symbol.
    assert fresh_pricing.formatted_access_fee.startswith("XOF ")


# ---------------------------------------------------------------------------
# The payment actually charged
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_checkout(db, settings):
    """A gateway that does not make an HTTP call.

    These two tests are about which number reaches the `Payment` row, not about
    any provider's API, so the mock adapter is the honest way to exercise the
    whole of `initiate_payment` without a network stub.
    """
    from apps.payments.models import Gateway, PaymentGatewayConfig

    settings.DEBUG = True
    settings.ENVIRONMENT = "local"
    settings.PAYMENTS_MOCK_MODE = True
    PaymentGatewayConfig.objects.filter(currency="NGN").update(is_active=False)
    return PaymentGatewayConfig.objects.create(
        gateway=Gateway.MOCK,
        currency="NGN",
        label="Demo checkout (no money moves)",
        is_active=True,
        is_test_mode=True,
    )


def test_the_gateway_charges_the_row_not_the_environment(
    db, student, mock_checkout, settings, fresh_pricing
):
    """The heart of it.

    `ACCESS_FEE_AMOUNT` in the environment is now a seed for the first row only.
    A deployment whose env var says something else must not change what is
    charged, or the two sources are back to disagreeing — which is exactly the
    state this whole change was written to end.
    """
    settings.ACCESS_FEE_AMOUNT = "50000.00"
    fresh_pricing.access_fee_amount = Decimal("5000.00")
    fresh_pricing.save()

    from apps.payments import services

    payment, _ = services.initiate_payment(student=student, gateway=mock_checkout.gateway)
    assert payment.amount == Decimal("5000.00")


def test_raising_the_fee_changes_what_is_charged(db, student, mock_checkout, fresh_pricing):
    fresh_pricing.access_fee_amount = Decimal("7500.00")
    fresh_pricing.save()

    from apps.payments import services

    payment, _ = services.initiate_payment(student=student, gateway=mock_checkout.gateway)
    assert payment.amount == Decimal("7500.00")
    assert payment.purpose == Payment.Purpose.ACCESS_FEE


def test_the_charged_amount_matches_what_the_public_api_advertises(
    api, student, mock_checkout, fresh_pricing, no_throttling
):
    """The assertion that would have caught the original bug.

    The page quoted ₦5,000 while the environment charged ₦50,000. Nothing tied
    the two together, so nothing failed. This does.
    """
    fresh_pricing.access_fee_amount = Decimal("6250.00")
    fresh_pricing.save()

    advertised = api.get("/api/pricing/").data["access_fee"]

    from apps.payments import services

    payment, _ = services.initiate_payment(student=student, gateway=mock_checkout.gateway)

    assert Decimal(advertised["amount"]) == payment.amount
    assert advertised["formatted"] == "₦6,250"


# ---------------------------------------------------------------------------
# Cost estimates and staleness
# ---------------------------------------------------------------------------


@pytest.fixture
def estimate(db):
    return CostEstimate.objects.create(
        label="Proof of funds",
        note="Held before the visa, not spent.",
        amount_display="₦2.5m to ₦4m",
        verified_on=timezone.localdate(),
        verified_source="Embassy guidance, checked by hand",
    )


def test_a_verified_estimate_shows_its_figure(estimate):
    assert estimate.is_stale is False
    assert estimate.public_amount == "₦2.5m to ₦4m"


def test_an_estimate_with_no_figure_shows_ask_us(db):
    row = CostEstimate.objects.create(label="Flights", note="Before a student job pays.")
    assert row.is_stale is True
    assert row.public_amount == UNVERIFIED_DISPLAY


def test_an_estimate_nobody_has_verified_shows_ask_us(db):
    row = CostEstimate.objects.create(
        label="Visa charges", note="Paid to the embassy.", amount_display="₦180,000"
    )
    assert row.public_amount == UNVERIFIED_DISPLAY


def test_an_estimate_goes_stale_by_itself(estimate, fresh_pricing):
    """The mechanism that matters: nobody has to remember to take it down."""
    assert estimate.public_amount == "₦2.5m to ₦4m"

    window = fresh_pricing.estimate_stale_after_days
    estimate.verified_on = timezone.localdate() - timedelta(days=window + 1)
    estimate.save()

    assert estimate.is_stale is True
    assert estimate.public_amount == UNVERIFIED_DISPLAY


def test_the_staleness_window_is_configurable(estimate, fresh_pricing):
    estimate.verified_on = timezone.localdate() - timedelta(days=200)
    estimate.save()
    assert estimate.is_stale is True

    fresh_pricing.estimate_stale_after_days = 365
    fresh_pricing.save()
    assert estimate.is_stale is False


# ---------------------------------------------------------------------------
# The public endpoint
# ---------------------------------------------------------------------------


def test_the_public_endpoint_needs_no_token(api, fresh_pricing, no_throttling):
    """It has to be reachable by everything, or the price gets hardcoded again."""
    response = api.get("/api/pricing/")
    assert response.status_code == 200
    assert response.data["access_fee"]["formatted"] == "₦5,000"
    assert response.data["access_fee"]["ascii"] == "NGN 5,000"
    assert response.data["access_fee"]["currency"] == "NGN"


def test_the_public_endpoint_never_leaks_a_stale_figure(api, estimate, fresh_pricing, no_throttling):
    estimate.verified_on = timezone.localdate() - timedelta(days=999)
    estimate.save()

    body = api.get("/api/pricing/").data
    row = next(c for c in body["costs"] if c["label"] == "Proof of funds")
    assert row["amount"] == UNVERIFIED_DISPLAY
    assert row["is_verified"] is False
    assert "2.5m" not in str(body)


def test_the_public_endpoint_hides_the_internal_source(api, estimate, no_throttling):
    body = api.get("/api/pricing/").data
    assert "Embassy guidance" not in str(body)
    assert "verified_source" not in str(body)


def test_inactive_estimates_are_not_served(api, estimate, no_throttling):
    estimate.is_active = False
    estimate.save()
    assert api.get("/api/pricing/").data["costs"] == []


# ---------------------------------------------------------------------------
# The staff endpoint
# ---------------------------------------------------------------------------


def test_only_someone_who_can_touch_gateway_config_can_change_the_fee(
    api, staff, superadmin, fresh_pricing, no_throttling
):
    """A price is money. It sits with the people who already hold the keys."""
    api.force_authenticate(user=staff)
    response = api.patch("/api/admin/pricing/", {"access_fee_amount": "1.00"}, format="json")
    assert response.status_code == 403
    assert Pricing.load().access_fee_amount == Decimal("5000.00")

    api.force_authenticate(user=superadmin)
    response = api.patch("/api/admin/pricing/", {"access_fee_amount": "7500.00"}, format="json")
    assert response.status_code == 200
    assert Pricing.load().access_fee_amount == Decimal("7500.00")


def test_a_price_change_is_audited(
    api, superadmin, fresh_pricing, no_throttling, django_capture_on_commit_callbacks
):
    from apps.core.models import AuditLog

    api.force_authenticate(user=superadmin)
    with django_capture_on_commit_callbacks(execute=True):
        api.patch("/api/admin/pricing/", {"access_fee_amount": "9000.00"}, format="json")

    entry = AuditLog.objects.filter(target_type="payments.Pricing").first()
    assert entry is not None
    assert entry.changes["access_fee_amount"]["to"] == "9000.00"


def test_the_staff_endpoint_refuses_a_nonsense_fee(api, superadmin, no_throttling):
    api.force_authenticate(user=superadmin)
    response = api.patch("/api/admin/pricing/", {"access_fee_amount": "0"}, format="json")
    assert response.status_code == 400


def test_a_student_cannot_read_the_staff_pricing(as_student, no_throttling):
    assert as_student.get("/api/admin/pricing/").status_code == 403


# ---------------------------------------------------------------------------
# The blog's house-style scan follows the fee
# ---------------------------------------------------------------------------


def test_the_scan_permits_the_current_fee_and_only_that(fresh_pricing):
    from apps.blog import ai

    assert ai.review_flags("The access fee is ₦5,000.").ok
    assert not ai.review_flags("The access fee is ₦7,500.").ok


def test_changing_the_fee_starts_flagging_the_old_one(fresh_pricing):
    """An old article still saying ₦5,000 is a wrong number on a live page."""
    from apps.blog import ai

    fresh_pricing.access_fee_amount = Decimal("7500.00")
    fresh_pricing.save()

    assert not ai.review_flags("The access fee is ₦5,000.").ok
    assert ai.review_flags("The access fee is ₦7,500.").ok


def test_the_house_style_prompt_quotes_the_live_fee(fresh_pricing):
    from apps.blog import ai

    assert "NGN 5,000" in ai.house_style()

    fresh_pricing.access_fee_amount = Decimal("7500.00")
    fresh_pricing.save()
    assert "NGN 7,500" in ai.house_style()
    assert "5,000" not in ai.house_style()
