import Link from "next/link";
import { PostCard } from "@/components/marketing/PostCard";
import { getBlogSettings, listPosts } from "@/lib/blog";

/**
 * The guides section on the landing page.
 *
 * Renders nothing at all when the setting is off or there are no live posts. An
 * empty "Latest guides" heading with white space under it is worse than no
 * section — it reads as a broken page, which on a site arguing for its own
 * trustworthiness is expensive.
 *
 * Whether it appears, how many articles it shows and what the heading says are
 * all editable settings. This is the section most likely to be tuned, and
 * tuning it should not be a deploy.
 */
export async function HomepageGuides() {
  const blogSettings = await getBlogSettings();
  if (!blogSettings.homepage_show_latest) return null;

  const { results } = await listPosts();
  const posts = results.slice(0, blogSettings.homepage_article_count);
  if (posts.length === 0) return null;

  return (
    <section aria-labelledby="latest-guides" className="border-t border-line bg-sunken">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2
              id="latest-guides"
              className="font-display text-3xl leading-tight font-extrabold tracking-tight text-balance text-ink"
            >
              {blogSettings.homepage_section_title}
            </h2>
            <p className="mt-2 max-w-xl text-base leading-relaxed text-muted">
              Written out properly, with no figure we cannot stand behind. Read them before you pay
              us anything.
            </p>
          </div>
          <Link
            href="/blog"
            className="rounded-lg border border-line px-5 py-2.5 text-sm font-semibold text-ink transition hover:border-accent"
          >
            All guides
          </Link>
        </div>

        <ul className="mt-10 grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((post) => (
            <li key={post.slug}>
              <PostCard post={post} settings={blogSettings} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
