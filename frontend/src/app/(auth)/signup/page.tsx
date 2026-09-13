"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { checkReferralCode, signup } from "@/lib/auth/client";
import { useSession } from "@/lib/auth/SessionProvider";
import { usePricing } from "@/lib/usePricing";
import { Alert, Button, Field, inputClass } from "@/components/ui";
import type { FieldErrors } from "@/types";

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useSession();

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    password: "",
    referral_code: params.get("ref") ?? "",
    accept_terms: false,
    marketing_opt_in: false,
  });
  const { pricing, ready: priceReady } = usePricing();
  const [errors, setErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState("");
  const [referrer, setReferrer] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const code = form.referral_code.trim();

  // A referral code is optional and never blocks signup — a wrong one is
  // simply ignored server-side (plan §6.3). Debounced so typing a code does
  // not fire a request per keystroke.
  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      const result = code.length < 4 ? null : await checkReferralCode(code).catch(() => null);
      if (cancelled) return;
      setReferrer(result?.valid ? (result.referrer_first_name ?? "") : null);
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [code]);

  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setErrors({});
    setMessage("");
    try {
      await signup({ ...form, referral_code: code || undefined });
      await refresh();
      router.push("/checkout");
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        setMessage(Object.keys(err.fieldErrors).length ? "" : err.message);
      } else {
        setMessage("Something went wrong. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  const firstError = (key: string) => errors[key]?.[0];

  return (
    <main className="mx-auto max-w-md px-6 py-12">
      <h1 className="text-2xl font-semibold text-ink">Create your account</h1>
      <p className="mt-1 text-sm text-muted">
        Takes a minute.{" "}
        {priceReady && pricing.access_fee.major_units > 0
          ? `The ${pricing.access_fee.formatted} access fee comes after this step, and you'll see exactly what it covers before you pay.`
          : "The access fee comes after this step, and you'll see exactly what it covers before you pay."}
      </p>

      <form onSubmit={submit} className="mt-8 space-y-5">
        {message && <Alert>{message}</Alert>}

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="First name" htmlFor="first_name" error={firstError("first_name")}>
            <input
              id="first_name"
              required
              autoComplete="given-name"
              value={form.first_name}
              onChange={(e) => update("first_name", e.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Last name" htmlFor="last_name" error={firstError("last_name")}>
            <input
              id="last_name"
              required
              autoComplete="family-name"
              value={form.last_name}
              onChange={(e) => update("last_name", e.target.value)}
              className={inputClass}
            />
          </Field>
        </div>

        <Field label="Email address" htmlFor="email" error={firstError("email")}>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field
          label="Phone number"
          htmlFor="phone"
          error={firstError("phone")}
          hint="So your counsellor can reach you."
        >
          <input
            id="phone"
            type="tel"
            autoComplete="tel"
            placeholder="+234…"
            value={form.phone}
            onChange={(e) => update("phone", e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field
          label="Password"
          htmlFor="password"
          error={firstError("password")}
          hint="At least 10 characters."
        >
          <input
            id="password"
            type="password"
            required
            minLength={10}
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field
          label="Referral code (optional)"
          htmlFor="referral_code"
          hint={
            referrer === null
              ? "If someone shared a code with you, enter it here."
              : referrer
                ? `Referred by ${referrer}.`
                : "Code recognised."
          }
        >
          <input
            id="referral_code"
            value={form.referral_code}
            onChange={(e) => update("referral_code", e.target.value.toUpperCase())}
            className={inputClass}
          />
        </Field>

        <div className="space-y-3 border-t border-line pt-5">
          <label className="flex items-start gap-2.5 text-sm text-muted">
            <input
              type="checkbox"
              required
              checked={form.accept_terms}
              onChange={(e) => update("accept_terms", e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-field-line"
            />
            <span>
              I agree to the{" "}
              <Link href="/terms" className="underline underline-offset-2">
                terms of service
              </Link>{" "}
              and{" "}
              <Link href="/privacy" className="underline underline-offset-2">
                privacy policy
              </Link>
              , including how my documents are stored and processed.
            </span>
          </label>
          {firstError("accept_terms") && (
            <p role="alert" className="text-xs text-danger">
              {firstError("accept_terms")}
            </p>
          )}

          <label className="flex items-start gap-2.5 text-sm text-muted">
            <input
              type="checkbox"
              checked={form.marketing_opt_in}
              onChange={(e) => update("marketing_opt_in", e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-field-line"
            />
            <span>Send me occasional updates about scholarships and intakes. Optional.</span>
          </label>
        </div>

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Creating your account…" : "Create account"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="underline underline-offset-2">
          Sign in
        </Link>
      </p>
    </main>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-md px-6 py-12">Loading…</main>}>
      <SignupForm />
    </Suspense>
  );
}
