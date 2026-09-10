"use client";

/**
 * Session handling.
 *
 * Tokens live in memory with a localStorage mirror so a refresh doesn't sign
 * the user out. That mirror is readable by any script on the origin, which is
 * the accepted trade-off for a token-based SPA; the mitigation is a short
 * access-token lifetime (30 minutes) and rotation on refresh. If this app ever
 * handles payouts directly rather than through a gateway's hosted page, move
 * to httpOnly cookies instead.
 */

import type { StudentProfile } from "@/types";

const ACCESS_KEY = "nasuru.access";
const REFRESH_KEY = "nasuru.refresh";

export interface SessionUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  email_verified_at: string | null;
}

export interface Session {
  user: SessionUser;
  student?: StudentProfile;
  admin?: Record<string, unknown>;
}

let accessToken: string | null = null;

function safeStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    // Private mode, or site data blocked. The session still works for this tab.
    return null;
  }
}

export function getAccessToken(): string | null {
  if (accessToken) return accessToken;
  accessToken = safeStorage()?.getItem(ACCESS_KEY) ?? null;
  return accessToken;
}

export function getRefreshToken(): string | null {
  return safeStorage()?.getItem(REFRESH_KEY) ?? null;
}

export function setTokens(tokens: { access: string; refresh?: string }) {
  accessToken = tokens.access;
  const storage = safeStorage();
  storage?.setItem(ACCESS_KEY, tokens.access);
  if (tokens.refresh) storage?.setItem(REFRESH_KEY, tokens.refresh);
}

export function clearTokens() {
  accessToken = null;
  const storage = safeStorage();
  storage?.removeItem(ACCESS_KEY);
  storage?.removeItem(REFRESH_KEY);
}
