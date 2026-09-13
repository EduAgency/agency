"use client";

/**
 * The staff side of pricing.
 *
 * Split from `@/lib/pricing` (which is the public read) because these are
 * different permissions doing different jobs: the access fee sits with whoever
 * holds the gateway keys, the cost estimates sit with whoever writes the pages.
 */

import { authFetch } from "@/lib/auth/client";

export interface AdminPricing {
  /** Exact decimal string. Sent back as a string so no float rounding happens. */
  access_fee_amount: string;
  access_fee_currency: string;
  access_fee_note: string;
  estimate_stale_after_days: number;
  formatted_access_fee: string;
  ascii_access_fee: string;
  currency_symbol: string;
  updated_at: string;
}

export interface AdminCostEstimate {
  id: string;
  label: string;
  amount_display: string;
  note: string;
  verified_on: string | null;
  /** Internal. Never served to a student. */
  verified_source: string;
  display_order: number;
  is_active: boolean;
  /** What a student currently sees — "ask us" when the row has gone stale. */
  public_amount: string;
  is_stale: boolean;
  created_at: string;
  updated_at: string;
}

export function getAdminPricing() {
  return authFetch<AdminPricing>("/api/admin/pricing/");
}

export function saveAdminPricing(patch: Partial<AdminPricing>) {
  return authFetch<AdminPricing>("/api/admin/pricing/", { method: "PATCH", body: patch });
}

export function listCostEstimates() {
  return authFetch<AdminCostEstimate[]>("/api/admin/cost-estimates/");
}

export function saveCostEstimate(id: string, patch: Partial<AdminCostEstimate>) {
  return authFetch<AdminCostEstimate>(`/api/admin/cost-estimates/${id}/`, {
    method: "PATCH",
    body: patch,
  });
}

export function createCostEstimate(payload: Partial<AdminCostEstimate>) {
  return authFetch<AdminCostEstimate>("/api/admin/cost-estimates/", {
    method: "POST",
    body: payload,
  });
}

export function deleteCostEstimate(id: string) {
  return authFetch<void>(`/api/admin/cost-estimates/${id}/`, { method: "DELETE" });
}
