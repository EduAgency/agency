"""Comments, and the spam defences that make them survivable.

Comments on a site for people who have been scammed before are worth having,
because the questions in them are the next twelve articles. They are also the
easiest way to get a competitor's phone number onto your own pages. So every
default here is the cautious one, and moderation is on.

Two rules that are not negotiable:

**The body is plain text.** No Markdown, no HTML, not ever. A comment box that
accepts markup is a persistent-XSS surface with no upside — nothing a reader
needs to ask requires a heading.

**Nothing is silently discarded.** All five spam checks *flag* for review; none
reject outright. A false positive that lands in a queue costs a moderator five
seconds. One that vanishes costs a reader their question and costs us the exact
trust this whole product is built on.

See docs/blog-system.md §3.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel

URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)


class CommentQuerySet(models.QuerySet):
    def public(self):
        """What a reader sees: approved, top-level first, pinned above the rest."""
        return self.filter(status=Comment.Status.APPROVED)

    def needing_review(self):
        return self.filter(status=Comment.Status.PENDING)


class Comment(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for review"
        APPROVED = "approved", "Published"
        SPAM = "spam", "Spam"
        REJECTED = "rejected", "Rejected"

    post = models.ForeignKey("blog.Post", on_delete=models.CASCADE, related_name="comments")
    # One level deep on purpose: deeper threads are unreadable on a phone, which
    # is where this audience reads. A reply to a reply attaches to the same root.
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )

    #: Set when a signed-in staff member replies, so an official answer reads as one.
    author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blog_comments",
    )
    name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(
        blank=True,
        help_text="Never rendered publicly. Used for moderation and, later, reply notification.",
    )
    website = models.URLField(blank=True)

    body = models.TextField(max_length=4000, help_text="Plain text. Escaped on output, always.")

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    flagged_reason = models.CharField(
        max_length=200, blank=True, help_text="Why an automated check flagged this, for the moderator."
    )
    is_pinned = models.BooleanField(default=False, help_text="Sits at the top of the thread.")

    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderated_comments",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)

    objects = CommentQuerySet.as_manager()

    class Meta:
        ordering = ("-is_pinned", "created_at")
        indexes = [
            models.Index(fields=["post", "status", "created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} on {self.post.slug}"

    def clean(self):
        if not self.body.strip():
            raise ValidationError({"body": "Write something."})
        if self.parent and self.parent.post_id != self.post_id:
            raise ValidationError({"parent": "A reply has to be on the same post."})
        if self.parent and self.parent.parent_id:
            raise ValidationError(
                {"parent": "Replies only go one level deep — attach it to the top-level comment."}
            )
        if not self.author_user_id and not self.name.strip():
            raise ValidationError({"name": "Tell us what to call you."})

    @property
    def display_name(self) -> str:
        if self.author_user:
            return self.author_user.get_full_name() or "Nasuru"
        return self.name or "Anonymous"

    @property
    def is_from_staff(self) -> bool:
        return bool(self.author_user_id)

    def approve(self, *, moderator=None) -> None:
        self.status = self.Status.APPROVED
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save(update_fields=["status", "moderated_by", "moderated_at", "updated_at"])

    def mark(self, status: str, *, moderator=None) -> None:
        self.status = status
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save(update_fields=["status", "moderated_by", "moderated_at", "updated_at"])


# ---------------------------------------------------------------------------
# Spam screening
# ---------------------------------------------------------------------------


class Screening:
    """The outcome of the automated checks: a status and a reason to show a moderator."""

    def __init__(self, status: str, reason: str = ""):
        self.status = status
        self.reason = reason

    @property
    def is_spam(self) -> bool:
        return self.status == Comment.Status.SPAM


def screen(
    body: str,
    *,
    website: str,
    seconds_on_page: float | None,
    blog_settings,
    trusted: bool = False,
) -> Screening:
    """Decide what status a new comment starts in.

    ``trusted`` is a signed-in staff member replying, who skips the queue —
    they are already accountable by name.
    """
    if trusted:
        return Screening(Comment.Status.APPROVED)

    reasons: list[str] = []

    link_count = len(URL_PATTERN.findall(body)) + (1 if website else 0)
    if link_count > blog_settings.comments_max_links:
        reasons.append(f"{link_count} links (limit {blog_settings.comments_max_links})")

    if seconds_on_page is not None and seconds_on_page < blog_settings.comments_min_seconds:
        reasons.append(f"submitted in {seconds_on_page:.0f}s")

    lowered = body.lower()
    hit = next((phrase for phrase in blog_settings.blocklist_phrases if phrase in lowered), None)
    if hit:
        reasons.append(f"blocked phrase “{hit}”")

    if reasons:
        return Screening(Comment.Status.SPAM, "; ".join(reasons))

    return Screening(
        Comment.Status.PENDING
        if blog_settings.comments_require_approval
        else Comment.Status.APPROVED
    )


def thread(post) -> list[dict]:
    """Approved comments as a two-level tree, ready to render.

    Built here rather than in a serializer because the shape — roots with their
    replies attached — is the same for the public page and the moderation view,
    and doing it in one query pair keeps an article page from doing N+1.
    """
    rows = list(
        post.comments.public()
        .select_related("author_user", "parent")
        .order_by("-is_pinned", "created_at")
    )
    roots = [c for c in rows if c.parent_id is None]
    replies: dict = {}
    for comment in rows:
        if comment.parent_id:
            replies.setdefault(comment.parent_id, []).append(comment)
    return [{"comment": root, "replies": replies.get(root.pk, [])} for root in roots]
