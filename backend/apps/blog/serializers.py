"""Serializers.

Two audiences, two shapes. The public serializers expose only what a reader
and a crawler need; the staff serializers expose the editorial machinery.
Keeping them separate means a new internal field cannot leak onto the public
site by accident, which is the usual way that happens.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .authors import AuthorProfile
from .comments import Comment
from .models import BlogSettings, Category, Post, PostFaq, PostRevision, Tag
from .rendering import render


class CategorySerializer(serializers.ModelSerializer):
    post_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "display_order", "post_count")


class TagSerializer(serializers.ModelSerializer):
    post_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "post_count")


class AuthorSerializer(serializers.Serializer):
    """The byline.

    No email, no id — a byline is public, a staff member's address is not. Falls
    back to the account name when there is no ``AuthorProfile``, so a post by
    someone who never set one up still has a byline.
    """

    name = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    avatar_alt = serializers.SerializerMethodField()
    has_page = serializers.SerializerMethodField()

    def _profile(self, user):
        return getattr(user, "author_profile", None)

    def get_name(self, user) -> str:
        profile = self._profile(user)
        if profile:
            return profile.display_name
        return user.get_full_name() or user.first_name or "Nasuru"

    def get_job_title(self, user) -> str:
        profile = self._profile(user)
        if profile and profile.headline:
            return profile.headline
        admin = getattr(user, "admin_profile", None)
        return getattr(admin, "job_title", "") or ""

    def get_slug(self, user) -> str:
        """Only set when the author actually has a page to link to."""
        profile = self._profile(user)
        return profile.slug if profile and profile.has_public_page else ""

    def get_avatar(self, user) -> str | None:
        profile = self._profile(user)
        return profile.avatar.url if profile and profile.avatar else None

    def get_avatar_alt(self, user) -> str:
        profile = self._profile(user)
        return profile.avatar_alt if profile else ""

    def get_has_page(self, user) -> bool:
        profile = self._profile(user)
        return bool(profile and profile.has_public_page)


class AuthorPageSerializer(serializers.ModelSerializer):
    """The author archive page, and the box under an article.

    The bio arrives rendered, through the same sanitiser as a post body — an
    author bio is published copy and gets the same treatment.
    """

    bio_html = serializers.SerializerMethodField()
    same_as = serializers.ListField(child=serializers.URLField(), read_only=True)
    post_count = serializers.IntegerField(source="live_post_count", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = AuthorProfile
        fields = (
            "display_name", "slug", "headline", "bio_html", "credentials",
            "avatar", "avatar_alt", "same_as", "post_count",
        )

    def get_bio_html(self, profile) -> str:
        html, _ = render(profile.bio)
        return html

    def get_avatar(self, profile) -> str | None:
        return profile.avatar.url if profile.avatar else None


class PostFaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostFaq
        fields = ("id", "question", "answer", "display_order")


class CommentSerializer(serializers.ModelSerializer):
    """A comment as a reader sees it.

    ``email``, ``ip_address`` and ``user_agent`` are absent by construction
    rather than filtered out — the safest way not to leak a field is for it never
    to be in the serializer at all.
    """

    author_name = serializers.CharField(source="display_name", read_only=True)
    is_from_staff = serializers.BooleanField(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id", "author_name", "is_from_staff", "body",
            "created_at", "is_pinned", "replies",
        )

    def get_replies(self, comment) -> list[dict]:
        # Filled from the tree the view already built. A nested serializer here
        # would re-query once per comment.
        rows = self.context.get("replies", {}).get(comment.pk, [])
        return CommentSerializer(rows, many=True, context={**self.context, "replies": {}}).data


class PostListSerializer(serializers.ModelSerializer):
    """Cards on /blog and on category and tag pages."""

    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    author = AuthorSerializer(read_only=True)
    hero_image = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "title", "slug", "excerpt", "published_at",
            "reading_minutes", "category", "tags", "author",
            "hero_image", "hero_alt", "comment_count",
        )

    comment_count = serializers.IntegerField(source="approved_comment_count", read_only=True)

    def get_hero_image(self, post) -> str | None:
        """The post's own image, or the configured site-wide fallback."""
        if post.hero_image:
            return post.hero_image.url
        fallback = BlogSettings.load().default_featured_image
        return fallback.url if fallback else None


