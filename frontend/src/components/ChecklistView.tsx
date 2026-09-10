"use client";

import { useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, ProgressBar, StatusBadge } from "@/components/ui";
import { useAnnouncer } from "@/components/ui/Announcer";
import { formatBytes, uploadWithProgress } from "@/lib/upload";
import type { Checklist, ChecklistItem } from "@/types";

/**
 * The checklist, grouped by category — the same shape as the spreadsheet
 * tracker it replaces, so the structure is already familiar.
 */
export function ChecklistView({
  checklist,
  onChange,
}: {
  checklist: Checklist;
  onChange: () => void;
}) {
  const grouped = useMemo(() => {
    const map = new Map<string, ChecklistItem[]>();
    for (const item of checklist.items) {
      const bucket = map.get(item.category_slug) ?? [];
      bucket.push(item);
      map.set(item.category_slug, bucket);
    }
    return checklist.categories.map((category) => ({
      ...category,
      items: map.get(category.slug) ?? [],
    }));
  }, [checklist]);

  const outstanding = checklist.required_count - checklist.verified_count;

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-line p-5">
        <ProgressBar
          percent={checklist.percent_complete}
          label={`${checklist.verified_count} of ${checklist.required_count} required documents verified`}
        />
        {/* Both numbers are shown. Progress counts verified documents, so a
            student is never told they are nearly done on the strength of files
            nobody has checked yet (plan §4.2). */}
        {checklist.percent_uploaded > checklist.percent_complete && (
          <p className="mt-3 text-xs text-subtle">
            {checklist.uploaded_count} uploaded · {checklist.verified_count} verified. The bar
            counts verified documents only, so it moves once our team has checked each one.
          </p>
        )}
        {outstanding === 0 && checklist.required_count > 0 && (
          <p className="mt-3 text-sm font-medium text-success">
            Everything required has been verified.
          </p>
        )}
      </section>

      {grouped.map((category) => (
        <section key={category.slug} className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="text-base font-semibold text-ink">{category.category}</h2>
            <span className="text-xs text-subtle tabular-nums">
              {category.verified}/{category.total}
            </span>
          </div>

          <ul className="divide-y divide-line rounded-xl border border-line">
            {category.items.map((item) => (
              <ChecklistRow key={item.id} item={item} onChange={onChange} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ChecklistRow({ item, onChange }: { item: ChecklistItem; onChange: () => void }) {
  const fileInput = useRef<HTMLInputElement>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const [percent, setPercent] = useState<number | null>(null);
  const [retrying, setRetrying] = useState("");
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const { announce, toast } = useAnnouncer();

  const isTask = item.evidence_type === "task";
  const canUpload = !isTask && item.status !== "verified" && item.status !== "waived";
  const busy = percent !== null;

  /** Local pre-check for an instant answer; the server checks again and wins. */
  function reject(file: File): string | null {
    const maxBytes = item.max_file_size_mb * 1024 * 1024;
    if (file.size > maxBytes) {
      return `This file is ${formatBytes(file.size)}. The limit is ${item.max_file_size_mb}MB.`;
    }
    const accepted = item.accepted_file_types ?? [];
    if (accepted.length) {
      const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
      if (!accepted.includes(extension)) return `Accepted file types: ${accepted.join(", ")}.`;
    }
    return null;
  }

  async function upload(file: File) {
    const problem = reject(file);
    if (problem) {
      setError(problem);
      return;
    }

    setError("");
    setRetrying("");
    setPercent(0);
    announce(`Uploading ${item.label}`);

    const body = new FormData();
    body.append("file", file);

    const handle = uploadWithProgress<unknown>(`/api/checklist-items/${item.id}/upload/`, body, {
      onProgress: setPercent,
      onRetry: (attempt, of) => setRetrying(`Connection dropped — retrying (${attempt} of ${of})…`),
    });
    cancelRef.current = handle.cancel;

    try {
      await handle.promise;
      toast(`${item.label} uploaded`, "success");
      onChange();
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        announce("Upload cancelled");
        return;
      }
      setError(
        err instanceof ApiError
          ? (err.fieldErrors.file?.[0] ?? err.message)
          : "That upload didn't go through. Check your connection and try again.",
      );
    } finally {
      setPercent(null);
      setRetrying("");
      cancelRef.current = null;
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <li
      className={`p-4 transition ${dragging ? "bg-info-bg ring-2 ring-info ring-inset" : ""}`}
      /* Drag-and-drop is an enhancement on top of the button, never the only
         way in: a keyboard user reaches the same action through the control. */
      onDragOver={
        canUpload
          ? (e) => {
              e.preventDefault();
              setDragging(true);
            }
          : undefined
      }
      onDragLeave={() => setDragging(false)}
      onDrop={
        canUpload
          ? (e) => {
              e.preventDefault();
              setDragging(false);
              const file = e.dataTransfer.files?.[0];
              if (file) void upload(file);
            }
          : undefined
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-ink">{item.label}</h3>
            {!item.is_required && <span className="text-xs text-subtle">optional</span>}
            {item.priority === "high" && item.status !== "verified" && (
              <span className="rounded bg-danger-bg px-1.5 py-0.5 text-xs text-danger">
                priority
              </span>
            )}
          </div>
          {item.help_text && <p className="mt-1 text-sm text-muted">{item.help_text}</p>}
          {item.due_date && (
            <p className="mt-1 text-xs text-subtle">
              Due {new Date(item.due_date).toLocaleDateString()}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <StatusBadge status={item.status} label={statusLabel(item)} />
          {canUpload && (
            <>
              <input
                ref={fileInput}
                id={`upload-${item.id}`}
                type="file"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void upload(file);
                }}
                accept={item.accepted_file_types?.join(",") || undefined}
                /* `capture` is deliberately absent: on a phone this keeps both
                   "take a photo" and "choose a file" available, rather than
                   forcing the camera on someone who already has a scan. */
                className="sr-only"
              />
              <label
                htmlFor={`upload-${item.id}`}
                className={`cursor-pointer rounded-lg border border-field-line px-3 py-1.5 text-xs font-medium text-muted transition hover:bg-sunken ${
                  busy ? "pointer-events-none opacity-50" : ""
                }`}
              >
                {item.status === "rejected" ? "Replace" : "Upload"}
                <span className="sr-only"> {item.label}</span>
              </label>
            </>
          )}
        </div>
      </div>

      {busy && (
        <div className="mt-3">
          <ProgressBar
            percent={percent}
            label={retrying || `Uploading ${item.label} — ${percent}%`}
          />
          <button
            type="button"
            onClick={() => cancelRef.current?.()}
            className="mt-1 text-xs text-muted underline underline-offset-2 hover:text-ink"
          >
            Cancel upload
          </button>
        </div>
      )}

      {/* A rejection always arrives with its reason — the server refuses one
          without it, so this is never an empty "rejected" (plan §10). */}
      {item.status === "rejected" && item.rejection_reason && (
        <div className="mt-3">
          <Alert>
            <span className="font-medium">Needs another look: </span>
            {item.rejection_reason}
          </Alert>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      )}
    </li>
  );
}

function statusLabel(item: ChecklistItem): string {
  if (item.evidence_type === "task" && item.status === "not_started") return "To do";
  return {
    not_started: "Not started",
    in_progress: "In progress",
    uploaded: "Uploaded",
    pending_review: "In review",
    verified: "Verified",
    rejected: "Needs attention",
    waived: "Waived",
    not_applicable: "Not applicable",
  }[item.status];
}
