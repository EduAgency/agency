"use client";

/**
 * The access fee, for client components.
 *
 * Checkout and signup both quote the price before any payment exists, so they
 * cannot read it off a payment response — they have to ask. This hook wraps that
 * fetch and, importantly, reports whether it has arrived yet.
 *
 * `ready` is the part callers must not skip. A checkout button that renders
 * "Pay —" for a moment is honest; one that renders a guessed price and then
 * corrects itself has already shown the user a number that was not true.
 */

import { useEffect, useState } from "react";
import { PRICING_UNAVAILABLE, type Pricing, fetchPricing } from "@/lib/pricing";

export function usePricing(): { pricing: Pricing; ready: boolean } {
  const [pricing, setPricing] = useState<Pricing>(PRICING_UNAVAILABLE);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const loaded = await fetchPricing();
      if (cancelled) return;
      setPricing(loaded);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { pricing, ready };
}
