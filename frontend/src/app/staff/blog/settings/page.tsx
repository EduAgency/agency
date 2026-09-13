"use client";

/**
 * Staff: blog settings.
 *
 * Grouped the way someone thinks about the problem, not the way the model is
 * ordered, and every control carries the *reason* next to it. A settings screen
 * whose explanations live in a wiki is a settings screen where people guess.
 *
 * Saving is explicit and sends only what changed. A settings form that PUTs
 * everything will happily overwrite a value a colleague changed in another tab
 * while this one sat open.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, Button, Field, LoadingRegion, Skeleton } from "@/components/ui";
import {
  type BlogSettings,
  type ExcerptSource,
  type ListingLayout,
  getSettings,
  saveSettings,
} from "@/lib/blog-settings";

const inputStyle =
  "w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-subtle";

export default function BlogSettingsPage() {
  const [settings, setSettings] = useState<BlogSettings | null>(null);
  const [baseline, setBaseline] = useState<BlogSettings | null>(null);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [readOnly, setReadOnly] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const loaded = await getSettings();
        if (cancelled) return;
        setSettings(loaded);
        setBaseline(loaded);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? "Your account cannot see the blog settings."
            : "We couldn't load the settings. Please refresh.",
        );
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function update<K extends keyof BlogSettings>(key: K, value: BlogSettings[K]) {
    setSettings((current) => (current ? { ...current, [key]: value } : current));
    setNotice("");
  }

  const dirty = settings && baseline && JSON.stringify(settings) !== JSON.stringify(baseline);

  async function save() {
    if (!settings || !baseline) return;
    setSaving(true);
    setError("");
    try {
      // Only the changed keys, so a colleague's edit in another tab survives.
      const patch: Partial<BlogSettings> = {};
      for (const key of Object.keys(settings) as (keyof BlogSettings)[]) {
        if (settings[key] !== baseline[key]) {
          (patch as Record<string, unknown>)[key] = settings[key];
        }
      }
      const saved = await saveSettings(patch);
      setSettings(saved);
      setBaseline(saved);
      setNotice("Saved. Public pages pick this up within a minute.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setReadOnly(true);
        setError("You can read the settings but not change them. Ask an editor.");
      } else if (err instanceof ApiError) {
        setError(
          Object.entries(err.fieldErrors)
            .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
            .join(" · ") || err.message,
        );
      } else {
        setError("We couldn't save that. Try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (!ready) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-8">
        <LoadingRegion label="Loading the blog settings">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="mt-5 h-96" />
        </LoadingRegion>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Alert tone="error">{error || "The settings could not be loaded."}</Alert>
        <Link
          href="/staff/blog"
          className="mt-5 inline-block text-sm font-medium text-accent hover:underline"
        >
          ← Back to guides
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/staff/blog" className="text-sm text-muted hover:text-ink">
            ← Guides
          </Link>
          <h1 className="mt-2 text-xl font-semibold text-ink">Blog settings</h1>
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">
            These change what every reader sees. Nothing here can put a claim on the site — they
            control how much of something true is shown, never what is asserted.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span aria-live="polite" className="text-xs text-subtle">
            {dirty ? "Unsaved changes" : "All changes saved"}
          </span>
          <Button type="button" onClick={save} disabled={saving || !dirty || readOnly}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>

      {error ? (
        <div className="mt-5">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}
      {notice ? (
        <div className="mt-5">
          <Alert tone="success">{notice}</Alert>
        </div>
      ) : null}

      <div className="mt-8 space-y-6">
        {/* --- Listing and homepage ------------------------------------- */}
        <Group
          title="Listing and homepage"
          note="What /blog looks like, and what the landing page shows."
        >
          <Choice
            label="Listing layout"
            id="listing-layout"
            value={settings.listing_layout}
            onChange={(value) => update("listing_layout", value as ListingLayout)}
            options={[
              ["featured", "One lead article, then a grid"],
              ["grid", "Equal cards in a grid"],
              ["list", "Compact rows"],
            ]}
          />
          <NumberField
            label="Articles per page"
            id="posts-per-page"
            hint="The staff table's 25 is too many for article cards."
            value={settings.posts_per_page}
            min={3}
            max={50}
            onChange={(value) => update("posts_per_page", value)}
          />
          <NumberField
            label="Related articles under an article"
            id="related-count"
            hint="A reader who finishes and finds nothing next leaves the site. 0 hides the section."
            value={settings.related_post_count}
            min={0}
            max={6}
            onChange={(value) => update("related_post_count", value)}
          />
          <Toggle
            label="Show guides on the landing page"
            id="homepage-show"
            hint="Renders nothing when there are no live posts, so this is only for hiding a section you have articles for."
            checked={settings.homepage_show_latest}
            onChange={(value) => update("homepage_show_latest", value)}
          />
          <NumberField
            label="Articles on the landing page"
            id="homepage-count"
            value={settings.homepage_article_count}
            min={1}
            max={9}
            onChange={(value) => update("homepage_article_count", value)}
          />
          <Field label="Landing page heading" htmlFor="homepage-title">
            <input
              id="homepage-title"
              value={settings.homepage_section_title}
              onChange={(event) => update("homepage_section_title", event.target.value)}
              maxLength={80}
              className={inputStyle}
            />
          </Field>
          <Toggle
            label="Show the author's byline"
            id="show-byline"
            checked={settings.show_author_byline}
            onChange={(value) => update("show_author_byline", value)}
          />
          <Toggle
            label="Show the published date"
            id="show-date"
            hint="Some evergreen guides read better undated. That is an editorial call, not a bug."
            checked={settings.show_published_date}
            onChange={(value) => update("show_published_date", value)}
          />
          <Toggle
            label="Show reading time"
            id="show-reading-time"
            checked={settings.show_reading_time}
            onChange={(value) => update("show_reading_time", value)}
          />
        </Group>

        {/* --- Excerpts ------------------------------------------------- */}
        <Group
          title="Excerpts"
          note="The excerpt is the listing card and the meta description fallback, so a blank one costs twice."
        >
          <Choice
            label="Where the excerpt comes from"
            id="excerpt-source"
            value={settings.excerpt_source}
            onChange={(value) => update("excerpt_source", value as ExcerptSource)}
            options={[
              ["manual_then_auto", "Use what the writer types, otherwise derive one"],
              ["manual", "Only what the writer types"],
              ["auto", "Always derived from the body (overwrites what is typed)"],
            ]}
          />
          <NumberField
            label="Derived excerpt length"
            id="excerpt-length"
            hint="Characters. Under 80 is a fragment, not an excerpt."
            value={settings.excerpt_length}
            min={80}
            max={400}
            onChange={(value) => update("excerpt_length", value)}
          />
          <Toggle
            label="Require an excerpt before publishing"
            id="excerpt-required"
            checked={settings.excerpt_required_to_publish}
            onChange={(value) => update("excerpt_required_to_publish", value)}
          />
          <Field label="Read-more label" htmlFor="read-more">
            <input
              id="read-more"
              value={settings.read_more_label}
              onChange={(event) => update("read_more_label", event.target.value)}
              maxLength={40}
              className={inputStyle}
            />
          </Field>
        </Group>

        {/* --- Featured images ------------------------------------------ */}
        <Group
          title="Featured images"
          note="Alt text is always required when there is an image. That is WCAG 1.1.1, not a preference, so it is not a setting."
        >
          <Toggle
            label="Require a featured image before publishing"
            id="image-required"
            hint="Turn this on once the design looks broken without one."
            checked={settings.featured_image_required}
            onChange={(value) => update("featured_image_required", value)}
          />
          <Field
            label="Aspect ratio"
            htmlFor="image-aspect"
            hint='Written as a ratio, e.g. "16:9". Crops listings consistently so one tall image cannot break a row.'
          >
            <input
              id="image-aspect"
              value={settings.featured_image_aspect}
              onChange={(event) => update("featured_image_aspect", event.target.value)}
              maxLength={10}
              className={inputStyle}
            />
          </Field>
          <Toggle
            label="Show on listing pages"
            id="image-listing"
            checked={settings.show_featured_on_listing}
            onChange={(value) => update("show_featured_on_listing", value)}
          />
          <Toggle
            label="Show on the article itself"
            id="image-detail"
            checked={settings.show_featured_on_detail}
            onChange={(value) => update("show_featured_on_detail", value)}
          />
          {settings.default_featured_image ? (
            <p className="text-xs text-subtle">
              A site-wide fallback image is set. Replace it in the Django admin.
            </p>
          ) : (
            <p className="text-xs text-subtle">
              No fallback image: posts without one get the typographic card.
            </p>
          )}
        </Group>

        {/* --- Comments ------------------------------------------------- */}
        <Group
          title="Comments"
          note="Every default here is the cautious one. The questions readers leave are the next twelve articles; the spam is what makes that expensive."
        >
          <Toggle
            label="Comments on"
            id="comments-enabled"
            hint="The master switch. Individual posts can still close their own."
            checked={settings.comments_enabled}
            onChange={(value) => update("comments_enabled", value)}
          />
          <Toggle
            label="Hold comments for review"
            id="comments-approval"
            hint="Off means finding out what got published from a reader. Leave it on."
            checked={settings.comments_require_approval}
            onChange={(value) => update("comments_require_approval", value)}
          />
          <Toggle
            label="Require an email address"
            id="comments-email"
            hint="Never shown on the page. It is how a reply reaches the asker."
            checked={settings.comments_require_email}
            onChange={(value) => update("comments_require_email", value)}
          />
          <Toggle
            label="Allow replies"
            id="comments-replies"
            hint="One level deep only — deeper threads are unreadable on a phone."
            checked={settings.comments_allow_replies}
            onChange={(value) => update("comments_allow_replies", value)}
          />
          <Toggle
            label="Tell staff about new comments"
            id="comments-notify"
            checked={settings.comments_notify_staff}
            onChange={(value) => update("comments_notify_staff", value)}
          />
          <NumberField
            label="Close comments after (days)"
            id="comments-close"
            hint="0 means never. An old thread attracting only spam is a real thing."
            value={settings.comments_close_after_days}
            min={0}
            max={3650}
            onChange={(value) => update("comments_close_after_days", value)}
          />
          <NumberField
            label="Links before a comment is flagged"
            id="comments-links"
            hint="Flagged for review, not rejected — a real question can carry a link."
            value={settings.comments_max_links}
            min={0}
            max={10}
            onChange={(value) => update("comments_max_links", value)}
          />
          <NumberField
            label="Minimum seconds before submitting"
            id="comments-seconds"
            hint="A form submitted faster than a person can type was not typed by one."
            value={settings.comments_min_seconds}
            min={0}
            max={60}
            onChange={(value) => update("comments_min_seconds", value)}
          />
          <NumberField
            label="Comments per hour per connection"
            id="comments-rate"
            value={settings.comments_per_hour_per_ip}
            min={1}
            max={50}
            onChange={(value) => update("comments_per_hour_per_ip", value)}
          />
          <Field
            label="Blocked phrases"
            htmlFor="comments-blocklist"
            hint="One per line. A match flags the comment for review rather than discarding it."
          >
            <textarea
              id="comments-blocklist"
              value={settings.comments_blocklist}
              onChange={(event) => update("comments_blocklist", event.target.value)}
              rows={4}
              className={`${inputStyle} font-mono text-[13px]`}
            />
          </Field>
          <p className="text-xs text-subtle">
            There is deliberately no CAPTCHA: it is an accessibility barrier, it sends a
            reader&rsquo;s data to a third party, and it stops fewer bots than the hidden honeypot
            field already does.
          </p>
        </Group>

        {/* --- Authors -------------------------------------------------- */}
        <Group
          title="Authors"
          note="An author who demonstrably exists does more for trust than any badge — and the Person markup on an author page is how a search engine knows it."
        >
          <Toggle
            label="Publish author pages"
            id="author-pages"
            hint="Only for authors who opted in and have at least one live article."
            checked={settings.author_pages_enabled}
            onChange={(value) => update("author_pages_enabled", value)}
          />
          <Toggle
            label="Show the author box under articles"
            id="author-bio"
            checked={settings.show_author_bio_on_article}
            onChange={(value) => update("show_author_bio_on_article", value)}
          />
          <p className="text-xs text-subtle">
            <Link href="/staff/blog/authors" className="font-medium text-accent hover:underline">
              Edit author profiles →
            </Link>
          </p>
        </Group>

        {/* --- SEO ------------------------------------------------------ */}
        <Group
          title="Search"
          note="Nothing here asserts anything the site does not also say in plain text."
        >
          <Field
            label="Title template"
            htmlFor="meta-template"
            hint="Placeholders: {title} and {site}. So renaming the brand is one edit, not one per post."
          >
            <input
              id="meta-template"
              value={settings.meta_title_template}
              onChange={(event) => update("meta_title_template", event.target.value)}
              maxLength={120}
              className={`${inputStyle} font-mono text-[13px]`}
            />
          </Field>
          <Field
            label="Fallback meta description"
            htmlFor="default-description"
            hint="Used where a page has neither its own description nor an excerpt."
          >
            <textarea
              id="default-description"
              value={settings.default_meta_description}
              onChange={(event) => update("default_meta_description", event.target.value)}
              rows={2}
              maxLength={180}
              className={inputStyle}
            />
          </Field>
          <Field
            label="X / Twitter handle"
            htmlFor="twitter-site"
            hint="Starts with @. Appears as the attribution on share cards."
          >
            <input
              id="twitter-site"
              value={settings.twitter_site}
              onChange={(event) => update("twitter_site", event.target.value)}
              placeholder="@nasuru"
              maxLength={40}
              className={inputStyle}
            />
          </Field>
          <Field
            label="Google Search Console verification"
            htmlFor="google-verification"
            hint="The content of the meta tag Search Console gives you. Here rather than in an env var, because the person who needs it is the person logged into Search Console."
          >
            <input
              id="google-verification"
              value={settings.google_site_verification}
              onChange={(event) => update("google_site_verification", event.target.value)}
              maxLength={120}
              className={`${inputStyle} font-mono text-[13px]`}
            />
          </Field>
          <Field label="Bing verification" htmlFor="bing-verification">
            <input
              id="bing-verification"
              value={settings.bing_site_verification}
              onChange={(event) => update("bing_site_verification", event.target.value)}
              maxLength={120}
              className={`${inputStyle} font-mono text-[13px]`}
            />
          </Field>
          <Toggle
            label="Keep tag pages out of search results"
            id="noindex-tags"
            hint="A tag page is usually a subset of a category page. Indexing both asks a search engine to choose between two pages saying the same thing, and it usually chooses neither."
            checked={settings.noindex_tag_pages}
            onChange={(value) => update("noindex_tag_pages", value)}
          />
          <Toggle
            label="List author pages in the sitemap"
            id="sitemap-authors"
            checked={settings.sitemap_include_authors}
            onChange={(value) => update("sitemap_include_authors", value)}
          />
          <Toggle
            label="Full article text in the RSS feed"
            id="feed-full"
            hint="A full-text feed is an invitation to scrape the whole blog. Off sends the excerpt and brings readers to the page."
            checked={settings.feed_full_text}
            onChange={(value) => update("feed_full_text", value)}
          />
          <NumberField
            label="Articles in the feed"
            id="feed-count"
            value={settings.feed_item_count}
            min={5}
            max={100}
            onChange={(value) => update("feed_item_count", value)}
          />
          <Field
            label="Analytics measurement ID"
            htmlFor="analytics-id"
            hint="Stored but NOT yet loaded on the site. A tracker needs a cookie-consent banner and a privacy-policy update first — shipping it without those would put the site in breach of its own policy."
          >
            <input
              id="analytics-id"
              value={settings.analytics_measurement_id}
              onChange={(event) => update("analytics_measurement_id", event.target.value)}
              placeholder="G-XXXXXXX"
              maxLength={40}
              className={`${inputStyle} font-mono text-[13px]`}
            />
          </Field>
        </Group>
      </div>

      <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-line pt-6">
        <Button type="button" onClick={save} disabled={saving || !dirty || readOnly}>
          {saving ? "Saving…" : "Save settings"}
        </Button>
        <span className="text-xs text-subtle">
          Last changed {new Date(settings.updated_at).toLocaleString("en-NG")}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small form primitives, local to this screen
