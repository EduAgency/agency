"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { authFetch } from "@/lib/auth/client";
import { useSession } from "@/lib/auth/SessionProvider";
import { FormRenderer } from "@/components/forms/FormRenderer";
import { Alert, BackLink } from "@/components/ui";
import type { FieldErrors, FormDefinition, FormValues } from "@/types";

/**
 * The intake form.
 *
 * There is nothing here that knows what fields an intake form has — the page
 * fetches whatever the admin published and renders it. Adding a question is an
 * admin action, not a deploy (plan §3.1).
 */
export default function IntakePage() {
  const router = useRouter();
  const { session, loading, hasAccess } = useSession();
  const [form, setForm] = useState<FormDefinition | null>(null);
  const [values, setValues] = useState<FormValues>({});
  const [serverErrors, setServerErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!session) return router.replace("/login");
    if (!hasAccess) return router.replace("/checkout");

    authFetch<FormDefinition>("/api/forms/student-intake/")
      .then(async (definition) => {
        setForm(definition);
        // Pick up an unfinished draft, if there is one.
        try {
          const submissions = await authFetch<{ status: string; data: FormValues }[]>(
            "/api/my/submissions/?form_slug=student-intake",
          );
          const draft = submissions.find((s) => s.status === "draft");
          if (draft) setValues(draft.data);
        } catch {
          // A missing draft is not an error.
        }
      })
      .catch(() => setMessage("This form isn't available right now."));
  }, [loading, session, hasAccess, router]);

  async function submit(data: FormValues, isDraft = false) {
    setBusy(true);
    setServerErrors({});
    setMessage("");
    try {
      await authFetch("/api/forms/student-intake/submit/", {
        method: "POST",
        body: { data, is_draft: isDraft },
      });
      if (isDraft) {
        setMessage("Saved. You can come back and finish this later.");
      } else {
        setDone(true);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setServerErrors(err.fieldErrors);
        setMessage(Object.keys(err.fieldErrors).length ? "" : err.message);
      } else {
        setMessage("We couldn't save that. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (loading || (!form && !message)) {
    return <div className="p-12 text-sm text-subtle">Loading…</div>;
  }

  if (done) {
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <h1 className="text-2xl font-semibold text-ink">Thank you</h1>
        <p className="mt-2 text-sm text-muted">
          {form?.success_message || "Your counsellor will review this shortly."}
        </p>
        <div className="mt-8">
          <BackLink href="/dashboard">Back to my applications</BackLink>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <BackLink href="/dashboard">Back to my applications</BackLink>

      {form && (
        <header className="mt-4">
          <h1 className="text-2xl font-semibold text-ink">{form.title}</h1>
          {form.description && <p className="mt-1 text-sm text-muted">{form.description}</p>}
        </header>
      )}

      {message && (
        <div className="mt-6">
          <Alert tone={serverErrors ? "info" : "error"}>{message}</Alert>
        </div>
      )}

      {form && (
        <div className="mt-8">
          <FormRenderer
            schema={form.schema}
            initialValues={values}
            serverErrors={serverErrors}
            submitLabel={form.submit_button_label || "Submit"}
            submitting={busy}
            onSubmit={(data) => submit(data, false)}
            onSaveDraft={form.allow_drafts ? (data) => submit(data, true) : undefined}
          />
        </div>
      )}
    </div>
  );
}
