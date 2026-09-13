"use client";

/**
 * Comments on an article.
 *
 * The existing thread is rendered on the server and passed in — it is indexable
 * text, and a page that answers a question in the body and three follow-ups
 * underneath ranks for all four. Only the form is a client component.
 *
 * Two things here are deliberate and easy to get wrong later:
 *
 * **The body is rendered as text, never as HTML.** React escapes it, and the
 * backend stores it as plain text. A comment box that accepts markup is a
 * persistent-XSS surface with no upside.
 *
 * **The spam defences are invisible to a real reader.** A honeypot input that
 * screen readers skip, and a timestamp taken when the form mounts. No CAPTCHA:
 * it is an accessibility problem, it ships a Nigerian reader's data to a third
 * party, and it stops fewer bots than the honeypot does.
 */

import { useEffect, useRef, useState } from "react";
import { Button, Field } from "@/components/ui";
import { type BlogComment, submitComment } from "@/lib/blog";

function formatWhen(iso: string): string {
  return new Intl.DateTimeFormat("en-NG", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Africa/Lagos",
  }).format(new Date(iso));
}

function CommentBody({ comment }: { comment: BlogComment }) {
  return (
    <article className="min-w-0">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <span className="font-semibold text-ink">{comment.author_name}</span>
        {comment.is_from_staff ? (
          <span className="rounded-full border border-accent px-2 py-0.5 text-xs font-medium text-accent">
            Nasuru
          </span>
        ) : null}
        {comment.is_pinned ? (
          <span className="rounded-full border border-line px-2 py-0.5 text-xs text-subtle">
            Pinned
          </span>
        ) : null}
        <time dateTime={comment.created_at} className="text-xs text-subtle">
          {formatWhen(comment.created_at)}
        </time>
      </p>
      {/* Plain text. Escaped by React, stored unparsed by the API. */}
      <p className="mt-1.5 text-sm leading-relaxed whitespace-pre-line text-muted">
        {comment.body}
      </p>
    </article>
  );
}

interface Props {
  slug: string;
  comments: BlogComment[];
  open: boolean;
  requireEmail: boolean;
  allowReplies: boolean;
  commentsEnabled: boolean;
}