// ---------------------------------------------------------------------------

function Group({
  title,
  note,
  children,
}: {
  title: string;
  note: string;
  children: React.ReactNode;
}) {
  const id = title.toLowerCase().replace(/\s+/g, "-");
  return (
    <section aria-labelledby={id} className="rounded-xl border border-line bg-surface p-5">
      <h2 id={id} className="font-display text-base font-bold text-ink">
        {title}
      </h2>
      <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">{note}</p>
      <div className="mt-5 space-y-5">{children}</div>
    </section>
  );
}

function Toggle({
  label,
  id,
  hint,
  checked,
  onChange,
}: {
  label: string;
  id: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1"
      />
      <label htmlFor={id} className="text-sm text-ink">
        {label}
        {hint ? (
          <span className="mt-0.5 block text-xs leading-relaxed text-subtle">{hint}</span>
        ) : null}
      </label>
    </div>
  );
}

function NumberField({
  label,
  id,
  hint,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  id: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label} htmlFor={id} hint={hint}>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        value={value}
        min={min}
        max={max}
        onChange={(event) =>
          onChange(Math.max(min, Math.min(max, Number(event.target.value) || min)))
        }
        className="w-28 rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink tabular-nums"
      />
    </Field>
  );
}

function Choice({
  label,
  id,
  hint,
  value,
  options,
  onChange,
}: {
  label: string;
  id: string;
  hint?: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label} htmlFor={id} hint={hint}>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputStyle}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </Field>
  );
}
