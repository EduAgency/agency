"use client";

/**
 * The composer's API client.
 *
 * Mirrors apps/blog/api.py. Two things worth knowing before using it:
 *
 * * Posts are addressed by **slug**, not id, on the staff routes too. The slug
 *   is stable from the first save and frozen at publish, so it is a safe handle.
 * * Nothing here publishes implicitly. `savePost` only ever writes a draft's
 *   fields; going live is `publishPost`, which the server gates on a separate
 *   permission and its own pre-flight checks.
 */

import { authFetch } from "@/lib/auth/client";
import type { Paginated } from "@/lib/staff";

export type PostStatus = "draft" | "in_review" | "scheduled" | "published" | "archived";
export type AiInvolvement = "none" | "outline" | "draft" | "edit";

export const STATUS_LABELS: Record<PostStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  scheduled: "Scheduled",
  published: "Published",
  archived: "Off the site",
};

export const AI_INVOLVEMENT_LABELS: Record<AiInvolvement, string> = {
  none: "Written entirely by a person",
  outline: "Outline suggested by AI",
  draft: "First draft by AI, edited by a person",
  edit: "Human draft, AI-assisted editing",
};

export interface TocEntry {
  level: number;
  text: string;
  anchor: string;
}

export interface AdminPost {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  body: string;
  body_html: string;
  toc: TocEntry[];
  status: PostStatus;
  published_at: string | null;
  category_id: string | null;
  tag_ids: string[];
  author_name: string;
  published_by_name: string;
  hero_image: string | null;
  hero_alt: string;
  hero_caption: string;
  hero_credit: string;
  comments_closed: boolean;
  comment_count: number;
  pending_comment_count: number;
  meta_title: string;
  meta_description: string;
  canonical_url: string;
  noindex: boolean;
  focus_keyword: string;
  ai_involvement: AiInvolvement;
  ai_notes: string;
  style_override_reason: string;
  reading_minutes: number;
  view_count: number;
  revision_count: number;
  created_at: string;
  updated_at: string;
}

export interface Preflight {
  ok: boolean;
  blockers: string[];
  warnings: string[];
}

export interface Revision {
  id: string;
  title: string;
  created_at: string;
  editor_name: string;
  note: string;
}

export interface BlogTaxonomy {
  id: string;
  name: string;
  slug: string;
  post_count?: number;
}

export function listAdminPosts(params: { status?: string; search?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.search) query.set("search", params.search);
  if (params.page && params.page > 1) query.set("page", String(params.page));
  const suffix = query.toString() ? `?${query}` : "";
  return authFetch<Paginated<AdminPost>>(`/api/admin/blog/posts/${suffix}`);
}

export function getAdminPost(slug: string) {
  return authFetch<AdminPost>(`/api/admin/blog/posts/${encodeURIComponent(slug)}/`);
}

export function createPost(body: Partial<AdminPost>) {
  return authFetch<AdminPost>("/api/admin/blog/posts/", {
    method: "POST",
    body,
  });
}

export function savePost(slug: string, body: Partial<AdminPost>) {
  return authFetch<AdminPost>(`/api/admin/blog/posts/${encodeURIComponent(slug)}/`, {
    method: "PATCH",
    body,
  });
}

export function preflight(slug: string) {
  return authFetch<Preflight>(`/api/admin/blog/posts/${encodeURIComponent(slug)}/preflight/`);
}

export function publishPost(
  slug: string,
  options: { publish_at?: string | null; force?: boolean } = {},
) {
  return authFetch<AdminPost>(`/api/admin/blog/posts/${encodeURIComponent(slug)}/publish/`, {
    method: "POST",
    body: options,
  });
}

export function unpublishPost(slug: string, reason = "") {
  return authFetch<AdminPost>(`/api/admin/blog/posts/${encodeURIComponent(slug)}/unpublish/`, {
    method: "POST",
    body: { reason },
  });
}

export function listRevisions(slug: string) {
  return authFetch<Revision[]>(`/api/admin/blog/posts/${encodeURIComponent(slug)}/revisions/`);
}

export function restoreRevision(slug: string, revisionId: string) {
  return authFetch<AdminPost>(
    `/api/admin/blog/posts/${encodeURIComponent(slug)}/revisions/${revisionId}/restore/`,
    { method: "POST" },
  );
}

export function listAdminCategories() {
  return authFetch<BlogTaxonomy[]>("/api/admin/blog/categories/");
}

export function listAdminTags() {
  return authFetch<BlogTaxonomy[]>("/api/admin/blog/tags/");
}

export function createTag(name: string) {
  return authFetch<BlogTaxonomy>("/api/admin/blog/tags/", {
    method: "POST",
    body: { name },
  });
}

// ---------------------------------------------------------------------------
// AI assist
// ---------------------------------------------------------------------------

export interface OutlineSection {
  heading: string;
  covers: string[];
}

export interface ArticleOutline {
  working_title: string;
  reader_question: string;
  excerpt: string;
  sections: OutlineSection[];
  suggested_tags: string[];
  what_we_cannot_claim: string[];
}

export interface SeoSuggestion {
  meta_title: string;
  meta_description: string;
  focus_keyword: string;
  slug: string;
  excerpt: string;
  internal_link_ideas: string[];
}

export interface TitleSuggestion {
  titles: string[];
  recommended: string;
  why: string;
}

export interface HouseStyleFlag {
  kind: "claim" | "country" | "figure";
  excerpt: string;
  why: string;
}

export interface HouseStyleReview {
  ok: boolean;
  flags: HouseStyleFlag[];
}

export interface AiResponse {
  outline?: ArticleOutline;
  body?: string;
  seo?: SeoSuggestion;
  titles?: TitleSuggestion;
  review?: HouseStyleReview;
}

type AiTask = "outline" | "draft" | "seo" | "titles" | "rewrite" | "review";

export function aiStatus() {
  return authFetch<{ enabled: boolean; model: string }>("/api/admin/blog/ai/status/");
}

/**
 * One endpoint for every assist. The server validates which fields each task
 * needs, so a missing field comes back as a field error rather than a silent
 * empty suggestion.
 */
export function aiAssist(task: AiTask, payload: Record<string, unknown>) {
  return authFetch<AiResponse>("/api/admin/blog/ai/", {
    method: "POST",
    body: { task, ...payload },
  });
}

export const HOUSE_STYLE_FLAG_LABELS: Record<HouseStyleFlag["kind"], string> = {
  claim: "Unsupportable claim",
  country: "Names a place",
  figure: "Unverified figure",
};
