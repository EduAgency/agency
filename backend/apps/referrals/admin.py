from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import ReferralCode, ReferralEvent, ReferralPayout, ReferralReward, ReferralRewardRule
from .services import approve_reward, mark_payout_paid


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "owner_type", "owner_label", "signups", "conversions", "earned", "is_active")
    list_filter = ("owner_type", "is_active")
    search_fields = ("code", "partner_name", "partner_email", "student__user__email")
    autocomplete_fields = ("student",)
    readonly_fields = ("signups", "conversions", "earned")

    @admin.display(description="Signups")
    def signups(self, obj):
        return obj.signup_count

    @admin.display(description="Conversions")
    def conversions(self, obj):
        return obj.conversion_count

    @admin.display(description="Earned")
    def earned(self, obj):
        return f"₦{obj.total_earned:,.2f}"


@admin.register(ReferralRewardRule)
class ReferralRewardRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "trigger", "calculation", "amount", "min_referrals", "max_referrals", "is_active", "priority")
    list_filter = ("trigger", "calculation", "is_active")
    search_fields = ("name",)


@admin.register(ReferralEvent)
class ReferralEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "code", "event_type", "referred_student", "is_flagged", "flag_reason")
    list_filter = ("event_type", "is_flagged", "created_at")
    search_fields = ("code__code", "referred_student__user__email", "signup_ip")
    readonly_fields = ("signup_ip", "device_fingerprint")
    list_select_related = ("code", "referred_student__user")


@admin.register(ReferralReward)
class ReferralRewardAdmin(admin.ModelAdmin):
    list_display = ("created_at", "code", "amount", "currency", "status", "flagged", "payout")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("code__code",)
    readonly_fields = ("rule_snapshot", "event")
    actions = ("approve_selected",)

    @admin.display(boolean=True, description="Flagged")
    def flagged(self, obj):
        return obj.event.is_flagged

    @admin.action(description="Approve for payout")
    def approve_selected(self, request, queryset):
        approved = 0
        for reward in queryset:
            try:
                approve_reward(reward, user=request.user)
                approved += 1
            except ValidationError as exc:
                self.message_user(request, f"{reward}: {exc.messages[0]}", messages.ERROR)
        if approved:
            self.message_user(request, f"Approved {approved} reward(s).")

    # Voiding needs a reason, so it is done on the individual record, not in bulk.


@admin.register(ReferralPayout)
class ReferralPayoutAdmin(admin.ModelAdmin):
    list_display = ("requested_at", "code", "amount", "currency", "status", "account_name", "paid_at")
    list_filter = ("status", "requested_at")
    search_fields = ("code__code", "account_name", "account_number", "payment_reference")
    actions = ("mark_paid",)

    @admin.action(description="Mark as paid")
    def mark_paid(self, request, queryset):
        for payout in queryset:
            mark_payout_paid(payout, user=request.user)
        self.message_user(request, f"Marked {queryset.count()} payout(s) paid.")
