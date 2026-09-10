"""
Referral attribution, reward calculation and fraud checks (plan §6).

Two rules drive everything here:
  1. A reward is earned on a **confirmed payment**, never on a signup alone.
  2. The rule that produced a reward is snapshotted onto it, so changing the
     programme later never rewrites history.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core import audit

from .models import ReferralCode, ReferralEvent, ReferralPayout, ReferralReward, ReferralRewardRule

logger = logging.getLogger(__name__)

# Above this, a reward always waits for a human even if the rule would
# auto-approve it — a coordinated fake-signup run should not be able to drain
# the reward pool overnight (§6.2).
MANUAL_REVIEW_THRESHOLD = Decimal("20000.00")


def get_or_create_code_for(student) -> ReferralCode:
    existing = student.referral_codes.filter(is_active=True).first()
    if existing:
        return existing
    return ReferralCode.objects.create(
        code=ReferralCode.generate_code(student.user.get_short_name()),
        owner_type=ReferralCode.OwnerType.STUDENT,
        student=student,
    )


def resolve_code(raw_code: str) -> ReferralCode | None:
    if not raw_code:
        return None
    return ReferralCode.objects.filter(code__iexact=raw_code.strip(), is_active=True).first()


# --------------------------------------------------------------------------
# Fraud checks
# --------------------------------------------------------------------------
def detect_fraud_signals(code: ReferralCode, student, *, ip: str = None, fingerprint: str = "") -> list[str]:
    """Return human-readable reasons this attribution looks wrong.

    Deliberately cheap and conservative: it flags for review, it does not
    silently discard. A false positive costs a minute of staff time; a false
    negative costs money.
    """
    reasons: list[str] = []

    if code.student_id and code.student_id == student.pk:
        reasons.append("Self-referral: the code belongs to this student.")

    if code.student_id and code.student.user.email.lower() == student.user.email.lower():
        reasons.append("Referrer and referee share an email address.")

    if ip:
        same_ip = ReferralEvent.objects.filter(
            code=code, signup_ip=ip, event_type=ReferralEvent.Type.SIGNUP
        ).exclude(referred_student=student)
        if same_ip.exists():
            reasons.append(f"{same_ip.count()} earlier signup(s) on this code from the same IP.")
        if code.student_id and code.student.user.last_login_ip == ip:
            reasons.append("Signup IP matches the referrer's last login IP.")

    if fingerprint:
        same_device = ReferralEvent.objects.filter(
            code=code, device_fingerprint=fingerprint
        ).exclude(referred_student=student)
        if same_device.exists():
            reasons.append("Another referral on this code came from the same device.")

    recent = ReferralEvent.objects.filter(
        code=code,
        event_type=ReferralEvent.Type.SIGNUP,
        created_at__gte=timezone.now() - timedelta(hours=1),
    ).count()
    if recent >= 10:
        reasons.append(f"{recent} signups on this code in the last hour.")

    return reasons


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------
@transaction.atomic
def record_signup(student, code: ReferralCode, *, ip: str = None, fingerprint: str = "") -> ReferralEvent | None:
    """Attribute a new student to a code. Earns nothing on its own."""
    if not code.is_usable:
        return None

    flags = detect_fraud_signals(code, student, ip=ip, fingerprint=fingerprint)
    try:
        event = ReferralEvent.objects.create(
            code=code,
            event_type=ReferralEvent.Type.SIGNUP,
            referred_student=student,
            signup_ip=ip,
            device_fingerprint=fingerprint[:128],
            is_flagged=bool(flags),
            flag_reason="; ".join(flags)[:255],
        )
    except IntegrityError:
        return ReferralEvent.objects.get(
            code=code, referred_student=student, event_type=ReferralEvent.Type.SIGNUP
        )

    if student.referred_by_code_id is None:
        student.referred_by_code = code
        student.source = student.Source.REFERRAL
        student.save(update_fields=["referred_by_code", "source", "updated_at"])

    _maybe_reward(event)
    return event


@transaction.atomic
def record_conversion(payment) -> ReferralReward | None:
    """Called from the payment success path — the only place a fee reward is earned."""
    if payment.purpose != payment.Purpose.ACCESS_FEE or not payment.student_id:
        return None

    student = payment.student
    code = student.referred_by_code
    if code is None:
        return None

    try:
        event = ReferralEvent.objects.create(
            code=code,
            event_type=ReferralEvent.Type.PAID,
            referred_student=student,
            payment=payment,
        )
    except IntegrityError:
        return None  # already converted — duplicate webhook, nothing to do

    signup = ReferralEvent.objects.filter(
        code=code, referred_student=student, event_type=ReferralEvent.Type.SIGNUP
    ).first()
    if signup and signup.is_flagged:
        event.is_flagged = True
        event.flag_reason = signup.flag_reason
        event.save(update_fields=["is_flagged", "flag_reason", "updated_at"])

    return _maybe_reward(event, payment_amount=payment.amount)


@transaction.atomic
def record_milestone(application, event_type: str) -> ReferralReward | None:
    """Offer / enrolment milestones, for tiered programmes."""
    student = application.student
    code = student.referred_by_code
    if code is None:
        return None
    try:
        event = ReferralEvent.objects.create(
            code=code, event_type=event_type, referred_student=student
        )
    except IntegrityError:
        return None
    return _maybe_reward(event)


# --------------------------------------------------------------------------
# Rewards
# --------------------------------------------------------------------------
def find_matching_rule(code: ReferralCode, trigger: str) -> ReferralRewardRule | None:
    """Highest-priority live rule whose tier window contains this code's
    conversion count."""
    conversions = code.conversion_count
    candidates = ReferralRewardRule.objects.filter(trigger=trigger, is_active=True).order_by(
        "-priority", "-min_referrals"
    )
    for rule in candidates:
        if not rule.is_live():
            continue
        if rule.owner_type and rule.owner_type != code.owner_type:
            continue
        if conversions < rule.min_referrals:
            continue
        if rule.max_referrals is not None and conversions >= rule.max_referrals:
            continue
        return rule
    return None


def _maybe_reward(event: ReferralEvent, payment_amount: Decimal = None) -> ReferralReward | None:
    rule = find_matching_rule(event.code, event.event_type)
    if rule is None:
        return None

    amount = rule.compute_amount(payment_amount)
    if amount <= 0:
        return None

    needs_review = (
        event.is_flagged
        or rule.requires_manual_approval
        or amount >= MANUAL_REVIEW_THRESHOLD
        or (rule.auto_approve_below is not None and amount >= rule.auto_approve_below)
    )

    reward = ReferralReward.objects.create(
        code=event.code,
        event=event,
        rule=rule,
        rule_snapshot=rule.snapshot(),
        amount=amount,
        currency=rule.currency,
        status=ReferralReward.Status.PENDING if needs_review else ReferralReward.Status.APPROVED,
        approved_at=None if needs_review else timezone.now(),
    )
    audit.record(
        "create", target=reward,
        metadata={
            "trigger": event.event_type,
            "amount": str(amount),
            "flagged": event.is_flagged,
            "needs_review": needs_review,
        },
        target_label=f"Referral reward {amount} to {event.code.code}",
    )
    return reward


@transaction.atomic
def approve_reward(reward: ReferralReward, *, user) -> ReferralReward:
    if reward.status != ReferralReward.Status.PENDING:
        raise ValidationError("Only pending rewards can be approved.")
    reward.status = ReferralReward.Status.APPROVED
    reward.approved_by = user
    reward.approved_at = timezone.now()
    reward.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    audit.record("update", target=reward, actor=user, changes={"status": {"from": "pending", "to": "approved"}})
    return reward


@transaction.atomic
def void_reward(reward: ReferralReward, *, user, reason: str) -> ReferralReward:
    if reward.status == ReferralReward.Status.PAID:
        raise ValidationError("A paid reward cannot be voided — raise a recovery instead.")
    if not reason.strip():
        raise ValidationError("Voiding a reward requires a reason.")
    previous = reward.status
    reward.status = ReferralReward.Status.VOID
    reward.void_reason = reason[:255]
    reward.save(update_fields=["status", "void_reason", "updated_at"])
    audit.record(
        "update", target=reward, actor=user,
        changes={"status": {"from": previous, "to": "void"}}, metadata={"reason": reason},
    )
    return reward


# --------------------------------------------------------------------------
# Payouts
# --------------------------------------------------------------------------
def available_balance(code: ReferralCode) -> Decimal:
    total = ReferralReward.objects.filter(
        code=code, status=ReferralReward.Status.APPROVED, payout__isnull=True
    ).aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0.00")


@transaction.atomic
def request_payout(code: ReferralCode, *, bank_name: str, account_number: str, account_name: str) -> ReferralPayout:
    rewards = list(
        ReferralReward.objects.select_for_update().filter(
            code=code, status=ReferralReward.Status.APPROVED, payout__isnull=True
        )
    )
    if not rewards:
        raise ValidationError("There is no approved balance to pay out yet.")

    total = sum((r.amount for r in rewards), Decimal("0.00"))
    payout = ReferralPayout.objects.create(
        code=code,
        amount=total,
        currency=rewards[0].currency,
        bank_name=bank_name,
        account_number=account_number,
        account_name=account_name,
    )
    ReferralReward.objects.filter(pk__in=[r.pk for r in rewards]).update(payout=payout)
    audit.record(
        "referral_payout", target=payout,
        metadata={"amount": str(total), "rewards": len(rewards)},
        target_label=f"Payout requested by {code.code}",
    )
    return payout


@transaction.atomic
def mark_payout_paid(payout: ReferralPayout, *, user, reference: str = "") -> ReferralPayout:
    payout.status = ReferralPayout.Status.PAID
    payout.paid_at = timezone.now()
    payout.payment_reference = reference[:100]
    payout.approved_by = user
    payout.save(update_fields=["status", "paid_at", "payment_reference", "approved_by", "updated_at"])
    payout.rewards.update(status=ReferralReward.Status.PAID, updated_at=timezone.now())
    audit.record(
        "referral_payout", target=payout, actor=user,
        metadata={"amount": str(payout.amount), "reference": reference},
    )
    return payout
