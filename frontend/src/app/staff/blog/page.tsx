"use client";

/**
 * Staff: the guides list.
 *
 * Ordered by last edited, not by publish date — the thing a writer wants on
 * opening this page is the draft they were in the middle of, which is almost
 * never the most recently published post.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, Button, LoadingRegion, ScrollableX, Skeleton } from "@/components/ui";
import {
  type AdminPost,
  type PostStatus,
  STATUS_LABELS,
  createPost,
  listAdminPosts,
} from "@/lib/blog-admin";
import { commentSummary } from "@/lib/blog-settings";

const FILTERS: { value: string; label: string }[] = [
  { value: "", label: "Everything" },
  { value: "draft", label: "Drafts" },
  { value: "in_review", label: "In review" },
  { value: "scheduled", label: "Scheduled" },
  { value: "published", label: "Published" },
  { value: "archived", label: "Off the site" },
];

const STATUS_STYLES: Record<PostStatus, string> = {
  draft: "border-line text-muted",
  in_review: "border-info-line bg-info-bg text-info",
  scheduled: "border-warning-line bg-warning-bg text-warning",
  published: "border-success-line bg-success-bg text-success",
  archived: "border-line text-subtle",
};

export default function StaffBlogList() {
  const router = useRouter();
  const [posts, setPosts] = useState<AdminPost[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [term, setTerm] = useState("");
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [pendingComments, setPendingComments] = useState(0);

  // The badge is the reason anyone opens the moderation queue, so it is worth a
  // second request. A failure just leaves the badge off.
  useEffect(() => {
    commentSummary()
      .then((counts) => setPendingComments(counts.pending))
      .catch(() => setPendingComments(0));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const page = await listAdminPosts({
          status: status || undefined,
          search: term.trim() || undefined,
        });
        if (cancelled) return;
        setPosts(page.results);
        setTotal(page.count);
        setError("");
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? "Your account does not have permission to write guides."
            : "We couldn't load the guides. Please refresh.",
        );
      } finally {
        if (!cancelled) setReady(true);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [status, term]);

  async function startPost(event: React.FormEvent) {
    event.preventDefault();
    if (newTitle.trim().length < 4) return;
    setCreating(true);
    setError("");
    try {
      const post = await createPost({ title: newTitle.trim() });
      router.push(`/staff/blog/${post.slug}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't start that draft. Try again.");
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="text-xl font-semibold text-ink">Guides</h1>
        <nav aria-label="Blog administration" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          <Link href="/staff/blog/comments" className="font-medium text-accent hover:underline">
            Comments
            {pendingComments ? (
              <span className="ml-1.5 rounded-full border border-warning-line bg-warning-bg px-1.5 py-0.5 text-xs text-ink">
                {pendingComments}
              </span>
            ) : null}
          </Link>
          <Link href="/staff/blog/authors" className="font-medium text-accent hover:underline">
            Authors
          </Link>
          <Link href="/staff/blog/settings" className="font-medium text-accent hover:underline">
            Settings
          </Link>
        </nav>
      </div>
      <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">
        Articles on the public site. A draft is invisible until someone with publishing permission
        puts it live, and the publish step checks it against the house style first.
      </p>

      {error ? (
        <div className="mt-5">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}

      <form onSubmit={startPost} className="mt-6 flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1">
          <label htmlFor="new-post-title" className="block text-sm font-medium text-ink">
            Start a new guide
          </label>
          <input
            id="new-post-title"
            value={newTitle}
            onChange={(event) => setNewTitle(event.target.value)}
            placeholder="Working title — you can change it later"
            className="mt-1.5 w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-subtle"
          />
        </div>
        <Button type="submit" disabled={creating || newTitle.trim().length < 4}>
          {creating ? "Creating…" : "Create draft"}
        </Button>
      </form>

      <div className="mt-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <span id="status-filter-label" className="block text-sm font-medium text-ink">
            Show
          </span>
          <div
            role="group"
            aria-labelledby="status-filter-label"
            className="mt-1.5 flex flex-wrap gap-2"
          >
            {FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                aria-pressed={status === filter.value}
                onClick={() => setStatus(filter.value)}
                className={
                  status === filter.value
                    ? "rounded-full border border-accent bg-accent px-3.5 py-1.5 text-sm font-medium text-on-accent"
                    : "rounded-full border border-line px-3.5 py-1.5 text-sm text-muted transition hover:border-accent hover:text-ink"
                }
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-w-56">
          <label htmlFor="post-search" className="sr-only">
            Search guides by title or body
          </label>
          <input
            id="post-search"
            type="search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Search titles and bodies…"
            className="w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-subtle"
          />
        </div>
      </div>

      <p aria-live="polite" className="mt-4 text-sm text-muted">
        {!ready ? "Loading…" : `${total} guide${total === 1 ? "" : "s"}`}
      </p>

      {!ready ? (
        <LoadingRegion label="Loading guides">
          <div className="mt-4 space-y-3">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        </LoadingRegion>
      ) : posts.length === 0 ? (
        <p className="mt-6 rounded-xl border border-line px-6 py-10 text-center text-sm text-muted">
          Nothing here yet.
        </p>
      ) : (
        <ScrollableX label="Guides">
          <table className="mt-4 w-full min-w-3xl border-collapse text-sm">
            <caption className="sr-only">
              Guides, most recently edited first, with status and AI provenance
            </caption>
            <thead>
              <tr className="border-b border-line text-left text-xs tracking-wide text-subtle uppercase">
                <th scope="col" className="py-2.5 pr-4 font-semibold">
                  Title
                </th>
                <th scope="col" className="py-2.5 pr-4 font-semibold">
                  Status
                </th>
                <th scope="col" className="py-2.5 pr-4 font-semibold">
                  Author
                </th>
                <th scope="col" className="py-2.5 pr-4 font-semibold">
                  AI
                </th>
                <th scope="col" className="py-2.5 pr-4 font-semibold">
                  Edited
                </th>
                <th scope="col" className="py-2.5 font-semibold">
                  Views
                </th>
              </tr>
            </thead>
            <tbody>
              {posts.map((post) => (
                <tr key={post.id} className="border-b border-line align-top">
                  <th scope="row" className="py-3 pr-4 font-normal">
                    <Link
                      href={`/staff/blog/${post.slug}`}
                      className="font-medium text-ink hover:underline"
                    >
                      {post.title}
                    </Link>
                    <span className="mt-0.5 block font-mono text-xs text-subtle">/{post.slug}</span>
                  </th>
                  <td className="py-3 pr-4">
                    <span
                      className={`inline-block rounded-full border px-2.5 py-0.5 text-xs ${STATUS_STYLES[post.status]}`}
                    >
                      {STATUS_LABELS[post.status]}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-muted">{post.author_name || "—"}</td>
                  <td className="py-3 pr-4 text-muted">
                    {post.ai_involvement === "none" ? "—" : post.ai_involvement}
                  </td>
                  <td className="py-3 pr-4 text-muted">
                    {new Date(post.updated_at).toLocaleDateString("en-NG", {
                      day: "numeric",
                      month: "short",
                    })}
                  </td>
                  <td className="py-3 text-muted tabular-nums">{post.view_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableX>
      )}
    </div>
  );
}
