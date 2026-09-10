"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "@/lib/auth/SessionProvider";
import { resendVerification } from "@/lib/auth/client";
import { listApplications } from "@/lib/applications";
import {
  Alert,
  Button,
  CardListSkeleton,
  LoadingRegion,
  ProgressBar,
  Skeleton,
} from "@/components/ui";
import type { Application } from "@/types";

export default function DashboardPage() {
  const router = useRouter();
  const { session, loading, hasAccess, handleApiError } = useSession();
  const [applications, setApplications] = useState<Application[]>([]);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [resendState, setResendState] = useState<"idle" | "sending" | "sent" | "failed">("idle");

  async function resend() {
    setResendState("sending");
    try {
      await resendVerification();
      setResendState("sent");
    } catch {
      setResendState("failed");
    }
  }

  useEffect(() => {
    if (loading) return;
    if (!session) {
      router.replace("/login");
      return;
    }
    if (!hasAccess) {
      router.replace("/checkout");
      return;
    }
    listApplications()
      .then((page) => setApplications(page.results))
      .catch((err) => {
        if (!handleApiError(err)) setError("We couldn't load your applications. Please refresh.");
      })
      .finally(() => setReady(true));
  }, [loading, session, hasAccess, router, handleApiError]);

  /* A skeleton in the shape of the list that is coming, rather than swapping
     the page for the word "Loading…" and reflowing everything twice (§B4). */
  if (loading || !ready) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12">
        <LoadingRegion label="Loading your applications">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="mt-2 h-4 w-72" />
          <div className="mt-10">
            <CardListSkeleton />
          </div>
        </LoadingRegion>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      {/* Navigation and sign-out live in the app shell now — this page used to
          build its own unlabelled nav alongside the shell's (§B1). */}
      <header>
        <h1 className="text-2xl font-semibold text-ink">
          Hello, {session?.user.first_name || "there"}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {applications.length === 0
            ? "You haven't started an application yet."
            : `${applications.length} application${applications.length === 1 ? "" : "s"} in progress.`}
        </p>
      </header>

      {!session?.user.email_verified_at && (
        <div className="mt-6">
          <Alert tone="info">
            Confirm your email address so we can send you document updates. Check your inbox for the
            link we sent when you signed up.
            <span className="mt-2 block" aria-live="polite">
              {resendState === "sent" ? (
                <span className="font-medium">
                  Sent. Check your inbox — the link expires in one hour.
                </span>
              ) : resendState === "failed" ? (
                <span className="font-medium">
                  We couldn&apos;t send it just now. Try again in a few minutes.
                </span>
              ) : (
                <button
                  type="button"
                  onClick={resend}
                  disabled={resendState === "sending"}
                  className="underline underline-offset-2 disabled:opacity-60"
                >
                  {resendState === "sending" ? "Sending…" : "Send the link again"}
                </button>
              )}
            </span>
          </Alert>
        </div>
      )}

      {error && (
        <div className="mt-6">
          <Alert>{error}</Alert>
        </div>
      )}

      <section className="mt-10 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">My applications</h2>
          <Link href="/applications/new">
            <Button variant="secondary">Add a school</Button>
          </Link>
        </div>

        {applications.length === 0 ? (
          <div className="rounded-xl border border-dashed border-field-line p-8 text-center">
            <p className="text-sm text-muted">
              Pick a school and we&apos;ll build your document checklist from its actual
              requirements.
            </p>
            <Link href="/applications/new" className="mt-4 inline-block">
              <Button>Choose a school</Button>
            </Link>
          </div>
        ) : (
          <ul className="space-y-3">
            {applications.map((application) => (
              <li key={application.id}>
                <Link
                  href={`/applications/${application.id}`}
                  className="block rounded-xl border border-line p-5 transition hover:border-line-strong"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="font-medium text-ink">{application.school.name}</h3>
                      <p className="text-sm text-muted">
                        {application.programme?.name}
                        {application.intake && ` · ${application.intake}`}
                      </p>
                    </div>
                    <span className="rounded-full bg-sunken px-2.5 py-0.5 text-xs font-medium text-muted">
                      {application.status_display}
                    </span>
                  </div>

                  {application.checklist ? (
                    <div className="mt-4">
                      <ProgressBar
                        percent={application.checklist.percent_complete}
                        label={`${application.checklist.verified_count} of ${application.checklist.required_count} documents verified`}
                      />
                    </div>
                  ) : (
                    <p className="mt-4 text-xs text-subtle">Your checklist is being prepared.</p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
