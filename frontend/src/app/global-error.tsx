"use client";

/**
 * Last resort: catches errors thrown by the root layout itself, where the
 * normal `error.tsx` boundary cannot run because the layout that would render
 * it is the thing that failed.
 *
 * This file must supply its own `html` and `body`, and cannot rely on the app's
 * fonts or providers — so the styling here is deliberately self-contained.
 */

import { useEffect } from "react";
import { reportError } from "@/lib/report-error";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportError(error, { boundary: "root-layout", digest: error.digest });
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem 1.25rem",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          background: "#ffffff",
          color: "#0f172a",
        }}
      >
        <main style={{ maxWidth: "28rem" }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 600, margin: 0 }}>Nasuru is unavailable</h1>
          <p style={{ marginTop: "0.75rem", lineHeight: 1.6, color: "#475569" }}>
            The application failed to start. This is a fault on our side, not with your account.
            Your documents and answers are safe.
          </p>
          <button
            onClick={reset}
            style={{
              marginTop: "1.75rem",
              borderRadius: "0.5rem",
              border: "none",
              background: "#0f172a",
              color: "#ffffff",
              padding: "0.7rem 1.25rem",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Reload
          </button>
          {error.digest && (
            <p style={{ marginTop: "1.75rem", fontSize: "0.875rem", color: "#64748b" }}>
              Reference: <code>{error.digest}</code>
            </p>
          )}
        </main>
      </body>
    </html>
  );
}
