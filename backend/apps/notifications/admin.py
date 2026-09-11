from django.contrib import admin

from .models import (
    ChannelConfig,
    Message,
    MessageThread,
    Notification,
    NotificationPreference,
    NotificationTemplate,
    TelegramLink,
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "channel", "is_active")
    list_filter = ("channel", "is_active")
    search_fields = ("key", "name", "subject")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "category", "channel", "subject", "status", "attempts")
    list_filter = ("status", "channel", "category", "created_at")
    search_fields = ("recipient__email", "subject", "body")
    date_hierarchy = "created_at"
    readonly_fields = ("sent_at", "read_at", "attempts", "error", "context")


class MessageInline(admin.TabularInline):
    model = Message
    extra = 1
    fields = ("sender", "body", "is_internal_note", "attachment", "created_at")
    readonly_fields = ("created_at",)


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ("subject", "student", "assigned_to", "is_closed", "last_message_at")
    list_filter = ("is_closed", "last_message_at")
    search_fields = ("subject", "student__user__email")
    autocomplete_fields = ("student", "application", "assigned_to")
    inlines = (MessageInline,)


@admin.register(ChannelConfig)
class ChannelConfigAdmin(admin.ModelAdmin):
    """Where the agency switches a delivery channel on.

    ``is_live`` is shown rather than just ``is_enabled`` because the two come
    apart constantly: somebody ticks the box, never pastes the token, and the
    channel is offered to students while quietly delivering nothing.
    """

    list_display = ("channel", "is_enabled", "live", "credentials_set")
    list_filter = ("is_enabled",)
    readonly_fields = ("live", "credentials_set")

    fieldsets = (
        (None, {"fields": ("channel", "is_enabled", "live", "credentials_set")}),
        (
            "WhatsApp (Meta Cloud API)",
            {
                "fields": ("whatsapp_phone_number_id", "whatsapp_business_account_id"),
                "description": "From the WhatsApp Business account. The access token goes below.",
            },
        ),
        (
            "Telegram (Bot API)",
            {
                "fields": ("telegram_bot_username",),
                "description": "The bot's @name, without the @. The bot token goes below.",
            },
        ),
        (
            "Secrets",
            {
                "fields": ("access_token", "webhook_verify_token"),
                "description": (
                    "Encrypted at rest. The verify token is the secret segment in the "
                    "provider webhook URL."
                ),
            },
        ),
    )

    @admin.display(boolean=True, description="Live")
    def live(self, obj):
        return obj.is_live

    @admin.display(boolean=True, description="Credentials set")
    def credentials_set(self, obj):
        return obj.is_configured


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Read-only: a preference is the user's to set, not staff's to change."""

    list_display = ("user", "category", "channel", "is_enabled")
    list_filter = ("category", "channel", "is_enabled")
    search_fields = ("user__email",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TelegramLink)
class TelegramLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "telegram_username", "linked_at")
    search_fields = ("user__email", "telegram_username")
    readonly_fields = ("chat_id", "telegram_username", "linked_at")

    def has_add_permission(self, request):
        return False
