"""Notification dispatch.

Every notification is persisted first and delivered second, so a failed email
provider never means the student was silently never told.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.template import Context, Template

from .models import Notification, NotificationTemplate

logger = logging.getLogger(__name__)


def _render(template_key: str, context: dict, fallback_subject: str, fallback_body: str) -> tuple[str, str]:
    template = NotificationTemplate.objects.filter(key=template_key, is_active=True).first()
    if template is None:
        return fallback_subject, fallback_body
    ctx = Context(context)
    return (
        Template(template.subject or fallback_subject).render(ctx),
        Template(template.body).render(ctx),
    )


def create_notification(
    *,
    recipient,
    category: str,
    body: str,
    subject: str = "",
    channel: str = NotificationTemplate.Channel.IN_APP,
    template_key: str = "",
    action_url: str = "",
    context: dict = None,
    send_now: bool = True,
) -> Notification:
    context = context or {}
    if template_key:
        subject, body = _render(template_key, context, subject, body)

    notification = Notification.objects.create(
        recipient=recipient,
        channel=channel,
        category=category,
        template_key=template_key,
        subject=subject[:200],
        body=body,
        action_url=action_url[:500],
        context=context,
    )
    if send_now and channel != NotificationTemplate.Channel.IN_APP:
        from .tasks import deliver_notification

        deliver_notification.delay(str(notification.pk))
    return notification


# --------------------------------------------------------------------------
# Concrete notifications
# --------------------------------------------------------------------------
def notify_payment_received(payment) -> None:
    if not payment.student_id:
        return
    create_notification(
        recipient=payment.student.user,
        category=Notification.Category.PAYMENT,
        template_key="payment_received",
        subject="Your payment is confirmed",
        body=(
            f"We've received your payment of {payment.currency} {payment.amount}. "
            "Your dashboard is now unlocked."
        ),
        channel=NotificationTemplate.Channel.EMAIL,
        action_url=f"{settings.FRONTEND_BASE_URL}/dashboard",
        context={"reference": payment.reference, "amount": str(payment.amount)},
    )


def notify_document_rejected(item, reason: str) -> None:
    """A rejection always carries its reason (plan §10) — 'rejected' with no
    explanation just generates a support ticket."""
    student = item.checklist.application.student
    create_notification(
        recipient=student.user,
        category=Notification.Category.DOCUMENT,
        template_key="document_rejected",
        subject=f"Action needed: {item.label}",
        body=(
            f"Your upload for '{item.label}' could not be accepted.\n\n"
            f"Reason: {reason}\n\nPlease upload a corrected version."
        ),
        channel=NotificationTemplate.Channel.EMAIL,
        action_url=f"{settings.FRONTEND_BASE_URL}/applications/{item.checklist.application_id}/checklist",
        context={"item": item.label, "reason": reason},
    )


def notify_document_verified(item) -> None:
    student = item.checklist.application.student
    create_notification(
        recipient=student.user,
        category=Notification.Category.DOCUMENT,
        template_key="document_verified",
        subject=f"Verified: {item.label}",
        body=f"'{item.label}' has been verified. Your checklist progress has been updated.",
        action_url=f"{settings.FRONTEND_BASE_URL}/applications/{item.checklist.application_id}/checklist",
        context={"item": item.label},
    )


def notify_application_status(application, note: str = "") -> None:
    create_notification(
        recipient=application.student.user,
        category=Notification.Category.APPLICATION,
        template_key="application_status",
        subject=f"{application.school.name}: {application.get_status_display()}",
        body=f"Your application to {application.school.name} is now: {application.get_status_display()}.\n{note}",
        channel=NotificationTemplate.Channel.EMAIL,
        action_url=f"{settings.FRONTEND_BASE_URL}/applications/{application.pk}",
        context={"school": application.school.name, "status": application.get_status_display()},
    )
