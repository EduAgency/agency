"use client";

/**
 * Step two of password recovery: the target of the emailed link.
 *
 * The 10-character minimum mirrors `PasswordResetConfirmSerializer`, and the
 * requirement is stated up front rather than only after a rejected submit —
 * the server also runs Django's validators, whose messages are surfaced
 * verbatim because they are more specific than anything generic we would write.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ApiError } from "@/lib/api";
import { confirmPasswordReset } from "@/lib/auth/client";
import { Alert, Button, Field, inputClass } from "@/components/ui";

const MIN_LENGTH = 10;

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
        <h1 className="text-2xl font-semibold text-ink">This link is incomplete</h1>
        <p className="mt-3 text-sm text-muted">
          Open the link from your email exactly as it was sent, or request a new one.
        </p>
        <p className="mt-8 text-sm">
          <Link href="/forgot-password" className="underline underline-offset-2">
            Request a new reset link
          </Link>
        </p>
      </main>
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setFieldError("");

    if (password !== confirm) {
      setFieldError("The two passwords don't match.");
      return;
    }

    setBusy(true);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
      // Long enough to read the confirmation, short enough not to feel stuck.
      setTimeout(() => router.push("/login"), 2500);
    } catch (err) {
      if (err instanceof ApiError) {
        const specific = err.fieldErrors.new_password?.[0];
        if (specific) setFieldError(specific);
        else setError(err.message);
      } else {
        setError("We couldn't reset your password just now. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
        <Alert tone="success">Your password is updated. Taking you to sign in…</Alert>
        <p className="mt-6 text-sm">
          <Link href="/login" className="underline underline-offset-2">
            Sign in now
          </Link>
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold text-ink">Choose a new password</h1>

      <form onSubmit={submit} className="mt-8 space-y-5">
        {error && <Alert>{error}</Alert>}

        <Field
          label="New password"
          htmlFor="password"
          hint={`At least ${MIN_LENGTH} characters. Avoid your name or a common word.`}
          error={fieldError}
        >
          <input
            id="password"
            type="password"
            required
            minLength={MIN_LENGTH}
            autoComplete="new-password"
            aria-invalid={fieldError ? true : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Confirm new password" htmlFor="confirm">
          <input
            id="confirm"
            type="password"
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Saving…" : "Save new password"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted">
        Link expired?{" "}
        <Link href="/forgot-password" className="underline underline-offset-2">
          Request a new one
        </Link>
      </p>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={<main className="mx-auto max-w-md px-6 py-12 text-sm text-subtle">Loading…</main>}
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