export function CommentThread({
  slug,
  comments,
  open,
  requireEmail,
  allowReplies,
  commentsEnabled,
}: Props) {
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [added, setAdded] = useState<BlogComment[]>([]);
  const [notice, setNotice] = useState("");

  if (!commentsEnabled) return null;

  const total = comments.length + added.length;

  return (
    <section aria-labelledby="comments" className="mt-14 border-t border-line pt-10">
      <h2 id="comments" className="font-display text-2xl font-bold tracking-tight text-ink">
        {total === 0 ? "Ask us something" : `Questions and answers (${total})`}
      </h2>
      <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
        {open
          ? "Ask anything about this. We answer here so the next person reading finds the answer too."
          : "Comments are closed on this guide, but you can still reach us directly."}
      </p>

      {total > 0 ? (
        <ul className="mt-8 space-y-8">
          {[...comments, ...added].map((comment) => (
            <li key={comment.id} className="border-t border-line pt-5 first:border-t-0 first:pt-0">
              <CommentBody comment={comment} />

              {comment.replies.length ? (
                <ul className="mt-4 space-y-4 border-l-2 border-line pl-4">
                  {comment.replies.map((reply) => (
                    <li key={reply.id}>
                      <CommentBody comment={reply} />
                    </li>
                  ))}
                </ul>
              ) : null}

              {open && allowReplies ? (
                <p className="mt-3">
                  <button
                    type="button"
                    onClick={() => setReplyTo(replyTo === comment.id ? null : comment.id)}
                    aria-expanded={replyTo === comment.id}
                    className="text-sm font-medium text-accent hover:underline"
                  >
                    {replyTo === comment.id ? "Cancel reply" : "Reply"}
                  </button>
                </p>
              ) : null}

              {replyTo === comment.id ? (
                <div className="mt-4 border-l-2 border-accent pl-4">
                  <CommentForm
                    slug={slug}
                    parent={comment.id}
                    requireEmail={requireEmail}
                    onDone={(message, posted) => {
                      setNotice(message);
                      setReplyTo(null);
                      if (posted) setAdded((rows) => [...rows, posted]);
                    }}
                  />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {notice ? (
        <p
          role="status"
          className="mt-6 rounded-lg border border-success-line bg-success-bg px-4 py-3 text-sm text-ink"
        >
          {notice}
        </p>
      ) : null}

      {open ? (
        <div className="mt-10 rounded-xl border border-line bg-sunken p-5 sm:p-6">
          <h3 className="font-display text-lg font-bold text-ink">Ask a question</h3>
          <CommentForm
            slug={slug}
            parent={null}
            requireEmail={requireEmail}
            onDone={(message, posted) => {
              setNotice(message);
              if (posted) setAdded((rows) => [...rows, posted]);
            }}
          />
        </div>
      ) : null}
    </section>
  );
}

function CommentForm({
  slug,
  parent,
  requireEmail,
  onDone,
}: {
  slug: string;
  parent: string | null;
  requireEmail: boolean;
  onDone: (message: string, posted: BlogComment | null) => void;
}) {
  const [body, setBody] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Set in the effect below rather than at render: reading the clock during
  // render is impure, and 0 is a safe start — it reads as "open for a long
  // time", which fails open rather than flagging a real reader as a bot.
  const mountedAt = useRef<number>(0);
  const idPrefix = parent ? `reply-${parent}` : "comment";

  // Also resets when a reply box is opened fresh, so a reply written after ten
  // minutes of reading is not judged on the page's original load time.
  useEffect(() => {
    mountedAt.current = Date.now();
  }, [parent]);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (body.trim().length < 5) {
      setError("Write a little more than that.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await submitComment(slug, {
        body: body.trim(),
        name: name.trim(),
        email: email.trim(),
        parent,
        honeypot,
        seconds_on_page: (Date.now() - mountedAt.current) / 1000,
      });
      setBody("");
      setName("");
      setEmail("");
      onDone(result.detail, result.comment);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not go through. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={send} className="mt-4 space-y-4">
      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-danger-line bg-danger-bg px-3 py-2.5 text-sm text-ink"
        >
          {error}
        </p>
      ) : null}

      <Field label="Your question" htmlFor={`${idPrefix}-body`}>
        <textarea
          id={`${idPrefix}-body`}
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={4}
          maxLength={4000}
          required
          className="w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-subtle"
          placeholder="What is not clear?"
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Your name" htmlFor={`${idPrefix}-name`}>
          <input
            id={`${idPrefix}-name`}
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            autoComplete="name"
            className="w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink"
          />
        </Field>
        <Field
          label={requireEmail ? "Email" : "Email (optional)"}
          htmlFor={`${idPrefix}-email`}
          hint="Never shown on the page. It is how our answer reaches you."
        >
          <input
            id={`${idPrefix}-email`}
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required={requireEmail}
            autoComplete="email"
            className="w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink"
          />
        </Field>
      </div>

      {/*
        The honeypot. Hidden from sight and from assistive technology, and not a
        `display: none` input — some bots skip those. `aria-hidden` plus
        `tabIndex={-1}` keeps it out of the keyboard order and the accessibility
        tree, so no real user can reach it.
      */}
      <div aria-hidden="true" className="absolute h-0 w-0 overflow-hidden">
        <label htmlFor={`${idPrefix}-url`}>Website</label>
        <input
          id={`${idPrefix}-url`}
          name="url"
          tabIndex={-1}
          autoComplete="off"
          value={honeypot}
          onChange={(event) => setHoneypot(event.target.value)}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy}>
          {busy ? "Sending…" : parent ? "Post reply" : "Post question"}
        </Button>
        <span className="text-xs text-subtle">
          We read everything. Answers appear here once checked.
        </span>
      </div>
    </form>
  );
}
