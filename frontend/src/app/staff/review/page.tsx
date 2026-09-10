"use client";

/**
 * The review queue.
 *
 * This is the screen the agency lives in, and until now it was a Django admin
 * changelist (docs/enterprise-readiness.md §D3). Staff throughput is what caps
 * how many students the agency can serve, so this page is built around one
 * question — "is this document acceptable?" — and removes everything that is
 * not part of answering it.
 *
 * Three decisions worth naming:
 *
 *   1. The document is shown beside the requirement it has to satisfy. A
 *      reviewer should never have to remember what the school asked for while
 *      looking at a passport scan.
 *   2. Rejection reasons are canned but editable. Consistency is the point: a
 *      student told "the photo is blurred, we cannot read the expiry date" can
 *      act on it; one told "rejected" opens a support ticket.
 *   3. It is keyboard-first. J/K to move, V to verify, R to reject — the queue
 *      is repetitive work, and reaching for a mouse on every item is the
 *      difference between forty decisions an hour and a hundred.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";
import { ApiError } from "@/lib/api";
import { useAnnouncer } from "@/components/ui/Announcer";
import { Alert, Button, LoadingRegion, Skeleton, StatusBadge } from "@/components/ui";
import {
  REJECTION_REASONS,
  listReviewQueue,
  reviewItem,
  type ReviewDecision,
  type ReviewItem,
} from "@/lib/staff";

function ReviewQueue() {
  const preselected = useSearchParams().get("item");
  const { announce, toast } = useAnnouncer();

  const [items, setItems] = useState<ReviewItem[]>([]);
  const [index, setIndex] = useState(0);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const reasonRef = useRef<HTMLTextAreaElement>(null);

  const current = items[index];

  /**
   * Fetch inside the effect, behind an async IIFE, so every state update
   * happens after an await rather than synchronously during the effect — the
   * same shape `SessionProvider` uses.
   */
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const page = await listReviewQueue({});
        if (cancelled) return;
        setItems(page.results);
        // Resolve a deep link from the command palette here, where the data
        // arrives, rather than in an effect that syncs one state to another.
        if (preselected) {
          const found = page.results.findIndex((item) => item.id === preselected);
          if (found >= 0) setIndex(found);
        }
        setError("");
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? "Your account does not have document review permission."
            : "We couldn't load the review queue. Please refresh.",
        );
      } finally {
        if (!cancelled) setReady(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [preselected, reloadKey]);

  const move = useCallback(
    (delta: number) => {
      setIndex((current) => Math.max(0, Math.min(items.length - 1, current + delta)));
      setRejecting(false);
      setReason("");
    },
    [items.length],
  );

  const decide = useCallback(
    async (decision: ReviewDecision, why = "") => {
      if (!current || busy) return;
      setBusy(true);
      try {
        await reviewItem(current.id, decision, why);
        toast(`${current.label} — ${decision.replace("_", " ")}`, "success");
        // Drop the decided item and stay at the same position, so the next one
        // slides under the cursor. Re-fetching would lose the reviewer's place.
        setItems((list) => list.filter((item) => item.id !== current.id));
        setIndex((position) => Math.max(0, Math.min(position, items.length - 2)));
        setRejecting(false);
        setReason("");
      } catch (err) {
        toast(
          err instanceof ApiError ? err.message : "That decision didn't save. Try again.",
          "error",
        );
      } finally {
        setBusy(false);
      }
    },
    [current, busy, items.length, toast],
  );

  /** J/K/V/R, ignored while the reviewer is typing a reason. */
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      const typing =
        target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable;
      if (typing || event.metaKey || event.ctrlKey || event.altKey) return;

      switch (event.key.toLowerCase()) {
        case "j":
          event.preventDefault();
          move(1);
          break;
        case "k":
          event.preventDefault();
          move(-1);
          break;
        case "v":
          event.preventDefault();
          void decide("verified");
          break;
        case "r":
          event.preventDefault();
          setRejecting(true);
          requestAnimationFrame(() => reasonRef.current?.focus());
          break;
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [move, decide]);

  useEffect(() => {
    if (current) announce(`${current.label}. Item ${index + 1} of ${items.length}.`);
  }, [current, index, items.length, announce]);

  if (!ready) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8">
        <LoadingRegion label="Loading the review queue">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="mt-6 h-96 w-full" />
        </LoadingRegion>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-12">
        <Alert>{error}</Alert>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-20 text-center">
        <h1 className="text-2xl font-semibold text-ink">The queue is empty</h1>
        <p className="mt-2 text-sm text-muted">
          Nothing is waiting for a decision. New uploads appear here automatically.
        </p>
        <button
          type="button"
          onClick={() => setReloadKey((key) => key + 1)}
          className="mt-6 text-sm text-muted underline underline-offset-4 hover:text-ink"
        >
          Check again
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-xl font-semibold text-ink">Review queue</h1>
        <p className="text-sm text-muted tabular-nums">
          {index + 1} of {items.length} waiting · oldest first
        </p>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <ReviewPane
          item={current}
          busy={busy}
          rejecting={rejecting}
          reason={reason}
          reasonRef={reasonRef}
          onReason={setReason}
          onStartReject={() => {
            setRejecting(true);
            requestAnimationFrame(() => reasonRef.current?.focus());
          }}
          onCancelReject={() => {
            setRejecting(false);
            setReason("");
          }}
          onDecide={decide}
        />

        <QueueList items={items} index={index} onPick={setIndex} />
      </div>
    </div>
  );
}

