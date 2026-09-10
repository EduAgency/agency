"""Referrals: nothing is earned on a signup, and self-referral is caught."""

from decimal import Decimal

import pytest

from apps.payments.gateways.base import TransactionResult
from apps.payments.services import mark_payment_successful
from apps.referrals.models import ReferralEvent, ReferralReward, ReferralRewardRule
from apps.referrals.services import (
    approve_reward,
    detect_fraud_signals,
    get_or_create_code_for,
    record_conversion,
    record_signup,
    request_payout,
)


@pytest.fixture
def paid_rule(db):
    return ReferralRewardRule.objects.create(
        name="Access fee conversion",
        trigger=ReferralRewardRule.Trigger.PAID,
        calculation=ReferralRewardRule.Calculation.PERCENTAGE,
        amount=Decimal("10.00"),
        max_amount=Decimal("2000.00"),
    )


@pytest.fixture
def confirm(django_capture_on_commit_callbacks):
    """Confirm a payment the way production does.

    Referral conversion is deliberately fired from ``transaction.on_commit`` so a
    rolled-back payment never mints a reward — which means tests have to let the
    commit hooks actually run.
    """

    def _confirm(payment):
        result = TransactionResult(
            reference=payment.reference, gateway_reference="1", status="successful",
            amount=payment.amount, currency=payment.currency,
        )
        with django_capture_on_commit_callbacks(execute=True):
            mark_payment_successful(payment, result)
        payment.refresh_from_db()
        return payment

    return _confirm


@pytest.mark.django_db
class TestAttribution:
    def test_a_student_gets_one_active_code(self, student):
        code = get_or_create_code_for(student)
        assert get_or_create_code_for(student) == code

    def test_signup_alone_earns_nothing(self, student, other_student, paid_rule):
        code = get_or_create_code_for(student)
        record_signup(other_student, code)
        assert ReferralEvent.objects.filter(event_type=ReferralEvent.Type.SIGNUP).count() == 1
        assert ReferralReward.objects.count() == 0

    def test_reward_lands_only_when_the_payment_is_confirmed(
        self, student, other_student, paid_rule, gateway_config, confirm
    ):
        from apps.payments.models import Payment

        code = get_or_create_code_for(student)
        record_signup(other_student, code)

        payment = Payment.objects.create(
            reference=Payment.generate_reference(), gateway="paystack", gateway_config=gateway_config,
            student=other_student, email=other_student.user.email,
            purpose=Payment.Purpose.ACCESS_FEE, amount=Decimal("5000.00"), currency="NGN",
        )
        assert ReferralReward.objects.count() == 0
        confirm(payment)

        reward = ReferralReward.objects.get()
        assert reward.amount == Decimal("500.00")  # 10% of ₦5,000
        assert reward.rule_snapshot["amount"] == "10.00"

    def test_a_duplicate_conversion_does_not_pay_twice(
        self, student, other_student, paid_rule, gateway_config, confirm
    ):
        from apps.payments.models import Payment

        code = get_or_create_code_for(student)
        record_signup(other_student, code)
        payment = Payment.objects.create(
            reference=Payment.generate_reference(), gateway="paystack", gateway_config=gateway_config,
            student=other_student, email=other_student.user.email,
            purpose=Payment.Purpose.ACCESS_FEE, amount=Decimal("5000.00"), currency="NGN",
        )
        confirm(payment)
        record_conversion(payment)  # a redelivered webhook
        assert ReferralReward.objects.count() == 1

    def test_changing_the_rule_later_does_not_rewrite_history(
        self, student, other_student, paid_rule, gateway_config, confirm
    ):
        from apps.payments.models import Payment

        code = get_or_create_code_for(student)
        record_signup(other_student, code)
        payment = Payment.objects.create(
            reference=Payment.generate_reference(), gateway="paystack", gateway_config=gateway_config,
            student=other_student, email=other_student.user.email,
            purpose=Payment.Purpose.ACCESS_FEE, amount=Decimal("5000.00"), currency="NGN",
        )
        confirm(payment)

        paid_rule.amount = Decimal("50.00")
        paid_rule.save()

        reward = ReferralReward.objects.get()
        assert reward.amount == Decimal("500.00")
        assert reward.rule_snapshot["amount"] == "10.00"


