from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .models import Application, ChecklistInstance, ChecklistItemInstance, DocumentUpload, StudentDocument
from .services import generate_checklist, resync_checklist


def _progress_bar(percent: int) -> str:
    colour = "#16a34a" if percent >= 80 else "#d97706" if percent >= 40 else "#dc2626"
    return format_html(
        '<div style="background:#e5e7eb;width:120px;height:14px;border-radius:7px;overflow:hidden;display:inline-block">'
        '<div style="background:{};width:{}%;height:100%"></div></div>&nbsp;{}%',
        colour, percent, percent,
    )


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItemInstance
    extra = 0
    fields = ("category_name", "label", "is_required", "status", "document", "reviewed_by", "reviewed_at")
    readonly_fields = ("category_name", "label", "is_required", "reviewed_by", "reviewed_at")
    autocomplete_fields = ("document",)
    ordering = ("category_order", "display_order")
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        # Items come from the snapshot, not from typing them in here.
        return False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "school", "programme", "intake", "status", "progress", "created_at")
    list_filter = ("status", "school", "school__country", "created_at")
    search_fields = ("student__user__email", "student__user__first_name", "student__user__last_name", "school__name", "external_reference")
    autocomplete_fields = ("student", "school", "programme")
    date_hierarchy = "created_at"
    list_select_related = ("student__user", "school", "programme")
    actions = ("generate_checklists", "resync_checklists")

    @admin.display(description="Checklist")
    def progress(self, obj):
        checklist = getattr(obj, "checklist", None)
        if checklist is None:
            return "— not generated —"
        return _progress_bar(checklist.percent_complete)

    @admin.action(description="Generate checklist from the school's live requirements")
    def generate_checklists(self, request, queryset):
        created = 0
        for application in queryset:
            try:
                generate_checklist(application, user=request.user)
                created += 1
            except ValidationError as exc:
                self.message_user(request, f"{application}: {exc.messages[0]}", messages.ERROR)
        if created:
            self.message_user(request, f"Generated {created} checklist(s).")

    @admin.action(description="Re-sync checklist to the latest requirement version")
    def resync_checklists(self, request, queryset):
        for application in queryset:
            checklist = getattr(application, "checklist", None)
            if checklist is None:
                continue
            try:
                report = resync_checklist(checklist, user=request.user)
            except ValidationError as exc:
                self.message_user(request, f"{application}: {exc.messages[0]}", messages.ERROR)
                continue
            if report.is_noop:
                self.message_user(request, f"{application}: already up to date.")
            else:
                self.message_user(
                    request,
                    f"{application}: +{len(report.added)} added, {len(report.updated)} updated, "
                    f"{len(report.preserved)} preserved.",
                )


@admin.register(ChecklistInstance)
class ChecklistInstanceAdmin(admin.ModelAdmin):
    list_display = ("application", "progress", "verified_count", "required_count", "source_version", "last_resynced_at")
    list_filter = ("progress_basis", "generated_at")
    search_fields = ("application__student__user__email", "application__school__name")
    readonly_fields = ("percent_complete", "percent_uploaded", "required_count", "verified_count", "uploaded_count", "source_version")
    inlines = (ChecklistItemInline,)
    list_select_related = ("application__student__user", "application__school")

    @admin.display(description="Progress")
    def progress(self, obj):
        return _progress_bar(obj.percent_complete)


@admin.register(ChecklistItemInstance)
class ChecklistItemInstanceAdmin(admin.ModelAdmin):
    """
    The document review queue (plan §7.4).

    Deliberately a top-level screen rather than something buried inside each
    student — this is the list the team works through every day, filtered to
    'In review' by default.
    """

    list_display = ("label", "student_email", "school", "category_name", "priority", "status", "updated_at")
    list_filter = ("status", "category_name", "priority", "is_required")
    search_fields = ("label", "checklist__application__student__user__email", "checklist__application__school__name")
    autocomplete_fields = ("document", "form_submission")
    readonly_fields = ("label", "category_name", "evidence_type", "reviewed_by", "reviewed_at")
    actions = ("mark_verified",)
    list_select_related = ("checklist__application__student__user", "checklist__application__school")

    @admin.display(description="Student", ordering="checklist__application__student__user__email")
    def student_email(self, obj):
        return obj.checklist.application.student.user.email

    @admin.display(description="School")
    def school(self, obj):
        return obj.checklist.application.school.name

    def get_changelist_instance(self, request):
        # Default the queue to what actually needs attention.
        if not request.GET and "status__exact" not in request.GET:
            request.GET = request.GET.copy()
            request.GET["status__exact"] = ChecklistItemInstance.Status.PENDING_REVIEW
        return super().get_changelist_instance(request)

    @admin.action(description="Mark verified")
    def mark_verified(self, request, queryset):
        for item in queryset:
            item.set_status(ChecklistItemInstance.Status.VERIFIED, user=request.user)
        self.message_user(request, f"Verified {queryset.count()} item(s).")

    # Rejection is intentionally not a bulk action: §10 requires a reason on
    # every rejection, and a reason is per-document, not per-batch.


class DocumentUploadInline(admin.TabularInline):
    model = DocumentUpload
    extra = 0
    fields = ("version", "file", "status", "size_bytes", "reviewed_by", "reviewed_at", "rejection_reason")
    readonly_fields = ("version", "file", "size_bytes", "reviewed_by", "reviewed_at")
    ordering = ("-version",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "shareable_key", "review_status", "expires_on", "updated_at")
    list_filter = ("category", "archived_at")
    search_fields = ("title", "student__user__email", "shareable_key")
    autocomplete_fields = ("student", "category")
    inlines = (DocumentUploadInline,)
    readonly_fields = ("current_upload",)
    list_select_related = ("student__user", "current_upload")


@admin.register(DocumentUpload)
class DocumentUploadAdmin(admin.ModelAdmin):
    list_display = ("document", "version", "status", "size_bytes", "uploaded_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("document__title", "document__student__user__email", "original_filename")
    readonly_fields = ("checksum_sha256", "size_bytes", "content_type", "original_filename")
