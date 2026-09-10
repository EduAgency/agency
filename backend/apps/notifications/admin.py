from django.contrib import admin

from .models import Message, MessageThread, Notification, NotificationTemplate


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
