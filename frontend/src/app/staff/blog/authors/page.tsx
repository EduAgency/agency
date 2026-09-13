"use client";

/**
 * Staff: author profiles.
 *
 * The screen everyone will use for their own profile, and that an editor uses
 * for the team's. It leads with "your profile" because that is what nine visits
 * out of ten are for.
 *
 * The bio and credentials fields are the interesting part. They go through the
 * same house-style scan as an article, so a bio claiming a qualification we
 * cannot evidence is refused with the offending sentence quoted back. That is
 * the most tempting place on the whole site to overstate something, and it is
 * the one place nobody would think to check.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, Button, Field, LoadingRegion, Skeleton } from "@/components/ui";
import {
  type AuthorProfile,
  getMyAuthorProfile,
  listAuthors,
  saveAuthor,
  saveMyAuthorProfile,
} from "@/lib/blog-settings";
import { SITE_URL } from "@/lib/seo";

const inputStyle =
  "w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-subtle";

export default function AuthorsPage() {
  const [mine, setMine] = useState<AuthorProfile | null>(null);
  const [others, setOthers] = useState<AuthorProfile[]>([]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [own, all] = await Promise.all([
      getMyAuthorProfile(),
      listAuthors().catch(() => [] as AuthorProfile[]),
    ]);
    setMine(own);
    setOthers(all.filter((profile) => profile.id !== own.id));
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await load();
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? "Your account cannot edit author profiles."
            : "We couldn't load the profiles. Please refresh.",
        );
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  if (!ready) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-8">
        <LoadingRegion label="Loading author profiles">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="mt-5 h-80" />
        </LoadingRegion>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <Link href="/staff/blog" className="text-sm text-muted hover:text-ink">
        ← Guides
      </Link>
      <h1 className="mt-2 text-xl font-semibold text-ink">Author profiles</h1>
      <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">
        A byline that links to a real person, with real profiles elsewhere, does more for a reader
        who has been lied to before than any badge. It is also what search engines use to tell an
        authored article from an anonymous one.
      </p>

      {error ? (
        <div className="mt-5">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}

      {mine ? <ProfileForm profile={mine} isOwn onSaved={load} /> : null}

      {others.length ? (
        <section aria-labelledby="team-authors" className="mt-10">
          <h2 id="team-authors" className="font-display text-base font-bold text-ink">
            The rest of the team
          </h2>
          <ul className="mt-4 space-y-4">
            {others.map((profile) => (
              <li key={profile.id}>
                <ProfileForm profile={profile} isOwn={false} onSaved={load} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function ProfileForm({
  profile,
  isOwn,
  onSaved,
}: {
  profile: AuthorProfile;
  isOwn: boolean;
  onSaved: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(profile);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [open, setOpen] = useState(isOwn);

  const dirty = JSON.stringify(draft) !== JSON.stringify(profile);
  const prefix = `author-${profile.id}`;

  function update<K extends keyof AuthorProfile>(key: K, value: AuthorProfile[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setNotice("");
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const patch: Partial<AuthorProfile> = {
        display_name: draft.display_name,
        headline: draft.headline,
        bio: draft.bio,
        credentials: draft.credentials,
        avatar_alt: draft.avatar_alt,
        website: draft.website,
        linkedin_url: draft.linkedin_url,
        x_url: draft.x_url,
        is_public: draft.is_public,
        show_in_directory: draft.show_in_directory,
      };
      if (isOwn) await saveMyAuthorProfile(patch);
      else await saveAuthor(profile.id, patch);
      setNotice("Saved.");
      await onSaved();
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

  return (
    <section
      aria-labelledby={`${prefix}-heading`}
      className="mt-6 rounded-xl border border-line bg-surface p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id={`${prefix}-heading`} className="font-display text-base font-bold text-ink">
            {isOwn ? "Your profile" : draft.display_name}
          </h2>
          <p className="mt-1 text-xs text-subtle">
            {profile.user_email} · {profile.post_count}{" "}
            {profile.post_count === 1 ? "live article" : "live articles"}
            {profile.has_public_page ? (
              <>
                {" · "}
                {/* Inline in a run of text, so it carries an underline: colour
                    alone is not a distinguishing feature (WCAG 1.4.1). */}
                <Link
                  href={`/blog/author/${profile.slug}`}
                  className="text-accent underline underline-offset-2"
                >
                  page is live
                </Link>
              </>
            ) : profile.is_public ? (
              " · page appears once an article is published"
            ) : (
              " · no public page"
            )}
          </p>
        </div>
        {!isOwn ? (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="text-sm font-medium text-accent hover:underline"
          >
            {open ? "Close" : "Edit"}
          </button>
        ) : null}
      </div>

      {open ? (
        <>
          {error ? (
            <div className="mt-4">
              <Alert tone="error">{error}</Alert>
            </div>
          ) : null}
          {notice ? (
            <div className="mt-4">
              <Alert tone="success">{notice}</Alert>
            </div>
          ) : null}

          <div className="mt-5 space-y-5">
            <Field
              label="Byline"
              htmlFor={`${prefix}-name`}
              hint="How the name appears on articles."
            >
              <input
                id={`${prefix}-name`}
                value={draft.display_name}
                onChange={(event) => update("display_name", event.target.value)}
                maxLength={120}
                className={inputStyle}
              />
            </Field>

            <Field
              label="Headline"
              htmlFor={`${prefix}-headline`}
              hint='The line under the name — "Admissions lead".'
            >
              <input
                id={`${prefix}-headline`}
                value={draft.headline}
                onChange={(event) => update("headline", event.target.value)}
                maxLength={140}
                className={inputStyle}
              />
            </Field>

            <Field
              label="Bio"
              htmlFor={`${prefix}-bio`}
              hint="Markdown. Checked against the house style, like an article — a bio is published copy."
            >
              <textarea
                id={`${prefix}-bio`}
                value={draft.bio}
                onChange={(event) => update("bio", event.target.value)}
                rows={5}
                className={inputStyle}
              />
            </Field>

            <Field
              label="Credentials"
              htmlFor={`${prefix}-credentials`}
              hint="Only what can be evidenced. This is the most tempting field on the site to overstate, so it is scanned too."
            >
              <input
                id={`${prefix}-credentials`}
                value={draft.credentials}
                onChange={(event) => update("credentials", event.target.value)}
                maxLength={200}
                className={inputStyle}
              />
            </Field>

            {draft.avatar ? (
              <Field
                label="Photo description"
                htmlFor={`${prefix}-avatar-alt`}
                hint="Required when there is a photo. Upload or change the photo in the Django admin."
              >
                <input
                  id={`${prefix}-avatar-alt`}
                  value={draft.avatar_alt}
                  onChange={(event) => update("avatar_alt", event.target.value)}
                  maxLength={160}
                  className={inputStyle}
                />
              </Field>
            ) : (
              <p className="text-xs text-subtle">
                No photo set. Add one in the Django admin if you want it on the byline.
              </p>
            )}

            <fieldset className="space-y-4">
              <legend className="text-sm font-medium text-ink">Elsewhere on the web</legend>
              <p className="text-xs leading-relaxed text-subtle">
                These become <code className="font-mono">sameAs</code> links in the page&rsquo;s
                structured data, which is how a search engine ties this byline to a real identity.
                It is the single most useful thing on this form.
              </p>
              <Field label="Website" htmlFor={`${prefix}-website`}>
                <input
                  id={`${prefix}-website`}
                  type="url"
                  value={draft.website}
                  onChange={(event) => update("website", event.target.value)}
                  className={inputStyle}
                />
              </Field>
              <Field label="LinkedIn" htmlFor={`${prefix}-linkedin`}>
                <input
                  id={`${prefix}-linkedin`}
                  type="url"
                  value={draft.linkedin_url}
                  onChange={(event) => update("linkedin_url", event.target.value)}
                  className={inputStyle}
                />
              </Field>
              <Field label="X / Twitter" htmlFor={`${prefix}-x`}>
                <input
                  id={`${prefix}-x`}
                  type="url"
                  value={draft.x_url}
                  onChange={(event) => update("x_url", event.target.value)}
                  className={inputStyle}
                />
              </Field>
            </fieldset>

            <div className="flex items-start gap-3">
              <input
                id={`${prefix}-public`}
                type="checkbox"
                checked={draft.is_public}
                onChange={(event) => update("is_public", event.target.checked)}
                className="mt-1"
              />
              <label htmlFor={`${prefix}-public`} className="text-sm text-ink">
                Publish an author page
                <span className="mt-0.5 block text-xs leading-relaxed text-subtle">
                  {SITE_URL}/blog/author/{draft.slug || "…"} — needs a bio, and only appears once
                  there is at least one live article.
                </span>
              </label>
            </div>

            <div className="flex items-start gap-3">
              <input
                id={`${prefix}-directory`}
                type="checkbox"
                checked={draft.show_in_directory}
                onChange={(event) => update("show_in_directory", event.target.checked)}
                className="mt-1"
              />
              <label htmlFor={`${prefix}-directory`} className="text-sm text-ink">
                List in the author directory
              </label>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button type="button" onClick={save} disabled={saving || !dirty}>
              {saving ? "Saving…" : "Save profile"}
            </Button>
            <span aria-live="polite" className="text-xs text-subtle">
              {dirty ? "Unsaved changes" : "All changes saved"}
            </span>
          </div>
        </>
      ) : null}
    </section>
  );
}
