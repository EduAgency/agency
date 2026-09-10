"use client";

import { useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { uploadDocument } from "@/lib/applications";
import { Alert, ProgressBar, StatusBadge } from "@/components/ui";
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
      <section className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
        <ProgressBar
          percent={checklist.percent_complete}
          label={`${checklist.verified_count} of ${checklist.required_count} required documents verified`}
        />
        {/* Both numbers are shown. Progress counts verified documents, so a
            student is never told they are nearly done on the strength of files
            nobody has checked yet (plan §4.2). */}
        {checklist.percent_uploaded > checklist.percent_complete && (
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            {checklist.uploaded_count} uploaded · {checklist.verified_count} verified. The bar counts
            verified documents only, so it moves once our team has checked each one.
          </p>
        )}
        {outstanding === 0 && checklist.required_count > 0 && (
          <p className="mt-3 text-sm font-medium text-emerald-700 dark:text-emerald-400">
            Everything required has been verified.
          </p>
        )}
      </section>

      {grouped.map((category) => (
        <section key={category.slug} className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {category.category}
            </h2>
            <span className="text-xs text-slate-500 tabular-nums dark:text-slate-400">
              {category.verified}/{category.total}
            </span>
          </div>

          <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
            {category.items.map((item) => (
              <ChecklistRow key={item.id} item={item} onChange={onChange} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ChecklistRow({
  item,
  onChange,
}: {
  item: ChecklistItem;
  onChange: () => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const isTask = item.evidence_type === "task";
  const canUpload = !isTask && item.status !== "verified" && item.status !== "waived";

  async function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    // Check locally first for an instant answer; the server checks again and wins.
    const maxBytes = item.max_file_size_mb * 1024 * 1024;
    if (file.size > maxBytes) {
      setError(`This file is ${(file.size / 1024 / 1024).toFixed(1)}MB. The limit is ${item.max_file_size_mb}MB.`);
      event.target.value = "";
      return;
    }
    const accepted = item.accepted_file_types ?? [];
    if (accepted.length) {
      const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
      if (!accepted.includes(extension)) {
        setError(`Accepted file types: ${accepted.join(", ")}.`);
        event.target.value = "";
        return;
      }
    }

    setBusy(true);
    setError("");
    try {
      await uploadDocument(item.id, file);
      onChange();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (err.fieldErrors.file?.[0] ?? err.message)
          : "That upload didn't go through. Try again.",
      );
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  return (
    <li className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-slate-900 dark:text-slate-100">{item.label}</h3>
            {!item.is_required && (
              <span className="text-xs text-slate-500 dark:text-slate-400">optional</span>
            )}
            {item.priority === "high" && item.status !== "verified" && (
              <span className="rounded bg-rose-50 px-1.5 py-0.5 text-xs text-rose-700 dark:bg-rose-950 dark:text-rose-300">
                priority
              </span>
            )}
          </div>
          {item.help_text && (
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{item.help_text}</p>
          )}
          {item.due_date && (
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
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
                type="file"
                onChange={handleFile}
                accept={item.accepted_file_types?.join(",") || undefined}
                className="hidden"
              />
              <button
                onClick={() => fileInput.current?.click()}
                disabled={busy}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {busy ? "Uploading…" : item.status === "rejected" ? "Replace" : "Upload"}
              </button>
            </>
          )}
        </div>
      </div>

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

      {error && <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">{error}</p>}
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
