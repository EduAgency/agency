"""Switch on the mock gateway for local development and demos.

    python manage.py enable_mock_payments

Deactivates any other gateway for the same currency so checkout offers exactly
one option, and refuses to run outside a development configuration.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.payments.gateways.mock import GATEWAY_NAME, is_enabled
from apps.payments.models import Gateway, PaymentGatewayConfig


class Command(BaseCommand):
    help = "Enable the mock payment gateway (development and demos only)."

    def add_arguments(self, parser):
        parser.add_argument("--currency", default="NGN")
        parser.add_argument(
            "--off",
            action="store_true",
            help="Deactivate the mock gateway again.",
        )

    def handle(self, *args, **options):
        currency = options["currency"].upper()

        if options["off"]:
            count = PaymentGatewayConfig.objects.filter(
                gateway=GATEWAY_NAME, currency=currency
            ).update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f"Mock gateway deactivated ({count} row(s))."))
            return

        if not is_enabled():
            raise CommandError(
                "Mock payments are not available in this configuration.\n"
                "Set PAYMENTS_MOCK_MODE=True with DJANGO_DEBUG=True and a "
                "non-production ENVIRONMENT, then run this again."
            )

        # One active gateway per currency, so the checkout page is unambiguous.
        others = PaymentGatewayConfig.objects.filter(
            currency=currency, is_active=True
        ).exclude(gateway=GATEWAY_NAME)
        deactivated = others.update(is_active=False)

        config, created = PaymentGatewayConfig.objects.update_or_create(
            gateway=Gateway.MOCK,
            currency=currency,
            defaults={
                "label": "Demo checkout (no money moves)",
                "is_active": True,
                "is_test_mode": True,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Mock gateway {'created' if created else 'updated'} for {currency}."
            )
        )
        if deactivated:
            self.stdout.write(f"Deactivated {deactivated} other gateway(s) for {currency}.")
        self.stdout.write(
            self.style.WARNING(
                "Payments will now be approved without money moving. "
                "Run with --off to undo."
            )
        )
        return str(config.pk)
