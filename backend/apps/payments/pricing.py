"""What things cost, as data.

Every price on this site used to be typed in three or four places: an env var
for the gateway, a TypeScript constant for the marketing copy, and the literal
``₦5,000`` inside the checkout button. That is not a style problem. The checkout
page could say one number while the gateway charged another, and nobody would
find out until a student did.

So there is one row, it is the only place a price lives, and everything else —
the payment service, the landing page, the blog's own house-style scan, the share
card — reads from it.

Two models:

* :class:`Pricing` — the singleton. What we charge.
* :class:`CostEstimate` — what the *student* will spend that is not ours: proof
  of funds, visa charges, flights. These are the figures the landing page shows
  under "tuition-free is not the same as free".

The second one carries the more interesting rule. A stale cost estimate is worse
than no estimate, because a student budgets against it and comes unstuck weeks
before an intake. So every row has a ``verified_on`` date, and one that has not
been checked inside :attr:`Pricing.estimate_stale_after_days` stops showing its
number and shows "ask us" instead — automatically, with nobody having to
remember.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel, TimeStampedModel

logger = logging.getLogger(__name__)

CACHE_KEY = "payments:pricing"
CACHE_SECONDS = 300

#: Shown in place of a figure nobody has verified recently. Deliberately an
#: invitation rather than an apology — the honest answer is that it varies.
UNVERIFIED_DISPLAY = "Ask us — this changes"


def _cache_get():
    try:
        return cache.get(CACHE_KEY)
    except Exception:  # pragma: no cover - the cache backend being down
        logger.warning("Pricing cache unavailable; reading from the database.")
        return None


def _cache_set(instance) -> None:
    try:
        cache.set(CACHE_KEY, instance, CACHE_SECONDS)
    except Exception:  # pragma: no cover
        pass


def _cache_clear() -> None:
    try:
        cache.delete(CACHE_KEY)
    except Exception:  # pragma: no cover
        logger.warning("Could not clear the pricing cache.")


class Pricing(TimeStampedModel):
    """What we charge. One row.

    The access fee lives here rather than in an environment variable because it
    is a business decision, not deployment configuration. Changing a price should
    not need a deploy, and more importantly it should not be possible to change
    it in one place and not the other.
    """

    SINGLETON_PK = 1

    # No `default` on the pk: Django forces an INSERT for an unsaved instance
    # whose primary key has one, so a second `Pricing(...).save()` would collide
    # instead of updating the live row.
    id = models.PositiveSmallIntegerField(primary_key=True, editable=False)

    access_fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("5000.00"),
        help_text=(
            "What platform access costs, once. This is the number the gateway charges and the "
            "number every page shows — they cannot disagree."
        ),
    )
    access_fee_currency = models.CharField(
        max_length=3, default="NGN", help_text="ISO 4217, e.g. NGN."
    )
    access_fee_note = models.CharField(
        max_length=200,
        blank=True,
        default="Covers everything from the first shortlist to landing on campus.",
        help_text="One line, shown next to the price.",
    )

    estimate_stale_after_days = models.PositiveSmallIntegerField(
        default=120,
        help_text=(
            "A cost estimate not verified inside this many days stops showing its figure and "
            "shows “ask us” instead. A stale number is worse than none."
        ),
    )

    class Meta:
        verbose_name = "pricing"
        verbose_name_plural = "pricing"

    def __str__(self) -> str:
        return f"{self.formatted_access_fee} access fee"

    def clean(self):
        if self.access_fee_amount <= 0:
            raise ValidationError(
                {"access_fee_amount": "A fee of zero or less is not a fee. Use a positive amount."}
            )
        if len(self.access_fee_currency) != 3 or not self.access_fee_currency.isalpha():
            raise ValidationError(
                {"access_fee_currency": "Three letters, e.g. NGN."}
            )
        self.access_fee_currency = self.access_fee_currency.upper()

    def save(self, *args, **kwargs):
        """Write onto the one row, whatever instance this is.

        An unsaved instance adopts the existing row: it takes its ``created_at``
        (an UPDATE would otherwise null an ``auto_now_add`` column it never
        loaded) and leaves the adding state so Django issues an UPDATE.
        """
        self.pk = self.SINGLETON_PK
        self.access_fee_currency = self.access_fee_currency.upper()
        if self._state.adding:
            existing = (
                type(self).objects.filter(pk=self.SINGLETON_PK).values("created_at").first()
            )
            if existing:
                self.created_at = existing["created_at"]
                self._state.adding = False
                kwargs.pop("force_insert", None)
        super().save(*args, **kwargs)
        _cache_clear()

    def delete(self, *args, **kwargs):
        raise RuntimeError("The pricing row is not deletable. Edit it instead.")

    @classmethod
    def load(cls) -> Pricing:
        """The live pricing.

        Cached, and the cache is an optimisation only: this is on the read path
        of every public page and of checkout, so a Redis outage must cost one
        query rather than the site.

        The first row is seeded from ``ACCESS_FEE_AMOUNT`` / ``ACCESS_FEE_CURRENCY``
        so an existing deployment's env vars carry over exactly once. After that
        the row is the source of truth and the env vars are ignored.
        """
        cached = _cache_get()
        if cached is not None:
            return cached

        from django.conf import settings as django_settings

        instance, _ = cls.objects.get_or_create(
            pk=cls.SINGLETON_PK,
            defaults={
                "access_fee_amount": Decimal(
                    getattr(django_settings, "ACCESS_FEE_AMOUNT", "5000.00")
                ),
                "access_fee_currency": getattr(
                    django_settings, "ACCESS_FEE_CURRENCY", "NGN"
                ).upper(),
            },
        )
        _cache_set(instance)
        return instance

    # -- formatting --------------------------------------------------------

    @property
    def access_fee_major_units(self) -> int | Decimal:
        """The amount without trailing zeros when it has none.

        ``5000`` rather than ``5000.00``, because "₦5,000.00" in marketing copy
        reads like a receipt.
        """
        if self.access_fee_amount == self.access_fee_amount.to_integral_value():
            return int(self.access_fee_amount)
        return self.access_fee_amount

    @property
    def currency_symbol(self) -> str:
        """The symbol, where we know one.

        Only currencies this business actually quotes in. An unknown code falls
        back to the code itself, which is always correct if less pretty.
        """
        return {
            "NGN": "₦",
            "USD": "$",
            "GBP": "£",
            "EUR": "€",
        }.get(self.access_fee_currency, f"{self.access_fee_currency} ")

    @property
    def formatted_access_fee(self) -> str:
        return f"{self.currency_symbol}{self.access_fee_major_units:,}"

    @property
    def ascii_access_fee(self) -> str:
        """For places that cannot render a currency symbol.

        The share-card renderer has no font outside basic Latin and silently
        drops what it cannot draw, so ``₦`` came out as a blank box there.
        """
        return f"{self.access_fee_currency} {self.access_fee_major_units:,}"

    @property
    def allowed_figures(self) -> set[str]:
        """The only figures the blog's house-style scan permits in published copy.

        Derived rather than written down, so changing the fee to ₦7,500 both
        allows "7,500" and starts flagging the old "5,000" that is now wrong
        wherever it survives in an article.
        """
        amount = self.access_fee_major_units
        return {f"{amount:,}", str(amount)}


class CostEstimate(BaseModel):
    """What the student spends that is not ours.

    Shown under "tuition-free is not the same as free", because "free" is the
    word that gets people into trouble: they budget for zero and discover the
    proof-of-funds requirement weeks before an intake.

    ``amount_display`` is free text rather than a number on purpose. These are
    ranges that vary by school and by city — "₦2.5m to ₦4m, held for six months"
    is the honest answer and no decimal field expresses it.
    """

    label = models.CharField(max_length=120, help_text='e.g. "Proof of funds".')
    amount_display = models.CharField(
        max_length=120,
        blank=True,
        help_text=(
            "The figure or range, as you would say it. Leave blank and the row shows "
            "“ask us” — which is the right answer when nobody has checked."
        ),
    )
    note = models.CharField(
        max_length=240, help_text="Why it exists, or who it is paid to. One line."
    )
    verified_on = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "The day somebody last checked this against a real source. Past the staleness "
            "window it stops showing the figure automatically."
        ),
    )
    verified_source = models.CharField(
        max_length=240,
        blank=True,
        help_text="Where the figure came from. Internal — never shown to a student.",
    )
    display_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "label")

    def __str__(self) -> str:
        return f"{self.label}: {self.public_amount}"

    @property
    def is_stale(self) -> bool:
        if not self.amount_display.strip():
            return True
        if self.verified_on is None:
            return True
        window = Pricing.load().estimate_stale_after_days
        return (timezone.localdate() - self.verified_on) > timedelta(days=window)

    @property
    def public_amount(self) -> str:
        """What a student sees.

        The whole point of this property: an unverified or out-of-date figure is
        never shown. Nobody has to remember to take it down.
        """
        return UNVERIFIED_DISPLAY if self.is_stale else self.amount_display.strip()
