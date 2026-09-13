"use client";

/**
 * The composer.
 *
 * Markdown in a textarea, not a rich-text editor. That is a deliberate choice,
 * not a shortcut: the body is rendered and sanitised server-side into a fixed
 * set of tags (apps/blog/rendering.py), so a WYSIWYG surface would offer
 * formatting the pipeline then silently discards. A writer who can see exactly
 * what they typed never loses work to that gap.
 *
 * Saving is explicit. Autosave sounds kinder until it silently overwrites a
 * paragraph someone was mid-way through rewriting; instead the page tracks
 * unsaved changes, warns before a reload, and keeps a server-side revision on
 * every save so nothing is unrecoverable either way.
 *
 * Publishing is a separate step with its own permission, and the pre-flight
 * panel shows what the server will check before it is pressed.
 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, Button, Field, LoadingRegion, Skeleton } from "@/components/ui";
import { BlogAiPanel } from "@/components/staff/BlogAiPanel";
import { FaqEditor } from "@/components/staff/FaqEditor";
import { HouseStyleReview } from "@/components/staff/HouseStyleReview";
import {
  AI_INVOLVEMENT_LABELS,
  type AdminPost,
  type AiInvolvement,
  type BlogTaxonomy,
  type Preflight,
  type Revision,
  STATUS_LABELS,
  aiAssist,
  aiStatus,
  createTag,
  getAdminPost,
  listAdminCategories,
  listAdminTags,
  listRevisions,
  preflight as fetchPreflight,
  publishPost,
  restoreRevision,
  savePost,
  unpublishPost,
} from "@/lib/blog-admin";
import { SITE_URL } from "@/lib/seo";

const inputStyle =
  "w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-subtle";

type Draft = Pick<
  AdminPost,
  | "title"
  | "excerpt"
  | "body"
  | "category_id"
  | "tag_ids"
  | "hero_alt"
  | "hero_caption"
  | "hero_credit"
  | "comments_closed"
  | "meta_title"
  | "meta_description"
  | "canonical_url"
  | "noindex"
  | "focus_keyword"
  | "ai_involvement"
  | "ai_notes"
  | "style_override_reason"
>;

function toDraft(post: AdminPost): Draft {
  return {
    title: post.title,
    excerpt: post.excerpt,
    body: post.body,
    category_id: post.category_id,
    tag_ids: post.tag_ids,
    hero_alt: post.hero_alt,
    hero_caption: post.hero_caption,
    hero_credit: post.hero_credit,
    comments_closed: post.comments_closed,
    meta_title: post.meta_title,
    meta_description: post.meta_description,
    canonical_url: post.canonical_url,
    noindex: post.noindex,
    focus_keyword: post.focus_keyword,
    ai_involvement: post.ai_involvement,
    ai_notes: post.ai_notes,
    style_override_reason: post.style_override_reason,
  };
}

export default function Composer({ params }: { params: Promise<{ slug: string }> }) {
  const [slug, setSlug] = useState("");
  const [post, setPost] = useState<AdminPost | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [baseline, setBaseline] = useState<Draft | null>(null);

  const [categories, setCategories] = useState<BlogTaxonomy[]>([]);
  const [tags, setTags] = useState<BlogTaxonomy[]>([]);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [check, setCheck] = useState<Preflight | null>(null);
  const [ai, setAi] = useState({ enabled: false, model: "" });

  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [newTag, setNewTag] = useState("");
  const [publishAt, setPublishAt] = useState("");
  const [preview, setPreview] = useState(false);

  useEffect(() => {
    params.then(({ slug: value }) => setSlug(value));
  }, [params]);

  const load = useCallback(async (postSlug: string) => {
    const [loaded, loadedCategories, loadedTags] = await Promise.all([
      getAdminPost(postSlug),
      listAdminCategories(),
      listAdminTags(),
    ]);
    setPost(loaded);
    setDraft(toDraft(loaded));
    setBaseline(toDraft(loaded));
    setCategories(loadedCategories);
    setTags(loadedTags);
    return loaded;
  }, []);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    (async () => {
      try {
        await load(slug);
        if (cancelled) return;
        const [status, history, preflightResult] = await Promise.all([
          aiStatus().catch(() => ({ enabled: false, model: "" })),
          listRevisions(slug).catch(() => []),
          fetchPreflight(slug).catch(() => null),
        ]);
        if (cancelled) return;
        setAi(status);
        setRevisions(history);
        setCheck(preflightResult);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 404
            ? "That guide does not exist."
            : "We couldn't load this guide. Please refresh.",
        );
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug, load]);

  const dirty = useMemo(
    () => Boolean(draft && baseline) && JSON.stringify(draft) !== JSON.stringify(baseline),
    [draft, baseline],
  );

  // The browser's own "leave site?" prompt. Crude, and the only thing that
  // reliably catches a closed tab.
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
    setNotice("");
  }

  function applyAiSuggestion(patch: Record<string, unknown>, involvement: AiInvolvement) {
    setDraft((current) => {
      if (!current) return current;
      // Provenance only ever escalates: once a draft has been machine-written,
      // a later metadata suggestion must not downgrade it to "AI-assisted edit".
      const rank: Record<AiInvolvement, number> = {
        none: 0,
        outline: 1,
        edit: 2,
        draft: 3,
      };
      const next =
        rank[involvement] > rank[current.ai_involvement] ? involvement : current.ai_involvement;
      return { ...current, ...patch, ai_involvement: next } as Draft;
    });
    setNotice("Applied to the draft. Save when you are happy with it.");
  }

  async function save() {
    if (!draft || !post) return;
    setSaving(true);
    setError("");
    try {
      const saved = await savePost(post.slug, draft);
      setPost(saved);
      setBaseline(toDraft(saved));
      setDraft(toDraft(saved));
      setNotice("Saved.");
      const [history, preflightResult] = await Promise.all([
        listRevisions(saved.slug).catch(() => revisions),
        fetchPreflight(saved.slug).catch(() => null),
      ]);
      setRevisions(history);
      setCheck(preflightResult);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? Object.entries(err.fieldErrors)
              .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
              .join(" · ") || err.message
          : "We couldn't save that. Try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function publish(force: boolean) {
    if (!post) return;
    setPublishing(true);
    setError("");
    try {
      const published = await publishPost(post.slug, {
        publish_at: publishAt ? new Date(publishAt).toISOString() : null,
        force,
      });
      setPost(published);
      setBaseline(toDraft(published));
      setDraft(toDraft(published));
      setNotice(
        published.status === "scheduled"
          ? "Scheduled. It will appear by itself at the time you set."
          : "Published. It is on the site now.",
      );
      setCheck(await fetchPreflight(published.slug).catch(() => null));
    } catch (err) {
      if (err instanceof ApiError) {
        const blockers = err.fieldErrors.blockers ?? [];
        const warnings = err.fieldErrors.warnings ?? [];
        setCheck({ ok: blockers.length === 0, blockers, warnings });
        setError(
          blockers.length
            ? "This cannot be published yet — see what needs fixing below."
            : warnings.length
              ? "There are warnings. Review them, then publish anyway if you are happy."
              : err.message,
        );
      } else {
        setError("We couldn't publish that. Try again.");
      }
    } finally {
      setPublishing(false);
    }
  }

  async function takeDown() {
    if (!post) return;
    setPublishing(true);
    try {
      const updated = await unpublishPost(post.slug, "Taken down from the composer");
      setPost(updated);
      setNotice("Taken off the site. The URL stays reserved.");
    } catch {
      setError("We couldn't take that down. Try again.");
    } finally {
      setPublishing(false);
    }
  }

  async function runReview() {
    if (!draft) return;
    try {
      const response = await aiAssist("review", { body: draft.body });
      if (response.review) {
        setCheck({
          ok: response.review.ok,
          blockers: response.review.flags.map((flag) => `${flag.why} — “${flag.excerpt}”`),
          warnings: check?.warnings ?? [],
        });
      }
    } catch {
      setError("The house-style check did not run. Save and try again.");
    }
  }

  async function addTag() {
    const name = newTag.trim();
    if (!name) return;
    try {
      const tag = await createTag(name);
      setTags((current) => [...current, tag]);
      update("tag_ids", [...(draft?.tag_ids ?? []), tag.id]);
      setNewTag("");
    } catch {
      setError("That tag could not be created — it may already exist.");
    }
  }

  async function restore(revisionId: string) {
    if (!post) return;
    try {
      await restoreRevision(post.slug, revisionId);
      await load(post.slug);
      setRevisions(await listRevisions(post.slug));
      setNotice("Restored. The version you replaced is still in the history.");
    } catch {
      setError("We couldn't restore that revision.");
    }
  }

  if (!ready) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8">
        <LoadingRegion label="Loading the guide">
          <Skeleton className="h-9 w-2/3" />
          <Skeleton className="mt-4 h-64" />
        </LoadingRegion>
      </div>
    );
  }

  if (!post || !draft) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Alert tone="error">{error || "That guide could not be loaded."}</Alert>
        <Link
          href="/staff/blog"
          className="mt-5 inline-block text-sm font-medium text-accent hover:underline"
        >
          ← Back to guides
        </Link>
      </div>
    );
  }

  const isLive = post.status === "published" || post.status === "scheduled";
  const words = draft.body.trim() ? draft.body.trim().split(/\s+/).length : 0;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/staff/blog" className="text-sm text-muted hover:text-ink">
            ← Guides
          </Link>
          <h1 className="mt-2 text-xl font-semibold text-ink">{draft.title || "Untitled guide"}</h1>
          <p className="mt-1 text-sm text-subtle">
            <span className="font-mono">
              {SITE_URL}/blog/{post.slug}
            </span>
            {isLive ? null : " — not live yet"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-full border border-line px-3 py-1 text-xs text-muted">
            {STATUS_LABELS[post.status]}
          </span>
          <span aria-live="polite" className="text-xs text-subtle">
            {dirty ? "Unsaved changes" : "All changes saved"}
          </span>
          <Button type="button" onClick={save} disabled={saving || !dirty}>
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

      <div className="mt-7 grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        {/* --- The draft --------------------------------------------------- */}
        <div className="min-w-0 space-y-5">
          <Field label="Title" htmlFor="post-title">
            <input
              id="post-title"
              value={draft.title}
              onChange={(event) => update("title", event.target.value)}
              className={inputStyle}
            />
          </Field>

          <Field
            label="Excerpt"
            htmlFor="post-excerpt"
            hint={`${draft.excerpt.length}/400 — shown on listings and used as the meta description when none is set.`}
          >
            <textarea
              id="post-excerpt"
              value={draft.excerpt}
              onChange={(event) => update("excerpt", event.target.value)}
              rows={2}
              maxLength={400}
              className={inputStyle}
            />
          </Field>

          <div>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <label htmlFor="post-body" className="block text-sm font-medium text-ink">
                Body
              </label>
              <div className="flex items-center gap-4 text-xs text-subtle">
                <span>
                  {words} words · about {Math.max(1, Math.round(words / 225))} min read
                </span>
                <button
                  type="button"
                  aria-pressed={preview}
                  onClick={() => setPreview((value) => !value)}
                  className="font-medium text-accent hover:underline"
                >
                  {preview ? "Edit" : "Preview"}
                </button>
              </div>
            </div>
            <p className="mt-1 text-xs text-subtle">
              Markdown. Start sections at <code className="font-mono">##</code> — the title is the
              page&rsquo;s only H1.
            </p>
            {preview ? (
              <div className="post-body mt-2 max-h-[40rem] overflow-auto rounded-lg border border-line bg-surface p-5">
                {/* Sanitised server-side; this is the saved render, so it lags
                    unsaved edits by one save — which the label says. */}
                <div dangerouslySetInnerHTML={{ __html: post.body_html }} />
              </div>
            ) : (
              <textarea
                id="post-body"
                value={draft.body}
                onChange={(event) => update("body", event.target.value)}
                rows={26}
                spellCheck
                className={`${inputStyle} font-mono text-[13px] leading-relaxed`}
              />
            )}
            {preview ? (
              <p className="mt-1.5 text-xs text-subtle">
                This is the last saved version. Save to refresh the preview.
              </p>
            ) : null}
          </div>

          {/* --- Pre-flight ----------------------------------------------- */}
          <section
            aria-labelledby="preflight"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="preflight" className="text-sm font-semibold text-ink">
                Before it can go live
              </h2>
              <button
                type="button"
                onClick={runReview}
                className="text-xs font-medium text-accent hover:underline"
              >
                Re-check the body now
              </button>
            </div>

            {check ? (
              <div className="mt-3 space-y-3">
                {check.blockers.length ? (
                  <div className="rounded-lg border border-danger-line bg-danger-bg px-3 py-3">
                    <h3 className="text-sm font-semibold text-ink">
                      {check.blockers.length} {check.blockers.length === 1 ? "blocker" : "blockers"}
                    </h3>
                    <ul className="mt-1.5 ml-4 list-disc space-y-1 text-sm text-ink">
                      {check.blockers.map((blocker) => (
                        <li key={blocker}>{blocker}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <HouseStyleReview
                    review={{ ok: true, flags: [] }}
                    label="Nothing is blocking it."
                  />
                )}

                {check.warnings.length ? (
                  <div className="rounded-lg border border-warning-line bg-warning-bg px-3 py-3">
                    <h3 className="text-sm font-semibold text-ink">Worth fixing, not blocking</h3>
                    <ul className="mt-1.5 ml-4 list-disc space-y-1 text-sm text-ink">
                      {check.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {/* The escape hatch for the one article the scan gets wrong:
                    a piece that quotes the claims it is warning readers about.
                    Offered only when there is something to override, and the
                    reason is copied into the audit record on publish. */}
                {check.blockers.length || draft.style_override_reason ? (
                  <Field
                    label="Override the house-style flags"
                    htmlFor="style-override"
                    hint="Only for a post that quotes the claims it warns against. Saved with the publish record."
                  >
                    <textarea
                      id="style-override"
                      value={draft.style_override_reason}
                      onChange={(event) => update("style_override_reason", event.target.value)}
                      rows={3}
                      placeholder="Why these phrases belong in this article"
                      className={inputStyle}
                    />
                  </Field>
                ) : null}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">Save the draft to run the checks.</p>
            )}

            <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-line pt-4">
              <div>
                <label htmlFor="publish-at" className="block text-xs font-semibold text-muted">
                  Publish at (leave blank for now)
                </label>
                <input
                  id="publish-at"
                  type="datetime-local"
                  value={publishAt}
                  onChange={(event) => setPublishAt(event.target.value)}
                  className="mt-1.5 rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink"
                />
              </div>
              <Button
                type="button"
                onClick={() => publish(false)}
                disabled={publishing || dirty || Boolean(check && !check.ok)}
              >
                {publishing ? "Publishing…" : publishAt ? "Schedule" : "Publish"}
              </Button>
              {check?.warnings.length && check.ok ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => publish(true)}
                  disabled={publishing || dirty}
                >
                  Publish anyway
                </Button>
              ) : null}
              {isLive ? (
                <Button type="button" variant="danger" onClick={takeDown} disabled={publishing}>
                  Take off the site
                </Button>
              ) : null}
            </div>
            {dirty ? (
              <p className="mt-2 text-xs text-warning">Save your changes before publishing.</p>
            ) : null}
          </section>
        </div>

        {/* --- Sidebar ----------------------------------------------------- */}
        <div className="space-y-6">
          <BlogAiPanel
            title={draft.title}
            body={draft.body}
            enabled={ai.enabled}
            model={ai.model}
            onApply={applyAiSuggestion}
          />

          {/* Its own component: entries save one at a time, not with the post. */}
          <FaqEditor postSlug={post.slug} />

          <section
            aria-labelledby="featured-image"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <h2 id="featured-image" className="text-sm font-semibold text-ink">
              Featured image
            </h2>
            {post.hero_image ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element -- signed R2 URL. */}
                <img
                  src={post.hero_image}
                  alt={draft.hero_alt}
                  className="mt-3 w-full rounded-lg border border-line object-cover"
                />
                <div className="mt-4 space-y-4">
                  <Field
                    label="What the image shows"
                    htmlFor="hero-alt"
                    hint="Required. An article hero is never decorative."
                  >
                    <input
                      id="hero-alt"
                      value={draft.hero_alt}
                      onChange={(event) => update("hero_alt", event.target.value)}
                      maxLength={200}
                      className={inputStyle}
                    />
                  </Field>
                  <Field
                    label="Caption"
                    htmlFor="hero-caption"
                    hint="Shown under the image. A different job from the alt text — optional."
                  >
                    <input
                      id="hero-caption"
                      value={draft.hero_caption}
                      onChange={(event) => update("hero_caption", event.target.value)}
                      maxLength={300}
                      className={inputStyle}
                    />
                  </Field>
                  <Field
                    label="Credit"
                    htmlFor="hero-credit"
                    hint="Fill this in if the image is not ours."
                  >
                    <input
                      id="hero-credit"
                      value={draft.hero_credit}
                      onChange={(event) => update("hero_credit", event.target.value)}
                      maxLength={160}
                      className={inputStyle}
                    />
                  </Field>
                </div>
              </>
            ) : (
              <p className="mt-2 text-sm leading-relaxed text-muted">
                No image. Upload one in the Django admin — the composer has no uploader yet, and
                whether a post needs one at all is a setting.
              </p>
            )}
          </section>

          <section
            aria-labelledby="post-comments"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <h2 id="post-comments" className="text-sm font-semibold text-ink">
              Comments
            </h2>
            <p className="mt-1.5 text-xs text-subtle">
              {post.comment_count} published
              {post.pending_comment_count ? (
                <>
                  {" · "}
                  <Link
                    href={`/staff/blog/comments?post=${post.slug}`}
                    className="font-semibold text-accent underline underline-offset-2"
                  >
                    {post.pending_comment_count} waiting for review
                  </Link>
                </>
              ) : null}
            </p>
            <div className="mt-3 flex items-start gap-2">
              <input
                id="comments-closed"
                type="checkbox"
                checked={draft.comments_closed}
                onChange={(event) => update("comments_closed", event.target.checked)}
                className="mt-1"
              />
              <label htmlFor="comments-closed" className="text-sm text-ink">
                Close comments on this guide
                <span className="block text-xs text-subtle">
                  Overrides the site-wide setting for this post only.
                </span>
              </label>
            </div>
          </section>

          <section
            aria-labelledby="placement"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <h2 id="placement" className="text-sm font-semibold text-ink">
              Placement
            </h2>
            <div className="mt-3 space-y-4">
              <Field label="Category" htmlFor="post-category">
                <select
                  id="post-category"
                  value={draft.category_id ?? ""}
                  onChange={(event) => update("category_id", event.target.value || null)}
                  className={inputStyle}
                >
                  <option value="">No category</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </Field>

              <fieldset>
                <legend className="text-sm font-medium text-ink">Tags</legend>
                <ul className="mt-2 space-y-1.5">
                  {tags.map((tag) => {
                    const checked = draft.tag_ids.includes(tag.id);
                    return (
                      <li key={tag.id} className="flex items-center gap-2">
                        <input
                          id={`tag-${tag.id}`}
                          type="checkbox"
                          checked={checked}
                          onChange={(event) =>
                            update(
                              "tag_ids",
                              event.target.checked
                                ? [...draft.tag_ids, tag.id]
                                : draft.tag_ids.filter((id) => id !== tag.id),
                            )
                          }
                        />
                        <label htmlFor={`tag-${tag.id}`} className="text-sm text-ink">
                          {tag.name}
                        </label>
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-3 flex gap-2">
                  <label htmlFor="new-tag" className="sr-only">
                    New tag name
                  </label>
                  <input
                    id="new-tag"
                    value={newTag}
                    onChange={(event) => setNewTag(event.target.value)}
                    placeholder="Add a tag"
                    className={inputStyle}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={addTag}
                    disabled={!newTag.trim()}
                  >
                    Add
                  </Button>
                </div>
              </fieldset>
            </div>
          </section>

          <section
            aria-labelledby="search"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <h2 id="search" className="text-sm font-semibold text-ink">
              Search
            </h2>
            <div className="mt-3 space-y-4">
              <Field
                label="Search title"
                htmlFor="meta-title"
                hint={`${(draft.meta_title || draft.title).length} chars — results cut near 60. Blank falls back to the title.`}
              >
                <input
                  id="meta-title"
                  value={draft.meta_title}
                  onChange={(event) => update("meta_title", event.target.value)}
                  maxLength={70}
                  className={inputStyle}
                />
              </Field>
              <Field
                label="Meta description"
                htmlFor="meta-description"
                hint={`${(draft.meta_description || draft.excerpt).length} chars — results cut near 155. Blank falls back to the excerpt.`}
              >
                <textarea
                  id="meta-description"
                  value={draft.meta_description}
                  onChange={(event) => update("meta_description", event.target.value)}
                  rows={3}
                  maxLength={180}
                  className={inputStyle}
                />
              </Field>
              <Field
                label="Focus keyword"
                htmlFor="focus-keyword"
                hint="What this should be found for. One phrase, not a list."
              >
                <input
                  id="focus-keyword"
                  value={draft.focus_keyword}
                  onChange={(event) => update("focus_keyword", event.target.value)}
                  className={inputStyle}
                />
              </Field>
              <Field
                label="Canonical URL"
                htmlFor="canonical-url"
                hint="Only if this was published somewhere else first."
              >
                <input
                  id="canonical-url"
                  type="url"
                  value={draft.canonical_url}
                  onChange={(event) => update("canonical_url", event.target.value)}
                  className={inputStyle}
                />
              </Field>
              <div className="flex items-start gap-2">
                <input
                  id="noindex"
                  type="checkbox"
                  checked={draft.noindex}
                  onChange={(event) => update("noindex", event.target.checked)}
                  className="mt-1"
                />
                <label htmlFor="noindex" className="text-sm text-ink">
                  Keep out of search results
                  <span className="block text-xs text-subtle">
                    For thin or duplicate pages only.
                  </span>
                </label>
              </div>

              {/* A rough search-result preview. Not pixel-accurate to any one
                  engine, and it does not need to be — its job is to show a
                  writer where their title gets cut. */}
              <div className="rounded-lg border border-line bg-sunken p-3">
                <p className="text-xs font-semibold text-subtle">Roughly how it will appear</p>
                <p className="mt-2 truncate text-sm text-info">
                  {draft.meta_title || draft.title || "Untitled"}
                </p>
                <p className="text-xs text-success">
                  {SITE_URL}/blog/{post.slug}
                </p>
                <p className="mt-1 text-xs leading-snug text-muted">
                  {(draft.meta_description || draft.excerpt || "No description yet.").slice(0, 160)}
                </p>
              </div>
            </div>
          </section>

          <section
            aria-labelledby="provenance"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <h2 id="provenance" className="text-sm font-semibold text-ink">
              Provenance
            </h2>
            <p className="mt-1.5 text-xs leading-relaxed text-subtle">
              Shown to readers on the article. If AI was involved, the notes are required before it
              can be published.
            </p>
            <div className="mt-3 space-y-4">
              <Field label="How AI was involved" htmlFor="ai-involvement">
                <select
                  id="ai-involvement"
                  value={draft.ai_involvement}
                  onChange={(event) =>
                    update("ai_involvement", event.target.value as AiInvolvement)
                  }
                  className={inputStyle}
                >
                  {Object.entries(AI_INVOLVEMENT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              {draft.ai_involvement !== "none" ? (
                <Field
                  label="What was generated, and what you changed"
                  htmlFor="ai-notes"
                  hint="Internal. Never shown on the site."
                >
                  <textarea
                    id="ai-notes"
                    value={draft.ai_notes}
                    onChange={(event) => update("ai_notes", event.target.value)}
                    rows={4}
                    className={inputStyle}
                  />
                </Field>
              ) : null}
            </div>
          </section>

          <section
            aria-labelledby="history"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <h2 id="history" className="text-sm font-semibold text-ink">
              History
            </h2>
            {revisions.length === 0 ? (
              <p className="mt-2 text-sm text-muted">No revisions yet.</p>
            ) : (
              <ul className="mt-3 space-y-2.5">
                {revisions.slice(0, 10).map((revision) => (
                  <li key={revision.id} className="flex items-start justify-between gap-3 text-sm">
                    <span>
                      <span className="block text-ink">{revision.note || "Edit"}</span>
                      <span className="block text-xs text-subtle">
                        {new Date(revision.created_at).toLocaleString("en-NG", {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}{" "}
                        · {revision.editor_name}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => restore(revision.id)}
                      className="shrink-0 text-xs font-semibold text-accent hover:underline"
                    >
                      Restore
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {post.status === "published" ? (
            <a
              href={`/blog/${post.slug}`}
              className="block rounded-xl border border-line bg-surface p-4 text-sm font-medium text-accent hover:underline"
            >
              View it on the site →
            </a>
          ) : null}
        </div>
      </div>
    </div>
  );
}
