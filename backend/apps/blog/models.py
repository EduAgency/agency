"""The blog.

Two rules shape this app, and most of the model design follows from them.

**A slug is a promise.** Once a post is published its URL is in search results,
in WhatsApp messages and on other people's sites. So `slug` is frozen at first
publish and changing it afterwards is refused rather than silently breaking
every inbound link. Retitling is allowed; re-slugging is a redirect, not an
edit.

**Nothing publishes without a person.** Claude can outline, draft and suggest
metadata (see `ai.py`), but `published_by` must be a real staff user and the
model refuses to publish without one. AI involvement is recorded on the post
rather than hidden — for a brand whose whole argument is "we do not make claims
you cannot check", quietly passing generated text off as first-hand experience
would be the same failure in a different costume.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import BaseModel

from . import rendering
from .authors import AuthorProfile  # noqa: F401  (re-exported; Django discovers it here)
from .comments import Comment  # noqa: F401
from .settings_model import BlogSettings, ExcerptSource  # noqa: F401

#: Average adult reading speed. Used for the "6 min read" label, which is a
#: courtesy to the reader rather than a metric anyone should optimise.
WORDS_PER_MINUTE = 225


class Category(BaseModel):
    """A small, curated set — not a folksonomy.

    Categories are part of the URL structure and the site's information
    architecture, so they are created deliberately by staff. Tags are where
    the long tail goes.
    """

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.TextField(
        blank=True, help_text="Shown on the category page and used as its meta description."
    )
    display_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "name")
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:90]
        super().save(*args, **kwargs)


class Tag(BaseModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:70]
        super().save(*args, **kwargs)


class PostQuerySet(models.QuerySet):
    def live(self):
        """Published, and past its publish time.

        Scheduling is enforced here rather than by a cron job flipping a flag,
        so a post can never be visible early because a worker was down.
        """
        return self.filter(status=Post.Status.PUBLISHED, published_at__lte=timezone.now())


class Post(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class AiInvolvement(models.TextChoices):
        NONE = "none", "Written entirely by a person"
        OUTLINE = "outline", "Outline suggested by AI"
        DRAFT = "draft", "First draft by AI, edited by a person"
        EDIT = "edit", "Human draft, AI-assisted editing"

    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=220,
        unique=True,
        help_text="Frozen once published — changing it breaks every inbound link.",
    )
    excerpt = models.TextField(
        max_length=400,
        blank=True,
        help_text="Shown on listings and used as the meta description when none is set.",
    )
    body = models.TextField(blank=True, help_text="Markdown.")
    # Rendered and sanitised on save, not per request: the public list and
    # detail endpoints are the hottest pages on the site and there is no reason
    # for them to re-parse Markdown for every visitor.
    body_html = models.TextField(blank=True, editable=False)
    toc = models.JSONField(default=list, blank=True, editable=False)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    published_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="A future time schedules the post; it appears by itself when that time passes.",
    )

    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="authored_posts",
    )
    #: Who took responsibility for it going live. Required to publish.
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="published_posts",
    )

    hero_image = models.ImageField(upload_to="blog/heroes/", null=True, blank=True, max_length=500)
    hero_alt = models.CharField(
        max_length=200, blank=True,
        help_text="What the image shows. Required if there is an image — a decorative hero is not a thing on an article.",
    )
    hero_caption = models.CharField(
        max_length=300, blank=True,
        help_text="Shown under the image. Optional, and a different job from the alt text.",
    )
    hero_credit = models.CharField(
        max_length=160, blank=True, help_text="Who the image belongs to. Fill this in if it is not ours."
    )

    comments_closed = models.BooleanField(
        default=False, help_text="Close comments on this post regardless of the site setting."
    )

    # --- SEO -------------------------------------------------------------
    meta_title = models.CharField(
        max_length=70, blank=True, help_text="Falls back to the title. Search engines truncate near 60."
    )
    meta_description = models.CharField(
        max_length=180, blank=True, help_text="Falls back to the excerpt. Truncated near 155."
    )
    canonical_url = models.URLField(
        blank=True, help_text="Only when this article was published elsewhere first."
    )
    noindex = models.BooleanField(
        default=False, help_text="Keep out of search results. Thin or duplicate pages only."
    )
    focus_keyword = models.CharField(
        max_length=120, blank=True,
        help_text="What this article should be found for. One phrase, not a list.",
    )

    # --- Provenance ------------------------------------------------------
    ai_involvement = models.CharField(
        max_length=10, choices=AiInvolvement.choices, default=AiInvolvement.NONE
    )
    ai_notes = models.TextField(
        blank=True, help_text="What was generated and what the editor changed. Internal."
    )

    # The house-style scan is deliberately blunt, and blunt rules have a real
    # false-positive class: an article that WARNS readers about "guaranteed
    # visa" language necessarily contains the phrase. Refusing to publish that
    # article would be the guard defeating the thing it exists to protect.
    #
    # So the scan can be overridden — but only in writing, and the reason is
    # copied into the audit record on publish. An editor who cannot write down
    # why the phrase belongs there has just discovered it does not.
    style_override_reason = models.TextField(
        blank=True,
        help_text=(
            "Why the house-style flags on this post are acceptable — for example, it quotes "
            "the claims it is warning readers about. Leave blank and the flags block publishing."
        ),
    )

    reading_minutes = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ("-published_at", "-created_at")
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self) -> str:
        return self.title

    # -- derived ----------------------------------------------------------

    @property
    def is_live(self) -> bool:
        return (
            self.status == self.Status.PUBLISHED
            and self.published_at is not None
            and self.published_at <= timezone.now()
        )

    @property
    def seo_title(self) -> str:
        return self.meta_title or self.title

    @property
    def seo_description(self) -> str:
        return self.meta_description or self.excerpt

    def estimate_reading_minutes(self) -> int:
        words = len(re.findall(r"\b[\w'-]+\b", self.body or ""))
        return max(1, round(words / WORDS_PER_MINUTE)) if words else 0

    # -- rules ------------------------------------------------------------

    def clean(self):
        if self.status == self.Status.PUBLISHED and not self.published_by_id:
            raise ValidationError(
                {"published_by": "A person has to take responsibility for publishing a post."}
            )
        if self.hero_image and not self.hero_alt.strip():
            # Not a setting, and never will be: WCAG 1.1.1 is not a preference.
            raise ValidationError(
                {"hero_alt": "Describe the image. An article hero is never decorative."}
            )
        if self.canonical_url and self.canonical_url.strip().rstrip("/").endswith(self.slug):
            # A self-referential canonical is the usual symptom of a copied
            # field, and it quietly tells search engines to ignore the page.
            raise ValidationError({"canonical_url": "Leave blank unless it points somewhere else."})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug(slugify(self.title)[:200])

        # A slug change on a live post used to be refused outright. That was
        # protecting inbound links; a 301 protects them properly, so the change
        # is allowed now and the old URL survives as a redirect.
        retired_slug = ""
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("slug", "status").first()
            if previous and previous["slug"] != self.slug and previous["status"] in {
                self.Status.PUBLISHED,
                self.Status.SCHEDULED,
                self.Status.ARCHIVED,
            }:
                retired_slug = previous["slug"]

        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()

        # A future publish time IS the schedule — no separate flag to fall out
        # of step with it.
        if (
            self.status == self.Status.PUBLISHED
            and self.published_at
            and self.published_at > timezone.now()
        ):
            self.status = self.Status.SCHEDULED

        self.body_html, headings = rendering.render(self.body)
        self.toc = [
            {"level": h.level, "text": h.text, "anchor": h.anchor} for h in headings
        ]
        self._apply_excerpt_policy()
        self.reading_minutes = self.estimate_reading_minutes()
        super().save(*args, **kwargs)

        if retired_slug:
            SlugRedirect.objects.update_or_create(old_slug=retired_slug, defaults={"post": self})
            # Moving back to a slug this post previously retired would leave a
            # redirect pointing at itself. Collapse it.
            SlugRedirect.objects.filter(post=self, old_slug=self.slug).delete()

    def _apply_excerpt_policy(self) -> None:
        """Fill or replace the excerpt according to the site setting.

        `manual` leaves a blank excerpt blank — the publish gate is what complains,
        not this. `auto` overwrites whatever was typed, which is the point of
        choosing it. `manual_then_auto` is the default and the sane one.
        """
        blog_settings = BlogSettings.load()
        if not self.body:
            return
        if blog_settings.excerpt_source == ExcerptSource.MANUAL:
            return
        if blog_settings.excerpt_source == ExcerptSource.AUTO or not self.excerpt.strip():
            self.excerpt = rendering.auto_excerpt(self.body, blog_settings.excerpt_length)

    @property
    def comments_are_open(self) -> bool:
        """Whether a reader can add a comment right now.

        Four conditions, and all of them have to agree: comments are on
        site-wide, this post has not closed them, the post is actually live, and
        the age limit has not passed.
        """
        blog_settings = BlogSettings.load()
        if not blog_settings.comments_enabled or self.comments_closed or not self.is_live:
            return False
        window = blog_settings.comments_close_after_days
        if window and self.published_at:
            return (timezone.now() - self.published_at).days <= window
        return True

    @property
    def approved_comment_count(self) -> int:
        return self.comments.public().count()

    def _unique_slug(self, base: str) -> str:
        base = base or "post"
        candidate, suffix = base, 2
        while type(self).objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base[:210]}-{suffix}"
            suffix += 1
        return candidate


class PostRevision(BaseModel):
    """A snapshot of the body, taken on every meaningful edit.

    Cheap insurance. The alternative is discovering that an afternoon of edits
    replaced a good paragraph and having no way back.
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="revisions")
    title = models.CharField(max_length=200)
    body = models.TextField()
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="post_revisions",
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["post", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.post.title} @ {self.created_at:%Y-%m-%d %H:%M}"


