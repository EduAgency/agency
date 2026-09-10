"use client";

/**
 * Document upload with progress, retry and cancellation.
 *
 * `fetch` cannot report upload progress — there is no readable stream for the
 * request body in any shipping browser — so this uses `XMLHttpRequest`, which
 * has exposed `upload.onprogress` for twenty years.
 *
 * Why it matters here specifically (docs/enterprise-readiness.md §B8): this is
 * the product's central action, performed by students on Nigerian mobile data,
 * uploading multi-megabyte scans of passports and transcripts. A silent upload
 * that can fail at 90% with nothing but "Try again" is the most likely single
 * cause of abandonment in the funnel.
 */

import { API_BASE_URL, ApiError } from "@/lib/api";
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from "@/lib/auth/store";
import { api } from "@/lib/api";

export interface UploadHandle<T> {
  promise: Promise<T>;
  cancel: () => void;
}

interface UploadOptions {
  /** 0–100, fired as the bytes leave the device. */
  onProgress?: (percent: number) => void;
  /** Called before each retry, so the UI can say "Retrying (2 of 3)…". */
  onRetry?: (attempt: number, of: number) => void;
  maxAttempts?: number;
}

/** Network blips and 5xx are worth retrying. A 400 never is. */
function isRetryable(status: number): boolean {
  return status === 0 || status === 408 || status === 429 || status >= 500;
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

function once<T>(
  path: string,
  body: FormData,
  token: string | null,
  signal: AbortSignal,
  onProgress?: (percent: number) => void,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}${path}`);
    request.withCredentials = true;
    request.setRequestHeader("Accept", "application/json");
    if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);
    // Content-Type is deliberately unset: the browser must add the multipart
    // boundary itself, and setting it by hand breaks the request body.

    request.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return;
      // Cap at 99: the last percent belongs to the server writing the file to
      // object storage, and showing 100% before that lands reads as a lie.
      onProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
    };

    request.onload = () => {
      let payload: unknown = null;
      try {
        payload = request.responseText ? JSON.parse(request.responseText) : null;
      } catch {
        payload = { detail: request.responseText };
      }

      if (request.status >= 200 && request.status < 300) {
        onProgress?.(100);
        resolve(payload as T);
        return;
      }

      const data = (payload ?? {}) as Record<string, unknown>;
      const detail =
        typeof data.detail === "string" ? data.detail : `Upload failed (${request.status}).`;
      const fieldErrors: Record<string, string[]> = {};
      for (const [key, value] of Object.entries(data)) {
        if (key === "detail" || key === "code") continue;
        fieldErrors[key] = Array.isArray(value) ? value.map(String) : [String(value)];
      }
      reject(new ApiError(detail, request.status, fieldErrors, String(data.code ?? "")));
    };

    request.onerror = () => reject(new ApiError("Network error during upload.", 0));
    request.ontimeout = () => reject(new ApiError("The upload timed out.", 408));
    request.onabort = () => reject(new DOMException("Aborted", "AbortError"));

    signal.addEventListener("abort", () => request.abort());
    request.send(body);
  });
}

/**
 * Upload with one token refresh and bounded retries.
 *
 * Mirrors `authFetch`: a 401 on a 30-minute access token is routine, so refresh
 * once and replay rather than throwing the student back to sign-in mid-upload.
 */
export function uploadWithProgress<T>(
  path: string,
  body: FormData,
  options: UploadOptions = {},
): UploadHandle<T> {
  const { onProgress, onRetry, maxAttempts = 3 } = options;
  const controller = new AbortController();

  const promise = (async (): Promise<T> => {
    let lastError: unknown;

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      if (attempt > 1) {
        onRetry?.(attempt, maxAttempts);
        onProgress?.(0);
        // Exponential backoff: 1s, then 2s. Long enough for a handover between
        // cell towers to settle, short enough that nobody gives up waiting.
        await wait(2 ** (attempt - 2) * 1000, controller.signal);
      }

      try {
        return await once<T>(path, body, getAccessToken(), controller.signal, onProgress);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") throw error;
        lastError = error;

        if (error instanceof ApiError && error.status === 401) {
          const refresh = getRefreshToken();
          if (!refresh) {
            clearTokens();
            throw error;
          }
          try {
            setTokens(
              await api.post<{ access: string; refresh?: string }>("/api/auth/token/refresh/", {
                refresh,
              }),
            );
            // Replay immediately on a fresh token; this is not a failed attempt.
            return await once<T>(path, body, getAccessToken(), controller.signal, onProgress);
          } catch {
            clearTokens();
            throw error;
          }
        }

        if (error instanceof ApiError && !isRetryable(error.status)) throw error;
      }
    }

    throw lastError;
  })();

  return { promise, cancel: () => controller.abort() };
}

/** Human-readable size, used in upload UI and the document vault. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
