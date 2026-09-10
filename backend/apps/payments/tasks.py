"""
Celery tasks for payments.

Webhook processing happens here, not in the request cycle (plan §5.2 step 4):
the HTTP handler logs the payload and returns 200 immediately, so a slow
database write can never blow the gateway's timeout and trigger a retry storm.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.core import audit

from .gateways.base import GatewayError, get_gateway
from .models import Payment, PaymentGatewayConfig, ReconciliationRun, WebhookEvent

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    autoretry_for=(GatewayError,),
    retry_backoff=True,
    retry_jitter=True,
)
def process_webhook_event_task(self, event_id: str):
    from .services import process_webhook_event

    event = WebhookEvent.objects.filter(pk=event_id).first()
    if event is None:
        logger.error("Webhook event %s vanished before processing", event_id)
        return
    try:
        process_webhook_event(event)
    except Exception as exc:
        event.error = str(exc)[:2000]
        event.status = WebhookEvent.Status.FAILED
        event.save(update_fields=["status", "error", "updated_at"])
        raise self.retry(exc=exc) from exc


@shared_task
def reconcile_gateway(gateway: str, hours: int = 48) -> dict:
    """
    Nightly cross-check of our records against the gateway's (plan §5.3).

    Webhooks do get lost — a network blip on their side, a deploy on ours. This
    is what catches "the student paid but our system never knew" before it
    becomes a support ticket.
    """
    from .services import mark_payment_successful

    config = PaymentGatewayConfig.objects.filter(gateway=gateway, is_active=True).first()
    if config is None:
        return {"gateway": gateway, "skipped": "no active configuration"}

    window_end = timezone.now()
    window_start = window_end - timedelta(hours=hours)
    run = ReconciliationRun.objects.create(
        gateway=gateway, window_start=window_start, window_end=window_end
    )

    adapter = get_gateway(config)
    details: list[dict] = []
    checked = corrected = mismatched = unknown = 0

    try:
        page = 1
        while page <= 20:  # hard stop; a wider window is a manual job
            results = adapter.list_transactions(window_start, window_end, page=page)
            if not results:
                break
            for result in results:
                checked += 1
                payment = Payment.objects.filter(reference=result.reference).first()

                if payment is None:
                    unknown += 1
                    details.append(
                        {
                            "type": "unknown_transaction",
                            "reference": result.reference,
                            "gateway_reference": result.gateway_reference,
                            "amount": str(result.amount),
                        }
                    )
                    continue

                if result.status == "successful" and not payment.is_successful:
                    mismatched += 1
                    if result.amount >= payment.amount:
                        mark_payment_successful(payment, result, source="reconciliation")
                        payment.reconciled_at = timezone.now()
                        payment.reconciliation_note = "Recovered by reconciliation — webhook not received."
                        payment.save(update_fields=["reconciled_at", "reconciliation_note", "updated_at"])
                        corrected += 1
                        details.append(
                            {"type": "recovered", "reference": payment.reference, "amount": str(result.amount)}
                        )
                    else:
                        details.append(
                            {
                                "type": "amount_mismatch",
                                "reference": payment.reference,
                                "expected": str(payment.amount),
                                "received": str(result.amount),
                            }
                        )
                elif result.status != "successful" and payment.is_successful:
                    mismatched += 1
                    details.append(
                        {
                            "type": "status_conflict",
                            "reference": payment.reference,
                            "ours": payment.status,
                            "theirs": result.status,
                        }
                    )
            page += 1
    except GatewayError as exc:
        run.error = str(exc)[:2000]
        logger.exception("Reconciliation failed for %s", gateway)

    run.transactions_checked = checked
    run.mismatches_found = mismatched
    run.payments_corrected = corrected
    run.unknown_transactions = unknown
    run.details = details[:500]
    run.finished_at = timezone.now()
    run.save()

    if mismatched or unknown:
        audit.record(
            "payment_status_change",
            target=run,
            metadata={"mismatches": mismatched, "unknown": unknown, "corrected": corrected},
            target_label=f"{gateway} reconciliation",
        )
    return {
        "gateway": gateway,
        "checked": checked,
        "mismatches": mismatched,
        "corrected": corrected,
        "unknown": unknown,
    }


@shared_task
def reconcile_all_gateways() -> list:
    return [
        reconcile_gateway(config.gateway)
        for config in PaymentGatewayConfig.objects.filter(is_active=True)
    ]


@shared_task
def retry_failed_webhooks(max_age_hours: int = 24) -> int:
    """Re-drive webhook events that failed processing — e.g. the gateway API was
    briefly unreachable during re-verification."""
    cutoff = timezone.now() - timedelta(hours=max_age_hours)
    events = WebhookEvent.objects.filter(
        status=WebhookEvent.Status.FAILED, created_at__gte=cutoff, attempts__lt=10
    )
    for event in events:
        process_webhook_event_task.delay(str(event.pk))
    return events.count()


@shared_task
def expire_stale_payments(hours: int = 24) -> int:
    """Mark long-abandoned checkout attempts, so 'pending' means something."""
    cutoff = timezone.now() - timedelta(hours=hours)
    return Payment.objects.filter(status=Payment.Status.PENDING, created_at__lt=cutoff).update(
        status=Payment.Status.ABANDONED,
        status_reason="No confirmation received within 24 hours.",
        updated_at=timezone.now(),
    )
