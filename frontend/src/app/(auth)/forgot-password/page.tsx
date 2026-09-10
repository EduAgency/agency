"use client";

/**
 * Step one of password recovery. The login page has linked here since it was
 * written; the route did not exist (docs/enterprise-readiness.md §A2).
 */

import Link from "next/link";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { requestPasswordReset } from "@/lib/auth/client";
import { Alert, Button, Field, inputClass } from "@/components/ui";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      // A 429 is the throttle (5/hour) and is worth saying plainly; anything
      // else is ours, not theirs.
      setError(
        err instanceof ApiError && err.status === 429
          ? "Too many reset attempts. Wait an hour and try again."
          : "We couldn't send the email just now. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
        <h1 className="text-2xl font-semibold text-ink">Check your email</h1>
        {/* Same wording whether or not the address is registered — anything
            else turns this form into a way to test which emails have accounts. */}
        <p className="mt-3 text-sm text-muted">
          If <span className="font-medium text-ink">{email}</span> has an account, a link to set a
          new password is on its way. It expires in one hour.
        </p>
        <p className="mt-4 text-sm text-muted">
          Nothing arrived? Check your spam folder, then{" "}
          <button
            type="button"
            onClick={() => setSent(false)}
            className="underline underline-offset-2"
          >
            try a different address
          </button>
          .
        </p>
        <p className="mt-8 text-sm">
          <Link href="/login" className="underline underline-offset-2">
            Back to sign in
          </Link>
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold text-ink">Reset your password</h1>
      <p className="mt-1 text-sm text-muted">
        Enter the address you signed up with and we&apos;ll send you a link to set a new password.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-5">
        {error && <Alert>{error}</Alert>}

        <Field label="Email address" htmlFor="email">
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Sending…" : "Send reset link"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted">
        Remembered it?{" "}
        <Link href="/login" className="underline underline-offset-2">
          Sign in
        </Link>
      </p>
    </main>
  );
}
