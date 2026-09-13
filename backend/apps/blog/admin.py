"""Django admin.

The composer in the staff console is the tool writers will actually use. This
exists for the things an admin does once a quarter — fixing a category, reading
a revision, checking who published what — and for recovery when the frontend is
down.
"""

from __future__ import annotations

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe

from . import moderation, services
from .models import (
    AuthorProfile,
    BlogSettings,
    Category,
    Comment,
    Post,
    PostFaq,
    PostRevision,
    SlugRedirect,
    Tag,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "display_order", "is_active", "post_count")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("display_order", "is_active")

    @admin.display(description="posts")
    def post_count(self, obj) -> int:
        return obj.posts.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


class PostFaqInline(admin.TabularInline):
    model = PostFaq
    extra = 1
    fields = ("question", "answer", "display_order")


class PostRevisionInline(admin.TabularInline):
    model = PostRevision
    extra = 0
    can_delete = False
    fields = ("created_at", "title", "editor", "note")
    readonly_fields = fields
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj) -> bool:
        return False


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title", "status", "category", "published_at",
        "ai_involvement", "reading_minutes", "view_count",
    )
    list_filter = ("status", "category", "ai_involvement", "noindex", "comments_closed")
    search_fields = ("title", "excerpt", "body", "slug")
    autocomplete_fields = ("tags",)
    inlines = [PostFaqInline, PostRevisionInline]
    date_hierarchy = "published_at"
    actions = ["publish_selected", "unpublish_selected"]
    readonly_fields = (
        "body_html_preview", "toc", "reading_minutes", "view_count",
        "published_by", "created_at", "updated_at",
    )
    fieldsets = (
        (None, {"fields": ("title", "slug", "excerpt", "body", "body_html_preview")}),
        ("Placement", {"fields": ("category", "tags", "author", "status", "published_at")}),
        (
            "Featured image",
            {
                "fields": ("hero_image", "hero_alt", "hero_caption", "hero_credit"),
                "description": (
                    "Alt text is required whenever there is an image — that is WCAG 1.1.1, not a "
                    "preference. Caption and credit are optional and do a different job."
                ),
            },
        ),
        ("Comments", {"fields": ("comments_closed",)}),
        (
            "Search",
            {
                "fields": ("meta_title", "meta_description", "focus_keyword", "canonical_url", "noindex"),
                "description": "Leave the title and description blank to fall back to the post's own.",
            },
        ),
        (
            "Provenance",
            {
                "fields": ("ai_involvement", "ai_notes", "style_override_reason"),
                "description": (
                    "If Claude wrote or edited any of this, say so and say what you changed. "
                    "The style override is only for a post that quotes the claims it is warning about."
                ),
            },
        ),
        ("Derived", {"fields": ("toc", "reading_minutes", "view_count", "published_by", "created_at", "updated_at")}),
    )

    def get_prepopulated_fields(self, request, obj=None):
        # Never re-derive the slug of a post that is already public.
        if obj and obj.status in {Post.Status.PUBLISHED, Post.Status.ARCHIVED}:
            return {}
        return {"slug": ("title",)}

    @admin.display(description="Rendered body")
    def body_html_preview(self, obj):
        if not obj or not obj.body_html:
            return "—"
        # Already sanitised by apps.blog.rendering on the way into the field,
        # which is the only path that writes it.
        return mark_safe(f'<div style="max-width:48rem">{obj.body_html}</div>')  # noqa: S308

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        if change:
            services.snapshot(obj, editor=request.user, note="Edited in Django admin")
        super().save_model(request, obj, form, change)

    @admin.action(description="Publish selected posts")
    def publish_selected(self, request, queryset):
        for post in queryset:
            try:
                services.publish(post, actor=request.user, force=True)
            except ValidationError as exc:
                blockers = exc.message_dict.get("blockers", exc.messages)
                self.message_user(
                    request,
                    f"{post.title}: " + " ".join(blockers),
                    level=messages.ERROR,
                )
            else:
                self.message_user(request, f"Published {post.title}.")

    @admin.action(description="Take selected posts off the site")
    def unpublish_selected(self, request, queryset):
        for post in queryset:
            services.unpublish(post, actor=request.user, reason="Unpublished from Django admin")
        self.message_user(request, f"Unpublished {queryset.count()} post(s).")


