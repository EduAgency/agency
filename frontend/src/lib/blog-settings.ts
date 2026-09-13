"use client";

/**
 * The staff side of the blog settings, authors, comments and FAQ entries.
 *
 * Kept separate from `blog-admin.ts` (the composer) because these are a
 * different job with a different permission: the composer needs
 * `can_write_content`, most of this needs `can_publish_content`.
 */

import { authFetch } from "@/lib/auth/client";
import type { Paginated } from "@/lib/staff";

export type ExcerptSource = "manual" | "auto" | "manual_then_auto";
export type ListingLayout = "featured" | "grid" | "list";

/** Every editable setting. Mirrors apps/blog/settings_model.BlogSettings. */
export interface BlogSettings {
  posts_per_page: number;
  homepage_show_latest: boolean;
  homepage_article_count: number;
  homepage_section_title: string;
  listing_layout: ListingLayout;
  show_reading_time: boolean;
  show_author_byline: boolean;
  show_published_date: boolean;
  related_post_count: number;

  excerpt_source: ExcerptSource;
  excerpt_length: number;
  excerpt_required_to_publish: boolean;
  read_more_label: string;

  featured_image_required: boolean;
  featured_image_aspect: string;
  show_featured_on_listing: boolean;
  show_featured_on_detail: boolean;
  default_featured_image: string | null;

  comments_enabled: boolean;
  comments_require_approval: boolean;
  comments_require_email: boolean;
  comments_allow_replies: boolean;
  comments_close_after_days: number;
  comments_notify_staff: boolean;
  comments_max_links: number;
  comments_min_seconds: number;
  comments_blocklist: string;
  comments_per_hour_per_ip: number;

  author_pages_enabled: boolean;
  show_author_bio_on_article: boolean;

  meta_title_template: string;
  default_meta_description: string;
  default_og_image: string | null;
  twitter_site: string;
  google_site_verification: string;
  bing_site_verification: string;
  analytics_measurement_id: string;
  feed_full_text: boolean;
  feed_item_count: number;
  sitemap_include_authors: boolean;
  noindex_tag_pages: boolean;

  featured_aspect_ratio: number;
  updated_at: string;
}

export function getSettings() {
  return authFetch<BlogSettings>("/api/admin/blog/settings/");
}

export function saveSettings(patch: Partial<BlogSettings>) {
  return authFetch<BlogSettings>("/api/admin/blog/settings/", {
    method: "PATCH",
    body: patch,
  });
}

// ---------------------------------------------------------------------------
// Authors
// ---------------------------------------------------------------------------

export interface AuthorProfile {
  id: string;
  user: string;
  user_email: string;
  display_name: string;
  slug: string;
  headline: string;
  bio: string;
  credentials: string;
  avatar: string | null;
  avatar_alt: string;
  website: string;
  linkedin_url: string;
  x_url: string;
  is_public: boolean;
  show_in_directory: boolean;
  post_count: number;
  has_public_page: boolean;
  created_at: string;
  updated_at: string;
}

export function listAuthors() {
  return authFetch<AuthorProfile[]>("/api/admin/blog/authors/");
}

export function getMyAuthorProfile() {
  return authFetch<AuthorProfile>("/api/admin/blog/authors/me/");
}

export function saveMyAuthorProfile(patch: Partial<AuthorProfile>) {
  return authFetch<AuthorProfile>("/api/admin/blog/authors/me/", {
    method: "PATCH",
    body: patch,
  });
}

export function saveAuthor(id: string, patch: Partial<AuthorProfile>) {
  return authFetch<AuthorProfile>(`/api/admin/blog/authors/${id}/`, {
    method: "PATCH",
    body: patch,
  });
}

// ---------------------------------------------------------------------------
// Comments
// ---------------------------------------------------------------------------

export type CommentStatus = "pending" | "approved" | "spam" | "rejected";

export const COMMENT_STATUS_LABELS: Record<CommentStatus, string> = {
  pending: "Waiting for review",
  approved: "Published",
  spam: "Spam",
  rejected: "Rejected",
};

export interface AdminComment {
  id: string;
  post_title: string;
  post_slug: string;
  author_name: string;
  /** Moderator-only. Never reaches a public serializer. */
  email: string;
  website: string;
  body: string;
  status: CommentStatus;
  flagged_reason: string;
  is_pinned: boolean;
  is_from_staff: boolean;
  parent: string | null;
  parent_body: string;
  moderated_by_name: string;
  moderated_at: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface CommentSummary {
  pending: number;
  approved: number;
  spam: number;
  rejected: number;
}

export function listComments(
  params: { status?: string; post?: string; search?: string; page?: number } = {},
) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.post) query.set("post", params.post);
  if (params.search) query.set("search", params.search);
  if (params.page && params.page > 1) query.set("page", String(params.page));
  const suffix = query.toString() ? `?${query}` : "";
  return authFetch<Paginated<AdminComment>>(`/api/admin/blog/comments/${suffix}`);
}

export function commentSummary() {
  return authFetch<CommentSummary>("/api/admin/blog/comments/summary/");
}

export function moderateComments(commentIds: string[], status: CommentStatus) {
  return authFetch<{ changed: number }>("/api/admin/blog/comments/moderate/", {
    method: "POST",
    body: { status, comment_ids: commentIds },
  });
}

export function pinComment(id: string) {
  return authFetch<AdminComment>(`/api/admin/blog/comments/${id}/pin/`, { method: "POST" });
}

export function replyToComment(id: string, body: string) {
  return authFetch<AdminComment>(`/api/admin/blog/comments/${id}/reply/`, {
    method: "POST",
    body: { body },
  });
}

// ---------------------------------------------------------------------------
// FAQ entries
// ---------------------------------------------------------------------------

export interface PostFaq {
  id: string;
  question: string;
  answer: string;
  display_order: number;
}

export function listFaqs(postSlug: string) {
  return authFetch<PostFaq[]>(`/api/admin/blog/faqs/?post=${encodeURIComponent(postSlug)}`);
}

export function createFaq(postSlug: string, question: string, answer: string, order: number) {
  return authFetch<PostFaq>("/api/admin/blog/faqs/", {
    method: "POST",
    body: { post: postSlug, question, answer, display_order: order },
  });
}

export function updateFaq(id: string, patch: Partial<PostFaq>) {
  return authFetch<PostFaq>(`/api/admin/blog/faqs/${id}/`, { method: "PATCH", body: patch });
}

export function deleteFaq(id: string) {
  return authFetch<void>(`/api/admin/blog/faqs/${id}/`, { method: "DELETE" });
}
