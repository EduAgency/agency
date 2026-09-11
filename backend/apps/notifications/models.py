from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.encryption import EncryptedTextField
from apps.core.models import BaseModel


class Channel(models.TextChoices):
    """Where a message can go.

    SMS is deliberately absent. It is the most expensive channel per message,
    the least rich, the easiest to spoof, and in Nigeria the one most associated
    with scams — which is the opposite of what this product needs to signal.
    WhatsApp and Telegram reach the same people, carry formatting and links,
    and confirm delivery.
    """

    IN_APP = "in_app", "In-app"
    EMAIL = "email", "Email"
    WHATSAPP = "whatsapp", "WhatsApp"
    TELEGRAM = "telegram", "Telegram"


#: Always created, never opted out of — it is the inbox, not a delivery channel.
IMPLICIT_CHANNELS = {Channel.IN_APP}

#: Channels a user can switch on and off per category.
CHOOSABLE_CHANNELS = [Channel.EMAIL, Channel.WHATSAPP, Channel.TELEGRAM]


class NotificationTemplate(BaseModel):
    """Admin-editable message bodies, so copy changes don't need a deploy."""

    # Kept as an attribute so existing references still resolve.
    Channel = Channel

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
        max_length=10, choices=Channel.choices, default=Channel.IN_APP,
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
NOTIFICATION_CHANNEL_CHOICES = Channel.choices


# ---------------------------------------------------------------------------
# Channel configuration and user preferences
# ---------------------------------------------------------------------------


class ChannelConfig(BaseModel):
    """Agency-level switch and credentials for one delivery channel.

    A channel is only offered to users when it is both **enabled** and
    **configured**. Showing someone a WhatsApp toggle that silently does
    nothing because no access token was ever set is worse than not offering it:
    they opt in, stop watching email, and miss a document rejection.
    """

    channel = models.CharField(max_length=10, choices=Channel.choices, unique=True)
    is_enabled = models.BooleanField(
        default=False, help_text="Offer this channel to users."
    )

    # WhatsApp Cloud API.
    whatsapp_phone_number_id = models.CharField(max_length=64, blank=True)
    whatsapp_business_account_id = models.CharField(max_length=64, blank=True)

    # Telegram Bot API. The username is public and is what users tap to link.
    telegram_bot_username = models.CharField(
        max_length=64, blank=True, help_text="Without the @."
    )

    # Encrypted, so a database dump does not hand over the ability to message
    # every student the agency has — same reasoning as the payment gateways.
    access_token = EncryptedTextField(blank=True)
    webhook_verify_token = EncryptedTextField(
        blank=True, help_text="Echoed back during provider webhook verification."
    )

    class Meta:
        ordering = ("channel",)
        verbose_name = "channel configuration"
        verbose_name_plural = "channel configurations"

    def __str__(self) -> str:
        state = "on" if self.is_live else "off"
        return f"{self.get_channel_display()} ({state})"

    @property
    def is_configured(self) -> bool:
        """Whether this channel has everything it needs to actually deliver."""
        if self.channel == Channel.EMAIL:
            return True  # Django's mail backend is configured in settings.
        if self.channel == Channel.WHATSAPP:
            return bool(self.access_token and self.whatsapp_phone_number_id)
        if self.channel == Channel.TELEGRAM:
            return bool(self.access_token and self.telegram_bot_username)
        return False

    @property
    def is_live(self) -> bool:
        return self.is_enabled and self.is_configured


class NotificationPreference(BaseModel):
    """One user's answer to 'tell me about X, here'.

    Stored per (user, category, channel) rather than as a blob so that opt-out
    rates are queryable — "how many students turned off document alerts" is a
    question worth being able to answer without parsing JSON.

    Absence of a row means the default in ``DEFAULT_PREFERENCES``, so a new
    category does not need a backfill.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    category = models.CharField(max_length=15, choices=Notification.Category.choices)
    channel = models.CharField(max_length=10, choices=Channel.choices)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "category", "channel")
        indexes = [models.Index(fields=["user", "category"])]

    def __str__(self) -> str:
        return f"{self.user} · {self.category}/{self.channel} = {self.is_enabled}"


class TelegramLink(BaseModel):
    """Connects a user to a Telegram chat.

    Telegram cannot be messaged by phone number — a bot can only write to a
    chat that the user opened first. So linking is: we mint a short-lived
    token, the user taps through to the bot, and the bot's ``/start <token>``
    tells us which chat belongs to which account.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram_link"
    )
    chat_id = models.CharField(max_length=64, unique=True, db_index=True)
    telegram_username = models.CharField(max_length=64, blank=True)
    linked_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.user} → @{self.telegram_username or self.chat_id}"


class TelegramLinkToken(BaseModel):
    """Single-use, short-lived token handed to the Telegram deep link."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram_link_tokens"
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

#: Categories that must always reach the account holder by email, whatever
#: else they switch off. These are transactional — a password reset or a
#: payment receipt is not marketing, and silently not sending one is a support
#: incident, not a preference honoured.
ALWAYS_EMAIL_CATEGORIES = {
    Notification.Category.ACCOUNT,
    Notification.Category.PAYMENT,
}

#: What a user gets before they touch anything. Email on for everything that
#: matters; the richer channels stay off until the user connects them, because
#: neither can be used without an explicit opt-in anyway.
DEFAULT_PREFERENCES: dict[str, set[str]] = {
    Notification.Category.ACCOUNT: {Channel.EMAIL},
    Notification.Category.PAYMENT: {Channel.EMAIL},
    Notification.Category.DOCUMENT: {Channel.EMAIL},
    Notification.Category.APPLICATION: {Channel.EMAIL},
    Notification.Category.MESSAGE: {Channel.EMAIL},
    Notification.Category.REFERRAL: {Channel.EMAIL},
    # Nudges and announcements. Off by default — opt-in, never opt-out.
    Notification.Category.SYSTEM: set(),
}

#: Shown in the preference centre so the choice is meaningful rather than a
#: row of unexplained toggles.
CATEGORY_DESCRIPTIONS = {
    Notification.Category.ACCOUNT: (
        "Sign-in, password and security. Always sent by email — these keep your account safe."
    ),
    Notification.Category.PAYMENT: (
        "Receipts and refunds. Always sent by email — this is your proof of payment."
    ),
    Notification.Category.DOCUMENT: "When a document is verified, or needs redoing.",
    Notification.Category.APPLICATION: "When an application moves forward, or a deadline is close.",
    Notification.Category.MESSAGE: "When your counsellor replies to you.",
    Notification.Category.REFERRAL: "When someone you referred signs up, and when a reward is earned.",
    Notification.Category.SYSTEM: "Occasional tips and reminders. Off unless you ask for them.",
}