class PostDetailSerializer(PostListSerializer):
    """One article, rendered, plus everything the page's ``<head>`` needs."""

    related = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + (
            "body_html", "toc", "updated_at",
            "seo_title", "seo_description", "canonical_url", "noindex",
            "ai_involvement", "related",
            "hero_caption", "hero_credit",
            "faqs", "comments_open", "comments", "author_bio",
        )

    faqs = PostFaqSerializer(many=True, read_only=True)
    comments_open = serializers.BooleanField(source="comments_are_open", read_only=True)
    comments = serializers.SerializerMethodField()
    author_bio = serializers.SerializerMethodField()

    def get_comments(self, post) -> list[dict]:
        """The approved thread, two levels deep.

        Built here rather than in the view so the serializer is the single
        definition of this response — the generated schema and the e2e contract
        both read it, and a field the view bolts on afterwards is invisible to
        both.

        One query for the whole tree, then grouped in memory: a nested
        serializer would issue one query per comment.
        """
        rows = list(post.comments.public().select_related("author_user"))
        replies: dict = {}
        for comment in rows:
            if comment.parent_id:
                replies.setdefault(comment.parent_id, []).append(comment)
        roots = sorted(
            (c for c in rows if c.parent_id is None),
            key=lambda c: (not c.is_pinned, c.created_at),
        )
        return CommentSerializer(
            roots, many=True, context={**self.context, "replies": replies}
        ).data

    def get_author_bio(self, post) -> dict | None:
        """The author box under the article, when the settings ask for one."""
        if not BlogSettings.load().show_author_bio_on_article:
            return None
        profile = getattr(post.author, "author_profile", None) if post.author_id else None
        if profile is None or not profile.is_public:
            return None
        return AuthorPageSerializer(profile, context=self.context).data

    def get_related(self, post) -> list[dict]:
        """Three more articles, nearest first.

        Same category before same tag before recent. Real internal linking is
        the single cheapest SEO win on a blog this size, and a reader who
        finishes an article and finds nothing next leaves the site.
        """
        limit = BlogSettings.load().related_post_count
        if limit <= 0:
            return []
        queryset = (
            Post.objects.live()
            .exclude(pk=post.pk)
            .select_related("category", "author")
            .prefetch_related("tags")
        )
        picked: list[Post] = []
        seen: set = set()

        pools = []
        if post.category_id:
            pools.append(queryset.filter(category_id=post.category_id))
        tag_ids = list(post.tags.values_list("id", flat=True))
        if tag_ids:
            pools.append(queryset.filter(tags__id__in=tag_ids).distinct())
        pools.append(queryset)

        for pool in pools:
            for candidate in pool[:6]:
                if candidate.pk in seen:
                    continue
                seen.add(candidate.pk)
                picked.append(candidate)
                if len(picked) == limit:
                    break
            if len(picked) == limit:
                break

        return PostListSerializer(picked, many=True, context=self.context).data


# ---------------------------------------------------------------------------
# Staff
# ---------------------------------------------------------------------------


class PostRevisionSerializer(serializers.ModelSerializer):
    editor_name = serializers.SerializerMethodField()

    class Meta:
        model = PostRevision
        fields = ("id", "title", "created_at", "editor_name", "note")

    def get_editor_name(self, revision) -> str:
        return revision.editor.get_full_name() if revision.editor else "system"


class AdminPostSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(),
        required=False, allow_null=True,
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        source="tags", queryset=Tag.objects.all(), many=True, required=False
    )
    author_name = serializers.SerializerMethodField()
    published_by_name = serializers.SerializerMethodField()
    revision_count = serializers.IntegerField(source="revisions.count", read_only=True)
    faqs = PostFaqSerializer(many=True, read_only=True)
    comment_count = serializers.IntegerField(source="approved_comment_count", read_only=True)
    pending_comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "title", "slug", "excerpt", "body", "body_html", "toc",
            "status", "published_at", "category_id", "tag_ids",
            "author_name", "published_by_name",
            "hero_image", "hero_alt",
            "meta_title", "meta_description", "canonical_url", "noindex",
            "focus_keyword", "ai_involvement", "ai_notes", "style_override_reason",
            "hero_caption", "hero_credit", "comments_closed",
            "faqs", "comment_count", "pending_comment_count",
            "reading_minutes", "view_count", "revision_count",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "body_html", "toc", "reading_minutes", "view_count",
            "status", "published_at", "faqs", "comment_count", "pending_comment_count",
        )
        extra_kwargs = {
            # Left out on create, derived from the title. Editable only while
            # the post is a draft — the model refuses a change after publish.
            "slug": {"required": False},
        }

    def get_pending_comment_count(self, post) -> int:
        return post.comments.needing_review().count()

    def get_author_name(self, post) -> str:
        return post.author.get_full_name() if post.author else ""

    def get_published_by_name(self, post) -> str:
        return post.published_by.get_full_name() if post.published_by else ""


