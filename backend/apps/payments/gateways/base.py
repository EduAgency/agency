"""Gateway adapter contract.

Paystack and Flutterwave differ in signature scheme, amount units, status
vocabulary and event names. Everything above this layer speaks one language;
each adapter translates.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from decimal import Decimal


class GatewayError(RuntimeError):
    """Gateway call failed. Carries the provider's message where we have one."""


@dataclass
class CheckoutSession:
    authorization_url: str
    gateway_reference: str
    raw: dict


@dataclass
class TransactionResult:
    """A gateway's view of one transaction, normalised."""

    reference: str
    gateway_reference: str
    status: str          # one of Payment.Status values
    amount: Decimal
    currency: str
    paid_at: str | None = None
    channel: str = ""
    fee: Decimal | None = None
    amount_settled: Decimal | None = None
    authorization_code: str = ""
    reason: str = ""
    raw: dict | None = None


@dataclass
class WebhookVerification:
    is_valid: bool
    event_type: str
    reference: str
    idempotency_key: str
    reason: str = ""


class BaseGateway(abc.ABC):
    name: str = ""
    #: Gateways that quote money in minor units (kobo, cents).
    uses_minor_units: bool = True

    def __init__(self, config):
        self.config = config

    # -- money ------------------------------------------------------------
    def to_gateway_amount(self, amount: Decimal) -> int | str:
        return int((amount * 100).to_integral_value()) if self.uses_minor_units else str(amount)

    def from_gateway_amount(self, amount) -> Decimal:
        value = Decimal(str(amount or 0))
        return (value / 100) if self.uses_minor_units else value

    # -- required behaviour ----------------------------------------------
    @abc.abstractmethod
    def initialize(self, payment, callback_url: str) -> CheckoutSession: ...

    @abc.abstractmethod
    def verify(self, reference: str) -> TransactionResult: ...

    @abc.abstractmethod
    def verify_webhook(self, body: bytes, headers: dict) -> WebhookVerification: ...

    @abc.abstractmethod
    def parse_webhook(self, payload: dict) -> TransactionResult | None: ...

    @abc.abstractmethod
    def list_transactions(self, start, end, page: int = 1) -> list[TransactionResult]: ...

    def refund(self, payment, amount: Decimal, reason: str) -> dict:
        raise NotImplementedError(f"{self.name} refunds are not automated yet.")


def get_gateway(config) -> BaseGateway:
    from .flutterwave import FlutterwaveGateway
    from .mock import MockGateway
    from .paystack import PaystackGateway

    # MockGateway refuses to construct outside a development configuration, so
    # registering it here cannot make it reachable in production.
    adapters = {
        "paystack": PaystackGateway,
        "flutterwave": FlutterwaveGateway,
        "mock": MockGateway,
    }
    try:
        return adapters[config.gateway](config)
    except KeyError as exc:
        raise GatewayError(f"No adapter for gateway '{config.gateway}'.") from exc
