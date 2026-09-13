# The blog system

The plan for turning the blog from "posts with a composer" into something an editorial team
actually runs: site-wide settings, comments with moderation, real author identity, and the SEO
surface that follows from all three.

Phase 5 in `enterprise-readiness.md` built the spine — `Post`, `Category`, `Tag`, revisions,
the publish gate, the house-style scan, and the public pages. This document covers the layer on
top, and it is written to be read before the code.

---

## 1. Why settings belong in the database, not in `settings.py`

Everything in this document that is a *decision* rather than a *mechanism* goes in one editable
record. Posts per page, whether comments need approval, how many articles the homepage shows —
these are things the person running the agency changes on a Tuesday afternoon because a page felt
too long. Putting them in Django settings means a deploy for every one of those, which in practice
means they never change and the defaults quietly become policy.

`BlogSettings` is therefore a **singleton row**, loaded through `BlogSettings.load()` and cached.
One row, enforced by `pk` pinning, because "which settings row is live?" is not a question anyone
should have to answer.

### What it holds

**Listing and homepage**

| Field | Default | Why it is a setting |
| --- | --- | --- |
| `posts_per_page` | 12 | A 25-row page was right for a staff table and wrong for article cards. |
| `homepage_article_count` | 3 | The landing page shows guides; how many is a design call that will change. |
| `homepage_show_latest` | true | An off switch that does not need a deploy, for the week there is nothing good to show. |
| `homepage_section_title` | "Guides" | The section heading, editable without touching JSX. |
| `listing_layout` | `featured` | `featured` (one lead + grid), `grid` (equal cards), `list` (compact rows). |
| `show_reading_time` | true | |
| `show_author_byline` | true | |
| `show_published_date` | true | Some evergreen guides read better undated. This is a real editorial choice. |
| `related_post_count` | 3 | |

**Excerpts**

| Field | Default | Why |
| --- | --- | --- |
| `excerpt_source` | `manual_then_auto` | `manual` (blank stays blank), `auto` (always derived), `manual_then_auto` (write one or get one). |
| `excerpt_length` | 240 | Characters, for the auto path. |
| `excerpt_required_to_publish` | true | It is the meta description fallback *and* the listing card, so a blank one costs twice. |
| `read_more_label` | "Read the guide" | |

**Featured images**

| Field | Default | Why |
| --- | --- | --- |
| `featured_image_required` | false | True once there is a design that looks broken without one. |
| `featured_image_aspect` | `16:9` | Used to crop consistently in listings, so one tall image cannot break a row. |
| `show_featured_on_listing` | true | |
| `show_featured_on_detail` | true | |
| `default_featured_image` | — | The fallback when a post has none. Blank means the typographic card. |

Alt text stays **required whenever an image is set** and is not a setting. That is WCAG 1.1.1, not
a preference.

**Comments** — see §3.

**Authors** — see §2.

**SEO**

| Field | Default | Why |
| --- | --- | --- |
| `meta_title_template` | `{title} — {site}` | So a rename of the brand does not mean editing every post. |
| `default_meta_description` | — | Used where a page has neither description nor excerpt. |
| `default_og_image` | — | Falls back to the generated card. |
| `twitter_site` | — | `@handle` for the share card attribution. |
| `google_site_verification` | — | Emitted as a meta tag. Search Console needs it and it is not worth a deploy. |
| `bing_site_verification` | — | |
| `analytics_measurement_id` | — | Declared here, wired later — see "Not doing yet". |
| `feed_full_text` | false | A full-text feed is an invitation to scrape the whole blog. |
| `feed_item_count` | 20 | |
| `sitemap_include_authors` | true | |
| `noindex_tag_pages` | true | Phase 5's reasoning, now editable rather than hard-coded. |

### The rule that keeps this honest

A setting that can put an unverifiable claim on the site does not exist. There is no
"testimonials" toggle, no "show placement count", no editable trust badge. Everything above
changes *how much* of something true is shown, never *what* is asserted.

---

