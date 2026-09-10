"use client";

import { api, ApiError, apiFetch } from "@/lib/api";
import { clearTokens, getAccessToken, getRefreshToken, setTokens, type Session } from "./store";

/**
 * Authenticated request with one automatic token refresh.
 *
 * A 401 on a 30-minute access token is routine, not a failure — refresh once
 * and replay. A second 401 means the session is genuinely over.
 */
export async function authFetch<T>(
  path: string,
  options: Parameters<typeof apiFetch>[1] = {},
): Promise<T> {
  try {
    return await apiFetch<T>(path, { ...options, token: getAccessToken() });
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;

    const refresh = getRefreshToken();
    if (!refresh) {
      clearTokens();
      throw error;
    }

    try {
      const renewed = await api.post<{ access: string; refresh?: string }>(
        "/api/auth/token/refresh/",
        { refresh },
      );
      setTokens(renewed);
    } catch {
      clearTokens();
      throw error;
    }

    return apiFetch<T>(path, { ...options, token: getAccessToken() });
  }
}

interface AuthResponse {
  user: Session["user"];
  tokens: { access: string; refresh: string };
}

export async function login(email: string, password: string): Promise<Session["user"]> {
  const response = await api.post<AuthResponse>("/api/auth/login/", { email, password });
  setTokens(response.tokens);
  return response.user;
}

export interface SignupInput {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  referral_code?: string;
  accept_terms: boolean;
  marketing_opt_in?: boolean;
}

export async function signup(input: SignupInput): Promise<Session["user"]> {
  const response = await api.post<AuthResponse>("/api/auth/signup/", input);
  setTokens(response.tokens);
  return response.user;
}

export function logout() {
  clearTokens();
}

/**
 * Password recovery and email confirmation.
 *
 * These endpoints have existed since the API layer landed — `password_reset` is
 * even given its own 5/hour throttle scope — but nothing in the app called
 * them, so a student who forgot their password had no way back into an account
 * they had already paid for (docs/enterprise-readiness.md §A2).
 */

/**
 * Always resolves with the same message whether or not the address is
 * registered. The server is deliberate about this and so is the UI: a reset
 * form that distinguishes the two cases is an account-enumeration oracle.
 */
export function requestPasswordReset(email: string) {
  return api.post<{ detail: string }>("/api/auth/password/reset/", { email });
}

export function confirmPasswordReset(token: string, newPassword: string) {
  return api.post<{ detail: string }>("/api/auth/password/reset/confirm/", {
    token,
    new_password: newPassword,
  });
}

export function verifyEmail(token: string) {
  return api.post<{ detail: string }>("/api/auth/verify-email/", { token });
}

/** Requires a signed-in user — the server reads the address off the session. */
export function resendVerification() {
  return authFetch<{ detail: string }>("/api/auth/resend-verification/", { method: "POST" });
}

export function fetchSession(): Promise<Session> {
  return authFetch<Session>("/api/auth/me/");
}

export function checkReferralCode(code: string) {
  return api.get<{ valid: boolean; referrer_first_name?: string }>(
    `/api/referrals/check/?code=${encodeURIComponent(code)}`,
  );
}
