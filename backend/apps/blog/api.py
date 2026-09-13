"""The blog API.

Public read, staff write, and a small set of AI-assist endpoints that never
write anything — they return suggestions for a human to accept.

The public endpoints are deliberately unauthenticated and cacheable: they are
what Next.js renders the marketing site from, and a crawler must be able to
reach every one of them.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, F, Q
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasAdminPermission
from apps.core import audit
from apps.core.models import AuditLog
from apps.core.pagination import DefaultPagination

from . import ai, moderation, services
from .authors import AuthorProfile
from .comments import Comment
from .models import BlogSettings, Category, Post, PostFaq, PostRevision, SlugRedirect, Tag
from .serializers import (
    AdminCommentSerializer,
    AdminPostSerializer,
    AgencyReplySerializer,
    AuthorPageSerializer,
    AuthorProfileSerializer,
    BlogSettingsSerializer,
    CategorySerializer,
    CommentModerationSerializer,
    CommentSerializer,
    CommentSubmissionSerializer,
    PostDetailSerializer,
    PostFaqSerializer,
    PostListSerializer,
    PostRevisionSerializer,
    PublishSerializer,
    TagSerializer,
)

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class MovedPermanently(Exception):
    """A slug that used to belong to this post. Carries the current one."""

    def __init__(self, slug: str):
        super().__init__(slug)
        self.slug = slug


class CommentThrottle(ScopedRateThrottle):
    """A ceiling above the per-IP count in moderation.submit.

    Two limits rather than one because they do different jobs: this one protects
    the database from a flood, the other enforces an editorial policy the
    settings screen can change.
    """

    scope = "blog_comment"


def _client_ip(request) -> str | None:
    """The caller's address, trusting the proxy header only for its first hop.

    Behind a single reverse proxy the left-most entry is the real client;
    anything further right is forgeable. Returns None rather than a wrong value,
    because a wrong value in a rate-limit key is worse than no key.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


class SettingsPagination(DefaultPagination):
    """Page size comes from the editable blog settings, not from code.

    `page_size` is read per request rather than at import, because the whole
    point of the setting is that changing it does not need a deploy.
    """

    @property
    def page_size(self):  # type: ignore[override]
        return BlogSettings.load().posts_per_page

    @page_size.setter
    def page_size(self, value):
        # DRF's __init__ does not set it, but a subclass or mixin might; a
        # read-only property would raise where the base class expects to assign.
        pass