## 2. Authors are people, not a `first_name` on a `User`

Right now a byline is `user.get_full_name()`. That is enough to say who wrote something and not
enough to make anyone believe them — which matters more here than on most blogs, because the whole
pitch is "we tell you things other agents won't".

`AuthorProfile`, one-to-one with `User`:

- `display_name` — the byline. Not necessarily the account name.
- `slug` — for `/blog/author/<slug>`.
- `headline` — "Admissions lead", the line under the name.
- `bio` — a paragraph, Markdown, rendered through the same sanitiser as post bodies.
- `avatar` + `avatar_alt`
- `credentials` — free text, and it goes through the house-style scan. An author bio is the most
  tempting place on the whole site to invent a qualification.
- `website`, `linkedin_url`, `x_url` — emitted as `sameAs` in `Person` JSON-LD, which is how a
  search engine connects a byline to a real identity. That is the actual SEO value here.
- `is_public` — an author page only exists when someone has opted into having one.
- `show_in_directory`

**Author archive pages** at `/blog/author/<slug>`: bio, the `Person` schema, and their posts. Only
for `is_public` profiles with at least one live post; otherwise 404 rather than a thin page.

The byline on an article links to the archive when it exists and is plain text when it does not.

---

## 3. Comments

### The decision

Comments on a site for people who have been scammed before are worth having, because the questions
in them are the next twelve articles. They are also the single easiest way to put spam — or a
competitor's phone number — on your own pages. So: **comments are moderated by default, and every
setting defaults to the cautious value.**

### The model

`Comment`:

- `post` FK, `parent` FK (self, for one level of replies — see below)
- `author_user` — set when a signed-in staff member replies, so an official answer is marked as one
- `name`, `email`, `website` — for everyone else. **Email is never rendered publicly**, only used
  for moderation and reply notification.
- `body` — plain text, escaped on output. No Markdown, no HTML, not ever. A comment box that
  accepts markup is a persistent-XSS surface with no upside.
- `status` — `pending` / `approved` / `spam` / `rejected`
- `ip_address`, `user_agent` — for rate limiting and abuse review, on the retention schedule
- `is_pinned` — so a good answer sits at the top

**Threading is one level deep.** A reply to a reply attaches to the same top-level comment. Deeper
threads are unreadable on a phone, which is where this audience reads.

### The settings

| Field | Default | Why |
| --- | --- | --- |
| `comments_enabled` | true | The master switch. |
| `comments_require_approval` | true | The alternative is discovering what got published from a reader. |
| `comments_require_email` | true | Not shown publicly; it is how a reply reaches the asker. |
| `comments_allow_replies` | true | |
| `comments_close_after_days` | 0 | 0 = never. An old thread attracting only spam is a real thing. |
| `comments_notify_staff` | true | A new comment writes an in-app notification and emails whoever can moderate. |
| `comments_max_links` | 1 | More than this and it is auto-flagged as spam, not rejected — a real question can carry a link. |
| `comments_min_seconds` | 4 | A form submitted faster than a person can type was not typed. |
| `comments_blocklist` | — | Newline-separated phrases that auto-flag. Editable, because spam changes. |
| `comments_per_hour_per_ip` | 5 | |

`Post.comments_closed` overrides the global setting for one post.

### Anti-spam, in layers, none of them a CAPTCHA

1. **Honeypot field** — a hidden input real users never fill.
2. **Time-to-submit** — rendered timestamp compared against submission, under `comments_min_seconds`
   is a bot.
3. **Link count** — over `comments_max_links` flags as spam rather than rejecting.
4. **Blocklist** — phrase match flags as spam.
5. **Rate limit** — DRF throttle plus a per-IP count.

All five *flag*, none of them silently discard. A false positive that lands in a moderation queue
costs a moderator five seconds; one that vanishes costs a reader their question and us the trust.

No CAPTCHA: it is an accessibility problem, it sends a Nigerian audience's data to a third party,
and it stops fewer bots than the honeypot.

### Moderation

