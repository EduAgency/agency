"""Markdown to HTML, once, on the server.

Rendering server-side rather than in the browser buys three things: the
frontend ships no Markdown parser, the HTML that reaches a crawler is the HTML
a reader sees, and sanitisation happens in exactly one place.

Post bodies are written by staff, so this is not a hostile-input problem in the
usual sense — but a body can also come out of :mod:`apps.blog.ai`, an editor
can paste from anywhere, and a compromised staff account should not be able to
put a script tag on a public page. So the output is sanitised on the way out
regardless of who typed it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import nh3
from markdown_it import MarkdownIt

# Tags an article legitimately needs, and nothing else. No <script>, no
# <iframe>, no <style>, no event handlers — nh3 drops anything not listed.
ALLOWED_TAGS = {
    "p", "br", "hr",
    "h2", "h3", "h4",
    "strong", "em", "del", "code", "pre",
    "ul", "ol", "li",
    "blockquote",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "figure", "figcaption",
    "span",
}

ALLOWED_ATTRIBUTES = {
    # No "rel" here on purpose: ammonia refuses to both accept an author-set
    # rel and apply link_rel below, and link_rel is the one we want.
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "loading", "width", "height"},
    "th": {"scope", "colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "h2": {"id"},
    "h3": {"id"},
    "h4": {"id"},
    "span": {"class"},
    "code": {"class"},
}

# H1 is the post title, rendered by the page. A body that starts at H2 keeps
# the document outline valid, which matters for both screen readers and search.
_MD = MarkdownIt("commonmark", {"linkify": True, "typographer": True}).enable(
    ["table", "strikethrough", "linkify"]
)

_HEADING_RE = re.compile(r"<h([234])>(.*?)</h\1>", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    anchor: str


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "section"


def render(markdown: str) -> tuple[str, list[Heading]]:
    """Return sanitised HTML and the heading outline.

    Headings get stable ``id`` anchors so the table of contents and any shared
    deep link keep working. Anchors are deduplicated, because two sections
    called "What it costs" in one article is a normal thing to write.
    """
    html = _MD.render(markdown or "")

    seen: dict[str, int] = {}
    headings: list[Heading] = []

    def anchor_heading(match: re.Match[str]) -> str:
        level = int(match.group(1))
        inner = match.group(2)
        text = _TAG_RE.sub("", inner).strip()
        base = _slug(text)
        seen[base] = seen.get(base, 0) + 1
        anchor = base if seen[base] == 1 else f"{base}-{seen[base]}"
        headings.append(Heading(level=level, text=text, anchor=anchor))
        return f'<h{level} id="{anchor}">{inner}</h{level}>'

    html = _HEADING_RE.sub(anchor_heading, html)

    clean = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        # Outbound links get rel="noopener nofollow" added by nh3's
        # link_rel default; an article linking a school's own site should not
        # pass authority to it, and we have not vetted it.
        link_rel="noopener nofollow",
        url_schemes={"http", "https", "mailto"},
    )
    return clean, headings


def plain_text(markdown: str) -> str:
    """Body as prose, for word counts and as an excerpt fallback."""
    html, _ = render(markdown)
    text = _TAG_RE.sub(" ", html)
    return " ".join(text.split())


def auto_excerpt(markdown: str, limit: int = 240) -> str:
    """First `limit` characters of prose, cut on a word boundary."""
    text = plain_text(markdown)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"