class BlogSettingsView(APIView):
    """The public slice of the blog settings.

    Only the values the frontend needs to render correctly — layout, labels,
    whether to show a byline. Verification codes, blocklists and the analytics id
    stay on the staff endpoint.
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: OpenApiResponse(description="Public display settings.")})
    def get(self, request):
        blog_settings = BlogSettings.load()
        return Response(
            {
                "posts_per_page": blog_settings.posts_per_page,
                "homepage_show_latest": blog_settings.homepage_show_latest,
                "homepage_article_count": blog_settings.homepage_article_count,
                "homepage_section_title": blog_settings.homepage_section_title,
                "listing_layout": blog_settings.listing_layout,
                "show_reading_time": blog_settings.show_reading_time,
                "show_author_byline": blog_settings.show_author_byline,
                "show_published_date": blog_settings.show_published_date,
                "read_more_label": blog_settings.read_more_label,
                "featured_image_aspect": blog_settings.featured_image_aspect,
                "featured_aspect_ratio": blog_settings.featured_aspect_ratio,
                "show_featured_on_listing": blog_settings.show_featured_on_listing,
                "show_featured_on_detail": blog_settings.show_featured_on_detail,
                "comments_enabled": blog_settings.comments_enabled,
                "comments_require_email": blog_settings.comments_require_email,
                "comments_allow_replies": blog_settings.comments_allow_replies,
                "comments_min_seconds": blog_settings.comments_min_seconds,
                "author_pages_enabled": blog_settings.author_pages_enabled,
                "show_author_bio_on_article": blog_settings.show_author_bio_on_article,
                "noindex_tag_pages": blog_settings.noindex_tag_pages,
                "twitter_site": blog_settings.twitter_site,
                "google_site_verification": blog_settings.google_site_verification,
                "bing_site_verification": blog_settings.bing_site_verification,
                "default_meta_description": blog_settings.default_meta_description,
                "default_og_image": (
                    blog_settings.default_og_image.url if blog_settings.default_og_image else None
                ),
                "meta_title_template": blog_settings.meta_title_template,
            }
        )


class PublicAuthorViewSet(viewsets.ReadOnlyModelViewSet):
    """Author archive pages.

    Only for profiles that opted in *and* have something to show — an author
    page with no posts is a thin page, and thin pages cost the whole site.
    """

    permission_classes = [AllowAny]
    serializer_class = AuthorPageSerializer
    pagination_class = None
    lookup_field = "slug"

    def get_queryset(self):
        if not BlogSettings.load().author_pages_enabled:
            return AuthorProfile.objects.none()
        return AuthorProfile.objects.filter(is_public=True).select_related("user")

    def get_object(self):
        profile = super().get_object()
        if not profile.has_public_page:
            raise NotFound("No such author page.")
        return profile

    def list(self, request, *args, **kwargs):
        rows = [p for p in self.get_queryset().filter(show_in_directory=True) if p.has_public_page]
        return Response(AuthorPageSerializer(rows, many=True, context={"request": request}).data)

    @extend_schema(responses={200: PostListSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def posts(self, request, slug=None):
        profile = self.get_object()
        rows = (
            Post.objects.live()
            .filter(author=profile.user)
            .select_related("category", "author")
            .prefetch_related("tags")
        )
        return Response(PostListSerializer(rows, many=True, context={"request": request}).data)


class PublicPostViewSet(viewsets.ReadOnlyModelViewSet):
    """Live posts, addressed by slug.

    A scheduled post is invisible here until its publish time passes, because
    :meth:`PostQuerySet.live` compares against the clock on every request
    rather than trusting a flag some job was meant to flip.
    """

    permission_classes = [AllowAny]
    pagination_class = SettingsPagination
    lookup_field = "slug"

    def get_queryset(self):
        queryset = (
            Post.objects.live()
            .select_related("category", "author")
            .prefetch_related("tags")
        )
        params = self.request.query_params
        if category := params.get("category"):
            queryset = queryset.filter(category__slug=category)
        if tag := params.get("tag"):
            queryset = queryset.filter(tags__slug=tag)
        if search := params.get("search"):
            # Plain containment rather than Postgres full-text search: at this
            # volume it is indistinguishable to a reader, and it keeps the test
            # suite runnable on SQLite.
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(excerpt__icontains=search)
                | Q(body__icontains=search)
            )
        return queryset.distinct()

    def get_serializer_class(self):
        return PostDetailSerializer if self.action == "retrieve" else PostListSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("category", str, description="Category slug."),
            OpenApiParameter("tag", str, description="Tag slug."),
            OpenApiParameter("search", str, description="Matches title, excerpt and body."),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_object(self):
        """Resolve the slug, falling back to the redirect table.

        A slug that used to belong to a live post answers 301 rather than 404,
        so a link printed on somebody else's site two years ago still lands on
        the article. Phase 5 refused slug changes to protect those links; a
        redirect protects them properly.
        """
        try:
            return super().get_object()
        except Http404:
            redirect = (
                SlugRedirect.objects.filter(old_slug=self.kwargs.get("slug", ""))
                .select_related("post")
                .first()
            )
            if redirect and redirect.post.is_live:
                raise MovedPermanently(redirect.post.slug) from None
            raise

    def retrieve(self, request, *args, **kwargs):
        try:
            post = self.get_object()
        except MovedPermanently as moved:
            # 301 with the new slug in the body as well as the header: the
            # Next.js route reads the body, a crawler follows the header.
            return Response(
                {"slug": moved.slug, "detail": "This guide moved."},
                status=status.HTTP_301_MOVED_PERMANENTLY,
                headers={"Location": f"/blog/{moved.slug}"},
            )

        # The comment thread is part of PostDetailSerializer, not bolted on
        # here — that keeps the serializer the single definition of this
        # response, which the OpenAPI schema and the e2e field contract both read.
        data = self.get_serializer(post).data

        # F() so concurrent reads cannot lose each other's increment, and no
        # save() so the body is not re-rendered on every page view.
        Post.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
        return Response(data)

    @extend_schema(
        request=CommentSubmissionSerializer,
        responses={201: OpenApiResponse(description="Submitted, possibly pending review.")},
    )
    @action(detail=True, methods=["post"], throttle_classes=[CommentThrottle])
    def comments(self, request, slug=None):
        """Add a comment. Unauthenticated by design.

        Everything that decides whether this is spam lives in
        apps.blog.moderation.submit — the view's only jobs are to find the post,
        pass the request metadata through, and translate the outcome.
        """
        post = self.get_object()
        serializer = CommentSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        parent = None
        if data.get("parent"):
            parent = Comment.objects.filter(
                pk=data["parent"], post=post, status=Comment.Status.APPROVED
            ).first()
            if parent is None:
                return Response(
                    {"parent": "That comment is not on this guide."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            result = moderation.submit(
                post=post,
                body=data["body"],
                name=data.get("name", ""),
                email=data.get("email", ""),
                website=data.get("website", ""),
                parent=parent,
                honeypot=data.get("honeypot", ""),
                seconds_on_page=data.get("seconds_on_page"),
                user=request.user,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except moderation.CommentsClosed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except moderation.RateLimited as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        except DjangoValidationError as exc:
            return Response(
                exc.message_dict or {"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST
            )

        published = result.comment is not None and result.comment.status == Comment.Status.APPROVED
        return Response(
            {
                "detail": result.message,
                "published": published,
                "comment": CommentSerializer(result.comment).data if published else None,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Category.objects.filter(is_active=True)
            .annotate(
                post_count=Count(
                    "posts",
                    filter=Q(posts__status=Post.Status.PUBLISHED)
                    & Q(posts__published_at__lte=timezone.now()),
                )
            )
            .filter(post_count__gt=0)
        )


class PublicTagViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = TagSerializer
    pagination_class = None
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Tag.objects.annotate(
                post_count=Count(
                    "posts",
                    filter=Q(posts__status=Post.Status.PUBLISHED)
                    & Q(posts__published_at__lte=timezone.now()),
                )
            )
            .filter(post_count__gt=0)
            .order_by("-post_count", "name")
        )


class SitemapIndexView(APIView):
    """Every public URL with a last-modified date.

    Next.js ``sitemap.ts`` reads this. Keeping the list here rather than in the
    frontend means a new content type appears in the sitemap by shipping the
    backend, and the dates are the database's, not a build timestamp.
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: OpenApiResponse(description="Sitemap entries.")})
    def get(self, request):
        posts = Post.objects.live().values("slug", "updated_at", "published_at")
        categories = (
            Category.objects.filter(is_active=True)
            .annotate(
                post_count=Count(
                    "posts",
                    filter=Q(posts__status=Post.Status.PUBLISHED)
                    & Q(posts__published_at__lte=timezone.now()),
                )
            )
            .filter(post_count__gt=0)
            .values("slug", "updated_at")
        )
        blog_settings = BlogSettings.load()
        authors = []
        if blog_settings.sitemap_include_authors and blog_settings.author_pages_enabled:
            authors = [
                {"slug": profile.slug, "last_modified": profile.updated_at.isoformat()}
                for profile in AuthorProfile.objects.filter(is_public=True)
                if profile.has_public_page
            ]

        return Response(
            {
                "posts": [
                    {
                        "slug": p["slug"],
                        "last_modified": (p["updated_at"] or p["published_at"]).isoformat(),
                    }
                    for p in posts
                ],
                "categories": [
                    {"slug": c["slug"], "last_modified": c["updated_at"].isoformat()}
                    for c in categories
                ],
                "authors": authors,
            }
        )


