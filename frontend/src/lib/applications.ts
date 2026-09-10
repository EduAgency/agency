"use client";

import { authFetch } from "@/lib/auth/client";
import type { Application, Checklist, ChecklistItem, StudentDocument } from "@/types";

interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export function listApplications() {
  return authFetch<Paginated<Application>>("/api/applications/");
}

export function getApplication(id: string) {
  return authFetch<Application>(`/api/applications/${id}/`);
}

export function getChecklist(applicationId: string) {
  return authFetch<Checklist>(`/api/applications/${applicationId}/checklist/`);
}

export function createApplication(input: { school: string; programme?: string; intake: string }) {
  return authFetch<Application>("/api/applications/", { method: "POST", body: input });
}

/** Upload against one checklist item. Multipart, so no JSON content-type. */
export function uploadDocument(itemId: string, file: File, title?: string) {
  const body = new FormData();
  body.append("file", file);
  if (title) body.append("title", title);
  return authFetch<ChecklistItem>(`/api/checklist-items/${itemId}/upload/`, {
    method: "POST",
    body,
  });
}

/**
 * The document vault — every document the student has uploaded, across all
 * applications. The API has supported this since the API layer landed; the
 * dashboard linked to `/documents` and the page did not exist
 * (docs/enterprise-readiness.md §A1).
 */
export function listDocuments() {
  return authFetch<Paginated<StudentDocument>>("/api/documents/");
}

export function listSchools() {
  return authFetch<
    Paginated<{
      id: string;
      name: string;
      country_name: string | null;
      programmes: { id: string; name: string; intakes: string[] }[];
    }>
  >("/api/schools/");
}
