"""Editorial actions, in one place.

Views call these; they do not move a post between states themselves. The
publish gate in particular is a single function, so there is exactly one path a
post can take onto the public site and exactly one place to read to know what
that path checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.models import AuditLog

from . import ai
from .models import BlogSettings, Post, PostRevision


@dataclass
class PublishCheck:
    """Why a post can or cannot go live, in terms an editor can act on."""

    blockers: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.blockers

    def as_dict(self) -> dict:
        return {"ok": self.ok, "blockers": self.blockers, "warnings": self.warnings}


def check_publishable(post: Post) -> PublishCheck:
    """Everything that must be true before a post is public.

    Blockers stop a publish. Warnings do not — an editor can knowingly publish
    a post with a long meta description; they cannot publish one with no body.
    """
    blockers: list[str] = []
    warnings: list[str] = []
    blog_settings = BlogSettings.load()

    if not post.title.strip():
        blockers.append("The post has no title.")
    if len(post.body.split()) < 120:
        blockers.append("The body is too short to be an article (under 120 words).")

    if not post.excerpt.strip():
        message = "Write an excerpt — it is what shows in listings and search results."
        (blockers if blog_settings.excerpt_required_to_publish else warnings).append(message)

    if post.hero_image and not post.hero_alt.strip():
        blockers.append("Describe the hero image. An article hero is never decorative.")
    if blog_settings.featured_image_required and not post.hero_image:
        blockers.append(
            "This post needs a featured image — the site is configured to require one."
        )
    if not post.category_id:
        warnings.append("No category: the post will not appear under any section.")

    # The house-style scan runs on every body, whoever wrote it. Claims,
    # invented figures and named places all block publishing — unless the post
    # carries a written reason, in which case they become warnings the editor
    # still has to acknowledge and the reason goes into the audit trail. See
    # Post.style_override_reason for why that escape hatch exists.
    review = ai.review_flags(post.body)
    overridden = bool(post.style_override_reason.strip())
    for flag in review.flags:
        message = f"{flag.why} — “{flag.excerpt}”"
        (warnings if overridden else blockers).append(message)

    if post.ai_involvement != Post.AiInvolvement.NONE and not post.ai_notes.strip():
        blockers.append(
            "This post used AI assistance. Record what was generated and what you changed."
        )

    if len(post.seo_title) > 60:
        warnings.append(
            f"The search title is {len(post.seo_title)} characters — search results cut near 60."
        )
    if not post.meta_description:
        warnings.append("No meta description: the excerpt will be used instead.")
    elif len(post.meta_description) > 155:
        warnings.append(
            f"The meta description is {len(post.meta_description)} characters — results cut near 155."
        )
    if not post.focus_keyword:
        warnings.append("No focus keyword set, so there is nothing to check the article against.")
    elif post.focus_keyword.lower() not in f"{post.title} {post.body}".lower():
        warnings.append(
            f'The focus keyword “{post.focus_keyword}” does not appear in the title or body.'
        )
    if len(post.toc) < 2:
        warnings.append("Fewer than two headings: long articles are hard to scan without them.")

    # An FAQ block is the cheapest route to a rich result, so its absence is
    # worth mentioning once — as a nudge, never as a gate.
    if not post.faqs.exists():
        warnings.append(
            "No FAQ entries. Two or three real questions here are the cheapest way to be found."
        )

    if post.pk and post.author_id and not hasattr(post.author, "author_profile"):
        warnings.append(
            "The author has no public profile, so the byline will not link anywhere and the "
            "article ships without Person markup."
        )

    return PublishCheck(blockers=blockers, warnings=warnings)


@transaction.atomic
def publish(post: Post, *, actor, when=None, force: bool = False) -> Post:
    """Put a post live, or schedule it.

    ``force`` skips nothing that protects a reader — it only exists so an
    editor can override the soft checks. Blockers are not overridable.
    """
    check = check_publishable(post)
    if not check.ok:
        raise ValidationError({"blockers": check.blockers})
    if check.warnings and not force:
        raise ValidationError({"warnings": check.warnings})

    post.published_by = actor
    post.published_at = when or post.published_at or timezone.now()
    post.status = Post.Status.PUBLISHED
    post.full_clean(exclude=["hero_image"])
    post.save()

    audit.record(
        AuditLog.Action.PUBLISH,
        target=post,
        actor=actor,
        target_label=post.title,
        metadata={
            "slug": post.slug,
            "scheduled": post.status == Post.Status.SCHEDULED,
            "published_at": post.published_at.isoformat(),
            "ai_involvement": post.ai_involvement,
            "style_override_reason": post.style_override_reason,
            "warnings_overridden": check.warnings if force else [],
        },
    )
    return post


@transaction.atomic
def unpublish(post: Post, *, actor, reason: str = "") -> Post:
    """Take a post off the site.

    The slug stays reserved. Whatever linked to it should get a 410, not a new
    post at the same URL.
    """
    post.status = Post.Status.ARCHIVED
    post.save(update_fields=["status", "updated_at"])
    audit.record(
        AuditLog.Action.PUBLISH,
        target=post,
        actor=actor,
        target_label=post.title,
        metadata={"action": "unpublished", "reason": reason, "slug": post.slug},
    )
    return post


def snapshot(post: Post, *, editor=None, note: str = "") -> PostRevision | None:
    """Record the current body, unless it is identical to the last snapshot."""
    latest = post.revisions.first()
    if latest and latest.body == post.body and latest.title == post.title:
        return None
    return PostRevision.objects.create(
        post=post, title=post.title, body=post.body, editor=editor, note=note
    )


def restore(revision: PostRevision, *, editor) -> Post:
    """Roll a post's body back to a revision, keeping the rollback in history."""
    post = revision.post
    snapshot(post, editor=editor, note="Before restore")
    post.title = revision.title
    post.body = revision.body
    post.save()
    snapshot(post, editor=editor, note=f"Restored from {revision.created_at:%Y-%m-%d %H:%M}")
    return post
