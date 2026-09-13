"""The blog: the rules that matter, and the ones that are easy to break later.

These tests are deliberately weighted towards the promises the app makes about
what can reach the public site — the slug freeze, the publish gate, the
house-style scan, the sanitiser — rather than towards CRUD coverage. The AI
module is exercised only through its offline parts; no test here calls Claude.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import AdminProfile
from apps.blog import ai, moderation, rendering, services
from apps.blog.comments import Comment
from apps.blog.models import (
    AuthorProfile,
    BlogSettings,
    Category,
    Post,
    PostFaq,
    SlugRedirect,
    Tag,
)

User = get_user_model()

# Long enough to clear the 120-word floor in check_publishable, and written in
# house style so the scan does not flag it — a fixture that the app's own rules
# reject would make every other assertion here meaningless.
GOOD_BODY = """
## What a school actually asks you for

Every school publishes a list of what it needs before it will look at your
application. The list is shorter than most people expect, and almost all of it
is paperwork you already have or can get in a week.

You will need proof that you finished secondary school, and proof of whatever
you studied after that. You will need a passport that is still valid. You will
need something written in your own voice explaining why you want the course.
Some schools want a reference from a teacher or an employer. Some want proof
that you can follow the course in the language it is taught in.

## Where people lose time

The delay is almost never the school. It is waiting on a transcript, or
discovering that a document has to be translated, or finding out that a passport
expires too soon. Start the paperwork before you start the applications, and you
remove most of the waiting from the process.

## What happens after an offer

An admission letter comes first. Only then does the visa application make
sense, because the visa is an application to go and study at a named school,
and without the letter there is nothing to apply about. Anyone who tells you to
start the visa first is either confused or selling you something.

## What it still costs

