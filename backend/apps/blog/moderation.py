"""Comment submission and moderation.

Two entry points. :func:`submit` is the one a reader reaches, and it is the only
place a `Comment` gets created from untrusted input — so every spam check,
rate limit and status decision lives here rather than being spread across the
view. :func:`moderate` is the staff side, and it always writes an audit row,
because "who approved this" is a question that eventually gets asked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.models import AuditLog

from .comments import Comment, screen
from .models import BlogSettings, Post


class CommentsClosed(Exception):
    """The post is not accepting comments. Not an error the reader caused."""


class RateLimited(Exception):
    """Too many comments from one address in an hour."""


@dataclass
class Submission:
    #: None when the honeypot caught it — nothing was written.
    comment: Comment | None
    #: What to tell the reader.
    message: str


def _check_rate(ip: str | None, limit: int) -> None:
    """Fixed-window count, keyed by the clock hour.

    A fixed window rather than a sliding one because it needs no TTL
    introspection and no sorted set — the key simply changes on the hour. The
    cost is that someone can burst across a boundary, which for comment spam is
    not worth a Redis data structure to prevent.
    """
    if not ip:
        return
    key = f"blog:comment-rate:{ip}:{timezone.now():%Y%m%d%H}"
    try:
        count = cache.get(key, 0)
    except Exception:  # pragma: no cover - a cache backend being down
        # Fail open. The DRF throttle above this is a separate ceiling, and
        # refusing every comment because Redis is down is the wrong trade.
        logging.getLogger(__name__).warning("Comment rate limiter unavailable; allowing.")
        return
    if count >= limit:
        raise RateLimited(
            f"That is {limit} comments in an hour from this connection. Try again later."
        )
    try:
        cache.set(key, count + 1, 3600)
    except Exception:  # pragma: no cover
        pass


@transaction.atomic
def submit(
    *,
    post: Post,
    body: str,
    name: str = "",
    email: str = "",
    website: str = "",
    parent: Comment | None = None,
    honeypot: str = "",
    seconds_on_page: float | None = None,
    user=None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> Submission:
    """Create a comment, screened.

    A filled honeypot is the one case that is neither stored nor explained: it
    cannot have come from a person, and telling a bot why it failed only helps
    it. The reader-facing response is identical to a success, so a script gets
    no signal either way.
    """
    blog_settings = BlogSettings.load()

    if not post.comments_are_open:
        raise CommentsClosed("Comments are closed on this guide.")
    if parent and not blog_settings.comments_allow_replies:
        raise CommentsClosed("Replies are turned off.")

    trusted = bool(user and getattr(user, "is_authenticated", False) and user.is_agency_staff)

    if honeypot.strip():
        # Pretend it worked. Nothing is written.
        return Submission(comment=None, message="Thanks — your comment is with us for review.")

    if not trusted:
        _check_rate(ip_address, blog_settings.comments_per_hour_per_ip)
        if blog_settings.comments_require_email and not email.strip():
            raise ValidationError(
                {"email": "We need an email so we can reply. It is never shown on the page."}
            )

    verdict = screen(
        body,
        website=website,
        seconds_on_page=seconds_on_page,
        blog_settings=blog_settings,
        trusted=trusted,
    )

    comment = Comment(
        post=post,
        parent=parent.parent if (parent and parent.parent_id) else parent,
        author_user=user if trusted else None,
        name="" if trusted else name.strip(),
        email="" if trusted else email.strip(),
        website="" if trusted else website.strip(),
        body=body.strip(),
        status=verdict.status,
        flagged_reason=verdict.reason,
        ip_address=ip_address,
        user_agent=user_agent[:400],
    )
    comment.full_clean(exclude=["ip_address"])
    comment.save()

    # Flagged and merely-pending give the identical message on purpose: a
    # spammer learns nothing from it, and a false positive does not accuse a
    # real reader of anything.
    message = (
        "Posted. Thanks for asking."
        if comment.status == Comment.Status.APPROVED
        else "Thanks — your comment is with us for review."
    )

    if blog_settings.comments_notify_staff and not trusted:
        _notify_staff(comment)

    return Submission(comment=comment, message=message)


def _notify_staff(comment: Comment) -> None:
    """Tell whoever can moderate that something is waiting.

    Failure here is logged and swallowed: a notification backend being down must
    not lose the reader's comment, which is already saved by this point.
    """
    from django.contrib.auth import get_user_model

    from apps.notifications.models import Notification
    from apps.notifications.services import create_notification

    User = get_user_model()
    recipients = User.objects.filter(
        is_active=True, admin_profile__can_publish_content=True
    ) | User.objects.filter(is_active=True, role=User.Role.SUPERADMIN)

    for user in recipients.distinct():
        try:
            create_notification(
                recipient=user,
                category=Notification.Category.SYSTEM,
                subject=f"New comment on “{comment.post.title}”",
                body=(
                    f"{comment.display_name} wrote:\n\n{comment.body[:400]}\n\n"
                    + (f"Flagged: {comment.flagged_reason}" if comment.flagged_reason else "")
                ).strip(),
                action_url=f"/staff/blog/comments?comment={comment.pk}",
                context={"post": comment.post.title, "status": comment.status},
            )
        except Exception:  # pragma: no cover - defensive
            import logging

            logging.getLogger(__name__).exception(
                "Could not notify %s about comment %s", user.pk, comment.pk
            )


@transaction.atomic
def moderate(comment: Comment, status: str, *, moderator) -> Comment:
    """Approve, reject or mark spam, with an audit row."""
    if status not in dict(Comment.Status.choices):
        raise ValidationError({"status": f"Not a comment status: {status}."})

    before = comment.status
    comment.mark(status, moderator=moderator)

    audit.record(
        AuditLog.Action.UPDATE,
        target=comment,
        actor=moderator,
        target_label=f"Comment on {comment.post.slug}",
        changes={"status": {"from": before, "to": status}},
        metadata={
            "post": comment.post.slug,
            "author": comment.display_name,
            "flagged_reason": comment.flagged_reason,
        },
    )
    return comment


@transaction.atomic
def reply_as_agency(comment: Comment, body: str, *, author) -> Comment:
    """Answer a reader in the thread, as the agency.

    Approved immediately: a named staff member is already accountable, and a
    moderation queue that holds our own replies is a queue nobody trusts.
    """
    root = comment if comment.parent_id is None else comment.parent
    reply = Comment.objects.create(
        post=comment.post,
        parent=root,
        author_user=author,
        body=body.strip(),
        status=Comment.Status.APPROVED,
        moderated_by=author,
        moderated_at=timezone.now(),
    )
    audit.record(
        AuditLog.Action.CREATE,
        target=reply,
        actor=author,
        target_label=f"Agency reply on {comment.post.slug}",
        metadata={"post": comment.post.slug, "in_reply_to": str(comment.pk)},
    )
    return reply
