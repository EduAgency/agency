import json

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .models import FormDefinition, FormSubmission


@admin.register(FormDefinition)
class FormDefinitionAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "version", "status", "audience", "purpose", "field_count", "submission_count")
    list_filter = ("status", "audience", "purpose")
    search_fields = ("title", "slug")
    readonly_fields = ("published_at", "published_by", "archived_at", "schema_preview")
    actions = ("publish_forms", "create_draft_version")

    fieldsets = (
        (None, {"fields": ("title", "slug", "version", "description", "change_note")}),
        ("Behaviour", {"fields": ("status", "audience", "purpose", "allow_multiple_submissions", "allow_drafts")}),
        ("Presentation", {"fields": ("submit_button_label", "success_message")}),
        ("Schema", {"fields": ("schema", "schema_preview")}),
        ("Publishing", {"classes": ("collapse",), "fields": ("published_at", "published_by", "archived_at")}),
    )

    @admin.display(description="Fields")
    def field_count(self, obj):
        from .schema import field_map

        try:
            return len(field_map(obj.schema or {}))
        except Exception:
            return "?"

    @admin.display(description="Submissions")
    def submission_count(self, obj):
        return obj.submissions.count()

    @admin.display(description="Structure")
    def schema_preview(self, obj):
        if not obj.schema:
            return "—"
        lines = []
        for section in obj.schema.get("sections", []):
            lines.append(f"▸ {section.get('title', section.get('key'))}")
            for field in section.get("fields", []):
                flag = "*" if field.get("required") else " "
                cond = "  (conditional)" if field.get("visible_when") else ""
                lines.append(f"    {flag} {field.get('label')} [{field.get('type')}]{cond}")
        return format_html("<pre style='margin:0'>{}</pre>", "\n".join(lines))

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and not obj.is_editable:
            # Published forms are immutable (§3.3) — use "Create draft version".
            fields += ["schema", "slug", "version", "audience", "purpose", "title"]
        return fields

    @admin.action(description="Publish selected forms")
    def publish_forms(self, request, queryset):
        for form in queryset:
            try:
                form.publish(user=request.user)
                self.message_user(request, f"Published {form}.")
            except (ValidationError, ValueError) as exc:
                self.message_user(request, f"{form}: {exc}", messages.ERROR)

    @admin.action(description="Create a new draft version")
    def create_draft_version(self, request, queryset):
        for form in queryset:
            try:
                draft = form.create_new_version(user=request.user)
                self.message_user(request, f"Created {draft}.")
            except ValidationError as exc:
                self.message_user(request, f"{form}: {exc.message if hasattr(exc, 'message') else exc}", messages.ERROR)


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ("form_slug", "form_version", "subject", "status", "submitted_at")
    list_filter = ("status", "form_slug")
    search_fields = ("form_slug", "student__user__email", "school__name")
    autocomplete_fields = ("form_definition", "student", "school", "application")
    readonly_fields = ("data_preview", "submitted_at")

    @admin.display(description="Version")
    def form_version(self, obj):
        return obj.form_definition.version

    @admin.display(description="Subject")
    def subject(self, obj):
        return obj.student or obj.school or obj.submitted_by or "—"

    @admin.display(description="Answers")
    def data_preview(self, obj):
        return format_html("<pre style='margin:0'>{}</pre>", json.dumps(obj.data, indent=2, default=str))
