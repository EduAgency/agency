"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useSession } from "@/lib/auth/SessionProvider";
import { initiatePayment, listGateways } from "@/lib/payments";
import { Alert, Button } from "@/components/ui";
import type { GatewayOption } from "@/types";

const INCLUDED = [
  "A document checklist built from your school's real requirements",
  "Document review with written feedback on anything rejected",
  "Application tracking across every school you apply to",
  "A counsellor you can message inside the platform",
];

export default function CheckoutPage() {
  const router = useRouter();
  const { session, loading, hasAccess } = useSession();
  const [gateways, setGateways] = useState<GatewayOption[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!session) {
      router.replace("/login");
      return;
    }
    if (hasAccess) {
      router.replace("/dashboard");
      return;
    }
    // Only gateways the admin has switched on are offered (plan §5.1).
    listGateways()
      .then((options) => {
        setGateways(options);
        setSelected(options[0]?.gateway ?? "");
      })
      .catch(() => setError("We couldn't load payment options. Please refresh."));
  }, [loading, session, hasAccess, router]);

  async function pay() {
    setBusy(true);
    setError("");
    try {
      const { checkout_url } = await initiatePayment({
        gateway: selected || undefined,
        callback_url: `${window.location.origin}/payment/callback`,
      });
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't start the payment. Try again.");
      setBusy(false);
    }
  }

  if (loading) return <main className="p-12 text-sm text-slate-500">Loading…</main>;

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Activate your account</h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        One payment of ₦5,000. This is the only fee we charge for the platform.
      </p>

      <section className="mt-8 rounded-xl border border-slate-200 p-6 dark:border-slate-800">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Platform access</span>
          <span className="text-2xl font-semibold text-slate-900 dark:text-slate-50">₦5,000</span>
        </div>

        <ul className="mt-5 space-y-2 text-sm text-slate-600 dark:text-slate-400">
          {INCLUDED.map((item) => (
            <li key={item} className="flex gap-2">
              <span aria-hidden className="text-emerald-600 dark:text-emerald-400">✓</span>
              {item}
            </li>
          ))}
        </ul>

        <p className="mt-5 border-t border-slate-200 pt-4 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
          This fee does not buy admission or a visa — those are decided by the school and the embassy.
          Read the <a href="/refund-policy" className="underline underline-offset-2">refund policy</a>{" "}
          before paying.
        </p>
      </section>

      {error && <div className="mt-6"><Alert>{error}</Alert></div>}

      {gateways.length > 1 && (
        <fieldset className="mt-6">
          <legend className="text-sm font-medium text-slate-800 dark:text-slate-200">Pay with</legend>
          <div className="mt-2 space-y-2">
            {gateways.map((gateway) => (
              <label
                key={gateway.gateway}
                className="flex items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2.5 text-sm dark:border-slate-800"
              >
                <input
                  type="radio"
                  name="gateway"
                  value={gateway.gateway}
                  checked={selected === gateway.gateway}
                  onChange={() => setSelected(gateway.gateway)}
                  className="h-4 w-4"
                />
                <span className="capitalize">{gateway.label || gateway.gateway}</span>
                {gateway.is_test_mode && (
                  <span className="ml-auto rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                    test mode
                  </span>
                )}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {gateways.length === 0 && !error ? (
        <div className="mt-6">
          <Alert tone="info">
            Payments are temporarily unavailable. Please check back shortly — nothing has been charged.
          </Alert>
        </div>
      ) : (
        <Button onClick={pay} disabled={busy || !gateways.length} className="mt-6 w-full">
          {busy ? "Taking you to checkout…" : "Pay ₦5,000"}
        </Button>
      )}
    </main>
  );
}
