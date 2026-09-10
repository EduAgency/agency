"use client";

/**
 * Route-segment error boundary.
 *
 * Without this, one thrown render blanks the whole app and the student is left
 * looking at white space with no way back (docs/enterprise-readiness.md §B7).
 * The copy says what to do next and never blames the reader.
 */

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui";
import { reportError } from "@/lib/report-error";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportError(error, { boundary: "app", digest: error.digest });
  }, [error]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold text-ink">This page didn&apos;t load</h1>
      <p className="mt-3 text-sm text-muted">
        Something on our side failed while building this page. Your documents and answers are safe —
        nothing you have already submitted is affected.
      </p>

      <div className="mt-8 flex flex-wrap gap-3">
        <Button onClick={reset}>Try again</Button>
        <Link href="/dashboard">
          <Button variant="secondary">Go to my dashboard</Button>
        </Link>
      </div>

      <p className="mt-8 text-sm text-muted">
        If it keeps happening,{" "}
        <Link href="/contact" className="underline underline-offset-2">
          contact us
        </Link>
        {error.digest && (
          <>
            {" "}
            and quote reference{" "}
            <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-xs">
              {error.digest}
            </code>
          </>
        )}
        .
      </p>
    </main>
  );
}