A queue at `/staff/blog/comments`: pending first, with post context, one-click approve / spam /
reject, bulk actions, and a reply box that posts as the agency. Every moderation action writes an
audit row, because "who approved this" is a question that eventually gets asked.

### SEO note

`commentCount` goes into the `BlogPosting` schema. The comments themselves are rendered
server-side, so they are indexable text on the page — which is most of the point: a page that
answers a question in the body *and* three follow-ups underneath ranks for all four.

---

## 4. Slug changes become safe

Phase 5 froze slugs at publish, which is right, and slightly too strict: sometimes a title was
wrong and the URL is embarrassing. `SlugRedirect` (old slug → post, permanent) makes a change
safe: changing a published post's slug now **creates a 301 redirect automatically** instead of
being refused. The public detail route resolves a miss against the redirect table and 301s.

This is strictly better than the refusal, because the refusal was protecting inbound links and a
301 protects them properly.

---

## 5. FAQ blocks, and why they are worth the model

`PostFaq` — ordered question/answer pairs on a post. Rendered on the page as a real definition
list, *and* emitted as `FAQPage` JSON-LD.

This is the highest-yield SEO feature in this document, because the questions this audience asks
are literal search queries ("can I apply with an HND", "how long does proof of funds need to sit
in the account") and `FAQPage` markup is how those become rich results. The rule is that it is
only emitted when the answers are also visible on the page — marking up content a reader cannot
see is exactly the kind of thing that earns a manual penalty, and it is dishonest besides.

---

## 6. Homepage integration

The landing page gains a guides section driven entirely by settings:
`homepage_show_latest`, `homepage_article_count`, `homepage_section_title`. It renders nothing at
all when there are no live posts — an empty "Latest guides" heading is worse than no section.

---

## 7. What the staff console gains

- `/staff/blog/settings` — every setting above, grouped, with the reasoning inline rather than in
  a wiki nobody opens.
- `/staff/blog/comments` — the moderation queue.
- `/staff/blog/authors` — author profiles, including the house-style scan on bios and credentials.
- The composer gains: a featured-image uploader with alt/caption/credit, an FAQ block editor, a
  per-post comment toggle, and a live SEO panel scored against the settings' own thresholds.

---

## 8. Not doing yet, deliberately

- **Analytics injection.** `analytics_measurement_id` is stored but nothing renders a script tag.
  Loading a third-party tracker needs a cookie-consent decision and a privacy-policy update
  first; shipping the field without the banner would put the site in breach of its own policy.
- **Comment reply-notification to the commenter.** Needs an unsubscribe link and a token, which is
  a small piece of work with a real abuse surface. Staff notification ships; reader notification
  does not.
- **Post series / multi-part guides.** Real value, no demand yet.
- **A/B testing titles.** Needs traffic that does not exist.
- **Full-text search.** Still `icontains`. Revisit at a few hundred posts.

---

## What shipped, against this plan

Everything in §1–§7 is built. The notes below are the places where building it
changed the plan, or where running it found something.

### Files

| Backend | Role |
| --- | --- |
| `apps/blog/settings_model.py` | `BlogSettings` — the singleton, 40 fields |
| `apps/blog/authors.py` | `AuthorProfile` |
| `apps/blog/comments.py` | `Comment`, the spam screening, the thread builder |
| `apps/blog/moderation.py` | `submit`, `moderate`, `reply_as_agency`, staff notification |
| `apps/blog/models.py` | `PostFaq`, `SlugRedirect`, and `Post`'s new fields |

| Frontend | Role |
| --- | --- |
| `app/staff/blog/settings/page.tsx` | Every setting, grouped, with its reasoning inline |
| `app/staff/blog/comments/page.tsx` | The moderation queue |
| `app/staff/blog/authors/page.tsx` | Author profiles — yours first, then the team's |
| `app/blog/author/[slug]/page.tsx` | Author archive, with `Person` + `ProfilePage` markup |
| `components/marketing/CommentThread.tsx` | The thread and the form |
| `components/marketing/ArticleExtras.tsx` | `FaqBlock`, `AuthorBox` |
| `components/marketing/HomepageGuides.tsx` | The landing page section |
| `components/staff/FaqEditor.tsx` | The FAQ block editor |
| `lib/blog-settings.ts` | The staff client for all of the above |

### Four things that came out of building it

**The settings singleton needed two fixes Django forced.** `BlogSettings` has no
`default` on its primary key, because Django forces an INSERT for an unsaved
instance whose pk has one — so `BlogSettings(posts_per_page=6).save()` collided
with the existing row instead of updating it. And `save()` on an unsaved instance
now adopts the live row's `created_at`, because an UPDATE of a never-loaded model
would otherwise null an `auto_now_add` column. Both are commented at the code.

**`BlogSettings.load()` is on every public page's read path, so its cache had to
become optional.** Running `make blog-seed` with Redis down took the whole seed
out with a `ConnectionError` — and by extension would have taken out every blog
page. The cache read, write and invalidation are now each allowed to fail, and
the worst case is one extra query. The comment rate limiter fails open for the
same reason: the DRF throttle above it is a separate ceiling, and refusing every
reader's comment because Redis is down is the wrong trade.

**The e2e field contract caught a real inconsistency.** The comment thread was
being bolted onto the detail response by the view rather than declared on
`PostDetailSerializer`, which meant the serializer, the generated OpenAPI schema
and the actual response disagreed. It is a serializer field now, and the view does
nothing but call it.

**One genuine accessibility defect, found by axe.** The author profile screen had
a link sitting inline in a run of text distinguished only by colour —
`link-in-text-block`, WCAG 1.4.1, serious. It and the composer's equivalent now
carry underlines.

### Two changes to the plan

**`Post.comments_closed` is a plain boolean, not nullable.** The plan implied a
three-state override (null = follow the setting). A boolean plus the four
conditions in `Post.comments_are_open` — site setting, per-post flag, the post
being live, and the age window — is simpler and has no case it cannot express.

**The publish gate gained two warnings rather than the settings gaining toggles.**
A post with no FAQ entries and an author with no public profile are both now
warnings on the pre-flight panel. Making them settings would have implied the
right answer is sometimes "no"; a warning says "this is cheap and you are leaving
it on the table", which is what is true.

### Verification

- **100 backend tests** in `tests/test_blog.py` (up from 44). The new ones cover
  the singleton and its cache, every excerpt policy, the required-image gate,
  author consent and the bio scan, FAQ validation, all five spam checks, the
  honeypot writing nothing, one-level threading, every comment-closing condition,
  that the public thread never carries an email, bulk moderation writing an audit
  row per comment, a writer being unable to moderate, and slug redirects over the
  API.
- **28 Playwright tests** on the staff side. Axe (WCAG 2.2 A + AA) over the
  settings screen, the moderation queue and the author profiles, in both colour
  schemes and at phone width, plus the earlier composer coverage. Behavioural
  tests assert that a flagged comment says *why*, that bulk actions do not appear
  until something is selected, that settings cannot be saved unchanged, and that
  the analytics field says plainly it is not wired up.
- `make lint-backend` clean, `tsc --noEmit` clean, `eslint` clean, 17 unit tests,
  54 contrast pairs across both themes, production build clean, `make blog-seed`
  runs and is idempotent.
- The field contract now covers all ten blog serializers.

### Still not done

- **Comment reply-notification to the commenter.** Staff get notified; the person
  who asked does not. It needs an unsubscribe token and has a real abuse surface,
  so it is a piece of work rather than a line.
- **No featured-image uploader in the composer.** The field works and Django
  admin can set it; the composer edits alt text, caption and credit only.
- **`analytics_measurement_id` renders nothing.** Deliberate — see §8.
- **Author avatars upload through Django admin only**, same reason as the hero.
- **No moderation of edits to an approved comment**, because we never edit a
  reader's words. If one needs changing it gets rejected and they are asked again.
