from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class NotificationTemplate(BaseModel):
    """Admin-editable message bodies, so copy changes don't need a deploy."""

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"
        IN_APP = "in_app", "In-app"

    key = models.SlugField(max_length=80, unique=True, help_text="e.g. document_rejected")
    name = models.CharField(max_length=150)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(help_text="Django template syntax; context varies per notification type.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("key",)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_channel_display()})"


class Notification(BaseModel):
    """
    One message to one recipient, with its delivery outcome.

    Kept as a record rather than fired-and-forgotten: when a student says they
    were never told their document was rejected, this answers the question.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        READ = "read", "Read"

    class Category(models.TextChoices):
        ACCOUNT = "account", "Account"
        PAYMENT = "payment", "Payment"
        DOCUMENT = "document", "Document"
        APPLICATION = "application", "Application"
        REFERRAL = "referral", "Referral"
        MESSAGE = "message", "Message"
        SYSTEM = "system", "System"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    channel = models.CharField(
        max_length=10, choices=NotificationTemplate.Channel.choices,
        default=NotificationTemplate.Channel.IN_APP,
    )
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.SYSTEM)
    template_key = models.SlugField(max_length=80, blank=True)

    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    action_url = models.CharField(max_length=500, blank=True)
    context = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_category_display()} → {self.recipient} ({self.get_status_display()})"


class MessageThread(BaseModel):
    """
    In-platform conversation with a student (plan §8.7, §10).

    Exists so institutional knowledge about a case lives in the platform rather
    than in a staff member's personal WhatsApp history.
    """

    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="threads"
    )
    application = models.ForeignKey(
        "applications.Application", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="threads",
    )
    subject = models.CharField(max_length=200)
    is_closed = models.BooleanField(default=False)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assigned_threads",
    )

    class Meta:
        ordering = ("-last_message_at", "-created_at")

    def __str__(self) -> str:
        return f"{self.subject} — {self.student.user}"


class Message(BaseModel):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sent_messages",
    )
    body = models.TextField()
    attachment = models.FileField(upload_to="messages/%Y/%m/", null=True, blank=True, max_length=500)
    is_internal_note = models.BooleanField(
        default=False, help_text="Staff-only note on the thread; never shown to the student."
    )
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.sender or 'system'}: {self.body[:60]}"


# Module-level aliases for drf-spectacular's ENUM_NAME_OVERRIDES.
NOTIFICATION_STATUS_CHOICES = Notification.Status.choices
NOTIFICATION_CATEGORY_CHOICES = Notification.Category.choices
NOTIFICATION_CHANNEL_CHOICES = NotificationTemplate.Channel.choices
