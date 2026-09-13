import Link from "next/link";
import { notFound } from "next/navigation";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";
import { PostCard } from "@/components/marketing/PostCard";
import { listCategories, listPosts } from "@/lib/blog";
import {
  breadcrumbSchema,
  itemListSchema,
  jsonLdGraph,
  organisationSchema,
  pageMetadata,
} from "@/lib/seo";

/**
 * /blog/category/[slug]
 *
 * A real section page, not a filtered view of the index: it gets its own title,
 * its own description and its own canonical URL, because that is what makes it
 * worth indexing separately. A category with no live posts 404s rather than
 * shipping an empty indexable page — thin pages cost the whole site.
 */

export const revalidate = 300;

async function findCategory(slug: string) {
  const categories = await listCategories();
  return categories.find((category) => category.slug === slug) ?? null;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const category = await findCategory(slug);
  if (!category) {
    return pageMetadata({
      title: "Not found — Nasuru",
      description: "",
      path: `/blog/category/${slug}`,
      noindex: true,
    });
  }
  return pageMetadata({
    title: `${category.name} — Nasuru guides`,
    description:
      category.description ||
      `Guides on ${category.name.toLowerCase()} for Nigerians applying to international schools.`,
    path: `/blog/category/${category.slug}`,
  });
}

export default async function CategoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [category, posts, categories] = await Promise.all([
    findCategory(slug),
    listPosts({ category: slug }),
    listCategories(),
  ]);

  if (!category || posts.results.length === 0) notFound();

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
              { name: category.name, path: `/blog/category/${category.slug}` },
            ]),
            itemListSchema(posts.results, `/blog/category/${category.slug}`),
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
                <li className="text-ink">{category.name}</li>
              </ol>
            </nav>
            <h1 className="font-display mt-4 text-4xl leading-tight font-extrabold tracking-tight text-balance text-ink">
              {category.name}
            </h1>
            {category.description ? (
              <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted">
                {category.description}
              </p>
            ) : null}
            <p className="mt-4 text-sm text-subtle">
              {posts.count} {posts.count === 1 ? "guide" : "guides"}
            </p>

            <nav aria-label="Other categories" className="mt-8">
              <ul className="flex flex-wrap gap-2">
                <li>
                  <Link
                    href="/blog"
                    className="inline-block rounded-full border border-line px-3.5 py-1.5 text-sm text-muted transition hover:border-accent hover:text-ink"
                  >
                    Everything
                  </Link>
                </li>
                {categories.map((other) => (
                  <li key={other.slug}>
                    {other.slug === category.slug ? (
                      <span
                        aria-current="page"
                        className="inline-block rounded-full border border-accent bg-accent px-3.5 py-1.5 text-sm font-medium text-on-accent"
                      >
                        {other.name}
                      </span>
                    ) : (
                      <Link
                        href={`/blog/category/${other.slug}`}
                        className="inline-block rounded-full border border-line px-3.5 py-1.5 text-sm text-muted transition hover:border-accent hover:text-ink"
                      >
                        {other.name}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
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
