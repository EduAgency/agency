/**
 * Blog data, fetched on the server.
 *
 * Every one of these runs in a server component, so the HTML a crawler gets is
 * the HTML a reader gets — no client-side fetch, no empty shell that fills in
 * after hydration. That is the whole reason the blog exists on this stack.
 *
 * Caching is time-based rather than tag-based because the publishing surface is
 * a separate Django process: it cannot call `revalidateTag`, and a webhook that
 * could is one more thing to keep working. Five minutes is well inside how fast
 * anyone expects a new article to appear.
 */

import { API_BASE_URL } from "@/lib/api";

const REVALIDATE_SECONDS = 300;

export interface BlogCategory {
  id: string;
  name: string;
  slug: string;
  description: string;
  display_order?: number;
  post_count?: number;
}

export interface BlogTag {
  id: string;
  name: string;
  slug: string;
  post_count?: number;
}

export interface BlogAuthor {
  name: string;
  job_title: string;
  /** Empty when the author has no public page — the byline is then plain text. */
  slug: string;
  avatar: string | null;
  avatar_alt: string;
  has_page: boolean;
}

export interface AuthorPage {
  display_name: string;
  slug: string;
  headline: string;
  /** Rendered and sanitised by the backend, like a post body. */
  bio_html: string;
  credentials: string;
  avatar: string | null;
  avatar_alt: string;
  same_as: string[];
  post_count: number;
}

export interface PostFaq {
  id: string;
  question: string;
  answer: string;
  display_order: number;
}

export interface BlogComment {
  id: string;
  author_name: string;
  is_from_staff: boolean;
  body: string;
  created_at: string;
  is_pinned: boolean;
  replies: BlogComment[];
}

/**
 * The editable, public slice of the blog settings.
 *
 * Read on every public page so the site renders the way the settings screen
 * says it should. Defaults here mirror the model's, so a page still renders
 * correctly when the API is unreachable.
 */
export interface PublicBlogSettings {
  posts_per_page: number;
  homepage_show_latest: boolean;
  homepage_article_count: number;
  homepage_section_title: string;
  listing_layout: "featured" | "grid" | "list";
  show_reading_time: boolean;
  show_author_byline: boolean;
  show_published_date: boolean;
  read_more_label: string;
  featured_image_aspect: string;
  featured_aspect_ratio: number;
  show_featured_on_listing: boolean;
  show_featured_on_detail: boolean;
  comments_enabled: boolean;
  comments_require_email: boolean;
  comments_allow_replies: boolean;
  comments_min_seconds: number;
  author_pages_enabled: boolean;
  show_author_bio_on_article: boolean;
  noindex_tag_pages: boolean;
  twitter_site: string;
  google_site_verification: string;
  bing_site_verification: string;
  default_meta_description: string;
  default_og_image: string | null;
  meta_title_template: string;
}

export const BLOG_SETTINGS_FALLBACK: PublicBlogSettings = {
  posts_per_page: 12,
  homepage_show_latest: true,
  homepage_article_count: 3,
  homepage_section_title: "Questions people ask us before they pay",
  listing_layout: "featured",
  show_reading_time: true,
  show_author_byline: true,
  show_published_date: true,
  read_more_label: "Read the guide",
  featured_image_aspect: "16:9",
  featured_aspect_ratio: 16 / 9,
  show_featured_on_listing: true,
  show_featured_on_detail: true,
  comments_enabled: true,
  comments_require_email: true,
  comments_allow_replies: true,
  comments_min_seconds: 4,
  author_pages_enabled: true,
  show_author_bio_on_article: true,
  noindex_tag_pages: true,
  twitter_site: "",
  google_site_verification: "",
  bing_site_verification: "",
  default_meta_description: "",
  default_og_image: null,
  meta_title_template: "{title} — {site}",
};

export interface BlogPostCard {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  published_at: string;
  reading_minutes: number;
  category: BlogCategory | null;
  tags: BlogTag[];
  author: BlogAuthor | null;
  hero_image: string | null;
  hero_alt: string;
  comment_count: number;
}

export interface TocEntry {
  level: number;
  text: string;
  anchor: string;
}

export interface BlogPost extends BlogPostCard {
  /** Rendered and sanitised by the backend. Never render raw `body` here. */
  body_html: string;
  toc: TocEntry[];
  updated_at: string;
  seo_title: string;
  seo_description: string;
  canonical_url: string;
  noindex: boolean;
  ai_involvement: "none" | "outline" | "draft" | "edit";
  related: BlogPostCard[];
  hero_caption: string;
  hero_credit: string;
  faqs: PostFaq[];
  comments_open: boolean;
  comments: BlogComment[];
  author_bio: AuthorPage | null;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

async function get<T>(path: string, revalidate = REVALIDATE_SECONDS): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      next: { revalidate },
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    // A blog that 500s because the API is briefly unreachable is worse than a
    // blog that renders its empty state. Callers decide what "nothing" means.
    return null;
  }
}

