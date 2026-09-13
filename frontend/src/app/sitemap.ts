import type { MetadataRoute } from "next";
import { getSitemapEntries } from "@/lib/blog";
import { absoluteUrl } from "@/lib/seo";

/**
 * The sitemap.
 *
 * Static pages are listed here; blog URLs come from the API, with the database's
 * own `updated_at` as `lastModified` — a build timestamp would tell a crawler
 * every page changed on every deploy, which teaches it to ignore the field.
 *
 * Two deliberate omissions. Authenticated routes (`/dashboard`, `/staff`, the
 * auth screens) are not here: a sitemap is a list of pages worth indexing, and
 * a sign-in wall is not one. Tag pages are not here either — they are
 * `noindex, follow` by default, so listing them would be contradicting
 * ourselves.
 */

export const revalidate = 3600;

const STATIC_PAGES: {
  path: string;
  priority: number;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
}[] = [
  { path: "/", priority: 1, changeFrequency: "weekly" },
  { path: "/blog", priority: 0.9, changeFrequency: "daily" },
  { path: "/contact", priority: 0.6, changeFrequency: "yearly" },
  { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
  { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  { path: "/refund-policy", priority: 0.4, changeFrequency: "yearly" },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const { posts, categories, authors } = await getSitemapEntries();
  const now = new Date();

  return [
    ...STATIC_PAGES.map((page) => ({
      url: absoluteUrl(page.path),
      lastModified: now,
      changeFrequency: page.changeFrequency,
      priority: page.priority,
    })),
    ...categories.map((category) => ({
      url: absoluteUrl(`/blog/category/${category.slug}`),
      lastModified: new Date(category.last_modified),
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
    ...posts.map((post) => ({
      url: absoluteUrl(`/blog/${post.slug}`),
      lastModified: new Date(post.last_modified),
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
    // Author pages, when the settings publish them. The API already filters to
    // profiles that opted in and have live posts, so nothing thin gets listed.
    ...authors.map((author) => ({
      url: absoluteUrl(`/blog/author/${author.slug}`),
      lastModified: new Date(author.last_modified),
      changeFrequency: "monthly" as const,
      priority: 0.5,
    })),
  ];
}