# ---------------------------------------------------------------------------
# Staff
# ---------------------------------------------------------------------------


class AdminPostViewSet(viewsets.ModelViewSet):
    """The composer's backing API.

    Reading and drafting needs ``can_write_content``; publishing needs
    ``can_publish_content`` and is checked again on the action itself, so a
    writer cannot reach it by crafting the request.
    """

    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_write_content"
    serializer_class = AdminPostSerializer
    pagination_class = DefaultPagination
    lookup_field = "slug"

    def get_queryset(self):
        queryset = (
            Post.objects.all()
            .select_related("category", "author", "published_by")
            .prefetch_related("tags", "revisions")
        )
        if status_filter := self.request.query_params.get("status"):
            queryset = queryset.filter(status=status_filter)
        if search := self.request.query_params.get("search"):
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(body__icontains=search)
            )
        return queryset.order_by("-updated_at")

    def perform_create(self, serializer):
        post = serializer.save(author=self.request.user)
        services.snapshot(post, editor=self.request.user, note="Created")

    def perform_update(self, serializer):
        post = serializer.instance
        # Snapshot the state we are about to replace, not the one we just wrote.
        services.snapshot(post, editor=self.request.user, note="Before edit")
        try:
            serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict or {"detail": exc.messages}) from exc

    def perform_destroy(self, instance):
        if instance.status in {Post.Status.PUBLISHED, Post.Status.SCHEDULED}:
            raise ValidationError(
                {
                    "detail": "Unpublish it first. Deleting a live post leaves every link "
                    "to it broken with no explanation."
                }
            )
        instance.delete()

    @extend_schema(responses={200: OpenApiResponse(description="Blockers and warnings.")})
    @action(detail=True, methods=["get"])
    def preflight(self, request, slug=None):
        """What stands between this draft and the public site."""
        return Response(services.check_publishable(self.get_object()).as_dict())

    @extend_schema(request=PublishSerializer, responses={200: AdminPostSerializer})
    @action(detail=True, methods=["post"], required_admin_permission="can_publish_content")
    def publish(self, request, slug=None):
        self._require_publisher(request)
        serializer = PublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = self.get_object()
        try:
            services.publish(
                post,
                actor=request.user,
                when=serializer.validated_data.get("publish_at"),
                force=serializer.validated_data["force"],
            )
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminPostSerializer(post, context={"request": request}).data)

    @extend_schema(responses={200: AdminPostSerializer})
    @action(detail=True, methods=["post"])
    def unpublish(self, request, slug=None):
        self._require_publisher(request)
        post = services.unpublish(
            self.get_object(), actor=request.user, reason=request.data.get("reason", "")
        )
        return Response(AdminPostSerializer(post, context={"request": request}).data)

    @extend_schema(responses={200: PostRevisionSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def revisions(self, request, slug=None):
        queryset = self.get_object().revisions.select_related("editor")
        return Response(PostRevisionSerializer(queryset, many=True).data)

    @extend_schema(responses={200: AdminPostSerializer})
    @action(detail=True, methods=["post"], url_path="revisions/(?P<revision_id>[^/.]+)/restore")
    def restore_revision(self, request, slug=None, revision_id=None):
        post = self.get_object()
        try:
            revision = post.revisions.get(pk=revision_id)
        except (PostRevision.DoesNotExist, ValueError, DjangoValidationError):
            return Response({"detail": "No such revision."}, status=status.HTTP_404_NOT_FOUND)
        services.restore(revision, editor=request.user)
        post.refresh_from_db()
        return Response(AdminPostSerializer(post, context={"request": request}).data)

    def _require_publisher(self, request):
        """Checked here as well as by the action's permission.

        The two are not redundant in practice: this is the check that survives
        someone adding a new publish-adjacent action and forgetting the
        decorator argument.
        """
        profile = getattr(request.user, "admin_profile", None)
        if request.user.role == User.Role.SUPERADMIN:
            return
        if not (profile and profile.has("can_publish_content")):
            raise PermissionDenied("You can write and edit posts, but not publish them.")


class AdminCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_publish_content"
    read_admin_permission = "can_write_content"
    serializer_class = CategorySerializer
    pagination_class = None
    lookup_field = "slug"
    queryset = Category.objects.annotate(post_count=Count("posts"))


class AdminTagViewSet(viewsets.ModelViewSet):
    permission_classes = [HasAdminPermission]
    required_admin_permission = "can_write_content"
    serializer_class = TagSerializer
    pagination_class = None
    lookup_field = "slug"
    queryset = Tag.objects.annotate(post_count=Count("posts"))


class AdminBlogSettingsView(APIView):
    """Read and write every site-wide blog setting.

    Behind `can_publish_content` rather than `can_write_content`: these values
    change what every reader sees, which is an editor's call and not a writer's.
    """

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_publish_content"
    read_admin_permission = "can_write_content"

    @extend_schema(responses={200: BlogSettingsSerializer})
    def get(self, request):
        return Response(BlogSettingsSerializer(BlogSettings.load()).data)

    @extend_schema(request=BlogSettingsSerializer, responses={200: BlogSettingsSerializer})
    def patch(self, request):
        instance = BlogSettings.load()
        serializer = BlogSettingsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        before = {field: getattr(instance, field) for field in serializer.validated_data}
        saved = serializer.save()
        after = {field: getattr(saved, field) for field in serializer.validated_data}

        audit.record(
            AuditLog.Action.UPDATE,
            target=saved,
            actor=request.user,
            target_label="Blog settings",
            changes=audit.diff(
                {k: str(v) for k, v in before.items()}, {k: str(v) for k, v in after.items()}
            ),
        )
        return Response(BlogSettingsSerializer(saved).data)


class AdminAuthorViewSet(viewsets.ModelViewSet):
    """Author profiles.

    A writer may edit their own; an editor may edit anyone's. That split matters
    because a bio is published copy — and `AuthorProfile.clean()` runs it through
    the same house-style scan as an article.
    """

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_write_content"
    serializer_class = AuthorProfileSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = AuthorProfile.objects.select_related("user")
        if self._may_edit_anyone():
            return queryset
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        # A writer can only create their own profile, whatever `user` they send.
        if self._may_edit_anyone():
            serializer.save()
        else:
            serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if not self._may_edit_anyone() and serializer.instance.user_id != self.request.user.pk:
            raise PermissionDenied("You can only edit your own author profile.")
        serializer.save()

    def _may_edit_anyone(self) -> bool:
        user = self.request.user
        if user.role == User.Role.SUPERADMIN:
            return True
        profile = getattr(user, "admin_profile", None)
        return bool(profile and profile.has("can_publish_content"))

    @extend_schema(responses={200: AuthorProfileSerializer})
    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """The signed-in user's own profile, created on first touch.

        Saves the composer a two-step "do you have a profile yet?" dance.
        """
        profile, _ = AuthorProfile.objects.get_or_create(
            user=request.user,
            defaults={"display_name": request.user.get_full_name() or request.user.email},
        )
        if request.method == "GET":
            return Response(AuthorProfileSerializer(profile).data)

        serializer = AuthorProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminCommentViewSet(viewsets.ReadOnlyModelViewSet):
    """The moderation queue.

    Read-only as a viewset: a comment's text is never edited by us — that would
    be putting words in a reader's mouth. The only writes are a status change and
    an agency reply, both of which are their own action and both audited.
    """

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_publish_content"
    read_admin_permission = "can_write_content"
    serializer_class = AdminCommentSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        queryset = Comment.objects.select_related("post", "author_user", "moderated_by", "parent")
        status_filter = self.request.query_params.get("status", "pending")
        if status_filter != "all":
            queryset = queryset.filter(status=status_filter)
        if post_slug := self.request.query_params.get("post"):
            queryset = queryset.filter(post__slug=post_slug)
        if search := self.request.query_params.get("search"):
            queryset = queryset.filter(
                Q(body__icontains=search) | Q(name__icontains=search) | Q(email__icontains=search)
            )
        # Oldest pending first: a queue people work through, not a feed.
        order = "created_at" if status_filter == Comment.Status.PENDING else "-created_at"
        return queryset.order_by(order)

    @extend_schema(responses={200: OpenApiResponse(description="Counts per status.")})
    @action(detail=False, methods=["get"])
    def summary(self, request):
        counts = dict(
            Comment.objects.values_list("status").annotate(n=Count("id")).values_list("status", "n")
        )
        return Response(
            {
                "pending": counts.get(Comment.Status.PENDING, 0),
                "approved": counts.get(Comment.Status.APPROVED, 0),
                "spam": counts.get(Comment.Status.SPAM, 0),
                "rejected": counts.get(Comment.Status.REJECTED, 0),
            }
        )

    @extend_schema(
        request=CommentModerationSerializer,
        responses={200: OpenApiResponse(description="How many changed.")},
    )
    @action(detail=False, methods=["post"], url_path="moderate")
    def moderate_many(self, request):
        """Bulk approve / spam / reject.

        Bulk because a moderator clearing a morning's queue should not click
        through fifteen confirmations; audited per comment because "who approved
        this" is asked about one comment, not about a batch.
        """
        serializer = CommentModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = Comment.objects.filter(pk__in=serializer.validated_data["comment_ids"])
        changed = 0
        for comment in rows:
            moderation.moderate(
                comment, serializer.validated_data["status"], moderator=request.user
            )
            changed += 1
        return Response({"changed": changed})

    @extend_schema(responses={200: AdminCommentSerializer})
    @action(detail=True, methods=["post"])
    def pin(self, request, pk=None):
        comment = self.get_object()
        comment.is_pinned = not comment.is_pinned
        comment.save(update_fields=["is_pinned", "updated_at"])
        return Response(AdminCommentSerializer(comment).data)

    @extend_schema(request=AgencyReplySerializer, responses={201: AdminCommentSerializer})
    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        serializer = AgencyReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = moderation.reply_as_agency(
            self.get_object(), serializer.validated_data["body"], author=request.user
        )
        return Response(AdminCommentSerializer(reply).data, status=status.HTTP_201_CREATED)


class AdminFaqViewSet(viewsets.ModelViewSet):
    """FAQ entries, addressed by post.

    Separate from the post serializer because they are ordered rows the composer
    adds and removes one at a time, and nesting a writable list inside the post
    payload makes a partial save ambiguous.
    """

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_write_content"
    serializer_class = PostFaqSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = PostFaq.objects.select_related("post")
        if post_slug := self.request.query_params.get("post"):
            return queryset.filter(post__slug=post_slug)
        return queryset

    def perform_create(self, serializer):
        slug = self.request.data.get("post")
        post = Post.objects.filter(slug=slug).first()
        if post is None:
            raise ValidationError({"post": "Send the post's slug."})
        try:
            serializer.save(post=post)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict or {"detail": exc.messages}) from exc

    def perform_update(self, serializer):
        try:
            serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict or {"detail": exc.messages}) from exc


