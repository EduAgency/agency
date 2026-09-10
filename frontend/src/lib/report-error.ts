/**
 * Single choke point for front-end crash reporting.
 *
 * The backend reports to Sentry (`config/settings.py`), but nothing reported
 * browser-side, so a thrown render was invisible to the team and looked to the
 * student like the app had simply stopped. Every error boundary funnels through
 * here.
 *
 * Wiring Sentry is then one change in one file:
 *
 *   npm install @sentry/nextjs
 *   # set NEXT_PUBLIC_SENTRY_DSN
 *
 * and replace the console call below with `Sentry.captureException`. Until a DSN
 * exists this still gives a consistent, greppable shape in the browser console
 * rather than a bare React stack.
 */

export interface ErrorContext {
  /** Where it happened — route segment, component, or action name. */
  boundary: string;
  /** Next.js attaches this to server-rendered errors; useful for log matching. */
  digest?: string;
}

export function reportError(error: unknown, context: ErrorContext): void {
  const payload = {
    ...context,
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack : undefined,
    at: new Date().toISOString(),
    url: typeof window === "undefined" ? undefined : window.location.pathname,
  };

  console.error("[nasuru] unhandled error", payload);
}
