"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { login } from "@/lib/auth/client";
import { useSession } from "@/lib/auth/SessionProvider";
import { Alert, Button, Field, inputClass } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      await refresh();
      router.push("/dashboard");
    } catch (err) {
      // The API returns one message for both wrong-password and no-such-account,
      // deliberately — the form must not confirm which addresses are registered.
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold text-ink">Sign in</h1>
      <p className="mt-1 text-sm text-muted">Continue with your applications.</p>

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

        <Field label="Password" htmlFor="password">
          <input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <div className="mt-6 space-y-2 text-sm text-muted">
        <p>
          <Link href="/forgot-password" className="underline underline-offset-2">
            Forgotten your password?
          </Link>
        </p>
        <p>
          New here?{" "}
          <Link href="/signup" className="underline underline-offset-2">
            Create an account
          </Link>
        </p>
      </div>
    </main>
  );
}