class PublishSerializer(serializers.Serializer):
    publish_at = serializers.DateTimeField(
        required=False, allow_null=True,
        help_text="A future time schedules the post instead of publishing it now.",
    )
    force = serializers.BooleanField(
        default=False,
        help_text="Publish despite the soft warnings. Blockers can never be overridden.",
    )


# ---------------------------------------------------------------------------
# Staff: settings, authors, comments, FAQs
# ---------------------------------------------------------------------------


class BlogSettingsSerializer(serializers.ModelSerializer):
    """Every site-wide blog setting, in one payload.

    `help_text` from the model reaches the settings screen through the generated
    schema, so the reasoning behind a toggle sits next to the toggle instead of
    in a wiki nobody opens.
    """

    featured_aspect_ratio = serializers.FloatField(read_only=True)

    class Meta:
        model = BlogSettings
        exclude = ("id", "created_at")
        read_only_fields = ("updated_at",)

    def validate(self, attrs):
        # Run the model's own rules rather than duplicating them here: they are
        # also enforced in the Django admin and by the seed command.
        instance = BlogSettings.load()
        for field, value in attrs.items():
            setattr(instance, field, value)
        instance.clean()
        return attrs


class AuthorProfileSerializer(serializers.ModelSerializer):
    """Staff view of an author profile."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    post_count = serializers.IntegerField(source="live_post_count", read_only=True)
    has_public_page = serializers.BooleanField(read_only=True)

    class Meta:
        model = AuthorProfile
        fields = (
            "id", "user", "user_email", "display_name", "slug", "headline",
            "bio", "credentials", "avatar", "avatar_alt",
            "website", "linkedin_url", "x_url",
            "is_public", "show_in_directory",
            "post_count", "has_public_page", "created_at", "updated_at",
        )
        read_only_fields = ("slug", "post_count", "has_public_page", "created_at", "updated_at")

    def validate(self, attrs):
        instance = self.instance or AuthorProfile(**{k: v for k, v in attrs.items() if k != "user"})
        if self.instance:
            for field, value in attrs.items():
                setattr(instance, field, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict or {"detail": exc.messages}) from exc
        return attrs


class AdminCommentSerializer(serializers.ModelSerializer):
    """The moderation queue's row.

    This one *does* carry the commenter's email, because a moderator judging
    whether something is spam needs it. It is behind `can_publish_content` and
    it never reaches a public serializer.
    """

    post_title = serializers.CharField(source="post.title", read_only=True)
    post_slug = serializers.CharField(source="post.slug", read_only=True)
    author_name = serializers.CharField(source="display_name", read_only=True)
    is_from_staff = serializers.BooleanField(read_only=True)
    moderated_by_name = serializers.SerializerMethodField()
    parent_body = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id", "post_title", "post_slug", "author_name", "email", "website",
            "body", "status", "flagged_reason", "is_pinned", "is_from_staff",
            "parent", "parent_body", "moderated_by_name", "moderated_at",
            "ip_address", "created_at",
        )
        read_only_fields = fields

    def get_moderated_by_name(self, comment) -> str:
        return comment.moderated_by.get_full_name() if comment.moderated_by else ""

    def get_parent_body(self, comment) -> str:
        """What this is replying to, so a moderator has the context in one row."""
        return comment.parent.body[:200] if comment.parent_id else ""


class CommentSubmissionSerializer(serializers.Serializer):
    """What a reader posts.

    `honeypot` is a field no person fills and `seconds_on_page` is how long the
    form was open. Both are validated in apps.blog.moderation, not here — the
    screening decision belongs in one place.
    """

    body = serializers.CharField(max_length=4000)
    name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    parent = serializers.UUIDField(required=False, allow_null=True)
    honeypot = serializers.CharField(required=False, allow_blank=True)
    seconds_on_page = serializers.FloatField(required=False, allow_null=True, min_value=0)


class CommentModerationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Comment.Status.choices)
    comment_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=100
    )


class AgencyReplySerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000)
