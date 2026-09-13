"""Claude-backed drafting help for the editorial team.

What this module is for: getting a writer from a blank page to a working draft
faster. What it is deliberately *not* for: publishing. Every function here
returns a suggestion. A person accepts it, edits it, and their name goes on
``Post.published_by``.

Three constraints are baked into the house style below rather than left to
whoever is writing the prompt on the day, because breaking any of them is a
business problem and not a style problem:

* **No country is ever named.** Students learn which countries and which
  schools when they pay. An article that names one gives away the product and
  contradicts the rest of the site.
* **No number we have not verified.** No placement counts, no success rates, no
  tuition figures, no processing times. The site's whole argument is that we
  only say things you can check.
* **Admission first, then the visa.** Getting that order wrong in public is the
  single most damaging thing we could publish, because acting on it wastes a
  student's money.

The model is told all of this, and then :func:`review_flags` checks the output
anyway — a prompt is guidance, not a guarantee.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from django.conf import settings
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MODEL = getattr(settings, "BLOG_AI_MODEL", "claude-opus-5")

# Claude Opus 5 takes ``fallbacks="default"`` with this beta, which re-runs a
# policy-declined request on a fallback model inside the same call. Nothing we
# ask here is near a policy line, so it is cheap insurance against a writer
# seeing an unexplained empty response.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AiUnavailable(RuntimeError):
    """No API key configured, or the SDK is not installed.

    Raised rather than returning empty output, so the API layer can answer with
    a clear "AI assist is not configured" instead of a blank draft.
    """


def is_enabled() -> bool:
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _client():
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        raise AiUnavailable("ANTHROPIC_API_KEY is not set.")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - the dependency is declared
        raise AiUnavailable("The anthropic package is not installed.") from exc
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ---------------------------------------------------------------------------
# House style
# ---------------------------------------------------------------------------

_HOUSE_STYLE_TEMPLATE = """You are drafting for the blog of a Nigerian international education agency.

WHO READS THIS
Nigerians - mostly 20 to 35, mostly first-generation international applicants -
deciding whether studying abroad is realistic for them. Many have been lied to
by an agent before. They are reading on a phone, on data they paid for.

WHAT THE AGENCY ACTUALLY DOES
Four things: finds tuition-free or low-fee international schools a Nigerian can
get into; tells the applicant exactly what each one requires; writes the CV and
motivation letter and arranges document translation; and advises on the visa
application once an admission letter exists. One fee of {fee_ascii} - written in
prose as {fee_formatted} - covers all of it, from the first list of schools to
landing on campus.

HARD RULES - breaking any of these makes the draft unusable
1. Never name a country, a city, or a school. Not as an example, not as an
   aside, not "such as". Which countries and which schools is what the fee
   buys. Write about the process, the requirements, the documents, the
   decisions.
2. Never state a number the agency has not published: no placement counts, no
   success or approval rates, no tuition amounts, no visa processing times, no
   "X% of students". If a number would help, write the sentence without it or
   say plainly that it varies and the reader should ask. The access fee is the
   only figure you may state.
3. Admission comes first, then the visa. Never imply a visa can be pursued
   before an admission letter exists.
4. Never guarantee an outcome - no admission, no visa, no scholarship is
   promised. Never write "guaranteed", "100%", "assured", or "we can get you
   in".
5. Tuition-free is not cost-free. Whenever the draft touches tuition-free
   study, say that living costs, proof of funds, travel and document fees are
   still the applicant's to cover, and that those figures vary by school and
   change.

