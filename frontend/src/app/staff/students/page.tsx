"use client";

/**
 * Staff student directory.
 *
 * Search is debounced and server-side — the API already indexes email, name and
 * phone, so there is no reason to pull the whole table into the browser and
 * filter it there.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, LoadingRegion, ScrollableX, Skeleton, StatusBadge } from "@/components/ui";
import { listStudents, type StaffStudent } from "@/lib/staff";

export default function StudentsPage() {
  const [term, setTerm] = useState("");
  const [students, setStudents] = useState<StaffStudent[]>([]);
  const [total, setTotal] = useState(0);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const page = await listStudents({ search: term.trim() || undefined });
        if (cancelled) return;
        setStudents(page.results);
        setTotal(page.count);
        setError("");
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? "Your account does not have student management permission."
            : "We couldn't load the student list. Please refresh.",
        );
      } finally {
        if (!cancelled) setReady(true);
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [term]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="text-xl font-semibold text-ink">Students</h1>

      <div className="mt-4 max-w-md">
        <label htmlFor="student-search" className="sr-only">
          Search students by name, email or phone
        </label>
        <input
          id="student-search"
          type="search"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="Search by name, email or phone…"
          className="w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-subtle"
        />
      </div>

      <p aria-live="polite" className="mt-3 text-sm text-muted">
        {!ready ? "Loading…" : `${total} student${total === 1 ? "" : "s"}`}
        {term.trim() && ready && ` matching “${term.trim()}”`}
      </p>

      {error && (
        <div className="mt-6">
          <Alert>{error}</Alert>
        </div>
      )}

      {!ready ? (
        <LoadingRegion label="Loading students">
          <div className="mt-6 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        </LoadingRegion>
      ) : students.length === 0 && !error ? (
        <p className="mt-10 text-sm text-muted">No students match that search.</p>
      ) : (
        <ScrollableX label="Students" className="mt-6 rounded-xl border border-line">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <caption className="sr-only">
              Students, newest first. Select a name to open their record.
            </caption>
            <thead>
              <tr className="border-b border-line bg-sunken">
                <th scope="col" className="px-4 py-2.5 font-medium text-ink">
                  Name
                </th>
                <th scope="col" className="px-4 py-2.5 font-medium text-ink">
                  Email
                </th>
                <th scope="col" className="px-4 py-2.5 font-medium text-ink">
                  Stage
                </th>
                <th scope="col" className="px-4 py-2.5 font-medium text-ink">
                  Access
                </th>
              </tr>
            </thead>
            <tbody>
              {students.map((student) => (
                <tr key={student.id} className="border-b border-line last:border-0 hover:bg-sunken">
                  <th scope="row" className="px-4 py-2.5 font-normal">
                    <Link
                      href={`/staff/students/${student.id}`}
                      className="font-medium text-ink underline-offset-4 hover:underline"
                    >
                      {student.user.full_name || "—"}
                    </Link>
                  </th>
                  <td className="px-4 py-2.5 text-muted">{student.user.email}</td>
                  <td className="px-4 py-2.5 text-muted">{student.stage_display}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge
                      status={student.has_platform_access ? "verified" : "not_started"}
                      label={student.has_platform_access ? "Paid" : "Not paid"}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableX>
      )}
    </div>
  );
}
