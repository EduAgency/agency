"""Flutterwave adapter (v3).

Two differences from Paystack that matter:

* Flutterwave authenticates webhooks with a shared "secret hash" sent verbatim
  in the ``verif-hash`` header — a plain equality check, not an HMAC. It is a
  weaker scheme, so this adapter always re-verifies the transaction against the
  API before any money is treated as received.
* Amounts are quoted in major units, not kobo.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import requests

from .base import BaseGateway, CheckoutSession, GatewayError, TransactionResult, WebhookVerification

API = "https://api.flutterwave.com/v3"
TIMEOUT = 20

STATUS_MAP = {
    "successful": "successful",
    "completed": "successful",
    "failed": "failed",
    "cancelled": "abandoned",
    "abandoned": "abandoned",
    "pending": "pending",
}


class FlutterwaveGateway(BaseGateway):
    name = "flutterwave"
    uses_minor_units = False

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
            raise GatewayError(f"Flutterwave request failed: {exc}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise GatewayError(f"Flutterwave returned non-JSON ({response.status_code}).") from exc
        if body.get("status") != "success":
            raise GatewayError(body.get("message") or f"Flutterwave error {response.status_code}.")
        return body.get("data", {})

    def initialize(self, payment, callback_url: str) -> CheckoutSession:
        body = {
            "tx_ref": payment.reference,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "redirect_url": callback_url,
            "customer": {
                "email": payment.email,
                "name": str(payment.student.user) if payment.student_id else "",
            },
            "meta": {
                "payment_id": str(payment.pk),
                "purpose": payment.purpose,
            },
            "customizations": {"title": "Nasuru", "description": payment.get_purpose_display()},
        }
        try:
            response = requests.post(
                f"{API}/payments", headers=self._headers, json=body, timeout=TIMEOUT
            )
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise GatewayError(f"Flutterwave checkout failed: {exc}") from exc
        if data.get("status") != "success":
            raise GatewayError(data.get("message") or "Flutterwave checkout failed.")
        return CheckoutSession(
            authorization_url=data["data"]["link"],
            gateway_reference=payment.reference,
            raw=data,
        )

    def _to_result(self, data: dict) -> TransactionResult:
        return TransactionResult(
            reference=data.get("tx_ref", "") or "",
            gateway_reference=str(data.get("id", "")),
            status=STATUS_MAP.get(str(data.get("status", "")).lower(), "pending"),
            amount=Decimal(str(data.get("amount", 0) or 0)),
            currency=data.get("currency", self.config.currency),
            paid_at=data.get("created_at"),
            channel=data.get("payment_type", "") or "",
            fee=Decimal(str(data["app_fee"])) if data.get("app_fee") is not None else None,
            amount_settled=(
                Decimal(str(data["amount_settled"])) if data.get("amount_settled") is not None else None
            ),
            reason=data.get("processor_response", "") or data.get("narration", "") or "",
            raw=data,
        )

    def verify(self, reference: str) -> TransactionResult:
        """Verify by *our* reference — the id Flutterwave assigns is not known
        until after the transaction exists."""
        data = self._request("GET", "/transactions/verify_by_reference", params={"tx_ref": reference})
        return self._to_result(data)

    def verify_webhook(self, body: bytes, headers: dict) -> WebhookVerification:
        supplied = headers.get("HTTP_VERIF_HASH", "")
        expected = self.config.webhook_secret or ""

        try:
            payload = json.loads(body.decode() or "{}")
        except ValueError:
            payload = {}

        data = payload.get("data") or {}
        event_type = payload.get("event", "") or payload.get("event.type", "")
        reference = data.get("tx_ref", "") or payload.get("txRef", "") or ""
        event_id = data.get("id") or payload.get("id")
        key = (
            f"flutterwave:{event_id}:{event_type}"
            if event_id
            else f"flutterwave:{hashlib.sha256(body).hexdigest()}"
        )

        if not expected:
            return WebhookVerification(False, event_type, reference, key, "No secret hash configured.")
        if not supplied:
            return WebhookVerification(False, event_type, reference, key, "Missing verif-hash header.")
        if not hmac.compare_digest(expected, supplied):
            return WebhookVerification(False, event_type, reference, key, "Secret hash mismatch.")
        return WebhookVerification(True, event_type, reference, key)

    def parse_webhook(self, payload: dict) -> TransactionResult | None:
        data = payload.get("data") or {}
        if not data:
            return None
        return self._to_result(data)

    def list_transactions(self, start, end, page: int = 1) -> list[TransactionResult]:
        data = self._request(
            "GET",
            "/transactions",
            params={
                "from": start.strftime("%Y-%m-%d"),
                "to": end.strftime("%Y-%m-%d"),
                "page": page,
                "status": "successful",
            },
        )
        return [self._to_result(item) for item in (data or [])]

    def refund(self, payment, amount: Decimal, reason: str) -> dict:
        if not payment.gateway_reference:
            raise GatewayError("Flutterwave refunds need the gateway transaction id.")
        return self._request(
            "POST",
            f"/transactions/{payment.gateway_reference}/refund",
            json={"amount": str(amount), "comments": reason[:255]},
        )
