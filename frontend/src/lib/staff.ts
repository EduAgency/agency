"use client";

/**
 * The staff API.
 *
 * Everything here already existed server-side — a review queue, a student
 * directory, an audit trail — but the only client for it was Django admin, so
 * reviewers verified passports through a generic changelist
 * (docs/enterprise-readiness.md §C, "Staff workspace").
 *
 * Permissions are enforced by the server on every route (`HasAdminPermission`
 * against a named `AdminProfile` flag). Hiding a control in this UI is a
 * usability choice, never a security boundary.
 */

import { authFetch } from "@/lib/auth/client";
import type { ChecklistItem } from "@/types";

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** A checklist item as the review queue returns it, with its student attached. */
export interface ReviewItem extends ChecklistItem {
  student_name?: string;
  student_email?: string;
  school_name?: string;
}

export type ReviewDecision =
  | "verified"
  | "rejected"
  | "waived"
  | "not_applicable"
  | "pending_review";

export interface StaffStudent {
  id: string;
  user: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    full_name: string;
    phone?: string;
    email_verified_at: string | null;
  };
  date_of_birth: string | null;
  nationality: string;
  country_of_residence: string;
  state_of_residence: string;
  whatsapp: string;
  stage: string;
  stage_display: string;
  has_platform_access: boolean;
  access_granted_at: string | null;
  source: string;
  referral_code: string;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

/**
 * Oldest-waiting first, which is what the server already orders by. Passing no
 * status deliberately returns only what needs a decision.
 */
export function listReviewQueue(params: { status?: string; search?: string; priority?: string }) {
  return authFetch<Paginated<ReviewItem>>(`/api/admin/review-queue/${query(params)}`);
}

/** Verify, reject or waive. The server refuses a rejection with no reason. */
export function reviewItem(
  itemId: string,
  decision: ReviewDecision,
  reason = "",
  reviewerNote = "",
) {
  return authFetch<ChecklistItem>(`/api/checklist-items/${itemId}/review/`, {
    method: "POST",
    body: { status: decision, reason, reviewer_note: reviewerNote },
  });
}

export function listStudents(params: { search?: string; stage?: string; page?: number }) {
  return authFetch<Paginated<StaffStudent>>(`/api/admin/students/${query(params)}`);
}

export function getStudent(id: string) {
  return authFetch<StaffStudent>(`/api/admin/students/${id}/`);
}

/**
 * Rejection reasons staff reach for constantly.
 *
 * Canned reasons are not laziness — they are consistency. A student who is told
 * "photo is blurred, we cannot read the expiry date" can act on it; one told
 * "rejected" cannot, and comes back as a support ticket. Every option is
 * editable before sending.
 */
export const REJECTION_REASONS = [
  "The image is too blurred to read. Please re-scan or photograph it in better light.",
  "Part of the document is cut off. We need the whole page, including all four corners.",
  "This document has expired. Please upload a current one.",
  "The name on this document does not match the name on your account.",
  "This is the wrong document for this requirement.",
  "We need the official version, not a photocopy or a screenshot.",
  "Only one page was uploaded — this document has more than one page.",
] as const;
