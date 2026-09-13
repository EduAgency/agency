import Link from "next/link";
import { notFound } from "next/navigation";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";
import { PostCard } from "@/components/marketing/PostCard";
import { getBlogSettings, listPosts, listTags } from "@/lib/blog";
import { breadcrumbSchema, jsonLdGraph, organisationSchema, pageMetadata } from "@/lib/seo";

/**
 * /blog/tag/[slug]
 *
 * Tag pages are `noindex, follow` on purpose. They are navigation for a reader
 * who wants more on one narrow thing, and they are almost always a subset of a
 * category page — indexing both asks a search engine to choose between two pages
 * that say the same thing, and it usually chooses neither. `follow` keeps the
 * links to the articles themselves working as internal links.
 */

export const revalidate = 300;

async function findTag(slug: string) {
  const tags = await listTags();
  return tags.find((tag) => tag.slug === slug) ?? null;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [tag, blogSettings] = await Promise.all([findTag(slug), getBlogSettings()]);
  return pageMetadata({
    title: tag ? `${tag.name} — Nasuru guides` : "Not found — Nasuru",
    description: tag ? `Every guide tagged ${tag.name}.` : "",
    path: `/blog/tag/${slug}`,
    // Tag pages are usually a subset of a category page, and indexing both
    // asks a search engine to choose between two pages saying the same thing.
    // Editable, because a site with no categories would want the opposite.
    noindex: blogSettings.noindex_tag_pages,
    blogSettings,
  });
}

export default async function TagPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [tag, posts] = await Promise.all([findTag(slug), listPosts({ tag: slug })]);

  if (!tag || posts.results.length === 0) notFound();

  return (
    <div className="bg-canvas">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLdGraph(
            organisationSchema(),
            breadcrumbSchema([
              { name: "Home", path: "/" },
              { name: "Guides", path: "/blog" },
              { name: tag.name, path: `/blog/tag/${tag.slug}` },
            ]),
          ),
        }}
      />

      <SiteHeader />

      <main id="content">
        <section className="border-b border-line">
          <div className="mx-auto max-w-6xl px-6 py-12">
            <nav aria-label="Breadcrumb" className="text-sm">
              <ol className="flex items-center gap-2 text-subtle">
                <li>
                  <Link href="/blog" className="hover:text-ink">
                    Guides
                  </Link>
                </li>
                <li aria-hidden="true">/</li>
                <li className="text-ink">{tag.name}</li>
              </ol>
            </nav>
            <h1 className="font-display mt-4 text-3xl leading-tight font-extrabold tracking-tight text-ink">
              Tagged <span className="text-accent">{tag.name}</span>
            </h1>
            <p className="mt-3 text-sm text-subtle">
              {posts.count} {posts.count === 1 ? "guide" : "guides"}
            </p>
          </div>
        </section>

        <div className="mx-auto max-w-6xl px-6 py-12">
          <ul className="grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {posts.results.map((post) => (
              <li key={post.slug}>
                <PostCard post={post} headingLevel={2} />
              </li>
            ))}
          </ul>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