@pytest.mark.django_db
class TestFraud:
    def test_self_referral_is_flagged(self, student):
        code = get_or_create_code_for(student)
        reasons = detect_fraud_signals(code, student)
        assert any("Self-referral" in r for r in reasons)

    def test_shared_ip_is_flagged(self, student, other_student, db):
        from django.contrib.auth import get_user_model

        from apps.accounts.models import StudentProfile

        User = get_user_model()
        code = get_or_create_code_for(student)
        record_signup(other_student, code, ip="102.89.1.1")

        third = StudentProfile.objects.get(
            user=User.objects.create_user(email="c@example.com", password="pass-word-1234")
        )
        reasons = detect_fraud_signals(code, third, ip="102.89.1.1")
        assert any("same IP" in r for r in reasons)

    def test_a_flagged_signup_holds_the_reward_for_review(
        self, student, other_student, paid_rule, gateway_config, confirm
    ):
        from apps.payments.models import Payment

        code = get_or_create_code_for(student)
        record_signup(other_student, code, ip="1.2.3.4", fingerprint="device-x")
        # Same device signs up again on the same code.
        event = ReferralEvent.objects.get(event_type=ReferralEvent.Type.SIGNUP)
        event.is_flagged = True
        event.flag_reason = "Same device"
        event.save()

        payment = Payment.objects.create(
            reference=Payment.generate_reference(), gateway="paystack", gateway_config=gateway_config,
            student=other_student, email=other_student.user.email,
            purpose=Payment.Purpose.ACCESS_FEE, amount=Decimal("5000.00"), currency="NGN",
        )
        confirm(payment)
        assert ReferralReward.objects.get().status == ReferralReward.Status.PENDING

    def test_a_large_reward_always_waits_for_a_human(self, student, other_student, gateway_config, confirm):
        from apps.payments.models import Payment

        ReferralRewardRule.objects.create(
            name="Huge", trigger=ReferralRewardRule.Trigger.PAID,
            calculation=ReferralRewardRule.Calculation.FIXED, amount=Decimal("50000.00"),
        )
        code = get_or_create_code_for(student)
        record_signup(other_student, code)
        payment = Payment.objects.create(
            reference=Payment.generate_reference(), gateway="paystack", gateway_config=gateway_config,
            student=other_student, email=other_student.user.email,
            purpose=Payment.Purpose.ACCESS_FEE, amount=Decimal("5000.00"), currency="NGN",
        )
        confirm(payment)
        assert ReferralReward.objects.get().status == ReferralReward.Status.PENDING


@pytest.mark.django_db
class TestPayouts:
    def test_only_approved_rewards_can_be_paid_out(
        self, student, other_student, paid_rule, gateway_config, staff, confirm
    ):
        from django.core.exceptions import ValidationError

        from apps.payments.models import Payment

        code = get_or_create_code_for(student)
        record_signup(other_student, code)
        payment = Payment.objects.create(
            reference=Payment.generate_reference(), gateway="paystack", gateway_config=gateway_config,
            student=other_student, email=other_student.user.email,
            purpose=Payment.Purpose.ACCESS_FEE, amount=Decimal("5000.00"), currency="NGN",
        )
        confirm(payment)
        reward = ReferralReward.objects.get()

        if reward.status == ReferralReward.Status.PENDING:
            approve_reward(reward, user=staff)

        payout = request_payout(code, bank_name="GTB", account_number="0123456789", account_name="Ada")
        assert payout.amount == Decimal("500.00")
        with pytest.raises(ValidationError, match="no approved balance"):
            request_payout(code, bank_name="GTB", account_number="0123456789", account_name="Ada")
