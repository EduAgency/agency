/**
 * What things cost, fetched — never typed.
 *
 * There used to be four copies of the access fee: an env var the gateway read, a
 * constant in `company.ts`, and the literal `₦5,000` inside the checkout button
 * and the signup blurb. That is not untidiness. The gateway and the button could
 * disagree, and the first person to find out would be a student looking at a
 * bank alert for a different number than the one they clicked.
 *
 * So there is one source — `/api/pricing/` — and everything renders from it.
 *
 * The fallback below is the *shape*, not the price. It exists so a page still
 * renders if the API is briefly unreachable, and it deliberately shows "—"
 * rather than a plausible-looking number: a wrong price on a page is worse than
 * a visibly missing one.
 */

import { API_BASE_URL } from "@/lib/api";

const REVALIDATE_SECONDS = 300;

export interface AccessFee {
  /** Exact decimal string, e.g. "5000.00". For arithmetic, not for display. */
  amount: string;
  major_units: number;
  currency: string;
  symbol: string;
  /** What to render. The symbol and grouping are decided server-side. */
  formatted: string;
  /** Basic Latin only, for renderers with no font for the currency symbol. */
  ascii: string;
  note: string;
}

export interface CostEstimate {
  id: string;
  label: string;
  /** Already replaced with "ask us" when the figure has gone stale. */
  amount: string;
  note: string;
  is_verified: boolean;
  display_order: number;
}

export interface Pricing {
  access_fee: AccessFee;
  costs: CostEstimate[];
  unverified_label: string;
}

/**
 * Shown when the API cannot be reached.
 *
 * Every money field is a dash on purpose. A page that quietly falls back to a
 * hardcoded ₦5,000 is exactly the bug this module exists to remove — it would
 * look correct and be wrong.
 */
export const PRICING_UNAVAILABLE: Pricing = {
  access_fee: {
    amount: "0",
    major_units: 0,
    currency: "NGN",
    symbol: "₦",
    formatted: "—",
    ascii: "—",
    note: "",
  },
  costs: [],
  unverified_label: "Ask us — this changes",
};

export async function getPricing(): Promise<Pricing> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/pricing/`, {
      headers: { Accept: "application/json" },
      next: { revalidate: REVALIDATE_SECONDS },
    });
    if (!response.ok) return PRICING_UNAVAILABLE;
    return (await response.json()) as Pricing;
  } catch {
    return PRICING_UNAVAILABLE;
  }
}

/** True when we actually know the price. Pages use this to hide a CTA rather than lie. */
export function isPriceKnown(pricing: Pricing): boolean {
  return pricing.access_fee.major_units > 0;
}

/**
 * The same fetch, for client components.
 *
 * Checkout and signup are client-side, and both quote the fee before any
 * payment is initiated — so they cannot get it from a payment response. This is
 * a plain browser fetch of the same public endpoint.
 */
export async function fetchPricing(): Promise<Pricing> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/pricing/`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return PRICING_UNAVAILABLE;
    return (await response.json()) as Pricing;
  } catch {
    return PRICING_UNAVAILABLE;
  }
}