export async function listPosts(
  params: {
    page?: number;
    category?: string;
    tag?: string;
    search?: string;
  } = {},
): Promise<Page<BlogPostCard>> {
  const query = new URLSearchParams();
  if (params.page && params.page > 1) query.set("page", String(params.page));
  if (params.category) query.set("category", params.category);
  if (params.tag) query.set("tag", params.tag);
  if (params.search) query.set("search", params.search);
  const suffix = query.toString() ? `?${query}` : "";
  return (
    (await get<Page<BlogPostCard>>(`/api/blog/posts/${suffix}`)) ?? {
      count: 0,
      next: null,
      previous: null,
      results: [],
    }
  );
}

/**
 * One article, or where it moved to.
 *
 * The API answers 301 with the current slug when a post's URL has changed, so
 * this cannot use the plain `get` helper — that treats any non-OK response as
 * nothing. Returning the redirect lets the page issue a real 301 of its own,
 * which is the whole point of keeping the old slug.
 */
export async function getPost(
  slug: string,
): Promise<{ post: BlogPost } | { movedTo: string } | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/blog/posts/${encodeURIComponent(slug)}/`, {
      headers: { Accept: "application/json" },
      next: { revalidate: REVALIDATE_SECONDS },
      redirect: "manual",
    });
    if (response.status === 301) {
      const body = (await response.json()) as { slug?: string };
      return body.slug ? { movedTo: body.slug } : null;
    }
    if (!response.ok) return null;
    return { post: (await response.json()) as BlogPost };
  } catch {
    return null;
  }
}

/** Post a comment. Runs in the browser, so it is a plain fetch. */
export async function submitComment(
  slug: string,
  payload: {
    body: string;
    name?: string;
    email?: string;
    website?: string;
    parent?: string | null;
    honeypot?: string;
    seconds_on_page?: number;
  },
): Promise<{ detail: string; published: boolean; comment: BlogComment | null }> {
  const response = await fetch(
    `${API_BASE_URL}/api/blog/posts/${encodeURIComponent(slug)}/comments/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      typeof data.detail === "string"
        ? data.detail
        : typeof data.email === "string" || Array.isArray(data.email)
          ? String(Array.isArray(data.email) ? data.email[0] : data.email)
          : "That did not go through. Please try again.";
    throw new Error(message);
  }
  return data;
}

/**
 * The public blog settings.
 *
 * Cached for a minute rather than five: a change here is what an editor
 * *expects* to see immediately after saving, and it is one small document.
 */
export async function getBlogSettings(): Promise<PublicBlogSettings> {
  return (await get<PublicBlogSettings>("/api/blog/settings/", 60)) ?? BLOG_SETTINGS_FALLBACK;
}

export async function getAuthor(slug: string): Promise<AuthorPage | null> {
  return get<AuthorPage>(`/api/blog/authors/${encodeURIComponent(slug)}/`);
}

export async function listAuthorPosts(slug: string): Promise<BlogPostCard[]> {
  return (await get<BlogPostCard[]>(`/api/blog/authors/${encodeURIComponent(slug)}/posts/`)) ?? [];
}

export async function listAuthors(): Promise<AuthorPage[]> {
  return (await get<AuthorPage[]>("/api/blog/authors/")) ?? [];
}

export async function listCategories(): Promise<BlogCategory[]> {
  return (await get<BlogCategory[]>("/api/blog/categories/")) ?? [];
}

export async function listTags(): Promise<BlogTag[]> {
  return (await get<BlogTag[]>("/api/blog/tags/")) ?? [];
}

export interface SitemapEntry {
  slug: string;
  last_modified: string;
}

export async function getSitemapEntries(): Promise<{
  posts: SitemapEntry[];
  categories: SitemapEntry[];
  authors: SitemapEntry[];
}> {
  return (
    (await get<{
      posts: SitemapEntry[];
      categories: SitemapEntry[];
      authors: SitemapEntry[];
    }>("/api/blog/sitemap/", 60)) ?? { posts: [], categories: [], authors: [] }
  );
}

/** "12 September 2026" — long form, because a blog date is read, not scanned. */
export function formatPostDate(iso: string): string {
  return new Intl.DateTimeFormat("en-NG", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Africa/Lagos",
  }).format(new Date(iso));
}

/**
 * How AI involvement is described to a reader.
 *
 * Shown on the article itself. A reader who can see that a draft was machine-
 * written and edited by a named person has a reason to trust the ones that say
 * otherwise; hiding it would cost more than it saves.
 */
export const AI_DISCLOSURE: Record<BlogPost["ai_involvement"], string | null> = {
  none: null,
  outline: "Outlined with AI assistance, written and checked by our team.",
  draft: "First draft written with AI assistance, then edited and fact-checked by our team.",
  edit: "Written by our team, edited with AI assistance.",
};
