"""RSS and Atom.

Served from Django rather than Next.js because the feed is generated from the
same queryset as everything else, and Django's syndication framework already
gets the XML details right — escaping, GUIDs, dates in RFC 822.

Aggregators, and a handful of readers who still use them, are a real trickle of
traffic that costs nothing to serve.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed

from .models import BlogSettings, Post


class LatestPostsFeed(Feed):
    title = f"{settings.SITE_NAME} — study abroad, explained plainly"
    description = (
        "How Nigerians actually get into international schools: what the "
        "requirements are, what the documents are, what it really costs."
    )

    def link(self) -> str:
        return f"{settings.SITE_BASE_URL}/blog"

    def feed_url(self) -> str:
        return f"{settings.SITE_BASE_URL}/blog/rss.xml"

    def items(self):
        count = BlogSettings.load().feed_item_count
        return (
            Post.objects.live()
            .select_related("category", "author")
            .order_by("-published_at")[:count]
        )

    def item_title(self, item: Post) -> str:
        return item.title

    def item_description(self, item: Post) -> str:
        """Excerpt by default.

        A full-text feed is an invitation to scrape the whole blog, so the
        setting defaults to off — but it is a setting, because for a site whose
        goal is reach there is a real argument the other way.
        """
        if BlogSettings.load().feed_full_text:
            return item.body_html
        return item.excerpt

    def item_link(self, item: Post) -> str:
        return f"{settings.SITE_BASE_URL}/blog/{item.slug}"

    def item_guid(self, item: Post) -> str:
        return f"{settings.SITE_BASE_URL}/blog/{item.slug}"

    def item_guid_is_permalink(self) -> bool:
        return True

    def item_pubdate(self, item: Post):
        return item.published_at

    def item_updateddate(self, item: Post):
        return item.updated_at

    def item_author_name(self, item: Post) -> str:
        if item.author:
            return item.author.get_full_name() or settings.SITE_NAME
        return settings.SITE_NAME

    def item_categories(self, item: Post) -> list[str]:
        names = [tag.name for tag in item.tags.all()]
        if item.category:
            names.insert(0, item.category.name)
        return names


class RssFeed(LatestPostsFeed):
    """RSS 2.0 — Django's default feed type."""


class AtomFeed(LatestPostsFeed):
    feed_type = Atom1Feed
    subtitle = LatestPostsFeed.description

    def feed_url(self) -> str:
        return f"{settings.SITE_BASE_URL}/blog/atom.xml"
