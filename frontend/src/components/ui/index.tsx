"use client";

import Link from "next/link";

/**
 * Shared primitives.
 *
 * Every colour here is a semantic token from `globals.css`. There is not one
 * `dark:` variant in this file and there should never be another: a component
 * that reads `bg-surface` is correct in both themes because the token changes
 * underneath it (docs/enterprise-readiness.md §B10).
 *
 * Focus is handled globally by `:focus-visible` in `globals.css`, so no
 * component declares its own ring (§B2).
 */

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
}) {
  const styles = {
    primary: "bg-accent text-on-accent hover:bg-accent-hover",
    secondary: "border border-field-line text-ink hover:border-line-strong hover:bg-sunken",
    danger: "bg-danger text-on-danger hover:opacity-90",
  }[variant];

  return (
    <button
      {...props}
      className={`rounded-lg px-4 py-2.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  error,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-subtle">{hint}</p>}
      {error && (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * `--field-line` rather than the decorative `--line`: an input's border is the
 * only thing identifying where the control is, so WCAG 1.4.11 holds it to 3:1.
 * The old value failed at roughly 1.5:1 in light mode.
 */
export const inputClass =
  "w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink transition placeholder:text-subtle hover:border-line-strong";

export function Alert({
  children,
  tone = "error",
}: {
  children: React.ReactNode;
  tone?: "error" | "info" | "success" | "warning";
}) {
  const styles = {
    error: "border-danger-line bg-danger-bg text-danger",
    info: "border-info-line bg-info-bg text-info",
    success: "border-success-line bg-success-bg text-success",
    warning: "border-warning-line bg-warning-bg text-warning",
  }[tone];

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-lg border px-4 py-3 text-sm ${styles}`}
    >
      {children}
    </div>
  );
}

/**
 * Progress bar.
 *
 * The fill is the accent until the work is finished, then success green. It
 * used to grade red / amber / green by percentage, which meant a student who
 * had just started saw a deep red bar telling them their application was in
 * trouble — when being at 25% of a checklist on day one is simply normal.
 * Colour here encodes how far along you are, not whether something is wrong;
 * the states that ARE wrong have their own badges and alerts.
 *
 * The percentage is always shown, so colour is never the only signal.
 */
export function ProgressBar({ percent, label }: { percent: number; label?: string }) {
  const tone = percent >= 100 ? "bg-success" : "bg-accent";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs text-muted">
        <span>{label}</span>
        <span className="font-medium tabular-nums">{percent}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-2 w-full overflow-hidden rounded-full bg-sunken"
      >
        <div
          className={`h-full rounded-full transition-all ${tone}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Checklist and document statuses.
 *
 * Sixteen hand-written light/dark class pairs collapsed to four token-based
 * ones. Colour is never the only signal — every badge carries its label.
 */
const STATUS_STYLES: Record<string, string> = {
  not_started: "bg-sunken text-muted",
  in_progress: "bg-info-bg text-info",
  uploaded: "bg-info-bg text-info",
  pending_review: "bg-warning-bg text-warning",
  verified: "bg-success-bg text-success",
  rejected: "bg-danger-bg text-danger",
  waived: "bg-sunken text-muted",
  not_applicable: "bg-sunken text-subtle",
};

export function StatusBadge({ status, label }: { status: string; label: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${
        STATUS_STYLES[status] ?? STATUS_STYLES.not_started
      }`}
    >
      {label}
    </span>
  );
}

export function BackLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="text-sm text-muted hover:text-ink">
      <span aria-hidden="true">← </span>
      {children}
    </Link>
  );
}

/**
 * Loading placeholder that holds the space the content will occupy.
 *
 * Eight routes used to swap the entire page for the word"Loading…", which
 * reflows everything twice and tells assistive tech nothing (§B4). A skeleton
 * keeps the layout still; the `aria-busy` region around it does the announcing.
 */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-sunken ${className}`} />;
}

/** A page-level loading state: announced once, then replaced by real content. */
export function LoadingRegion({
  label = "Loading",
  children,
}: {
  label?: string;
  children: React.ReactNode;
}) {
  return (
    <div role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

/** The skeleton shape used by list pages, so they all settle the same way. */
export function CardListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="rounded-xl border border-line p-5">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="mt-2 h-4 w-1/3" />
          <Skeleton className="mt-4 h-2 w-full" />
        </div>
      ))}
    </div>
  );
}

/**
 * A horizontally scrollable container that a keyboard can actually scroll.
 *
 * `overflow-x: auto` alone creates a region reachable only by pointer — axe
 * reports it as `scrollable-region-focusable`, and it is a genuine trap: a wide
 * table on a phone has content a keyboard user cannot get to at all.
 * `tabIndex={0}` makes it a stop, and the label says what it is once focused.
 *
 * Found by the mobile axe run on the privacy policy's sub-processor table.
 */
export function ScrollableX({
  label,
  className = "",
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div tabIndex={0} role="region" aria-label={label} className={`overflow-x-auto ${className}`}>
      {children}
    </div>
  );
}
