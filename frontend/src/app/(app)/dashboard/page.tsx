"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "@/lib/auth/SessionProvider";
import { listApplications } from "@/lib/applications";
import { Alert, Button, ProgressBar } from "@/components/ui";
import type { Application } from "@/types";

export default function DashboardPage() {
  const router = useRouter();
  const { session, loading, hasAccess, signOut, handleApiError } = useSession();
  const [applications, setApplications] = useState<Application[]>([]);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

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

  if (loading || !ready) return <main className="p-12 text-sm text-slate-500">Loading…</main>;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">
            Hello, {session?.user.first_name || "there"}
          </h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            {applications.length === 0
              ? "You haven't started an application yet."
              : `${applications.length} application${applications.length === 1 ? "" : "s"} in progress.`}
          </p>
        </div>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/referrals" className="text-slate-600 hover:underline dark:text-slate-400">
            Referrals
          </Link>
          <Link href="/documents" className="text-slate-600 hover:underline dark:text-slate-400">
            Documents
          </Link>
          <button onClick={signOut} className="text-slate-600 hover:underline dark:text-slate-400">
            Sign out
          </button>
        </nav>
      </header>

      {!session?.user.email_verified_at && (
        <div className="mt-6">
          <Alert tone="info">
            Confirm your email address so we can send you document updates. Check your inbox for the
            link we sent when you signed up.
          </Alert>
        </div>
      )}

      {error && <div className="mt-6"><Alert>{error}</Alert></div>}

      <section className="mt-10 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">My applications</h2>
          <Link href="/applications/new">
            <Button variant="secondary">Add a school</Button>
          </Link>
        </div>

        {applications.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Pick a school and we&apos;ll build your document checklist from its actual requirements.
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
                  className="block rounded-xl border border-slate-200 p-5 transition hover:border-slate-400 dark:border-slate-800 dark:hover:border-slate-600"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="font-medium text-slate-900 dark:text-slate-100">
                        {application.school.name}
                      </h3>
                      <p className="text-sm text-slate-600 dark:text-slate-400">
                        {application.programme?.name}
                        {application.intake && ` · ${application.intake}`}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
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
                    <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
                      Your checklist is being prepared.
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
