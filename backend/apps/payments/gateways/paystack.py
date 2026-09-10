"""Paystack adapter.

Webhook authenticity is an HMAC-SHA512 of the raw request body keyed with the
secret key, sent as X-Paystack-Signature. Comparing against a re-serialised
body would break on whitespace, so the raw bytes are what gets hashed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import requests

from .base import BaseGateway, CheckoutSession, GatewayError, TransactionResult, WebhookVerification

API = "https://api.paystack.co"
TIMEOUT = 20

STATUS_MAP = {
    "success": "successful",
    "failed": "failed",
    "abandoned": "abandoned",
    "reversed": "reversed",
    "ongoing": "processing",
    "pending": "pending",
    "queued": "processing",
}


class PaystackGateway(BaseGateway):
    name = "paystack"
    uses_minor_units = True  # kobo

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.config.secret_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = requests.request(
                method, f"{API}{path}", headers=self._headers, timeout=TIMEOUT, **kwargs
            )
        except requests.RequestException as exc:
            raise GatewayError(f"Paystack request failed: {exc}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise GatewayError(f"Paystack returned non-JSON ({response.status_code}).") from exc
        if not body.get("status"):
            raise GatewayError(body.get("message") or f"Paystack error {response.status_code}.")
        return body.get("data", {})

    def initialize(self, payment, callback_url: str) -> CheckoutSession:
        data = self._request(
            "POST",
            "/transaction/initialize",
            json={
                "email": payment.email,
                "amount": self.to_gateway_amount(payment.amount),
                "currency": payment.currency,
                "reference": payment.reference,
                "callback_url": callback_url,
                "metadata": {
                    "payment_id": str(payment.pk),
                    "purpose": payment.purpose,
                    "student_id": str(payment.student_id) if payment.student_id else None,
                },
            },
        )
        return CheckoutSession(
            authorization_url=data["authorization_url"],
            gateway_reference=data.get("reference", payment.reference),
            raw=data,
        )

    def _to_result(self, data: dict) -> TransactionResult:
        auth = data.get("authorization") or {}
        return TransactionResult(
            reference=data.get("reference", ""),
            gateway_reference=str(data.get("id", "")),
            status=STATUS_MAP.get(str(data.get("status", "")).lower(), "pending"),
            amount=self.from_gateway_amount(data.get("amount")),
            currency=data.get("currency", self.config.currency),
            paid_at=data.get("paid_at") or data.get("paidAt"),
            channel=data.get("channel", "") or "",
            fee=self.from_gateway_amount(data["fees"]) if data.get("fees") is not None else None,
            amount_settled=(
                self.from_gateway_amount(data.get("amount", 0)) - self.from_gateway_amount(data["fees"])
                if data.get("fees") is not None
                else None
            ),
            authorization_code=auth.get("authorization_code", "") or "",
            reason=data.get("gateway_response", "") or "",
            raw=data,
        )

    def verify(self, reference: str) -> TransactionResult:
        return self._to_result(self._request("GET", f"/transaction/verify/{reference}"))

    def verify_webhook(self, body: bytes, headers: dict) -> WebhookVerification:
        signature = headers.get("HTTP_X_PAYSTACK_SIGNATURE", "")
        secret = (self.config.webhook_secret or self.config.secret_key or "").encode()
        expected = hmac.new(secret, body, hashlib.sha512).hexdigest()

        try:
            payload = json.loads(body.decode() or "{}")
        except ValueError:
            payload = {}

        event_type = payload.get("event", "")
        reference = (payload.get("data") or {}).get("reference", "")
        # Paystack does not send an event id, so the key is derived from the
        # body itself — a redelivery of the identical event collapses to one row.
        key = f"paystack:{hashlib.sha256(body).hexdigest()}"

        if not signature:
            return WebhookVerification(False, event_type, reference, key, "Missing signature header.")
        if not hmac.compare_digest(expected, signature):
            return WebhookVerification(False, event_type, reference, key, "Signature mismatch.")
        return WebhookVerification(True, event_type, reference, key)

    def parse_webhook(self, payload: dict) -> TransactionResult | None:
        event = payload.get("event", "")
        data = payload.get("data") or {}
        if not event.startswith("charge.") and not event.startswith("transaction."):
            return None
        result = self._to_result(data)
        if event == "charge.success":
            result.status = "successful"
        return result

    def list_transactions(self, start, end, page: int = 1) -> list[TransactionResult]:
        data = self._request(
            "GET",
            "/transaction",
            params={
                "from": start.isoformat(),
                "to": end.isoformat(),
                "perPage": 100,
                "page": page,
                "status": "success",
            },
        )
        return [self._to_result(item) for item in (data or [])]

    def refund(self, payment, amount: Decimal, reason: str) -> dict:
        return self._request(
            "POST",
            "/refund",
            json={
                "transaction": payment.reference,
                "amount": self.to_gateway_amount(amount),
                "merchant_note": reason[:255],
            },
        )
