"""
Webhook receivers.

Both endpoints do the same three things and nothing else: read the raw body,
log it, and queue processing. They return 200 fast — a gateway that times out
waiting on us will retry, and retries are how duplicate-processing bugs get
found in production instead of in staging.
"""

from __future__ import annotations

import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Gateway, WebhookEvent
from .services import log_webhook
from .tasks import process_webhook_event_task

logger = logging.getLogger(__name__)

MAX_WEBHOOK_BODY = 512 * 1024  # generous for a payment payload, small enough to bound abuse


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def _receive(request, gateway: str):
    body = request.body
    if len(body) > MAX_WEBHOOK_BODY:
        logger.warning("Oversized %s webhook body rejected (%d bytes)", gateway, len(body))
        return JsonResponse({"status": "rejected"}, status=413)

    event = log_webhook(
        gateway=gateway, body=body, headers=dict(request.META), source_ip=_client_ip(request)
    )

    if event.status == WebhookEvent.Status.INVALID_SIGNATURE:
        # 200, not 401: the payload is already logged for investigation, and an
        # error status just makes the gateway retry something we will keep
        # rejecting. Genuine deliveries are never affected.
        logger.warning("Rejected %s webhook: %s", gateway, event.error)
        return JsonResponse({"status": "rejected"}, status=200)

    if event.status == WebhookEvent.Status.VERIFIED:
        process_webhook_event_task.delay(str(event.pk))

    return JsonResponse({"status": "received"}, status=200)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    return _receive(request, Gateway.PAYSTACK)


@csrf_exempt
@require_POST
def flutterwave_webhook(request):
    return _receive(request, Gateway.FLUTTERWAVE)
