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

export function fetchSession(): Promise<Session> {
  return authFetch<Session>("/api/auth/me/");
}

export function checkReferralCode(code: string) {
  return api.get<{ valid: boolean; referrer_first_name?: string }>(
    `/api/referrals/check/?code=${encodeURIComponent(code)}`,
  );
}
