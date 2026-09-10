from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only by construction — an audit trail nobody can edit is the only
    kind worth having (plan §7.9)."""

    list_display = ("created_at", "actor_label", "action", "target_type", "target_label", "ip_address")
    list_filter = ("action", "target_type", "created_at")
    search_fields = ("actor_label", "target_label", "target_id", "ip_address")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
