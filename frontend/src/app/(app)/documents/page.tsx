"use client";

/**
 * The document vault: every file the student has uploaded, across every
 * application, in one place.
 *
 * The dashboard has linked here since it was written and the route did not
 * exist (docs/enterprise-readiness.md §A1). The API did — `/api/documents/`
 * returns each document with its full version history and its `shareable_key`,
 * which is the thing worth surfacing: a passport uploaded once satisfies the
 * passport requirement on every school at once, and a student who does not know
 * that will upload the same file five times.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "@/lib/auth/SessionProvider";
import { listDocuments } from "@/lib/applications";
import { Alert, BackLink, StatusBadge } from "@/components/ui";
import type { DocumentUpload, StudentDocument } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not uploaded",
  in_progress: "In progress",
  uploaded: "Uploaded",
  pending_review: "Waiting for review",
  verified: "Verified",
  rejected: "Needs redoing",
  waived: "Waived",
  not_applicable: "Not applicable",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en-NG", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function DocumentsPage() {
  const router = useRouter();
  const { session, loading, hasAccess, handleApiError } = useSession();
  const [documents, setDocuments] = useState<StudentDocument[]>([]);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!session) {
      router.replace("/login");
      return;
    }
    if (!hasAccess) {
      router.replace("/checkout");
      return;
    }
    listDocuments()
      .then((page) => setDocuments(page.results))
      .catch((err) => {
        if (!handleApiError(err)) setError("We couldn't load your documents. Please refresh.");
      })
      .finally(() => setReady(true));
  }, [loading, session, hasAccess, router, handleApiError]);

  if (loading || !ready) {
    return <div className="p-12 text-sm text-subtle">Loading…</div>;
  }

  const expiring = documents.filter((doc) => doc.is_expired);

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <BackLink href="/dashboard">Back to dashboard</BackLink>

      <header className="mt-6">
        <h1 className="text-2xl font-semibold text-ink">My documents</h1>
        <p className="mt-1 text-sm text-muted">
          Everything you have uploaded, across all your applications. Upload a document once and it
          counts towards every school that asks for it.
        </p>
      </header>

      {error && (
        <div className="mt-6">
          <Alert>{error}</Alert>
        </div>
      )}

      {expiring.length > 0 && (
        <div className="mt-6">
          <Alert>
            {expiring.length === 1
              ? "One of your documents has expired and will need replacing."
              : `${expiring.length} of your documents have expired and will need replacing.`}
          </Alert>
        </div>
      )}

      {documents.length === 0 ? (
        <div className="mt-10 rounded-xl border border-dashed border-field-line p-8 text-center">
          <p className="text-sm text-muted">
            You haven&apos;t uploaded anything yet. Documents you upload against a checklist appear
            here automatically.
          </p>
          <Link
            href="/dashboard"
            className="mt-4 inline-block text-sm font-medium text-ink underline underline-offset-4"
          >
            Go to my applications
          </Link>
        </div>
      ) : (
        <ul className="mt-10 space-y-4">
          {documents.map((document) => (
            <DocumentCard key={document.id} document={document} />
          ))}
        </ul>
      )}
    </div>
  );
}

function DocumentCard({ document }: { document: StudentDocument }) {
  const [showHistory, setShowHistory] = useState(false);
  const current = document.current;
  // Version 1 is the original, so anything above 1 means there is history worth
  // offering — a student whose document was rejected wants to see what changed.
  const previousVersions = document.uploads.filter((upload) => upload.id !== current?.id);

  return (
    <li className="rounded-xl border border-line p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-medium text-ink">{document.title}</h2>
          <p className="mt-0.5 text-sm text-muted">
            {document.category}
            {current && ` · ${formatBytes(current.size_bytes)}`}
            {current && ` · uploaded ${formatDate(current.created_at)}`}
          </p>
        </div>
        <StatusBadge
          status={document.review_status}
          label={STATUS_LABELS[document.review_status] ?? document.review_status}
        />
      </div>

      {document.review_status === "rejected" && current?.rejection_reason && (
        <p className="mt-3 rounded-lg bg-danger-bg px-3 py-2 text-sm text-danger">
          <span className="font-medium">Why it was rejected:</span> {current.rejection_reason}
        </p>
      )}

      {document.is_expired && (
        <p className="mt-3 text-sm text-warning">
          This document expired
          {document.expires_on && ` on ${formatDate(document.expires_on)}`}. Schools will not accept
          it — upload a current one.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        {current?.download_url && (
          <a
            href={current.download_url}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-ink underline underline-offset-4"
          >
            View document
            <span className="sr-only"> {document.title} (opens in a new tab)</span>
          </a>
        )}

        {previousVersions.length > 0 && (
          <button
            type="button"
            onClick={() => setShowHistory((open) => !open)}
            aria-expanded={showHistory}
            className="text-muted underline underline-offset-4"
          >
            {showHistory ? "Hide" : "Show"} earlier versions ({previousVersions.length})
          </button>
        )}
      </div>

      {showHistory && previousVersions.length > 0 && (
        <ul className="mt-4 space-y-2 border-t border-line pt-4">
          {previousVersions.map((upload) => (
            <VersionRow key={upload.id} upload={upload} />
          ))}
        </ul>
      )}
    </li>
  );
}

function VersionRow({ upload }: { upload: DocumentUpload }) {
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
      <span className="text-muted">
        <span className="font-mono text-xs">v{upload.version}</span> · {upload.original_filename} ·{" "}
        {formatDate(upload.created_at)}
      </span>
      <StatusBadge status={upload.status} label={STATUS_LABELS[upload.status] ?? upload.status} />
    </li>
  );
}
