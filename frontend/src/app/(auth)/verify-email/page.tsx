"use client";

/**
 * Target of the confirmation link sent at signup.
 *
 * The dashboard has always asked students to confirm their address; there was
 * no page for the link to land on and no way to request another
 * (docs/enterprise-readiness.md §A2).
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { verifyEmail } from "@/lib/auth/client";
import { Alert } from "@/components/ui";

type State = "checking" | "confirmed" | "failed";

function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<State>(token ? "checking" : "failed");
  // React 18+ runs effects twice in development; a verification token is
  // single-use, so the second run would report a valid link as expired.
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;
    verifyEmail(token)
      .then(() => setState("confirmed"))
      .catch(() => setState("failed"));
  }, [token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold text-ink">
        {state === "checking" ? "Confirming your email…" : "Email confirmation"}
      </h1>

      <div className="mt-6" aria-live="polite">
        {state === "checking" && <p className="text-sm text-muted">One moment.</p>}

        {state === "confirmed" && (
          <Alert tone="success">
            Your email address is confirmed. We can now send you document updates.
          </Alert>
        )}

        {state === "failed" && (
          <Alert>
            This link is invalid or has expired. Sign in and request a new one from your dashboard.
          </Alert>
        )}
      </div>

      <p className="mt-8 text-sm">
        <Link
          href={state === "confirmed" ? "/dashboard" : "/login"}
          className="underline underline-offset-2"
        >
          {state === "confirmed" ? "Go to my dashboard" : "Go to sign in"}
        </Link>
      </p>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={<main className="mx-auto max-w-md px-6 py-12 text-sm text-subtle">Loading…</main>}
    >
      <VerifyEmail />
    </Suspense>
  );
}
