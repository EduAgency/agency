import { API_BASE_URL } from "@/lib/api";

/**
 * /blog/rss.xml
 *
 * Django generates the feed (apps/blog/feeds.py); this route serves it from the
 * site's own origin. Feed URLs get saved in readers and quoted in directories,
 * so it should live on the domain people know — not on the API host, which is an
 * implementation detail that may well move.
 *
 * A thin proxy rather than a second feed generator: two implementations of the
 * same XML is two places for the item list to drift.
 */

export const revalidate = 600;

const UNAVAILABLE = new Response("The feed is temporarily unavailable.", {
  status: 503,
  headers: { "Content-Type": "text/plain; charset=utf-8" },
});

export async function GET() {
  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/blog/rss.xml`, {
      headers: { Accept: "application/rss+xml" },
      next: { revalidate },
    });
  } catch {
    // This route prerenders at build time, so an API that is unreachable
    // during the build must degrade to a 503 the next request can replace —
    // never fail the deploy.
    return UNAVAILABLE.clone();
  }

  if (!upstream.ok) return UNAVAILABLE.clone();

  return new Response(await upstream.text(), {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=600, stale-while-revalidate=3600",
    },
  });
}
