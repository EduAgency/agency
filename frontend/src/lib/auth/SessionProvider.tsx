"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api";
import { fetchSession, logout as clearSession } from "./client";
import { clearTokens, getAccessToken, type Session } from "./store";

interface SessionContextValue {
  session: Session | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signOut: () => void;
  /** True once a confirmed payment has unlocked the dashboard. */
  hasAccess: boolean;
  /**
   * Send the user wherever a failed request says they belong: back to sign-in,
   * or to checkout if the only thing missing is the access fee. Returns true if
   * it handled the error, so callers can skip showing a message.
   */
  handleApiError: (error: unknown) => boolean;
}

const SessionContext = createContext<SessionContextValue | null>(null);

async function loadSession(): Promise<Session | null> {
  if (!getAccessToken()) return null;
  try {
    return await fetchSession();
  } catch {
    return null;
  }
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  // Every state update happens after an await, so the effect never triggers a
  // cascading synchronous render.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const next = await loadSession();
      if (cancelled) return;
      setSession(next);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const refresh = useCallback(async () => {
    setSession(await loadSession());
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setSession(null);
    setReloadKey((key) => key + 1);
  }, []);

  const handleApiError = useCallback(
    (error: unknown): boolean => {
      if (!(error instanceof ApiError)) return false;
      if (error.needsAccessFee) {
        router.replace("/checkout");
        return true;
      }
      if (error.status === 401) {
        clearTokens();
        setSession(null);
        router.replace("/login");
        return true;
      }
      return false;
    },
    [router],
  );

  const value = useMemo<SessionContextValue>(
    () => ({
      session,
      loading,
      refresh,
      signOut,
      hasAccess: Boolean(session?.student?.has_platform_access),
      handleApiError,
    }),
    [session, loading, refresh, signOut, handleApiError],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside a SessionProvider.");
  return context;
}