# ---------------------------------------------------------------------------
# AI assist
# ---------------------------------------------------------------------------


class AiAssistThrottle(ScopedRateThrottle):
    scope = "blog_ai"


class AiRequestSerializer(serializers.Serializer):
    """One envelope for every assist, because they share a permission,
    a throttle, and the same "this is a suggestion" contract."""

    task = serializers.ChoiceField(
        choices=["outline", "draft", "seo", "titles", "rewrite", "review"]
    )
    topic = serializers.CharField(required=False, allow_blank=True, max_length=300)
    audience_note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    must_cover = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    body = serializers.CharField(required=False, allow_blank=True, max_length=60000)
    instruction = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    outline = serializers.JSONField(required=False)
    words = serializers.IntegerField(required=False, min_value=300, max_value=3000, default=1100)

    def validate(self, attrs):
        task = attrs["task"]
        needs = {
            "outline": ["topic"],
            "draft": ["outline"],
            "seo": ["title", "body"],
            "titles": ["body"],
            "rewrite": ["body", "instruction"],
            "review": ["body"],
        }[task]
        missing = [field for field in needs if not attrs.get(field)]
        if missing:
            raise serializers.ValidationError(
                {field: "Required for this task." for field in missing}
            )
        return attrs


class AiAssistView(APIView):
    """Ask Claude for a suggestion. Writes nothing.

    Every response carries a ``review`` block from the same house-style scan
    that gates publishing, so an editor sees a problem in the suggestion before
    they paste it into the draft rather than at publish time.
    """

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_write_content"
    throttle_classes = [AiAssistThrottle]

    @extend_schema(
        request=AiRequestSerializer,
        responses={200: OpenApiResponse(description="A suggestion, plus a house-style review.")},
    )
    def post(self, request):
        if not ai.is_enabled():
            return Response(
                {
                    "detail": "AI assist is not configured on this environment. "
                    "Set ANTHROPIC_API_KEY to enable it.",
                    "code": "ai_not_configured",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = AiRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            payload = self._run(data)
        except ai.AiUnavailable as exc:
            return Response(
                {"detail": str(exc), "code": "ai_unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        scannable = payload.get("body") or payload.get("text") or ""
        if scannable:
            payload["review"] = ai.review_flags(scannable).as_dict()
        return Response(payload)

    def _run(self, data: dict) -> dict:
        task = data["task"]

        if task == "outline":
            outline = ai.suggest_outline(
                data["topic"],
                audience_note=data.get("audience_note", ""),
                must_cover=data.get("must_cover", ""),
            )
            return {"outline": outline.model_dump()}

        if task == "draft":
            try:
                outline = ai.ArticleOutline.model_validate(data["outline"])
            except Exception as exc:
                raise ValidationError({"outline": f"Not a valid outline: {exc}"}) from exc
            body = ai.write_draft(outline, words=data["words"])
            return {"body": body}

        if task == "seo":
            return {"seo": ai.suggest_seo(data["title"], data["body"]).model_dump()}

        if task == "titles":
            return {
                "titles": ai.suggest_titles(
                    data["body"], current_title=data.get("title", "")
                ).model_dump()
            }

        if task == "rewrite":
            return {"body": ai.rewrite(data["body"], data["instruction"])}

        # review — the local scan only, no model call and no cost.
        return {"review": ai.review_flags(data["body"]).as_dict(), "text": ""}


class AiStatusView(APIView):
    """Whether the composer should show its assist controls at all."""

    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "can_write_content"

    @extend_schema(responses={200: OpenApiResponse(description="AI assist availability.")})
    def get(self, request):
        return Response({"enabled": ai.is_enabled(), "model": ai.MODEL if ai.is_enabled() else ""})
