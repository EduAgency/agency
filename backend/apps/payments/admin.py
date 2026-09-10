import json

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Payment,
    PaymentGatewayConfig,
    ReconciliationRun,
    Refund,
    WebhookEvent,
)
from .tasks import process_webhook_event_task, reconcile_gateway


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    """
    Gateway keys live here, encrypted at rest.

    Access is restricted to superusers plus staff with ``can_manage_payment_config``
    — the point of the granular permission model in §7.8 is that a document
    reviewer never sees this screen.
    """

    list_display = ("gateway", "currency", "mode", "is_active", "secret_key_fingerprint", "updated_at")
    list_filter = ("gateway", "is_active", "is_test_mode")
    readonly_fields = ("secret_key_fingerprint", "webhook_url_hint")

    fieldsets = (
        (None, {"fields": ("gateway", "label", "currency", "is_active", "is_test_mode", "display_order")}),
        (
            "Credentials",
            {
                "description": "Secrets are encrypted with FIELD_ENCRYPTION_KEY before they touch the database.",
                "fields": ("public_key", "secret_key", "encryption_key", "webhook_secret", "secret_key_fingerprint"),
            },
        ),
        ("Setup", {"fields": ("webhook_url_hint",)}),
    )

    @admin.display(description="Mode")
    def mode(self, obj):
        return "TEST" if obj.is_test_mode else "LIVE"

    @admin.display(description="Webhook URL to register with the gateway")
    def webhook_url_hint(self, obj):
        if not obj.pk:
            return "Save first."
        return format_html("<code>https://&lt;your-api-domain&gt;/api/payments/webhooks/{}/</code>", obj.gateway)

    def has_module_permission(self, request):
        return self._allowed(request)

    def has_view_permission(self, request, obj=None):
        return self._allowed(request)

    def has_change_permission(self, request, obj=None):
        return self._allowed(request)

    def has_add_permission(self, request):
        return self._allowed(request)

    @staticmethod
    def _allowed(request) -> bool:
        user = request.user
        if user.is_superuser:
            return True
        profile = getattr(user, "admin_profile", None)
        return bool(profile and profile.has("can_manage_payment_config"))

    def save_model(self, request, obj, form, change):
        from apps.core import audit

        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        audit.record(
            "gateway_config_change",
            target=obj,
            actor=request.user,
            # Field names only — never the values (the audit scrubber drops them anyway).
            metadata={"changed_fields": list(form.changed_data)},
        )


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    fields = ("amount", "currency", "reason", "status", "requested_by", "completed_at")
    readonly_fields = ("requested_by", "completed_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "email", "purpose", "money", "status", "confirmation", "created_at")
    list_filter = ("status", "gateway", "purpose", "currency", "confirmed_by_webhook", "created_at")
    search_fields = ("reference", "gateway_reference", "email", "student__user__email")
    date_hierarchy = "created_at"
    inlines = (RefundInline,)
    readonly_fields = (
        "reference", "gateway", "gateway_reference", "amount", "currency", "amount_settled",
        "gateway_fee", "paid_at", "channel", "authorization_code", "confirmed_by_webhook",
        "confirmed_by_reconciliation", "reconciled_at", "metadata_preview", "initiated_ip",
    )
    list_select_related = ("student__user",)

    @admin.display(description="Amount", ordering="amount")
    def money(self, obj):
        return f"{obj.currency} {obj.amount:,.2f}"

    @admin.display(description="Confirmed by")
    def confirmation(self, obj):
        if obj.confirmed_by_webhook:
            return "webhook"
        if obj.confirmed_by_reconciliation:
            return "reconciliation"
        return "—"

    @admin.display(description="Metadata")
    def metadata_preview(self, obj):
        return format_html("<pre style='margin:0'>{}</pre>", json.dumps(obj.metadata, indent=2, default=str))

    def has_add_permission(self, request):
        # Payments originate from checkout, never from typing one in here.
        return False


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    """The raw webhook log — the answer to 'did they actually pay?' (§5.2)."""

    list_display = ("created_at", "gateway", "event_type", "status", "payment", "attempts", "source_ip")
    list_filter = ("gateway", "status", "event_type", "created_at")
    search_fields = ("idempotency_key", "payment__reference", "source_ip")
    date_hierarchy = "created_at"
    readonly_fields = ("gateway", "event_type", "idempotency_key", "payload_preview", "headers", "signature", "source_ip", "attempts", "processed_at")
    exclude = ("payload",)
    actions = ("reprocess",)

    @admin.display(description="Payload")
    def payload_preview(self, obj):
        return format_html("<pre style='margin:0;max-height:400px;overflow:auto'>{}</pre>", json.dumps(obj.payload, indent=2, default=str))

    @admin.action(description="Re-process selected events")
    def reprocess(self, request, queryset):
        for event in queryset:
            process_webhook_event_task.delay(str(event.pk))
        self.message_user(request, f"Queued {queryset.count()} event(s) for re-processing.")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("payment", "amount", "currency", "status", "requested_by", "approved_by", "completed_at")
    list_filter = ("status", "currency")
    search_fields = ("payment__reference", "reason")
    autocomplete_fields = ("payment",)


@admin.register(ReconciliationRun)
class ReconciliationRunAdmin(admin.ModelAdmin):
    list_display = ("started_at", "gateway", "transactions_checked", "mismatches_found", "payments_corrected", "unknown_transactions")
    list_filter = ("gateway", "started_at")
    readonly_fields = [f.name for f in ReconciliationRun._meta.fields]
    actions = ("run_now",)

    @admin.action(description="Run reconciliation now for these gateways")
    def run_now(self, request, queryset):
        for gateway in set(queryset.values_list("gateway", flat=True)):
            reconcile_gateway.delay(gateway)
        self.message_user(request, "Reconciliation queued.", messages.INFO)

    def has_add_permission(self, request):
        return False
