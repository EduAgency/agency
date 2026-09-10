"use client";

import { authFetch } from "@/lib/auth/client";
import type { GatewayOption, Payment } from "@/types";

export function listGateways(currency = "NGN") {
  return authFetch<GatewayOption[]>(`/api/payments/gateways/?currency=${currency}`);
}

export function initiatePayment(input: {
  gateway?: string;
  purpose?: string;
  callback_url?: string;
}) {
  return authFetch<{ payment: Payment; checkout_url: string }>("/api/payments/initiate/", {
    method: "POST",
    body: input,
  });
}

/**
 * Ask the server to confirm a payment after the gateway redirect.
 *
 * This is not what makes a payment real — the webhook is (plan §5.2). It exists
 * so a student returning from checkout gets an answer immediately instead of
 * staring at a spinner while the webhook lands.
 */
export function verifyPayment(reference: string) {
  return authFetch<Payment>("/api/payments/verify/", {
    method: "POST",
    body: { reference },
  });
}

export function listMyPayments() {
  return authFetch<Payment[]>("/api/payments/mine/");
}