HOW TO WRITE
Short sentences. Plain words. Second person. Nigerian English, not American -
"admission", not "acceptance"; "secondary school", not "high school". Answer
the reader's real question in the first two sentences; they will not scroll for
it. Name the objection or the fear directly instead of talking around it - a
reader who has been scammed before respects being told what could go wrong. No
hype, no exclamation marks, no "in today's globalised world", no "embark on
your journey", no emoji. If something is genuinely uncertain, say so; a hedge
you can defend beats a claim you cannot.
"""


def house_style() -> str:
    """The system prompt, with the live access fee interpolated.

    A function rather than a constant because the fee is a database row now. If
    it changes, the model is told the new number on the very next request — and
    the scan below starts flagging the old one.
    """
    pricing = _pricing()
    return _HOUSE_STYLE_TEMPLATE.format(
        fee_ascii=pricing.ascii_access_fee,
        fee_formatted=pricing.formatted_access_fee,
    )


# ---------------------------------------------------------------------------
# Structured outputs
# ---------------------------------------------------------------------------


class OutlineSection(BaseModel):
    heading: str = Field(description="An H2 a reader would scan for. Sentence case, no numbering.")
    covers: list[str] = Field(description="Two to four points this section makes.", max_length=4)


class ArticleOutline(BaseModel):
    working_title: str = Field(description="Under 70 characters.")
    reader_question: str = Field(
        description="The single question this article answers, in the reader's own words."
    )
    excerpt: str = Field(description="Two sentences, under 300 characters, for listings.")
    sections: list[OutlineSection] = Field(min_length=3, max_length=8)
    suggested_tags: list[str] = Field(max_length=6)
    what_we_cannot_claim: list[str] = Field(
        description=(
            "Facts this topic tempts a writer to invent - figures, countries, "
            "timelines. The editor should verify or cut each one."
        ),
        max_length=6,
    )


class SeoMetadata(BaseModel):
    meta_title: str = Field(description="Under 60 characters, front-loads the topic.")
    meta_description: str = Field(description="140-155 characters, ends with a reason to click.")
    focus_keyword: str = Field(description="One phrase a Nigerian applicant would actually type.")
    slug: str = Field(description="Lowercase, hyphenated, under 60 characters, no stop words.")
    excerpt: str = Field(description="Under 300 characters.")
    internal_link_ideas: list[str] = Field(
        description="Other article topics this one should link to.", max_length=5
    )


class TitleOptions(BaseModel):
    titles: list[str] = Field(min_length=3, max_length=6)
    recommended: str
    why: str = Field(description="One sentence on why the recommended title wins.")


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


def _parse(prompt: str, output_format, *, max_tokens: int = 8000):
    client = _client()
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        thinking={"type": "adaptive"},
        system=house_style(),
        messages=[{"role": "user", "content": prompt}],
        output_format=output_format,
    )
    if response.stop_reason == "refusal":
        raise AiUnavailable("The model declined this request. Rephrase the brief.")
    return response.parsed_output


def _stream_text(prompt: str, *, max_tokens: int = 16000) -> str:
    """Long-form generation.

    Streamed because a full article takes a while to produce and a non-streamed
    request that long risks a gateway timeout before the first byte.
    """
    client = _client()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        thinking={"type": "adaptive"},
        system=house_style(),
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        raise AiUnavailable("The model declined this request. Rephrase the brief.")
    return "\n".join(b.text for b in message.content if b.type == "text").strip()


def suggest_outline(topic: str, *, audience_note: str = "", must_cover: str = "") -> ArticleOutline:
    prompt = f"Plan an article on: {topic}\n"
    if audience_note:
        prompt += f"\nWho specifically is reading it: {audience_note}\n"
    if must_cover:
        prompt += f"\nIt must cover: {must_cover}\n"
    prompt += (
        "\nGive the outline. In what_we_cannot_claim, list the specific things a "
        "writer would be tempted to state as fact here and that we have not "
        "verified - the editor will check or cut each one."
    )
    return _parse(prompt, ArticleOutline)


def write_draft(outline: ArticleOutline, *, words: int = 1100) -> str:
    """Turn an accepted outline into a Markdown draft."""
    sections = "\n".join(
        f"## {s.heading}\n" + "\n".join(f"- {point}" for point in s.covers)
        for s in outline.sections
    )
    prompt = (
        f"Write the article. Around {words} words of Markdown.\n\n"
        f"Working title: {outline.working_title}\n"
        f"The one question it answers: {outline.reader_question}\n\n"
        f"Structure - use these as H2s, in this order:\n\n{sections}\n\n"
        "Start with the answer, not a preamble. Use H2s and short paragraphs; a "
        "bulleted list only where the content is genuinely a list. Do not write "
        "a title line - the H1 is handled separately. Do not add a call to "
        "action; that is templated onto the page. Output Markdown only."
    )
    return _stream_text(prompt)


def rewrite(body: str, instruction: str) -> str:
    prompt = (
        f"Revise this draft. What to change: {instruction}\n\n"
        "Keep the writer's structure and any specific detail they added unless "
        "the instruction says otherwise. Output the full revised Markdown, "
        "nothing else.\n\n---\n\n" + body
    )
    return _stream_text(prompt)


def suggest_seo(title: str, body: str) -> SeoMetadata:
    prompt = (
        f"Write the search metadata for this article.\n\nTitle: {title}\n\n"
        "Article:\n\n" + body[:20000]
    )
    return _parse(prompt, SeoMetadata, max_tokens=4000)


def suggest_titles(body: str, *, current_title: str = "") -> TitleOptions:
    prompt = "Propose titles for this article.\n"
    if current_title:
        prompt += f"\nThe current one is: {current_title}\n"
    prompt += (
        "\nEach should be something a reader would click without feeling sold to. "
        "No colon-plus-subtitle formula, no numbered listicle framing unless the "
        "article really is a list.\n\n---\n\n" + body[:20000]
    )
    return _parse(prompt, TitleOptions, max_tokens=3000)


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------

# Checked against generated *and* human-written bodies. Deliberately blunt: a
# false positive costs an editor five seconds, a false negative puts an
# unverifiable claim on a page a student acts on.
GUARANTEE_PATTERNS = [
    (r"\bguarantee(?:d|s)?\b", "Promises an outcome we cannot promise."),
    (r"\b100\s*%", "Reads as a guarantee."),
    (r"\bassured\b", "Reads as a guarantee."),
    (r"\bwe can get you\b", "Promises an outcome we cannot promise."),
    (r"\bsure\s+(?:admission|visa)\b", "Promises an outcome we cannot promise."),
]

VISA_ORDER_PATTERNS = [
    (
        r"\bvisa\b[^.]{0,60}\bbefore\b[^.]{0,40}\badmission\b",
        "Puts the visa before the admission letter. That order is wrong.",
    ),
]

# Not exhaustive and not meant to be — it catches the ones a model reaches for
# when writing about study abroad for a Nigerian audience.
COUNTRY_WORDS = [
    "uk", "united kingdom", "britain", "british", "england", "scotland", "wales",
    "ireland", "irish", "usa", "united states", "america", "american", "canada",
    "canadian", "germany", "german", "france", "french", "poland", "polish",
    "hungary", "hungarian", "czechia", "czech", "netherlands", "dutch",
    "belgium", "sweden", "swedish", "norway", "finland", "denmark", "austria",
    "switzerland", "italy", "italian", "spain", "spanish", "portugal", "malta",
    "cyprus", "turkey", "china", "chinese", "japan", "korea", "malaysia",
    "australia", "australian", "new zealand", "dubai", "qatar", "russia",
    "ukraine", "latvia", "lithuania", "estonia", "romania", "bulgaria",
    "greece", "croatia", "slovakia", "slovenia", "belarus", "georgia",
    "armenia", "india", "brazil", "mexico", "argentina", "south africa",
    "egypt", "morocco", "tunisia",
]

# Any figure that is not the access fee. Matched loosely, then filtered.
NUMBER_PATTERN = re.compile(
    r"(?:₦|N|NGN|\$|£|€)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|million|thousand))?"
    r"|\d[\d,]*(?:\.\d+)?\s?%"
    r"|(?<![\w.])\d[\d,]{2,}(?![\w.])",
    re.IGNORECASE,
)



@dataclass
class Flag:
    kind: str
    excerpt: str
    why: str


@dataclass
class Review:
    flags: list[Flag] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.flags

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "flags": [{"kind": f.kind, "excerpt": f.excerpt, "why": f.why} for f in self.flags],
        }


def _context(text: str, start: int, end: int, radius: int = 60) -> str:
    snippet = text[max(0, start - radius) : min(len(text), end + radius)]
    return " ".join(snippet.split())


#: Currency markers a figure may be written with, longest first so "NGN" is
#: matched before the bare "N".
CURRENCY_PREFIXES = ("NGN", "₦", "$", "£", "€", "N")


def _pricing():
    """The live pricing row.

    Imported lazily: apps.payments imports nothing from apps.blog, and keeping it
    that way means neither app needs to know the other exists at import time.
    """
    from apps.payments.pricing import Pricing

    return Pricing.load()


def allowed_figures() -> set[str]:
    """The only figures published copy may state.

    Derived from the pricing row rather than written down here, so raising the
    fee to ₦7,500 both permits "7,500" and starts flagging every surviving
    "5,000" in an old article — which is now a wrong number on a live page.
    """
    return _pricing().allowed_figures


def _is_access_fee(raw: str, permitted: set[str]) -> bool:
    digits = raw.strip()
    for prefix in CURRENCY_PREFIXES:
        if digits.upper().startswith(prefix):
            digits = digits[len(prefix) :].strip()
            break
    return digits in permitted


def review_flags(text: str) -> Review:
    """Scan a body for the things the house style forbids.

    Runs on every draft an editor asks Claude for, and again on every body
    before publish, whoever wrote it. It reports; it never edits.
    """
    review = Review()
    lowered = text.lower()
    permitted = allowed_figures()

    for pattern, why in GUARANTEE_PATTERNS + VISA_ORDER_PATTERNS:
        for match in re.finditer(pattern, lowered):
            review.flags.append(Flag("claim", _context(text, match.start(), match.end()), why))

    for word in COUNTRY_WORDS:
        for match in re.finditer(rf"(?<!\w){re.escape(word)}(?!\w)", lowered):
            review.flags.append(
                Flag(
                    "country",
                    _context(text, match.start(), match.end()),
                    f'Names a place ("{word}"). Which countries is what the fee buys.',
                )
            )

    for match in NUMBER_PATTERN.finditer(text):
        raw = match.group(0).strip()
        if _is_access_fee(raw, permitted):
            continue
        review.flags.append(
            Flag(
                "figure",
                _context(text, match.start(), match.end()),
                f'States a figure ("{raw}"). Verify it or cut it — the access fee is the '
                "only figure we publish.",
            )
        )

    return review
