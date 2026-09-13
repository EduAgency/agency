"""What everything currently costs, and what has gone stale.

Exists because a price is the one piece of configuration where being wrong is
expensive in both directions — charge too much and it is a refund and a
complaint; quote too little on a page and it is a chargeback and a reputation.

Run it after any deploy that touches pricing, and on a schedule to catch cost
estimates ageing out. Exits non-zero when something needs attention, so it works
as a CI or cron check as well as a thing a person reads.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.payments.pricing import CostEstimate, Pricing


class Command(BaseCommand):
    help = "Show the live access fee and flag any cost estimate that has gone stale."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit non-zero if any active cost estimate is unverified or stale.",
        )

    def handle(self, *args, **options):
        pricing = Pricing.load()

        self.stdout.write(self.style.MIGRATE_HEADING("Access fee"))
        self.stdout.write(f"  charged     {pricing.ascii_access_fee}")
        self.stdout.write(f"  displayed   {pricing.formatted_access_fee}")
        self.stdout.write(f"  last edited {pricing.updated_at:%Y-%m-%d %H:%M}")

        # The row is the source of truth, but a deployment whose env var says
        # something else is a deployment where somebody expects the env var to
        # work. Worth saying out loud once.
        env_amount = getattr(settings, "ACCESS_FEE_AMOUNT", None)
        if env_amount and str(pricing.access_fee_amount) != str(env_amount):
            self.stdout.write(
                self.style.WARNING(
                    f"  note        ACCESS_FEE_AMOUNT in the environment is {env_amount}, which is "
                    f"NOT what is charged. The database row wins; the env var seeds the first row "
                    f"only. Edit the fee in the admin, or at /api/admin/pricing/."
                )
            )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Cost estimates shown to students"))

        estimates = list(CostEstimate.objects.filter(is_active=True))
        if not estimates:
            self.stdout.write("  (none configured — the costs table on the landing page is empty)")
            return

        stale = 0
        for estimate in estimates:
            if estimate.is_stale:
                stale += 1
                reason = (
                    "no figure set"
                    if not estimate.amount_display.strip()
                    else "never verified"
                    if estimate.verified_on is None
                    else f"last verified {estimate.verified_on}"
                )
                self.stdout.write(
                    self.style.WARNING(f"  ! {estimate.label}: showing “ask us” ({reason})")
                )
            else:
                self.stdout.write(
                    f"  ✓ {estimate.label}: {estimate.amount_display} "
                    f"(verified {estimate.verified_on})"
                )

        self.stdout.write("")
        if stale:
            message = (
                f"{stale} of {len(estimates)} estimates are showing “ask us” instead of a figure. "
                f"That is the safe state, not a broken one — but each is a question a student is "
                f"asking that the page could answer."
            )
            self.stdout.write(self.style.WARNING(message))
            if options["strict"]:
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS("Every estimate is verified and in date."))
