import uuid

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """created_at / updated_at on everything — cheap now, priceless in support."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    UUID primary key for anything exposed over the API.

    Sequential integers on student/application/payment URLs leak volume and
    invite enumeration; these records are addressed by opaque id instead.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    class Meta:
        abstract = True


class ArchivableQuerySet(models.QuerySet):
    def active(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)


class ArchivableModel(models.Model):
    """
    Soft-archive instead of delete.

    Plan §10: a withdrawn or rejected student's record is archived, never
    deleted — both for our own history and for accreditation review. Hard
    deletion is reserved for NDPR erasure requests, which go through
    apps.accounts.services.erase_student() so the erasure is itself logged.
    """

    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    archived_reason = models.CharField(max_length=255, blank=True)

    objects = ArchivableQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def archive(self, reason: str = "") -> None:
        from django.utils import timezone

        self.archived_at = timezone.now()
        self.archived_reason = reason
        self.save(update_fields=["archived_at", "archived_reason", "updated_at"])


class AuditLog(TimeStampedModel):
    """
    Append-only record of every sensitive action (plan §7.9).

    Written through apps.core.audit.record(); rows are never updated or deleted
    from application code. If you find yourself wanting to edit one, you want a
    new row instead.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Created"
        UPDATE = "update", "Updated"
        DELETE = "delete", "Deleted"
        ARCHIVE = "archive", "Archived"
        LOGIN = "login", "Logged in"
        LOGIN_FAILED = "login_failed", "Login failed"
        PUBLISH = "publish", "Published"
        DOCUMENT_VERIFY = "document_verify", "Document verified"
        DOCUMENT_REJECT = "document_reject", "Document rejected"
        DOCUMENT_DOWNLOAD = "document_download", "Document downloaded"
        PAYMENT_STATUS_CHANGE = "payment_status_change", "Payment status changed"
        PAYMENT_REFUND = "payment_refund", "Payment refunded"
        GATEWAY_CONFIG_CHANGE = "gateway_config_change", "Gateway config changed"
        REFERRAL_PAYOUT = "referral_payout", "Referral payout"
        CHECKLIST_RESYNC = "checklist_resync", "Checklist re-synced"
        PERMISSION_CHANGE = "permission_change", "Permission changed"
        DATA_EXPORT = "data_export", "Data exported"
        DATA_ERASURE = "data_erasure", "Data erased"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
        help_text="Null for system/automated actions (e.g. webhook processing).",
    )
    actor_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Denormalised actor identity, kept readable after the user is deleted.",
    )
    action = models.CharField(max_length=40, choices=Action.choices, db_index=True)

    # Generic target, stored as strings so an audit row survives the target's deletion.
    target_type = models.CharField(max_length=100, blank=True, db_index=True)
    target_id = models.CharField(max_length=64, blank=True, db_index=True)
    target_label = models.CharField(max_length=255, blank=True)

    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="{'field': {'from': x, 'to': y}} — never store raw secrets or document contents.",
    )
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["target_type", "target_id", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_label or 'system'} {self.action} {self.target_label}"