Tuition-free means the school does not charge you tuition. It does not mean the
year is free. You still pay to live somewhere, to eat, to travel, and to have
documents translated, and most schools want to see that you can cover those
before they will admit you. Those figures vary by school and they change, so ask
us rather than trusting a number you read somewhere.
""".strip()


@pytest.fixture(autouse=True)
def fresh_blog_settings(db):
    """A clean settings row per test.

    `BlogSettings.load()` caches, and the cache outlives a transaction rollback
    — so without this, a test that turns comments off turns them off for
    everything that runs after it.
    """
    from django.core.cache import cache

    cache.delete("blog:settings")
    settings_row = BlogSettings.load()
    yield settings_row
    cache.delete("blog:settings")


@pytest.fixture
def editor(db):
    """Staff who can write and publish."""
    user = User.objects.create_user(
        email="editor@nasuru.com", password="pass-word-1234",
        role=User.Role.ADMIN, is_staff=True, first_name="Ngozi", last_name="Eze",
    )
    profile, _ = AdminProfile.objects.get_or_create(user=user)
    profile.can_write_content = True
    profile.can_publish_content = True
    profile.save()
    return user


@pytest.fixture
def writer(db):
    """Staff who can draft but must not be able to publish."""
    user = User.objects.create_user(
        email="writer@nasuru.com", password="pass-word-1234",
        role=User.Role.COUNSELLOR, is_staff=True, first_name="Tunde",
    )
    profile, _ = AdminProfile.objects.get_or_create(user=user)
    profile.can_write_content = True
    profile.can_publish_content = False
    profile.save()
    return user


@pytest.fixture
def blog_category(db):
    return Category.objects.create(name="Applying", description="How the process works.")


@pytest.fixture
def draft(db, editor, blog_category):
    return Post.objects.create(
        title="What a school asks you for",
        body=GOOD_BODY,
        excerpt="The list is shorter than most people expect.",
        category=blog_category,
        author=editor,
        focus_keyword="what a school asks you for",
    )


# ---------------------------------------------------------------------------
# Model rules
# ---------------------------------------------------------------------------


def test_slug_is_derived_and_unique(db, editor):
    first = Post.objects.create(title="How to write a motivation letter", author=editor)
    second = Post.objects.create(title="How to write a motivation letter", author=editor)
    assert first.slug == "how-to-write-a-motivation-letter"
    assert second.slug == "how-to-write-a-motivation-letter-2"


def test_changing_a_live_slug_leaves_a_redirect(draft, editor):
    """The freeze became a 301.

    Refusing the change protected inbound links; a redirect protects them
    properly, so the change is allowed and the old URL keeps working.
    """
    services.publish(draft, actor=editor, force=True)
    original = draft.slug

    draft.slug = "a-better-slug"
    draft.save()
    draft.refresh_from_db()

    assert draft.slug == "a-better-slug"
    assert SlugRedirect.objects.filter(old_slug=original, post=draft).exists()


def test_moving_back_to_an_old_slug_does_not_leave_a_self_redirect(draft, editor):
    services.publish(draft, actor=editor, force=True)
    original = draft.slug

    draft.slug = "interim-slug"
    draft.save()
    draft.slug = original
    draft.save()

    assert not SlugRedirect.objects.filter(old_slug=original).exists()
    assert SlugRedirect.objects.filter(old_slug="interim-slug", post=draft).exists()


def test_retitling_a_published_post_is_allowed(draft, editor):
    """The title is editorial; the URL is a promise. Only the URL is frozen."""
    services.publish(draft, actor=editor, force=True)
    draft.title = "What every school asks you for"
    draft.save()
    draft.refresh_from_db()
    assert draft.title == "What every school asks you for"
    assert draft.slug == "what-a-school-asks-you-for"


def test_publishing_requires_a_named_person(draft):
    draft.status = Post.Status.PUBLISHED
    draft.published_at = timezone.now()
    with pytest.raises(ValidationError) as exc:
        draft.full_clean(exclude=["hero_image"])
    assert "published_by" in exc.value.message_dict


def test_a_future_publish_time_becomes_a_schedule(draft, editor):
    services.publish(draft, actor=editor, when=timezone.now() + timedelta(days=2), force=True)
    draft.refresh_from_db()
    assert draft.status == Post.Status.SCHEDULED
    assert draft.pk not in {p.pk for p in Post.objects.live()}


def test_a_scheduled_post_goes_live_by_itself(draft, editor):
    """No cron job flips a flag — live() reads the clock."""
    services.publish(draft, actor=editor, when=timezone.now() + timedelta(minutes=1), force=True)
    Post.objects.filter(pk=draft.pk).update(
        status=Post.Status.PUBLISHED, published_at=timezone.now() - timedelta(minutes=1)
    )
    assert draft.pk in {p.pk for p in Post.objects.live()}


def test_reading_time_and_excerpt_are_derived(db, editor):
    post = Post.objects.create(title="Derived fields", body=GOOD_BODY, author=editor)
    assert post.reading_minutes >= 1
    assert post.excerpt  # filled from the body when the writer left it blank


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_script_tags_never_survive_rendering():
    html, _ = rendering.render("Hello\n\n<script>alert(1)</script>\n\n<p onclick=\"x()\">hi</p>")
    assert "<script" not in html
    assert "onclick" not in html


def test_javascript_urls_are_stripped():
    """Raw HTML, not Markdown link syntax — Markdown refuses the scheme on its
    own, so this exercises the sanitiser, which is the layer that has to hold
    when a writer pastes HTML."""
    html, _ = rendering.render('<a href="javascript:alert(1)">click</a>')
    assert "javascript:" not in html
    html, _ = rendering.render('<img src="javascript:alert(1)">')
    assert "javascript:" not in html


def test_headings_get_stable_deduplicated_anchors():
    html, headings = rendering.render("## What it costs\n\ntext\n\n## What it costs\n\nmore")
    assert [h.anchor for h in headings] == ["what-it-costs", "what-it-costs-2"]
    assert 'id="what-it-costs-2"' in html


def test_toc_is_stored_on_save(draft):
    assert len(draft.toc) >= 3
    assert draft.toc[0]["level"] == 2
    assert "anchor" in draft.toc[0]


# ---------------------------------------------------------------------------
# The house-style scan
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "We guarantee your admission.",
        "Our approval rate is 100%.",
        "Your visa is assured once you pay.",
    ],
)
def test_guarantees_are_flagged(body):
    review = ai.review_flags(body)
    assert not review.ok
    assert any(f.kind == "claim" for f in review.flags)


def test_naming_a_country_is_flagged():
    review = ai.review_flags("Many students choose Germany for its tuition-free universities.")
    assert any(f.kind == "country" for f in review.flags)


def test_unverified_figures_are_flagged_but_the_access_fee_is_not(access_fee):
    """The permitted figure is read from the pricing row, never typed here.

    This test used to hardcode ₦5,000 and passed only because the code did too.
    It now asks what the fee actually is — which is also how it caught that the
    environment was charging ₦50,000.
    """
    review = ai.review_flags("Living costs run to ₦18,000,000 a year.")
    assert any(f.kind == "figure" for f in review.flags)
    assert ai.review_flags(f"The access fee is {access_fee.formatted_access_fee}.").ok


def test_visa_before_admission_is_flagged():
    review = ai.review_flags("You should apply for the visa before your admission letter arrives.")
    assert any("order is wrong" in f.why for f in review.flags)


def test_the_good_body_passes_its_own_rules():
    assert ai.review_flags(GOOD_BODY).ok, ai.review_flags(GOOD_BODY).as_dict()


# ---------------------------------------------------------------------------
# The publish gate
# ---------------------------------------------------------------------------


def test_a_short_post_cannot_be_published(db, editor):
    post = Post.objects.create(title="Too short", body="Three words only.", author=editor)
    check = services.check_publishable(post)
    assert not check.ok
    with pytest.raises(ValidationError):
        services.publish(post, actor=editor, force=True)


def test_a_flagged_claim_blocks_publishing_even_with_force(db, editor, blog_category):
    post = Post.objects.create(
        title="Guaranteed admission",
        body=GOOD_BODY + "\n\nWe guarantee your admission.",
        excerpt="x",
        category=blog_category,
        author=editor,
    )
    with pytest.raises(ValidationError) as exc:
        services.publish(post, actor=editor, force=True)
    assert exc.value.message_dict["blockers"]


def test_an_article_warning_about_scam_claims_can_be_published_with_a_reason(
    db, editor, blog_category
):
    """The guard's own false-positive case, and the reason the override exists.

    An article teaching readers to spot "guaranteed visa" language necessarily
    contains the phrase. Refusing to publish it would be the house-style scan
    defeating the thing it is there to protect.
    """
    post = Post.objects.create(
        title="Spotting a dishonest agent",
        body=GOOD_BODY
        + (
            r"""

