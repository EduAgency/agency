"""Create the pricing row and the four cost estimates the landing page shows.

The four labels come from the copy that used to be hardcoded in the frontend's
``company.ts``. Their **figures do not**, and that is deliberate: each row is
created with a blank ``amount_display`` and no ``verified_on``, so the page shows
"ask us" until somebody has actually checked a number against a current source
and recorded where it came from.

Which is the honest state. Nobody has checked them.

Idempotent — existing rows are left exactly as they are, so running this after
someone has filled the figures in does not wipe their work.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.payments.pricing import CostEstimate, Pricing

ESTIMATES = [
    (
        "Proof of funds",
        "Held before the visa, not spent — but you must be able to show it, "
        "often for months beforehand.",
        10,
    ),
    ("Visa and health charges", "Paid to the embassy, never to us.", 20),
    ("Flights and first month", "Before any student job starts paying.", 30),
    (
        "Language or English test",
        "Only where the school actually requires one — many do not.",
        40,
    ),
]


class Command(BaseCommand):
    help = "Create the pricing row and the student-cost estimates, without inventing any figures."

    @transaction.atomic
    def handle(self, *args, **options):
        existed = Pricing.objects.exists()
        pricing = Pricing.load()
        self.stdout.write(
            f"  pricing   {pricing.ascii_access_fee} "
            + ("(already configured)" if existed else "(seeded from the environment)")
        )

        created = 0
        for label, note, order in ESTIMATES:
            _, made = CostEstimate.objects.get_or_create(
                label=label,
                defaults={
                    "note": note,
                    "display_order": order,
                    # No figure and no verification date on purpose: the row
                    # shows "ask us" until a person checks one and says where
                    # they got it. A seeded number would look researched.
                    "amount_display": "",
                    "verified_on": None,
                },
            )
            if made:
                created += 1
                self.stdout.write(f"  estimate  {label} (no figure yet — shows “ask us”)")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"{created} estimate(s) created. Fill in the figures at "
                f"/staff/pricing or in the Django admin — each needs a source and a date."
            )
        )
        self.stdout.write("Run `make pricing` any time to see what has gone stale.")