@admin.register(PostRevision)
class PostRevisionAdmin(admin.ModelAdmin):
    list_display = ("post", "created_at", "editor", "note")
    list_filter = ("post",)
    readonly_fields = ("post", "title", "body", "editor", "note", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(BlogSettings)
class BlogSettingsAdmin(admin.ModelAdmin):
    """The singleton.

    Add and delete are both refused: there is one row, and the whole design
    depends on there being one row. The staff console's settings screen is the
    intended editor; this exists for recovery.
    """

    fieldsets = (
        (
            "Listing and homepage",
            {
                "fields": (
                    "posts_per_page", "listing_layout",
                    "homepage_show_latest", "homepage_article_count", "homepage_section_title",
                    "show_reading_time", "show_author_byline", "show_published_date",
                    "related_post_count",
                )
            },
        ),
        (
            "Excerpts",
            {
                "fields": (
                    "excerpt_source", "excerpt_length",
                    "excerpt_required_to_publish", "read_more_label",
                )
            },
        ),
        (
            "Featured images",
            {
                "fields": (
                    "featured_image_required", "featured_image_aspect",
                    "show_featured_on_listing", "show_featured_on_detail",
                    "default_featured_image",
                )
            },
        ),
        (
            "Comments",
            {
                "fields": (
                    "comments_enabled", "comments_require_approval", "comments_require_email",
                    "comments_allow_replies", "comments_close_after_days", "comments_notify_staff",
                    "comments_max_links", "comments_min_seconds", "comments_blocklist",
                    "comments_per_hour_per_ip",
                ),
                "description": "Every default here is the cautious one. Leave approval on.",
            },
        ),
        ("Authors", {"fields": ("author_pages_enabled", "show_author_bio_on_article")}),
        (
            "SEO",
            {
                "fields": (
                    "meta_title_template", "default_meta_description", "default_og_image",
                    "twitter_site", "google_site_verification", "bing_site_verification",
                    "analytics_measurement_id",
                    "feed_full_text", "feed_item_count",
                    "sitemap_include_authors", "noindex_tag_pages",
                )
            },
        ),
    )

    def has_add_permission(self, request) -> bool:
        return not BlogSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "headline", "is_public", "post_count")
    list_filter = ("is_public", "show_in_directory")
    search_fields = ("display_name", "user__email", "headline")
    readonly_fields = ("slug", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("user", "display_name", "slug", "headline")}),
        (
            "Bio",
            {
                "fields": ("bio", "credentials"),
                "description": (
                    "Both go through the house-style scan. An author bio is the most tempting "
                    "place on the site to invent a qualification."
                ),
            },
        ),
        ("Photo", {"fields": ("avatar", "avatar_alt")}),
        (
            "Elsewhere",
            {
                "fields": ("website", "linkedin_url", "x_url"),
                "description": "Emitted as Person.sameAs — how a search engine ties a byline to a real identity.",
            },
        ),
        ("Visibility", {"fields": ("is_public", "show_in_directory")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="live posts")
    def post_count(self, obj) -> int:
        return obj.live_post_count


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Moderation of last resort.

    The staff console's queue is the tool people should use; this is here for the
    same reason the rest of this file is. The comment body is read-only on
    purpose — editing a reader's words is putting something in their mouth.
    """

    list_display = ("display_name", "post", "status", "flagged_reason", "is_pinned", "created_at")
    list_filter = ("status", "is_pinned", "post")
    search_fields = ("body", "name", "email")
    actions = ["approve_selected", "mark_spam", "reject_selected"]
    readonly_fields = (
        "post", "parent", "author_user", "name", "email", "website", "body",
        "flagged_reason", "ip_address", "user_agent",
        "moderated_by", "moderated_at", "created_at", "updated_at",
    )
    fields = ("status", "is_pinned", *readonly_fields)

    def has_add_permission(self, request) -> bool:
        return False

    @admin.action(description="Approve selected comments")
    def approve_selected(self, request, queryset):
        for comment in queryset:
            moderation.moderate(comment, Comment.Status.APPROVED, moderator=request.user)
        self.message_user(request, f"Approved {queryset.count()} comment(s).")

    @admin.action(description="Mark selected as spam")
    def mark_spam(self, request, queryset):
        for comment in queryset:
            moderation.moderate(comment, Comment.Status.SPAM, moderator=request.user)
        self.message_user(request, f"Marked {queryset.count()} as spam.")

    @admin.action(description="Reject selected comments")
    def reject_selected(self, request, queryset):
        for comment in queryset:
            moderation.moderate(comment, Comment.Status.REJECTED, moderator=request.user)
        self.message_user(request, f"Rejected {queryset.count()} comment(s).")


@admin.register(SlugRedirect)
class SlugRedirectAdmin(admin.ModelAdmin):
    """Created automatically when a live post's slug changes.

    Editable because occasionally you want to point an old URL somewhere new by
    hand — a retired article at a successor, for instance.
    """

    list_display = ("old_slug", "post", "created_at")
    search_fields = ("old_slug", "post__slug", "post__title")
    autocomplete_fields = ("post",)
