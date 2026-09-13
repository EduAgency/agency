"""Site-wide blog settings, as one editable row.

Everything here is a *decision* rather than a mechanism: how many articles the
homepage shows, whether comments need approval, how long an auto-excerpt runs.
Those are things the person running the agency changes because a page felt too
long — and in Django settings that means a deploy per change, which in practice
means they never change and the defaults quietly become policy.

Singleton, enforced by pinning the primary key. "Which settings row is live?" is
not a question anybody should have to answer.

See docs/blog-system.md §1.
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel

logger = logging.getLogger(__name__)

CACHE_KEY = "blog:settings"
CACHE_SECONDS = 300


def _cache_get():
    try:
        return cache.get(CACHE_KEY)
    except Exception:  # pragma: no cover - a cache backend being down
        logger.warning("Blog settings cache unavailable; reading from the database.")
        return None


def _cache_set(instance) -> None:
    try:
        cache.set(CACHE_KEY, instance, CACHE_SECONDS)
    except Exception:  # pragma: no cover
        pass


def _cache_clear() -> None:
    """Best-effort invalidation.

    If this fails the worst case is that editors see the old value for up to
    CACHE_SECONDS, which is a far smaller problem than a save that raises.
    """
    try:
        cache.delete(CACHE_KEY)
    except Exception:  # pragma: no cover
        logger.warning("Could not clear the blog settings cache.")


class ExcerptSource(models.TextChoices):
    MANUAL = "manual", "Only what the writer types"
    AUTO = "auto", "Always derived from the body"
    MANUAL_THEN_AUTO = "manual_then_auto", "Use what the writer types, otherwise derive one"


class ListingLayout(models.TextChoices):
    FEATURED = "featured", "One lead article, then a grid"
    GRID = "grid", "Equal cards in a grid"
    LIST = "list", "Compact rows"


class BlogSettings(TimeStampedModel):
    """The one row. Read it with :meth:`load`, never by querying directly."""

    SINGLETON_PK = 1

    # No `default` on purpose. Django forces an INSERT for an unsaved instance
    # whose primary key has one, which made a second `BlogSettings(...).save()`
    # collide instead of updating the existing row. Without the default, `save()`
    # pins the pk itself and Django tries an UPDATE first.
    id = models.PositiveSmallIntegerField(primary_key=True, editable=False)

    # --- Listing and homepage ----------------------------------------------
    posts_per_page = models.PositiveSmallIntegerField(
        default=12,
        help_text="Articles per page on /blog. The staff table's 25 is too many for cards.",
    )
    homepage_show_latest = models.BooleanField(
        default=True,
        help_text="Show the guides section on the landing page. Renders nothing when there are no live posts.",
    )
    homepage_article_count = models.PositiveSmallIntegerField(
        default=3, help_text="How many articles the landing page shows."
    )
    homepage_section_title = models.CharField(
        max_length=80,
        default="Questions people ask us before they pay",
        help_text="The heading above the landing page's guides.",
    )
    listing_layout = models.CharField(
        max_length=10, choices=ListingLayout.choices, default=ListingLayout.FEATURED
    )
    show_reading_time = models.BooleanField(default=True)
    show_author_byline = models.BooleanField(default=True)
    show_published_date = models.BooleanField(
        default=True,
        help_text="Some evergreen guides read better undated. An editorial call, not a bug.",
    )
    related_post_count = models.PositiveSmallIntegerField(default=3)

    # --- Excerpts -----------------------------------------------------------
    excerpt_source = models.CharField(
        max_length=20, choices=ExcerptSource.choices, default=ExcerptSource.MANUAL_THEN_AUTO
    )
    excerpt_length = models.PositiveSmallIntegerField(
        default=240, help_text="Characters, for a derived excerpt."
    )
    excerpt_required_to_publish = models.BooleanField(
        default=True,
        help_text="It is the meta description fallback and the listing card, so a blank one costs twice.",
    )
    read_more_label = models.CharField(max_length=40, default="Read the guide")

    # --- Featured images ----------------------------------------------------
    featured_image_required = models.BooleanField(
        default=False, help_text="Turn on once the design looks broken without one."
    )
    featured_image_aspect = models.CharField(
        max_length=10,
        default="16:9",
        help_text="Used to crop listings consistently so one tall image cannot break a row.",
    )
    show_featured_on_listing = models.BooleanField(default=True)
    show_featured_on_detail = models.BooleanField(default=True)
    default_featured_image = models.ImageField(
        upload_to="blog/settings/",
        null=True,
        blank=True,
        max_length=500,
        help_text="Fallback when a post has no image. Blank means the typographic card.",
    )

    # --- Comments -----------------------------------------------------------
    comments_enabled = models.BooleanField(default=True, help_text="The master switch.")
    comments_require_approval = models.BooleanField(
        default=True,
        help_text="Off means finding out what got published from a reader. Leave it on.",
    )
    comments_require_email = models.BooleanField(
        default=True, help_text="Never shown publicly — it is how a reply reaches the asker."
    )
    comments_allow_replies = models.BooleanField(default=True)
    comments_close_after_days = models.PositiveSmallIntegerField(
        default=0, help_text="0 means never. An old thread attracting only spam is a real thing."
    )
    comments_notify_staff = models.BooleanField(default=True)
    comments_max_links = models.PositiveSmallIntegerField(
        default=1, help_text="More than this is flagged as spam, not rejected — a real question can carry a link."
    )
    comments_min_seconds = models.PositiveSmallIntegerField(
        default=4, help_text="A form submitted faster than a person can type was not typed."
    )
    comments_blocklist = models.TextField(
        blank=True, help_text="One phrase per line. A match flags the comment for review."
    )
    comments_per_hour_per_ip = models.PositiveSmallIntegerField(default=5)

    # --- Authors ------------------------------------------------------------
    author_pages_enabled = models.BooleanField(
        default=True, help_text="Publish /blog/author/<slug> pages for authors who opt in."
    )
    show_author_bio_on_article = models.BooleanField(default=True)

    # --- SEO ----------------------------------------------------------------
    meta_title_template = models.CharField(
        max_length=120,
        default="{title} — {site}",
        help_text="Placeholders: {title}, {site}. So renaming the brand is not an edit per post.",
    )
    default_meta_description = models.CharField(
        max_length=180, blank=True, help_text="Used where a page has neither description nor excerpt."
    )
    default_og_image = models.ImageField(
        upload_to="blog/settings/",
        null=True,
        blank=True,
        max_length=500,
        help_text="Share card fallback. Blank uses the generated card.",
    )
    twitter_site = models.CharField(
        max_length=40, blank=True, help_text="@handle, for share card attribution."
    )
    google_site_verification = models.CharField(
        max_length=120, blank=True, help_text="Emitted as a meta tag. Search Console needs it."
    )
    bing_site_verification = models.CharField(max_length=120, blank=True)
    analytics_measurement_id = models.CharField(
        max_length=40,
        blank=True,
        help_text=(
            "Stored but NOT yet rendered. Loading a tracker needs a cookie-consent banner and a "
            "privacy-policy update first — see docs/blog-system.md §8."
        ),
    )
    feed_full_text = models.BooleanField(
        default=False, help_text="A full-text feed is an invitation to scrape the whole blog."
    )
    feed_item_count = models.PositiveSmallIntegerField(default=20)
    sitemap_include_authors = models.BooleanField(default=True)
    noindex_tag_pages = models.BooleanField(
        default=True,
        help_text="Tag pages are usually a subset of a category page; indexing both splits the ranking.",
    )

    class Meta:
        verbose_name = "blog settings"
        verbose_name_plural = "blog settings"

    def __str__(self) -> str:
        return "Blog settings"

    def clean(self):
        if self.excerpt_length < 80:
            raise ValidationError(
                {"excerpt_length": "Under 80 characters is not an excerpt, it is a fragment."}
            )
        if "{title}" not in self.meta_title_template:
            raise ValidationError(
                {"meta_title_template": "The template has to contain {title}."}
            )
        if self.twitter_site and not self.twitter_site.startswith("@"):
            raise ValidationError({"twitter_site": "Start it with @."})
        if ":" not in self.featured_image_aspect:
            raise ValidationError({"featured_image_aspect": 'Write it as a ratio, e.g. "16:9".'})

    def save(self, *args, **kwargs):
        """Write onto the one row, whatever instance this is.

        ``BlogSettings(posts_per_page=6).save()`` has to mean "set that on the
        live row", not "insert a second one". So an unsaved instance adopts the
        existing row: it takes its ``created_at`` (an UPDATE would otherwise null
        an ``auto_now_add`` column it never loaded) and drops out of the adding
        state so Django issues an UPDATE.
        """
        self.pk = self.SINGLETON_PK
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
        raise RuntimeError("The blog settings row is not deletable. Edit it instead.")

    @classmethod
    def load(cls) -> BlogSettings:
        """The live settings.

        Cached rather than fetched per request because the public listing reads
        it on every page view and it changes a handful of times a year. The cache
        is invalidated on save, so an editor never sees a stale value.

        The cache is an optimisation and nothing more. Every public blog page now
        goes through here, so a Redis outage must cost one query — not the whole
        blog. Both the read and the write are therefore allowed to fail silently.
        """
        cached = _cache_get()
        if cached is not None:
            return cached
        instance, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        _cache_set(instance)
        return instance

    # -- derived -----------------------------------------------------------

    @property
    def blocklist_phrases(self) -> list[str]:
        return [line.strip().lower() for line in self.comments_blocklist.splitlines() if line.strip()]

    def format_meta_title(self, title: str, site_name: str) -> str:
        return self.meta_title_template.format(title=title, site=site_name)

    @property
    def featured_aspect_ratio(self) -> float:
        """Width / height, for the CSS `aspect-ratio` the frontend applies."""
        try:
            width, height = (float(part) for part in self.featured_image_aspect.split(":", 1))
            return width / height if height else 16 / 9
        except (TypeError, ValueError, ZeroDivisionError):
            return 16 / 9
