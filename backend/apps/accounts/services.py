"""Account lifecycle: tokens, verification, and NDPR erasure."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core import audit

from .models import EmailVerificationToken, User

VERIFY_TTL = timedelta(days=3)
RESET_TTL = timedelta(hours=2)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(user: User, purpose: str) -> str:
    """Create a single-use token. Only the hash is stored, so a database leak
    does not hand over working password-reset links."""
    ttl = VERIFY_TTL if purpose == EmailVerificationToken.Purpose.VERIFY_EMAIL else RESET_TTL

    # Any earlier unused token for the same purpose is retired.
    EmailVerificationToken.objects.filter(
        user=user, purpose=purpose, used_at__isnull=True
    ).update(used_at=timezone.now())

    raw = secrets.token_urlsafe(32)
    EmailVerificationToken.objects.create(
        user=user, purpose=purpose, token_hash=_hash(raw), expires_at=timezone.now() + ttl
    )
    return raw


@transaction.atomic
def consume_token(raw: str, purpose: str) -> User | None:
    entry = (
        EmailVerificationToken.objects.select_for_update()
        .filter(token_hash=_hash(raw), purpose=purpose)
        .first()
    )
    if entry is None or not entry.is_usable:
        return None
    entry.used_at = timezone.now()
    entry.save(update_fields=["used_at", "updated_at"])
    return entry.user


def send_verification_email(user: User) -> None:
    from apps.notifications.models import Notification, NotificationTemplate
    from apps.notifications.services import create_notification

    token = issue_token(user, EmailVerificationToken.Purpose.VERIFY_EMAIL)
    url = f"{settings.FRONTEND_BASE_URL}/verify-email?token={token}"
    create_notification(
        recipient=user,
        category=Notification.Category.ACCOUNT,
        channel=NotificationTemplate.Channel.EMAIL,
        template_key="verify_email",
        subject="Confirm your email address",
        body=f"Welcome to Nasuru. Confirm your email address to continue:\n\n{url}\n\nThis link expires in 3 days.",
        action_url=url,
    )


def send_password_reset(user: User) -> None:
    from apps.notifications.models import Notification, NotificationTemplate
    from apps.notifications.services import create_notification

    token = issue_token(user, EmailVerificationToken.Purpose.RESET_PASSWORD)
    url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"
    create_notification(
        recipient=user,
        category=Notification.Category.ACCOUNT,
        channel=NotificationTemplate.Channel.EMAIL,
        template_key="password_reset",
        subject="Reset your password",
        body=f"Use this link to set a new password:\n\n{url}\n\nIt expires in 2 hours. If you didn't ask for this, ignore this email.",
        action_url=url,
    )


def issue_jwt(user: User) -> dict:
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


@transaction.atomic
def erase_student(student, *, user, reason: str) -> dict:
    """
    NDPR erasure (plan §10).

    Deletes the personal data and the document files, while keeping the
    non-identifying skeleton needed for financial records and accreditation
    review. The erasure itself is audited — that record is the proof the
    request was honoured.
    """
    from apps.applications.models import DocumentUpload

    uploads = DocumentUpload.objects.filter(document__student=student)
    file_count = uploads.count()
    for upload in uploads:
        if upload.file:
            upload.file.delete(save=False)

    student.documents.all().delete()
    student.form_submissions.all().delete()

    account = student.user
    placeholder = f"erased-{student.pk}@deleted.invalid"
    audit.record(
        "data_erasure",
        target=student,
        actor=user,
        metadata={"reason": reason, "files_deleted": file_count},
        target_label=f"Erasure of {account.email}",
    )

    account.email = placeholder
    account.first_name = ""
    account.last_name = ""
    account.phone = ""
    account.is_active = False
    account.set_unusable_password()
    account.save()

    student.whatsapp = ""
    student.internal_notes = ""
    student.state_of_residence = ""
    student.date_of_birth = None
    student.archive(reason=f"NDPR erasure: {reason}")

    return {"files_deleted": file_count, "student_id": str(student.pk)}
