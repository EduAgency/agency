"use client";

/**
 * Staff: the comment moderation queue.
 *
 * Built as a queue rather than a feed: pending first, oldest first, with enough
 * context in each row to decide without opening anything. A moderator clearing a
 * morning's backlog should be able to work down the page with the keyboard and
 * never lose their place.
 *
 * Two things the design is deliberate about:
 *
 * **Why a comment was flagged is always visible.** "3 links (limit 1)" tells a
 * moderator in one glance that this is probably spam; an unexplained "flagged"
 * badge teaches them to approve everything.
 *
 * **Marking spam is not deleting.** Nothing here destroys a reader's words. Spam
 * and rejected are states, and both are reachable again from the filter.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, Button, LoadingRegion, Skeleton } from "@/components/ui";
import {
  type AdminComment,
  COMMENT_STATUS_LABELS,
  type CommentStatus,
  type CommentSummary,
  commentSummary,
  listComments,
  moderateComments,
  pinComment,
  replyToComment,
} from "@/lib/blog-settings";

const FILTERS: { value: string; label: string; key?: keyof CommentSummary }[] = [
  { value: "pending", label: "Waiting", key: "pending" },
  { value: "approved", label: "Published", key: "approved" },
  { value: "spam", label: "Spam", key: "spam" },
  { value: "rejected", label: "Rejected", key: "rejected" },
  { value: "all", label: "Everything" },
];

export default function CommentQueue() {
  const [status, setStatus] = useState("pending");
  const [term, setTerm] = useState("");
  const [comments, setComments] = useState<AdminComment[]>([]);
  const [summary, setSummary] = useState<CommentSummary | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    const [page, counts] = await Promise.all([
      listComments({ status, search: term.trim() || undefined }),
      commentSummary().catch(() => null),
    ]);
    setComments(page.results);
    if (counts) setSummary(counts);
    setSelected(new Set());
  }, [status, term]);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        await load();
        if (!cancelled) setError("");
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? "Your account cannot moderate comments."
            : "We couldn't load the queue. Please refresh.",
        );
      } finally {
        if (!cancelled) setReady(true);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [load]);

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function moderate(ids: string[], next: CommentStatus) {
    if (ids.length === 0) return;
    setBusy(true);
    setError("");
    try {
      const result = await moderateComments(ids, next);
      setNotice(
        `${result.changed} ${result.changed === 1 ? "comment" : "comments"} → ${COMMENT_STATUS_LABELS[next].toLowerCase()}.`,
      );
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "You can read the queue but not act on it. Ask an editor."
          : "That did not go through. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(id: string) {
    if (replyBody.trim().length < 3) return;
    setBusy(true);
    try {
      await replyToComment(id, replyBody.trim());
      setReplyBody("");
      setReplyTo(null);
      setNotice("Replied. Your answer is live on the article.");
      await load();
    } catch {
      setError("The reply did not send. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function togglePin(id: string) {
    try {
      await pinComment(id);
      await load();
    } catch {
      setError("Could not pin that.");
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <Link href="/staff/blog" className="text-sm text-muted hover:text-ink">
        ← Guides
      </Link>
      <h1 className="mt-2 text-xl font-semibold text-ink">Comments</h1>
      <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">
        The questions readers leave here are the next twelve articles. Nothing is deleted — spam and
        rejected are states you can come back to.
      </p>

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

      <div className="mt-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <span id="queue-filter-label" className="block text-sm font-medium text-ink">
            Show
          </span>
          <div
            role="group"
            aria-labelledby="queue-filter-label"
            className="mt-1.5 flex flex-wrap gap-2"
          >
            {FILTERS.map((filter) => {
              const count = filter.key && summary ? summary[filter.key] : null;
              return (
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
                  {count !== null ? (
                    <span
                      className={
                        status === filter.value ? "ml-1.5 opacity-80" : "ml-1.5 text-subtle"
                      }
                    >
                      {count}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>

        <div className="min-w-56">
          <label htmlFor="comment-search" className="sr-only">
            Search comments by text, name or email
          </label>
          <input
            id="comment-search"
            type="search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Search comments…"
            className="w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-subtle"
          />
        </div>
      </div>

      {/* Bulk bar. Only rendered when something is selected, so it never sits
          there as a row of dead buttons. */}
      {selected.size > 0 ? (
        <div className="mt-5 flex flex-wrap items-center gap-3 rounded-lg border border-accent bg-sunken px-4 py-3">
          <span className="text-sm font-medium text-ink">{selected.size} selected</span>
          <Button type="button" onClick={() => moderate([...selected], "approved")} disabled={busy}>
            Approve
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => moderate([...selected], "spam")}
            disabled={busy}
          >
            Spam
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => moderate([...selected], "rejected")}
            disabled={busy}
          >
            Reject
          </Button>
          <button
            type="button"
            onClick={() => setSelected(new Set())}
            className="text-sm text-muted hover:text-ink"
          >
            Clear
          </button>
        </div>
      ) : null}

      <p aria-live="polite" className="mt-5 text-sm text-muted">
        {!ready
          ? "Loading…"
          : `${comments.length} ${comments.length === 1 ? "comment" : "comments"}`}
      </p>

      {!ready ? (
        <LoadingRegion label="Loading comments">
          <div className="mt-4 space-y-3">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        </LoadingRegion>
      ) : comments.length === 0 ? (
        <p className="mt-6 rounded-xl border border-line px-6 py-12 text-center text-sm text-muted">
          {status === "pending" ? "Nothing waiting. Queue is clear." : "Nothing here."}
        </p>
      ) : (
        <ul className="mt-4 space-y-4">
          {comments.map((comment) => (
            <li key={comment.id} className="rounded-xl border border-line bg-surface p-4">
              <div className="flex flex-wrap items-start gap-3">
                <input
                  id={`select-${comment.id}`}
                  type="checkbox"
                  checked={selected.has(comment.id)}
                  onChange={() => toggle(comment.id)}
                  className="mt-1"
                />
                <label htmlFor={`select-${comment.id}`} className="sr-only">
                  Select the comment by {comment.author_name}
                </label>

                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
                    <span className="font-semibold text-ink">{comment.author_name}</span>
                    {comment.email ? (
                      <span className="font-mono text-xs text-subtle">{comment.email}</span>
                    ) : null}
                    {comment.is_from_staff ? (
                      <span className="rounded-full border border-accent px-2 py-0.5 text-xs text-accent">
                        Us
                      </span>
                    ) : null}
                    <span className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">
                      {COMMENT_STATUS_LABELS[comment.status]}
                    </span>
                    {comment.is_pinned ? (
                      <span className="rounded-full border border-line px-2 py-0.5 text-xs text-subtle">
                        Pinned
                      </span>
                    ) : null}
                  </p>

                  {comment.flagged_reason ? (
                    <p className="mt-2 rounded-lg border border-warning-line bg-warning-bg px-3 py-2 text-xs text-ink">
                      Flagged: {comment.flagged_reason}
                    </p>
                  ) : null}

                  {comment.parent_body ? (
                    <p className="mt-2 border-l-2 border-line pl-3 text-xs text-subtle italic">
                      In reply to: {comment.parent_body}
                    </p>
                  ) : null}

                  {/* Plain text, escaped by React. */}
                  <p className="mt-2 text-sm leading-relaxed whitespace-pre-line text-ink">
                    {comment.body}
                  </p>

                  <p className="mt-2 flex flex-wrap items-center gap-x-3 text-xs text-subtle">
                    <Link
                      href={`/blog/${comment.post_slug}`}
                      className="text-accent hover:underline"
                    >
                      {comment.post_title}
                    </Link>
                    <span>{new Date(comment.created_at).toLocaleString("en-NG")}</span>
                    {comment.moderated_by_name ? (
                      <span>Last touched by {comment.moderated_by_name}</span>
                    ) : null}
                  </p>

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {comment.status !== "approved" ? (
                      <Button
                        type="button"
                        onClick={() => moderate([comment.id], "approved")}
                        disabled={busy}
                      >
                        Approve
                      </Button>
                    ) : null}
                    {comment.status !== "spam" ? (
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => moderate([comment.id], "spam")}
                        disabled={busy}
                      >
                        Spam
                      </Button>
                    ) : null}
                    {comment.status !== "rejected" ? (
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => moderate([comment.id], "rejected")}
                        disabled={busy}
                      >
                        Reject
                      </Button>
                    ) : null}
                    {comment.status === "approved" ? (
                      <button
                        type="button"
                        onClick={() => togglePin(comment.id)}
                        className="text-sm font-medium text-accent hover:underline"
                      >
                        {comment.is_pinned ? "Unpin" : "Pin to the top"}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => {
                        setReplyTo(replyTo === comment.id ? null : comment.id);
                        setReplyBody("");
                      }}
                      aria-expanded={replyTo === comment.id}
                      className="text-sm font-medium text-accent hover:underline"
                    >
                      {replyTo === comment.id ? "Cancel" : "Reply as Nasuru"}
                    </button>
                  </div>

                  {replyTo === comment.id ? (
                    <div className="mt-3 border-l-2 border-accent pl-3">
                      <label
                        htmlFor={`reply-${comment.id}`}
                        className="block text-xs font-semibold text-muted"
                      >
                        Your answer — published immediately, under our name
                      </label>
                      <textarea
                        id={`reply-${comment.id}`}
                        value={replyBody}
                        onChange={(event) => setReplyBody(event.target.value)}
                        rows={3}
                        className="mt-1.5 w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink"
                      />
                      <div className="mt-2">
                        <Button
                          type="button"
                          onClick={() => sendReply(comment.id)}
                          disabled={busy || replyBody.trim().length < 3}
                        >
                          Post reply
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
