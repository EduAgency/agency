"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { usePricing } from "@/lib/usePricing";
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
  // The fee comes from /api/pricing/, the same row the gateway charges from.
  const { pricing, ready: priceReady } = usePricing();
  const fee = pricing.access_fee;
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

  // The price is never rendered from a constant: the button and the gateway read
  // the same row, so they cannot show different numbers.
  if (loading || !priceReady) {
    return <div className="p-12 text-sm text-subtle">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-lg px-6 py-12">
      <h1 className="text-2xl font-semibold text-ink">Activate your account</h1>
      <p className="mt-1 text-sm text-muted">
        One payment of {fee.formatted}. This is the only fee we charge for the platform.
      </p>

      <section className="mt-8 rounded-xl border border-line p-6">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium text-muted">Platform access</span>
          <span className="text-2xl font-semibold text-ink">{fee.formatted}</span>
        </div>

        <ul className="mt-5 space-y-2 text-sm text-muted">
          {INCLUDED.map((item) => (
            <li key={item} className="flex gap-2">
              <span aria-hidden className="text-success">
                ✓
              </span>
              {item}
            </li>
          ))}
        </ul>

        <p className="mt-5 border-t border-line pt-4 text-xs text-subtle">
          This fee does not buy admission or a visa — those are decided by the school and the
          embassy. Read the{" "}
          <a href="/refund-policy" className="underline underline-offset-2">
            refund policy
          </a>{" "}
          before paying.
        </p>
      </section>

      {error && (
        <div className="mt-6">
          <Alert>{error}</Alert>
        </div>
      )}

      {gateways.length > 1 && (
        <fieldset className="mt-6">
          <legend className="text-sm font-medium text-ink">Pay with</legend>
          <div className="mt-2 space-y-2">
            {gateways.map((gateway) => (
              <label
                key={gateway.gateway}
                className="flex items-center gap-2.5 rounded-lg border border-line px-3 py-2.5 text-sm"
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
                  <span className="ml-auto rounded bg-warning-bg px-2 py-0.5 text-xs text-warning">
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
            Payments are temporarily unavailable. Please check back shortly — nothing has been
            charged.
          </Alert>
        </div>
      ) : (
        <Button onClick={pay} disabled={busy || !gateways.length} className="mt-6 w-full">
          {busy ? "Taking you to checkout…" : `Pay ${fee.formatted}`}
        </Button>
      )}
    </div>
  );
}
