"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "@/lib/auth/SessionProvider";
import { getApplication, getChecklist } from "@/lib/applications";
import { ChecklistView } from "@/components/ChecklistView";
import { Alert, BackLink } from "@/components/ui";
import type { Application, Checklist } from "@/types";

export default function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { session, loading, hasAccess, handleApiError } = useSession();

  const [application, setApplication] = useState<Application | null>(null);
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  const redirectTo = !loading && !session ? "/login" : !loading && !hasAccess ? "/checkout" : null;

  // The load runs inside the effect as an async IIFE so no state is set
  // synchronously during render.
  useEffect(() => {
    if (loading) return;
    if (redirectTo) {
      router.replace(redirectTo);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const [app, list] = await Promise.all([getApplication(id), getChecklist(id)]);
        if (cancelled) return;
        setApplication(app);
        setChecklist(list);
      } catch (err) {
        if (cancelled) return;
        if (!handleApiError(err)) setError("We couldn't load this application.");
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, loading, redirectTo, router, handleApiError]);

  /**
   * Refetch the whole checklist after an upload rather than patching the item
   * in place — the percentages are computed server-side, and guessing them here
   * is how the bar drifts out of step with the truth.
   */
  const handleItemChange = useCallback(() => {
    getChecklist(id)
      .then(setChecklist)
      .catch(() => undefined);
  }, [id]);

  if (loading || !ready) return <div className="p-12 text-sm text-subtle">Loading…</div>;

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <BackLink href="/dashboard">Back to my applications</BackLink>

      {error && (
        <div className="mt-6">
          <Alert>{error}</Alert>
        </div>
      )}

      {application && (
        <header className="mt-4">
          <h1 className="text-2xl font-semibold text-ink">{application.school.name}</h1>
          <p className="mt-1 text-sm text-muted">
            {application.programme?.name}
            {application.intake && ` · ${application.intake}`} · {application.status_display}
          </p>
        </header>
      )}

      <div className="mt-8">
        {checklist ? (
          <ChecklistView checklist={checklist} onChange={handleItemChange} />
        ) : (
          !error && (
            <Alert tone="info">
              Your checklist is being prepared. Your counsellor will have it ready shortly.
            </Alert>
          )
        )}
      </div>
    </div>
  );
}
