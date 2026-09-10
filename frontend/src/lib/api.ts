/**
 * Backend client.
 *
 * The API lives on Render/Railway/Fly, not on Vercel — Django needs a
 * long-lived process for webhooks, uploads and Celery, which serverless
 * functions cannot provide (plan §2.1). This client therefore always talks to
 * an absolute origin, never a co-located route.
 */

import type { FieldErrors } from "@/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8010";

export class ApiError extends Error {
  status: number;
  /** Per-field messages, keyed the same way the form schema keys fields. */
  fieldErrors: FieldErrors;
  code: string;

  constructor(message: string, status: number, fieldErrors: FieldErrors = {}, code = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.code = code;
  }

  /** True when the student simply hasn't paid yet — a prompt, not a failure. */
  get needsAccessFee(): boolean {
    return this.status === 403 && this.code === "access_fee_required";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  token?: string | null;
};

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, token, headers, ...rest } = options;

  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(isFormData ? {} : body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "include",
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { detail: text };
  }

  if (!response.ok) {
    const data = (payload ?? {}) as Record<string, unknown>;
    const detail =
      typeof data.detail === "string" ? data.detail : `Request failed (${response.status}).`;
    const fieldErrors: FieldErrors = {};
    for (const [key, value] of Object.entries(data)) {
      if (key === "detail" || key === "code") continue;
      fieldErrors[key] = Array.isArray(value) ? value.map(String) : [String(value)];
    }
    throw new ApiError(detail, response.status, fieldErrors, String(data.code ?? ""));
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, token?: string | null) => apiFetch<T>(path, { method: "GET", token }),
  post: <T>(path: string, body?: unknown, token?: string | null) =>
    apiFetch<T>(path, { method: "POST", body, token }),
  patch: <T>(path: string, body?: unknown, token?: string | null) =>
    apiFetch<T>(path, { method: "PATCH", body, token }),
  delete: <T>(path: string, token?: string | null) =>
    apiFetch<T>(path, { method: "DELETE", token }),
};
