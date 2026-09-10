from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AdminProfile, EmailVerificationToken, StudentProfile, User


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    fk_name = "user"
    extra = 0
    readonly_fields = ("access_granted_at", "access_granted_by_payment")


class AdminProfileInline(admin.StackedInline):
    model = AdminProfile
    can_delete = False
    fk_name = "user"
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("email", "get_full_name", "role", "is_active", "email_is_verified", "created_at")
    list_filter = ("role", "is_active", "is_staff", "created_at")
    search_fields = ("email", "first_name", "last_name", "phone")
    readonly_fields = ("created_at", "updated_at", "last_login", "last_login_ip")

    fieldsets = (
        (None, {"fields": ("email", "password", "role")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone")}),
        ("Status", {"fields": ("is_active", "is_staff", "is_superuser", "email_verified_at")}),
        (
            "Consent (NDPR)",
            {
                "fields": (
                    "accepted_terms_at", "accepted_terms_version",
                    "accepted_privacy_at", "accepted_privacy_version",
                    "marketing_opt_in",
                )
            },
        ),
        ("Permissions", {"classes": ("collapse",), "fields": ("groups", "user_permissions")}),
        ("Timestamps", {"classes": ("collapse",), "fields": ("last_login", "last_login_ip", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "role", "password1", "password2")}),
    )

    @admin.display(boolean=True, description="Email verified")
    def email_is_verified(self, obj):
        return obj.email_is_verified

    def get_inlines(self, request, obj=None):
        if obj is None:
            return []
        return [StudentProfileInline] if obj.is_student else [AdminProfileInline]


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "stage", "has_platform_access", "assigned_counsellor", "source", "created_at")
    list_filter = ("stage", "has_platform_access", "source", "archived_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "user__phone")
    autocomplete_fields = ("user", "assigned_counsellor")
    readonly_fields = ("access_granted_at", "access_granted_by_payment", "created_at", "updated_at")
    list_select_related = ("user", "assigned_counsellor")


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "job_title", "can_review_documents", "can_view_payments", "can_manage_payment_config")
    list_filter = ("can_review_documents", "can_view_payments", "can_manage_payment_config")
    search_fields = ("user__email", "job_title")
    autocomplete_fields = ("user",)
    actions = ("reset_to_role_defaults",)

    @admin.action(description="Reset permissions to role defaults")
    def reset_to_role_defaults(self, request, queryset):
        for profile in queryset:
            profile.apply_role_defaults()
        self.message_user(request, f"Reset {queryset.count()} profile(s) to role defaults.")


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "expires_at", "used_at")
    list_filter = ("purpose",)
    search_fields = ("user__email",)
    readonly_fields = ("token_hash",)