## What to walk away from

Anyone offering a guaranteed visa is selling you something. So is anyone who
wants to start the visa before your admission letter exists. Walk away from both.
"""
        ),
        excerpt="The phrases that should end a conversation.",
        category=blog_category,
        author=editor,
    )

    blocked = services.check_publishable(post)
    assert not blocked.ok
    with pytest.raises(ValidationError):
        services.publish(post, actor=editor, force=True)

    post.style_override_reason = (
        "Quotes the claims it is warning readers about; each appears in a sentence "
        "telling the reader to walk away."
    )
    post.save()

    allowed = services.check_publishable(post)
    assert allowed.ok
    # Not silently waved through — they become warnings the editor acknowledges.
    assert any("guaranteed" in warning for warning in allowed.warnings)

    services.publish(post, actor=editor, force=True)
    assert post.is_live


def test_the_override_reason_reaches_the_audit_trail(
    draft, editor, django_capture_on_commit_callbacks
):
    """Audit rows are written on_commit, so the callback has to be run here —
    in production it fires when the publish transaction lands."""
    from apps.core.models import AuditLog

    draft.style_override_reason = "Quotes the claims it warns against."
    draft.save()
    with django_capture_on_commit_callbacks(execute=True):
        services.publish(draft, actor=editor, force=True)

    entry = AuditLog.objects.filter(
        action=AuditLog.Action.PUBLISH, target_id=str(draft.pk)
    ).first()
    assert entry is not None
    assert entry.metadata["style_override_reason"] == "Quotes the claims it warns against."


def test_ai_assisted_posts_must_record_what_changed(draft, editor):
    draft.ai_involvement = Post.AiInvolvement.DRAFT
    draft.save()
    check = services.check_publishable(draft)
    assert any("Record what was generated" in b for b in check.blockers)

    draft.ai_notes = "Claude drafted sections 1-3; I rewrote the costs section and cut two claims."
    draft.save()
    assert services.check_publishable(draft).ok


def test_warnings_do_not_block_but_must_be_acknowledged(db, editor, blog_category):
    post = Post.objects.create(
        title="A title that is quite a lot longer than sixty characters, which search results will cut",
        body=GOOD_BODY,
        excerpt="Fine.",
        category=blog_category,
        author=editor,
        focus_keyword="something absent from the article",
    )
    check = services.check_publishable(post)
    assert check.ok  # no blockers
    assert check.warnings

    with pytest.raises(ValidationError) as exc:
        services.publish(post, actor=editor)
    assert "warnings" in exc.value.message_dict

    services.publish(post, actor=editor, force=True)
    assert post.is_live


def test_publishing_records_who_did_it(draft, editor):
    services.publish(draft, actor=editor, force=True)
    assert draft.published_by == editor


# ---------------------------------------------------------------------------
# Revisions
# ---------------------------------------------------------------------------


def test_revisions_deduplicate_and_restore(draft, editor):
    services.snapshot(draft, editor=editor, note="first")
    assert services.snapshot(draft, editor=editor, note="identical") is None

    original_body = draft.body
    draft.body = GOOD_BODY + "\n\n## An extra section\n\nSome more prose here."
    draft.save()
    services.snapshot(draft, editor=editor, note="second")

    first = draft.revisions.order_by("created_at").first()
    services.restore(first, editor=editor)
    draft.refresh_from_db()
    assert draft.body == original_body


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def test_public_list_shows_only_live_posts(api, draft, editor, no_throttling):
    assert api.get("/api/blog/posts/").data["count"] == 0
    services.publish(draft, actor=editor, force=True)
    body = api.get("/api/blog/posts/").data
    assert body["count"] == 1
    assert body["results"][0]["slug"] == draft.slug


def test_a_draft_is_not_reachable_by_slug(api, draft, no_throttling):
    assert api.get(f"/api/blog/posts/{draft.slug}/").status_code == 404


def test_public_detail_never_leaks_editorial_fields(api, draft, editor, no_throttling):
    draft.ai_notes = "internal only"
    draft.save()
    services.publish(draft, actor=editor, force=True)
    body = api.get(f"/api/blog/posts/{draft.slug}/").data
    assert "internal only" not in str(body)
    assert "body" not in body  # only the rendered body_html is public
    assert "focus_keyword" not in body
    assert body["body_html"]


def test_sitemap_lists_live_posts(api, draft, editor, no_throttling):
    services.publish(draft, actor=editor, force=True)
    body = api.get("/api/blog/sitemap/").data
    assert [p["slug"] for p in body["posts"]] == [draft.slug]
    assert body["categories"][0]["slug"] == draft.category.slug


def test_rss_feed_renders(client, draft, editor):
    services.publish(draft, actor=editor, force=True)
    response = client.get("/api/blog/rss.xml")
    assert response.status_code == 200
    assert draft.title.encode() in response.content
    # Excerpt only — a full-text feed invites scraping the whole blog.
    assert b"Where people lose time" not in response.content


# ---------------------------------------------------------------------------
# Staff API and permissions
# ---------------------------------------------------------------------------


def test_a_writer_can_draft(api, writer, blog_category, no_throttling):
    api.force_authenticate(user=writer)
    response = api.post(
        "/api/admin/blog/posts/",
        {"title": "A new draft", "body": GOOD_BODY, "category_id": str(blog_category.id)},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["status"] == "draft"
    assert response.data["author_name"] == "Tunde"


def test_a_writer_cannot_publish(api, writer, draft, no_throttling):
    api.force_authenticate(user=writer)
    response = api.post(f"/api/admin/blog/posts/{draft.slug}/publish/", {}, format="json")
    assert response.status_code == 403


def test_an_editor_can_publish(api, editor, draft, no_throttling):
    api.force_authenticate(user=editor)
    response = api.post(f"/api/admin/blog/posts/{draft.slug}/publish/", {"force": True}, format="json")
    assert response.status_code == 200, response.data
    draft.refresh_from_db()
    assert draft.is_live


def test_preflight_explains_what_is_missing(api, editor, db, no_throttling):
    post = Post.objects.create(title="Thin", body="Not enough.", author=editor)
    api.force_authenticate(user=editor)
    body = api.get(f"/api/admin/blog/posts/{post.slug}/preflight/").data
    assert body["ok"] is False
    assert any("too short" in b for b in body["blockers"])


def test_a_live_post_cannot_be_deleted(api, editor, draft, no_throttling):
    services.publish(draft, actor=editor, force=True)
    api.force_authenticate(user=editor)
    response = api.delete(f"/api/admin/blog/posts/{draft.slug}/")
    assert response.status_code == 400
    assert Post.objects.filter(pk=draft.pk).exists()


def test_a_student_cannot_reach_the_composer(as_student, draft, no_throttling):
    assert as_student.get("/api/admin/blog/posts/").status_code == 403


def test_editing_a_post_snapshots_the_previous_body(api, editor, draft, no_throttling):
    api.force_authenticate(user=editor)
    before = draft.revisions.count()
    response = api.patch(
        f"/api/admin/blog/posts/{draft.slug}/",
        {"body": GOOD_BODY + "\n\n## One more thing\n\nAdded later."},
        format="json",
    )
    assert response.status_code == 200
    assert draft.revisions.count() == before + 1


# ---------------------------------------------------------------------------
# AI assist endpoints — the parts that do not call Claude
# ---------------------------------------------------------------------------


def test_ai_assist_says_so_when_it_is_not_configured(api, editor, settings, no_throttling):
    settings.ANTHROPIC_API_KEY = ""
    api.force_authenticate(user=editor)
    response = api.post("/api/admin/blog/ai/", {"task": "review", "body": "x"}, format="json")
    assert response.status_code == 503
    assert response.data["code"] == "ai_not_configured"


def test_the_review_task_runs_without_a_model_call(api, editor, settings, no_throttling):
    settings.ANTHROPIC_API_KEY = "sk-ant-not-a-real-key"
    api.force_authenticate(user=editor)
    response = api.post(
        "/api/admin/blog/ai/",
        {"task": "review", "body": "We guarantee admission to Germany within 2 weeks."},
        format="json",
    )
    assert response.status_code == 200
    kinds = {f["kind"] for f in response.data["review"]["flags"]}
    assert {"claim", "country"} <= kinds


def test_ai_assist_validates_what_each_task_needs(api, editor, settings, no_throttling):
    settings.ANTHROPIC_API_KEY = "sk-ant-not-a-real-key"
    api.force_authenticate(user=editor)
    response = api.post("/api/admin/blog/ai/", {"task": "seo", "title": "x"}, format="json")
    assert response.status_code == 400
    assert "body" in response.data


def test_ai_status_is_honest(api, editor, settings, no_throttling):
    api.force_authenticate(user=editor)
    settings.ANTHROPIC_API_KEY = ""
    assert api.get("/api/admin/blog/ai/status/").data["enabled"] is False
    settings.ANTHROPIC_API_KEY = "sk-ant-not-a-real-key"
    assert api.get("/api/admin/blog/ai/status/").data["enabled"] is True


def test_a_student_cannot_spend_the_ai_budget(as_student, settings, no_throttling):
    settings.ANTHROPIC_API_KEY = "sk-ant-not-a-real-key"
    response = as_student.post("/api/admin/blog/ai/", {"task": "review", "body": "x"}, format="json")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tags and categories
# ---------------------------------------------------------------------------


def test_empty_categories_and_tags_are_hidden_from_the_public(api, draft, editor, no_throttling):
    Tag.objects.create(name="Unused")
    assert api.get("/api/blog/categories/").data == []
    services.publish(draft, actor=editor, force=True)
    assert [c["slug"] for c in api.get("/api/blog/categories/").data] == [draft.category.slug]
    assert api.get("/api/blog/tags/").data == []


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_the_settings_row_is_a_singleton(db):
    first = BlogSettings.load()
    second = BlogSettings(posts_per_page=99)
    second.save()
    assert BlogSettings.objects.count() == 1
    assert second.pk == first.pk


def test_the_settings_row_cannot_be_deleted(db, fresh_blog_settings):
    with pytest.raises(RuntimeError):
        fresh_blog_settings.delete()


def test_saving_settings_clears_the_cache(db, fresh_blog_settings):
    assert BlogSettings.load().posts_per_page == 12
    fresh_blog_settings.posts_per_page = 6
    fresh_blog_settings.save()
    assert BlogSettings.load().posts_per_page == 6


def test_settings_reject_a_meta_template_without_the_title(db, fresh_blog_settings):
    fresh_blog_settings.meta_title_template = "Nasuru guides"
    with pytest.raises(ValidationError) as exc:
        fresh_blog_settings.clean()
    assert "meta_title_template" in exc.value.message_dict


def test_the_excerpt_setting_controls_derivation(db, editor, fresh_blog_settings):
    from apps.blog.settings_model import ExcerptSource

    fresh_blog_settings.excerpt_source = ExcerptSource.MANUAL
    fresh_blog_settings.save()
    manual = Post.objects.create(title="Manual excerpts", body=GOOD_BODY, author=editor)
    assert manual.excerpt == ""

    fresh_blog_settings.excerpt_source = ExcerptSource.AUTO
    fresh_blog_settings.excerpt_length = 100
    fresh_blog_settings.save()
    auto = Post.objects.create(
        title="Auto excerpts", body=GOOD_BODY, excerpt="typed by hand", author=editor
    )
    assert auto.excerpt != "typed by hand"
    assert len(auto.excerpt) <= 101  # the ellipsis


def test_a_required_featured_image_blocks_publishing(draft, editor, fresh_blog_settings):
    assert services.check_publishable(draft).ok

    fresh_blog_settings.featured_image_required = True
    fresh_blog_settings.save()

    check = services.check_publishable(draft)
    assert not check.ok
    assert any("featured image" in blocker for blocker in check.blockers)


def test_an_optional_excerpt_becomes_a_warning(db, editor, blog_category, fresh_blog_settings):
    from apps.blog.settings_model import ExcerptSource

    fresh_blog_settings.excerpt_source = ExcerptSource.MANUAL
    fresh_blog_settings.excerpt_required_to_publish = False
    fresh_blog_settings.save()

    post = Post.objects.create(
        title="No excerpt", body=GOOD_BODY, category=blog_category, author=editor
    )
    check = services.check_publishable(post)
    assert check.ok
    assert any("excerpt" in warning for warning in check.warnings)


def test_public_settings_endpoint_hides_the_private_values(api, fresh_blog_settings, no_throttling):
    fresh_blog_settings.comments_blocklist = "buy followers"
    fresh_blog_settings.analytics_measurement_id = "G-SECRET"
    fresh_blog_settings.save()

    body = api.get("/api/blog/settings/").data
    assert body["posts_per_page"] == 12
    assert "comments_blocklist" not in body
    assert "analytics_measurement_id" not in body
    assert "comments_per_hour_per_ip" not in body


def test_only_an_editor_can_change_the_settings(api, writer, editor, no_throttling):
    api.force_authenticate(user=writer)
    assert api.patch("/api/admin/blog/settings/", {"posts_per_page": 4}, format="json").status_code == 403
    # A writer may still read them — the composer shows the thresholds it is judged against.
    assert api.get("/api/admin/blog/settings/").status_code == 200

    api.force_authenticate(user=editor)
    response = api.patch("/api/admin/blog/settings/", {"posts_per_page": 4}, format="json")
    assert response.status_code == 200
    assert BlogSettings.load().posts_per_page == 4


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------


@pytest.fixture
def author_profile(editor):
    return AuthorProfile.objects.create(
        user=editor,
        display_name="Ngozi Eze",
        headline="Admissions lead",
        bio="Ngozi has sat with applicants through every stage of this process.",
        is_public=True,
        linkedin_url="https://www.linkedin.com/in/example",
    )


def test_an_author_page_needs_consent_and_a_post(author_profile, draft, editor):
    assert author_profile.is_public
    assert author_profile.has_public_page is False  # nothing live yet

    services.publish(draft, actor=editor, force=True)
    author_profile.refresh_from_db()
    assert author_profile.has_public_page is True

    author_profile.is_public = False
    author_profile.save()
    assert author_profile.has_public_page is False


def test_a_public_profile_needs_a_bio(editor):
    profile = AuthorProfile(user=editor, display_name="Someone", is_public=True, bio="")
    with pytest.raises(ValidationError) as exc:
        profile.clean()
    assert "bio" in exc.value.message_dict


def test_an_author_bio_goes_through_the_house_style_scan(editor):
    profile = AuthorProfile(
        user=editor,
        display_name="Someone",
        bio="She has placed students in Germany with a guaranteed visa.",
    )
    with pytest.raises(ValidationError) as exc:
        profile.clean()
    assert "bio" in exc.value.message_dict


def test_external_links_become_same_as(author_profile):
    assert author_profile.same_as == ["https://www.linkedin.com/in/example"]


def test_the_author_page_404s_without_live_posts(api, author_profile, no_throttling):
    assert api.get(f"/api/blog/authors/{author_profile.slug}/").status_code == 404


def test_the_author_page_serves_a_rendered_bio(api, author_profile, draft, editor, no_throttling):
    services.publish(draft, actor=editor, force=True)
    body = api.get(f"/api/blog/authors/{author_profile.slug}/").data
    assert body["display_name"] == "Ngozi Eze"
    assert "<p>" in body["bio_html"]
    assert body["post_count"] == 1


def test_the_byline_links_only_when_there_is_a_page(api, author_profile, draft, editor, no_throttling):
    services.publish(draft, actor=editor, force=True)
    body = api.get(f"/api/blog/posts/{draft.slug}/").data
    assert body["author"]["slug"] == author_profile.slug
    assert body["author"]["has_page"] is True

    author_profile.is_public = False
    author_profile.save()
    body = api.get(f"/api/blog/posts/{draft.slug}/").data
    assert body["author"]["slug"] == ""
    assert body["author"]["has_page"] is False


def test_a_writer_cannot_edit_someone_elses_profile(api, writer, author_profile, no_throttling):
    api.force_authenticate(user=writer)
    response = api.patch(
        f"/api/admin/blog/authors/{author_profile.pk}/",
        {"headline": "hijacked"},
        format="json",
    )
    assert response.status_code == 404  # not even visible in their queryset


def test_a_writer_gets_their_own_profile_on_first_touch(api, writer, no_throttling):
    api.force_authenticate(user=writer)
    response = api.get("/api/admin/blog/authors/me/")
    assert response.status_code == 200
    assert AuthorProfile.objects.filter(user=writer).exists()


# ---------------------------------------------------------------------------
# FAQ blocks
# ---------------------------------------------------------------------------


def test_an_faq_question_needs_a_question_mark(draft):
    entry = PostFaq(post=draft, question="Whether an HND qualifies", answer="Usually, yes.")
    with pytest.raises(ValidationError) as exc:
        entry.clean()
    assert "question" in exc.value.message_dict


def test_an_faq_answer_goes_through_the_house_style_scan(draft):
    entry = PostFaq(
        post=draft,
        question="Can I apply with an HND?",
        answer="Yes, and we guarantee admission within 3 weeks.",
    )
    with pytest.raises(ValidationError) as exc:
        entry.clean()
    assert "answer" in exc.value.message_dict


def test_faqs_reach_the_public_detail(api, draft, editor, no_throttling):
    PostFaq.objects.create(
        post=draft,
        question="Can I apply with an HND?",
        answer="Usually yes, and the requirement list for each school says so explicitly.",
    )
    services.publish(draft, actor=editor, force=True)
    body = api.get(f"/api/blog/posts/{draft.slug}/").data
    assert [f["question"] for f in body["faqs"]] == ["Can I apply with an HND?"]


def test_a_post_with_no_faqs_gets_a_warning_not_a_blocker(draft):
    check = services.check_publishable(draft)
    assert check.ok
    assert any("FAQ" in warning for warning in check.warnings)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@pytest.fixture
def live_post(draft, editor):
    services.publish(draft, actor=editor, force=True)
    return draft


def test_a_comment_starts_pending_when_approval_is_required(live_post):
    result = moderation.submit(
        post=live_post, body="How long does a transcript usually take?",
        name="Ada", email="ada@example.com", seconds_on_page=30,
    )
    assert result.comment.status == Comment.Status.PENDING
    assert "review" in result.message
    assert live_post.approved_comment_count == 0


def test_turning_approval_off_publishes_immediately(live_post, fresh_blog_settings):
    fresh_blog_settings.comments_require_approval = False
    fresh_blog_settings.save()
    result = moderation.submit(
        post=live_post, body="Thanks, this was clear.", name="Ada",
        email="ada@example.com", seconds_on_page=30,
    )
    assert result.comment.status == Comment.Status.APPROVED


def test_too_many_links_is_flagged_as_spam(live_post):
    result = moderation.submit(
        post=live_post,
        body="Great post https://one.example https://two.example https://three.example",
        name="Bot", email="bot@example.com", seconds_on_page=30,
    )
    assert result.comment.status == Comment.Status.SPAM
    assert "links" in result.comment.flagged_reason


def test_a_form_submitted_too_fast_is_flagged(live_post):
    result = moderation.submit(
        post=live_post, body="Interesting read, thank you.", name="Bot",
        email="bot@example.com", seconds_on_page=1,
    )
    assert result.comment.status == Comment.Status.SPAM
    assert "submitted in" in result.comment.flagged_reason


def test_a_blocked_phrase_is_flagged(live_post, fresh_blog_settings):
    fresh_blog_settings.comments_blocklist = "cheap visa\nbuy followers"
    fresh_blog_settings.save()
    result = moderation.submit(
        post=live_post, body="I can get you a cheap visa, message me.", name="Bot",
        email="bot@example.com", seconds_on_page=30,
    )
    assert result.comment.status == Comment.Status.SPAM
    assert "cheap visa" in result.comment.flagged_reason


def test_a_flagged_comment_gets_the_same_message_as_a_pending_one(live_post):
    spam = moderation.submit(
        post=live_post, body="x https://a.example https://b.example", name="Bot",
        email="b@example.com", seconds_on_page=30,
    )
    clean = moderation.submit(
        post=live_post, body="A genuine question about transcripts, thank you.",
        name="Ada", email="ada@example.com", seconds_on_page=30,
    )
    # A spammer learns nothing, and a false positive accuses nobody.
    assert spam.message == clean.message


def test_a_filled_honeypot_writes_nothing(live_post):
    result = moderation.submit(
        post=live_post, body="spam", name="Bot", email="b@example.com",
        honeypot="filled in", seconds_on_page=30,
    )
    assert result.comment is None
    assert Comment.objects.count() == 0


def test_staff_replies_skip_the_queue(live_post, editor):
    result = moderation.submit(
        post=live_post, body="Answering in the thread.", user=editor, seconds_on_page=0
    )
    assert result.comment.status == Comment.Status.APPROVED
    assert result.comment.is_from_staff


def test_replies_only_go_one_level_deep(live_post, editor):
    root = moderation.submit(
        post=live_post, body="First question here, thank you.", name="Ada",
        email="ada@example.com", seconds_on_page=30,
    ).comment
    root.approve(moderator=editor)

    reply = moderation.reply_as_agency(root, "Here is the answer.", author=editor)
    nested = moderation.submit(
        post=live_post, body="A follow-up to the answer.", name="Ada",
        email="ada@example.com", parent=reply, seconds_on_page=30,
    ).comment

    # Attached to the root, not to the reply.
    assert nested.parent_id == root.pk


def test_comments_respect_the_master_switch(live_post, fresh_blog_settings):
    fresh_blog_settings.comments_enabled = False
    fresh_blog_settings.save()
    assert live_post.comments_are_open is False
    with pytest.raises(moderation.CommentsClosed):
        moderation.submit(post=live_post, body="Hello there.", name="Ada", email="a@example.com")


def test_a_post_can_close_its_own_comments(live_post):
    live_post.comments_closed = True
    live_post.save()
    assert live_post.comments_are_open is False


def test_comments_close_after_the_configured_window(live_post, fresh_blog_settings):
    fresh_blog_settings.comments_close_after_days = 30
    fresh_blog_settings.save()
    assert live_post.comments_are_open is True

    Post.objects.filter(pk=live_post.pk).update(
        published_at=timezone.now() - timedelta(days=45)
    )
    live_post.refresh_from_db()
    assert live_post.comments_are_open is False


def test_a_draft_never_accepts_comments(draft):
    assert draft.comments_are_open is False


def test_the_public_thread_shows_only_approved_comments(api, live_post, editor, no_throttling):
    hidden = moderation.submit(
        post=live_post, body="Pending question about transcripts.", name="Ada",
        email="ada@example.com", seconds_on_page=30,
    ).comment
    shown = moderation.submit(
        post=live_post, body="Approved question about translations.", name="Bola",
        email="bola@example.com", seconds_on_page=30,
    ).comment
    shown.approve(moderator=editor)

    body = api.get(f"/api/blog/posts/{live_post.slug}/").data
    bodies = [c["body"] for c in body["comments"]]
    assert shown.body in bodies
    assert hidden.body not in bodies
    assert body["comment_count"] == 1


def test_the_public_thread_never_carries_an_email(api, live_post, editor, no_throttling):
    comment = moderation.submit(
        post=live_post, body="A question about proof of funds.", name="Ada",
        email="ada@example.com", seconds_on_page=30,
    ).comment
    comment.approve(moderator=editor)

    body = api.get(f"/api/blog/posts/{live_post.slug}/").data
    assert "ada@example.com" not in str(body)


def test_posting_a_comment_over_the_api(api, live_post, no_throttling):
    response = api.post(
        f"/api/blog/posts/{live_post.slug}/comments/",
        {
            "body": "How long does the transcript usually take?",
            "name": "Ada",
            "email": "ada@example.com",
            "seconds_on_page": 42,
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["published"] is False
    assert Comment.objects.count() == 1


def test_posting_to_a_closed_post_conflicts(api, live_post, no_throttling):
    live_post.comments_closed = True
    live_post.save()
    response = api.post(
        f"/api/blog/posts/{live_post.slug}/comments/",
        {"body": "Hello there, a question.", "name": "Ada", "email": "a@example.com"},
        format="json",
    )
    assert response.status_code == 409


def test_a_missing_email_is_refused_when_required(api, live_post, no_throttling):
    response = api.post(
        f"/api/blog/posts/{live_post.slug}/comments/",
        {"body": "A question with no address.", "name": "Ada", "seconds_on_page": 30},
        format="json",
    )
    assert response.status_code == 400
    assert "email" in response.data


def test_the_moderation_queue_is_oldest_first(api, live_post, editor, no_throttling):
    for n in range(3):
        moderation.submit(
            post=live_post, body=f"Question number {n} about documents.", name="Ada",
            email="ada@example.com", seconds_on_page=30,
        )
    api.force_authenticate(user=editor)
    rows = api.get("/api/admin/blog/comments/").data["results"]
    assert len(rows) == 3
    assert rows[0]["body"].endswith("0 about documents.")


def test_bulk_moderation_audits_each_comment(api, live_post, editor, no_throttling, django_capture_on_commit_callbacks):
    from apps.core.models import AuditLog

    ids = []
    for n in range(2):
        ids.append(
            str(
                moderation.submit(
                    post=live_post, body=f"Question {n} about translations.", name="Ada",
                    email="ada@example.com", seconds_on_page=30,
                ).comment.pk
            )
        )

    api.force_authenticate(user=editor)
    with django_capture_on_commit_callbacks(execute=True):
        response = api.post(
            "/api/admin/blog/comments/moderate/",
            {"status": "approved", "comment_ids": ids},
            format="json",
        )
    assert response.status_code == 200
    assert response.data["changed"] == 2
    assert Comment.objects.public().count() == 2
    assert AuditLog.objects.filter(target_type="blog.Comment").count() == 2


def test_a_writer_cannot_moderate(api, writer, live_post, no_throttling):
    comment = moderation.submit(
        post=live_post, body="A question awaiting review.", name="Ada",
        email="ada@example.com", seconds_on_page=30,
    ).comment
    api.force_authenticate(user=writer)
    response = api.post(
        "/api/admin/blog/comments/moderate/",
        {"status": "approved", "comment_ids": [str(comment.pk)]},
        format="json",
    )
    assert response.status_code == 403


def test_a_student_cannot_see_the_moderation_queue(as_student, no_throttling):
    assert as_student.get("/api/admin/blog/comments/").status_code == 403


def test_an_agency_reply_is_published_immediately(live_post, editor):
    comment = moderation.submit(
        post=live_post, body="A question about the order of things.", name="Ada",
        email="ada@example.com", seconds_on_page=30,
    ).comment
    reply = moderation.reply_as_agency(comment, "Admission first, then the visa.", author=editor)
    assert reply.status == Comment.Status.APPROVED
    assert reply.is_from_staff
    assert reply.parent_id == comment.pk


# ---------------------------------------------------------------------------
# Slug redirects over the API
# ---------------------------------------------------------------------------


def test_an_old_slug_redirects(api, draft, editor, no_throttling):
    services.publish(draft, actor=editor, force=True)
    original = draft.slug
    draft.slug = "a-clearer-slug"
    draft.save()

    response = api.get(f"/api/blog/posts/{original}/")
    assert response.status_code == 301
    assert response.data["slug"] == "a-clearer-slug"
    assert response["Location"] == "/blog/a-clearer-slug"


def test_a_redirect_to_an_unpublished_post_still_404s(api, draft, editor, no_throttling):
    services.publish(draft, actor=editor, force=True)
    original = draft.slug
    draft.slug = "moved-then-hidden"
    draft.save()
    services.unpublish(draft, actor=editor)

    assert api.get(f"/api/blog/posts/{original}/").status_code == 404


def test_an_unknown_slug_still_404s(api, no_throttling):
    assert api.get("/api/blog/posts/never-existed/").status_code == 404


# ---------------------------------------------------------------------------
# Settings-driven listing
# ---------------------------------------------------------------------------


def test_page_size_follows_the_setting(api, editor, blog_category, fresh_blog_settings, no_throttling):
    for n in range(5):
        post = Post.objects.create(
            title=f"Guide number {n}", body=GOOD_BODY, excerpt="x",
            category=blog_category, author=editor,
        )
        services.publish(post, actor=editor, force=True)

    fresh_blog_settings.posts_per_page = 2
    fresh_blog_settings.save()

    body = api.get("/api/blog/posts/").data
    assert body["count"] == 5
    assert len(body["results"]) == 2


def test_related_post_count_follows_the_setting(
    api, editor, blog_category, fresh_blog_settings, no_throttling
):
    posts = []
    for n in range(5):
        post = Post.objects.create(
            title=f"Related guide {n}", body=GOOD_BODY, excerpt="x",
            category=blog_category, author=editor,
        )
        services.publish(post, actor=editor, force=True)
        posts.append(post)

    fresh_blog_settings.related_post_count = 1
    fresh_blog_settings.save()

    body = api.get(f"/api/blog/posts/{posts[0].slug}/").data
    assert len(body["related"]) == 1


def test_the_sitemap_lists_author_pages(api, author_profile, draft, editor, no_throttling):
    services.publish(draft, actor=editor, force=True)
    body = api.get("/api/blog/sitemap/").data
    assert [a["slug"] for a in body["authors"]] == [author_profile.slug]


def test_author_pages_can_be_switched_off(api, author_profile, draft, editor, fresh_blog_settings, no_throttling):
    services.publish(draft, actor=editor, force=True)
    fresh_blog_settings.author_pages_enabled = False
    fresh_blog_settings.save()

    assert api.get(f"/api/blog/authors/{author_profile.slug}/").status_code == 404
    assert api.get("/api/blog/sitemap/").data["authors"] == []
