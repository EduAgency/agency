import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from . import providers
from .models import Notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=120, retry_backoff=True)
def deliver_notification(self, notification_id: str):
    """Deliver one notification on one channel.

    Failures are split in two, because treating them alike wastes an hour of
    retries on a message that was never going to send:

    * ``ChannelNotConfigured`` — no credentials, no address, blocked bot,
      number not on WhatsApp. Permanent. Recorded and left alone.
    * anything else — a timeout, a 500, a DNS blip. Retried with backoff.

    Either way the notification row keeps the error, so "why didn't they get
    it?" has an answer.
    """
    notification = Notification.objects.filter(pk=notification_id).first()
    if notification is None or notification.status in {
        Notification.Status.SENT,
        Notification.Status.DELIVERED,
    }:
        return

    notification.attempts += 1

    try:
        providers.send(notification)
    except providers.ChannelNotConfigured as exc:
        notification.status = Notification.Status.FAILED
        notification.error = str(exc)[:2000]
        notification.save(update_fields=["status", "error", "attempts", "updated_at"])
        logger.warning(
            "notification %s undeliverable on %s: %s", notification.pk, notification.channel, exc
        )
        return
    except Exception as exc:
        notification.status = Notification.Status.FAILED
        notification.error = str(exc)[:2000]
        notification.save(update_fields=["status", "error", "attempts", "updated_at"])
        raise self.retry(exc=exc) from exc

    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.error = ""
    notification.save(update_fields=["status", "sent_at", "error", "attempts", "updated_at"])


@shared_task
def send_checklist_nudges(days_idle: int = 7) -> int:
    """Nudge students whose checklist has not moved — the drop-off point plan
    §10 asks us to actually measure and act on."""
    from datetime import timedelta

    from apps.applications.models import Application, ChecklistInstance

    from .services import create_notification

    cutoff = timezone.now() - timedelta(days=days_idle)
    stale = ChecklistInstance.objects.filter(
        updated_at__lt=cutoff,
        percent_complete__lt=100,
        application__status__in=[Application.Status.DRAFT, Application.Status.PREPARING],
        application__archived_at__isnull=True,
    ).select_related("application__student__user", "application__school")

    count = 0
    for checklist in stale:
        create_notification(
            recipient=checklist.application.student.user,
            category=Notification.Category.APPLICATION,
            template_key="checklist_nudge",
            subject=f"Your {checklist.application.school.name} checklist is waiting",
            body=(
                f"You're {checklist.percent_complete}% through your checklist for "
                f"{checklist.application.school.name}. Pick up where you left off."
            ),
            action_url=f"{settings.FRONTEND_BASE_URL}/applications/{checklist.application_id}/checklist",
        )
        count += 1
    return count
