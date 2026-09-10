from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    Country,
    Programme,
    RequirementCategory,
    RequirementItem,
    School,
    SchoolRequirementSet,
)


@admin.register(RequirementCategory)
class RequirementCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "iso_code", "is_active")
    search_fields = ("name", "iso_code")


class ProgrammeInline(admin.TabularInline):
    model = Programme
    extra = 0
    fields = ("name", "level", "intakes", "application_deadline", "is_active")
    show_change_link = True


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "kind", "is_partner", "is_active", "requirement_set_status")
    list_filter = ("kind", "country", "is_partner", "is_active")
    search_fields = ("name", "city")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProgrammeInline,)
    list_select_related = ("country",)

    @admin.display(description="Live requirements")
    def requirement_set_status(self, obj):
        current = obj.current_requirement_set
        return f"v{current.version} ({current.items.count()} items)" if current else "— none published —"


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "level", "application_deadline", "is_active")
    list_filter = ("level", "school__country", "is_active")
    search_fields = ("name", "school__name")
    autocomplete_fields = ("school",)


class RequirementItemInline(admin.TabularInline):
    model = RequirementItem
    extra = 1
    fields = (
        "display_order", "category", "label", "evidence_type",
        "is_required", "priority", "is_shareable", "shareable_key", "is_active",
    )
    autocomplete_fields = ("category",)
    ordering = ("category__display_order", "display_order")


@admin.register(SchoolRequirementSet)
class SchoolRequirementSetAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "version", "item_count", "is_template", "published_at")
    list_filter = ("status", "is_template", "school__country")
    search_fields = ("name", "school__name")
    autocomplete_fields = ("school", "programme")
    inlines = (RequirementItemInline,)
    readonly_fields = ("published_at", "cloned_from")
    actions = ("publish_sets", "clone_as_template")

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.filter(is_active=True).count()

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        # A published set is frozen; edits go through a new version, so a
        # student's snapshot can never be rewritten underneath them (§4.3).
        if obj and not obj.is_editable:
            fields += ["name", "school", "programme", "is_template", "version"]
        return fields

    @admin.action(description="Publish selected requirement sets")
    def publish_sets(self, request, queryset):
        published = 0
        for requirement_set in queryset:
            try:
                requirement_set.publish(user=request.user)
                published += 1
            except ValidationError as exc:
                self.message_user(request, f"{requirement_set}: {exc.message if hasattr(exc, 'message') else exc}", messages.ERROR)
        if published:
            self.message_user(request, f"Published {published} requirement set(s).")

    @admin.action(description="Clone as a reusable template")
    def clone_as_template(self, request, queryset):
        for requirement_set in queryset:
            clone = requirement_set.clone(name=f"{requirement_set.name} (template)", user=request.user)
            clone.is_template = True
            clone.school = None
            clone.programme = None
            clone.save(update_fields=["is_template", "school", "programme", "updated_at"])
        self.message_user(request, f"Created {queryset.count()} template(s).")


@admin.register(RequirementItem)
class RequirementItemAdmin(admin.ModelAdmin):
    list_display = ("label", "requirement_set", "category", "evidence_type", "is_required", "priority", "is_active")
    list_filter = ("category", "evidence_type", "is_required", "priority", "is_active")
    search_fields = ("label", "requirement_set__name", "requirement_set__school__name")
    autocomplete_fields = ("requirement_set", "category", "linked_form")
