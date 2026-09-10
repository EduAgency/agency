import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import Notification, NotificationTemplate

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=120, retry_backoff=True)
def deliver_notification(self, notification_id: str):
    notification = Notification.objects.filter(pk=notification_id).first()
    if notification is None or notification.status in {
        Notification.Status.SENT,
        Notification.Status.DELIVERED,
    }:
        return

    notification.attempts += 1
    try:
        if notification.channel == NotificationTemplate.Channel.EMAIL:
            message = EmailMultiAlternatives(
                subject=notification.subject or "Nasuru",
                body=notification.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[notification.recipient.email],
            )
            message.send(fail_silently=False)
        elif notification.channel in {
            NotificationTemplate.Channel.SMS,
            NotificationTemplate.Channel.WHATSAPP,
        }:
            # Wire a provider (Termii, Twilio) here. Until then the notification
            # is recorded and marked failed rather than silently dropped.
            raise NotImplementedError(f"{notification.channel} delivery is not configured yet.")

        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at", "attempts", "updated_at"])
    except NotImplementedError as exc:
        notification.status = Notification.Status.FAILED
        notification.error = str(exc)
        notification.save(update_fields=["status", "error", "attempts", "updated_at"])
    except Exception as exc:
        notification.status = Notification.Status.FAILED
        notification.error = str(exc)[:2000]
        notification.save(update_fields=["status", "error", "attempts", "updated_at"])
        raise self.retry(exc=exc) from exc


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
            channel=NotificationTemplate.Channel.EMAIL,
            action_url=f"{settings.FRONTEND_BASE_URL}/applications/{checklist.application_id}/checklist",
        )
        count += 1
    return count
