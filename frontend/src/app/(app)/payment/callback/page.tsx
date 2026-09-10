"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useSession } from "@/lib/auth/SessionProvider";
import { verifyPayment } from "@/lib/payments";
import { Alert, Button } from "@/components/ui";
import type { PaymentStatus } from "@/types";

/** Poll a few times: the webhook usually lands within seconds of the redirect. */
const POLL_MS = 3000;
const MAX_POLLS = 10;

function Callback() {
  const params = useSearchParams();
  const { refresh } = useSession();
  const [status, setStatus] = useState<PaymentStatus | "unknown">("unknown");
  const [message, setMessage] = useState("");
  // Paystack returns ?reference=…, Flutterwave ?tx_ref=…
  const reference = params.get("reference") ?? params.get("tx_ref") ?? "";

  useEffect(() => {
    if (!reference) return;

    let cancelled = false;
    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    // A plain loop rather than a self-scheduling callback: the webhook usually
    // lands within seconds, and we stop asking either way after MAX_POLLS.
    void (async () => {
      for (let attempt = 0; attempt < MAX_POLLS && !cancelled; attempt += 1) {
        try {
          const payment = await verifyPayment(reference);
          if (cancelled) return;
          setStatus(payment.status);

          if (payment.status === "successful") {
            await refresh();
            return;
          }
          if (payment.status !== "pending" && payment.status !== "processing") {
            return;
          }
        } catch {
          if (cancelled) return;
          setMessage("We couldn't confirm this payment yet. It may still be processing.");
          return;
        }
        await sleep(POLL_MS);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [reference, refresh]);

  if (status === "successful") {
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <h1 className="text-2xl font-semibold text-ink">Payment confirmed</h1>
        <p className="mt-2 text-sm text-muted">
          Your dashboard is unlocked. Let&apos;s get your checklist started.
        </p>
        <Link href="/dashboard" className="mt-8 inline-block">
          <Button>Go to my dashboard</Button>
        </Link>
      </div>
    );
  }

  if (status === "failed" || status === "abandoned") {
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <h1 className="text-2xl font-semibold text-ink">That payment didn&apos;t go through</h1>
        <p className="mt-2 text-sm text-muted">
          Nothing has been charged. You can try again with the same or a different method.
        </p>
        <Link href="/checkout" className="mt-8 inline-block">
          <Button>Try again</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md px-6 py-20 text-center">
      <h1 className="text-2xl font-semibold text-ink">Confirming your payment</h1>
      {/* Deliberately not"Paid". Nothing is confirmed until the gateway's
          webhook says so, and telling a student otherwise is how disputes start. */}
      <p className="mt-2 text-sm text-muted">
        We&apos;re waiting for your bank and payment provider to confirm. This usually takes a few
        seconds, and it&apos;s safe to leave this page — we&apos;ll email you the moment it clears.
      </p>
      {(message || !reference) && (
        <div className="mt-6 text-left">
          <Alert tone="info">
            {message ||
              "We couldn't identify this payment from the link you followed. Check your payment history — if you were charged, it will appear there."}
          </Alert>
        </div>
      )}
      {reference && <p className="mt-6 font-mono text-xs text-subtle">Reference: {reference}</p>}
      <Link
        href="/dashboard"
        className="mt-8 inline-block text-sm text-muted underline underline-offset-4"
      >
        Go to my dashboard
      </Link>
    </div>
  );
}

export default function PaymentCallbackPage() {
  return (
    <Suspense fallback={<div className="p-12 text-sm text-subtle">Loading…</div>}>
      <Callback />
    </Suspense>
  );
}