class PostFaq(BaseModel):
    """A question and its answer, on a post.

    Rendered on the page as a real definition list *and* emitted as `FAQPage`
    JSON-LD. This is the highest-yield SEO feature in the blog, because the
    questions this audience asks are literal search queries.

    The rule is that the markup is only emitted when the answer is also visible
    on the page. Marking up content a reader cannot see is what earns a manual
    penalty, and it is dishonest besides.
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="faqs")
    question = models.CharField(max_length=200)
    answer = models.TextField(max_length=1200, help_text="Plain prose. Two or three sentences.")
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "created_at")
        verbose_name = "FAQ entry"
        verbose_name_plural = "FAQ entries"

    def __str__(self) -> str:
        return self.question

    def clean(self):
        if not self.question.strip().endswith("?"):
            raise ValidationError({"question": "A question ends with a question mark."})
        # An answer is published copy like any other.
        from . import ai

        review = ai.review_flags(self.answer)
        if not review.ok:
            raise ValidationError(
                {"answer": " ".join(f"{f.why} — “{f.excerpt}”" for f in review.flags)}
            )


class SlugRedirect(BaseModel):
    """An old URL, kept working.

    Created automatically when a live post's slug changes. The public detail
    route resolves a miss against this table and answers 301, so a link printed
    on somebody's blog two years ago still lands on the article.
    """

    old_slug = models.SlugField(max_length=220, unique=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="slug_redirects")

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.old_slug} → {self.post.slug}"


POST_STATUS_CHOICES = Post.Status.choices
POST_AI_INVOLVEMENT_CHOICES = Post.AiInvolvement.choices