function ReviewPane({
  item,
  busy,
  rejecting,
  reason,
  reasonRef,
  onReason,
  onStartReject,
  onCancelReject,
  onDecide,
}: {
  item: ReviewItem;
  busy: boolean;
  rejecting: boolean;
  reason: string;
  reasonRef: React.RefObject<HTMLTextAreaElement | null>;
  onReason: (value: string) => void;
  onStartReject: () => void;
  onCancelReject: () => void;
  onDecide: (decision: ReviewDecision, reason?: string) => void;
}) {
  const upload = item.document?.current ?? null;
  const isImage = upload?.content_type?.startsWith("image/");
  const isPdf = upload?.content_type === "application/pdf";

  return (
    <section aria-label="Document under review" className="rounded-xl border border-line">
      <header className="border-b border-line p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-ink">{item.label}</h2>
            <p className="mt-0.5 text-sm text-muted">
              {item.student_name ?? item.student_email ?? "Student"}
              {item.school_name && ` · ${item.school_name}`}
            </p>
          </div>
          <StatusBadge status={item.status} label={item.status_display ?? item.status} />
        </div>

        {/* The requirement sits beside the document, not a click away — the
            whole question is whether this file satisfies this rule. */}
        {(item.description || item.help_text) && (
          <div className="mt-4 rounded-lg bg-sunken p-3">
            <p className="text-xs font-medium tracking-wide text-subtle uppercase">
              What this must show
            </p>
            <p className="mt-1 text-sm text-muted">{item.description || item.help_text}</p>
          </div>
        )}
      </header>

      <div className="border-b border-line bg-sunken p-4">
        {!upload ? (
          <p className="py-16 text-center text-sm text-muted">
            Nothing has been uploaded against this item yet.
          </p>
        ) : isImage && upload.download_url ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={upload.download_url}
            alt={`${item.label} uploaded by ${item.student_name ?? "the student"}`}
            className="mx-auto max-h-[28rem] w-auto rounded-lg bg-surface object-contain"
          />
        ) : isPdf && upload.download_url ? (
          <object
            data={upload.download_url}
            type="application/pdf"
            className="h-[28rem] w-full rounded-lg"
            aria-label={`${item.label}, PDF`}
          >
            <p className="p-6 text-center text-sm text-muted">
              Your browser cannot display this PDF inline.{" "}
              <a href={upload.download_url} className="underline">
                Open it in a new tab
              </a>
              .
            </p>
          </object>
        ) : (
          <p className="py-16 text-center text-sm text-muted">
            {upload.original_filename} cannot be previewed.{" "}
            {upload.download_url && (
              <a href={upload.download_url} className="underline underline-offset-2">
                Download it
              </a>
            )}
          </p>
        )}

        {upload && (
          <p className="mt-3 text-center text-xs text-subtle">
            {upload.original_filename} · v{upload.version} ·{" "}
            {new Date(upload.created_at).toLocaleString("en-NG")}
          </p>
        )}
      </div>

      <div className="p-5">
        {rejecting ? (
          <div className="space-y-3">
            <div>
              <p className="text-sm font-medium text-ink">Why is it being rejected?</p>
              <p className="mt-0.5 text-xs text-subtle">
                The student sees this word for word. Pick a starting point and edit it.
              </p>
            </div>

            <ul className="flex flex-wrap gap-2">
              {REJECTION_REASONS.map((canned) => (
                <li key={canned}>
                  <button
                    type="button"
                    onClick={() => {
                      onReason(canned);
                      reasonRef.current?.focus();
                    }}
                    className="rounded-full border border-field-line px-3 py-1 text-left text-xs text-muted hover:border-line-strong hover:text-ink"
                  >
                    {canned.length > 46 ? `${canned.slice(0, 46)}…` : canned}
                  </button>
                </li>
              ))}
            </ul>

            <label htmlFor="rejection-reason" className="sr-only">
              Rejection reason
            </label>
            <textarea
              id="rejection-reason"
              ref={reasonRef}
              rows={3}
              value={reason}
              onChange={(event) => onReason(event.target.value)}
              className="w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink"
            />

            <div className="flex flex-wrap gap-3">
              <Button
                variant="danger"
                disabled={busy || reason.trim().length === 0}
                onClick={() => onDecide("rejected", reason.trim())}
              >
                {busy ? "Saving…" : "Send rejection"}
              </Button>
              <Button variant="secondary" onClick={onCancelReject} disabled={busy}>
                Cancel
              </Button>
            </div>
            {reason.trim().length === 0 && (
              <p className="text-xs text-subtle">
                A reason is required — the server refuses a rejection without one.
              </p>
            )}
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => onDecide("verified")} disabled={busy || !upload}>
              Verify <kbd className="ml-1.5 font-mono text-xs opacity-70">V</kbd>
            </Button>
            <Button variant="secondary" onClick={onStartReject} disabled={busy || !upload}>
              Reject <kbd className="ml-1.5 font-mono text-xs opacity-70">R</kbd>
            </Button>
            <Button variant="secondary" onClick={() => onDecide("waived")} disabled={busy}>
              Waive
            </Button>
            <p className="ml-auto text-xs text-subtle">
              <kbd className="font-mono">J</kbd> next · <kbd className="font-mono">K</kbd> previous
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function QueueList({
  items,
  index,
  onPick,
}: {
  items: ReviewItem[];
  index: number;
  onPick: (index: number) => void;
}) {
  return (
    <section aria-label="Waiting for review" className="rounded-xl border border-line">
      <h2 className="border-b border-line px-4 py-3 text-sm font-medium text-ink">
        Waiting ({items.length})
      </h2>
      <ul className="max-h-[32rem] divide-y divide-line overflow-y-auto">
        {items.map((item, position) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onPick(position)}
              aria-current={position === index ? "true" : undefined}
              className={`w-full px-4 py-3 text-left ${
                position === index ? "bg-sunken" : "hover:bg-sunken"
              }`}
            >
              <p className="truncate text-sm font-medium text-ink">{item.label}</p>
              <p className="truncate text-xs text-muted">
                {item.student_name ?? item.student_email ?? "Student"}
              </p>
            </button>
          </li>
        ))}
      </ul>
      <p className="border-t border-line px-4 py-2 text-xs text-subtle">
        <Link href="/staff/students" className="underline underline-offset-2">
          Browse all students
        </Link>
      </p>
    </section>
  );
}

export default function ReviewQueuePage() {
  return (
    <Suspense fallback={<div className="p-12 text-sm text-subtle">Loading…</div>}>
      <ReviewQueue />
    </Suspense>
  );
}
