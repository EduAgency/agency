"use client";

/**
 * One student, on one page.
 *
 * Django admin spread this across six changelists — user, profile, applications,
 * checklist items, payments, referrals — so answering "where is this person
 * stuck?" meant six tabs and a mental join. Everything a counsellor needs to
 * answer a phone call is here.
 */

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, BackLink, LoadingRegion, Skeleton, StatusBadge } from "@/components/ui";
import { getStudent, type StaffStudent } from "@/lib/staff";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-NG", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function StudentRecordPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [student, setStudent] = useState<StaffStudent | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getStudent(id)
      .then(setStudent)
      .catch((err) => {
        setError(
          err instanceof ApiError && err.status === 404
            ? "No student with that reference."
            : "We couldn't load this student. Please refresh.",
        );
      })
      .finally(() => setReady(true));
  }, [id]);

  if (!ready) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-8">
        <LoadingRegion label="Loading student record">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="mt-6 h-48 w-full" />
        </LoadingRegion>
      </div>
    );
  }

  if (error || !student) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-12">
        <BackLink href="/staff/students">Back to students</BackLink>
        <div className="mt-6">
          <Alert>{error || "Not found."}</Alert>
        </div>
      </div>
    );
  }

  const contact = [
    { label: "Email", value: student.user.email },
    { label: "Phone", value: student.user.phone || "—" },
    { label: "WhatsApp", value: student.whatsapp || "—" },
  ];

  const profile = [
    { label: "Date of birth", value: formatDate(student.date_of_birth) },
    { label: "Nationality", value: student.nationality || "—" },
    {
      label: "Lives in",
      value: [student.state_of_residence, student.country_of_residence].filter(Boolean).join(", ") || "—",
    },
    { label: "Came from", value: student.source || "—" },
    { label: "Referral code", value: student.referral_code },
  ];

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <BackLink href="/staff/students">Back to students</BackLink>

      <header className="mt-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">
            {student.user.full_name || student.user.email}
          </h1>
          <p className="mt-1 text-sm text-muted">{student.stage_display}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            status={student.has_platform_access ? "verified" : "not_started"}
            label={
              student.has_platform_access
                ? `Paid ${formatDate(student.access_granted_at)}`
                : "Access fee not paid"
            }
          />
          <StatusBadge
            status={student.user.email_verified_at ? "verified" : "pending_review"}
            label={student.user.email_verified_at ? "Email confirmed" : "Email unconfirmed"}
          />
        </div>
      </header>

      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        <DetailCard title="Contact" rows={contact} />
        <DetailCard title="Profile" rows={profile} />
      </div>

      <section className="mt-8 rounded-xl border border-line p-5">
        <h2 className="text-base font-semibold text-ink">Applications and documents</h2>
        <p className="mt-2 text-sm text-muted">
          Documents waiting on a decision for this student appear in the{" "}
          <Link href="/staff/review" className="underline underline-offset-2">
            review queue
          </Link>
          , oldest first.
        </p>
        {/* Honest placeholder rather than a fake panel: the per-student
            application and payment timeline needs endpoints that return them
            scoped to one student, which the admin API does not expose yet. */}
        <p className="mt-4 rounded-lg bg-sunken p-3 text-xs text-muted">
          A per-student application timeline and payment history are not shown here yet — the admin
          API does not expose those scoped to a single student. Tracked in
          docs/enterprise-readiness.md, Phase 3.
        </p>
      </section>
    </div>
  );
}

function DetailCard({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; value: string }[];
}) {
  return (
    <section className="rounded-xl border border-line p-5">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <dl className="mt-3 space-y-2 text-sm">
        {rows.map((row) => (
          <div key={row.label} className="flex flex-wrap justify-between gap-2">
            <dt className="text-muted">{row.label}</dt>
            <dd className="text-right text-ink">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
