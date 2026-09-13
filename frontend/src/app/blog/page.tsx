import Link from "next/link";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";
import { PostCard } from "@/components/marketing/PostCard";
import { getBlogSettings, listCategories, listPosts } from "@/lib/blog";
import {
  blogSchema,
  breadcrumbSchema,
  itemListSchema,
  jsonLdGraph,
  organisationSchema,
  pageMetadata,
} from "@/lib/seo";

/**
 * /blog — the index.
 *
 * This page exists to answer questions a student is already typing into Google,
 * which is the only reason a blog on a site like this is worth maintaining. So
 * it is built for someone arriving cold from a search result, not for someone
 * browsing: the newest article gets the space, the categories are the
 * navigation, and nothing here asks for a sign-up before it has been useful.
 *
 * Server-rendered throughout. Every article is in the initial HTML.
 */

export const revalidate = 300;

/**
 * Generated rather than static so the editable settings reach it: the Search
 * Console verification tag and the share-card @handle both live there.
 */
export async function generateMetadata() {
  const blogSettings = await getBlogSettings();
  return pageMetadata({
    title: "Guides — Nasuru",
    description:
      "Straight answers about studying abroad from Nigeria: what schools actually require, " +
      "which documents to start on first, why admission comes before the visa, and what a " +
      "tuition-free place still costs.",
    path: "/blog",
    blogSettings,
  });
}

export default async function BlogIndex({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; q?: string }>;
}) {
  const params = await searchParams;
  const page = Math.max(1, Number(params.page ?? 1) || 1);
  const search = params.q?.trim() ?? "";

  const [posts, categories, blogSettings] = await Promise.all([
    listPosts({ page, search: search || undefined }),
    listCategories(),
    getBlogSettings(),
  ]);

  // `featured` gives the newest article the space; `grid` treats them equally;
  // `list` is the compact rows. Which one is an editable setting, because it is a
  // design call that will change and should not need a deploy.
  const layout = blogSettings.listing_layout;
  const leadOut = layout === "featured" && !search;
  const [lead, ...rest] = posts.results;
  const gridPosts = leadOut ? rest : posts.results;
  const totalPages = Math.max(1, Math.ceil(posts.count / blogSettings.posts_per_page));

  return (
    <div className="bg-canvas">
      <script
        type="application/ld+json"
        // Static, server-generated structured data — no user input reaches it.
        dangerouslySetInnerHTML={{
          __html: jsonLdGraph(
            organisationSchema(),
            blogSchema(),
            breadcrumbSchema([
              { name: "Home", path: "/" },
              { name: "Guides", path: "/blog" },
            ]),
            itemListSchema(posts.results, "/blog"),
          ),
        }}
      />

      <SiteHeader current="/blog" />

      <main id="content">
        <section className="border-b border-line">
          <div className="mx-auto max-w-6xl px-6 py-12 sm:py-16">
            <p className="text-sm font-semibold tracking-wide text-accent uppercase">Guides</p>
            <h1 className="font-display mt-3 max-w-3xl text-4xl leading-[1.1] font-extrabold tracking-tight text-balance text-ink sm:text-5xl">
              The answers people normally pay an agent to find out
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-relaxed text-muted">
              What schools actually ask for, which documents to start on first, why the admission
              letter comes before the visa, and what a tuition-free place still costs you. Written
              plainly, with no figures we cannot stand behind.
            </p>

            {categories.length ? (
              <nav aria-label="Categories" className="mt-8">
                <ul className="flex flex-wrap gap-2">
                  <li>
                    <span className="inline-block rounded-full border border-accent bg-accent px-3.5 py-1.5 text-sm font-medium text-on-accent">
                      Everything
                    </span>
                  </li>
                  {categories.map((category) => (
                    <li key={category.slug}>
                      <Link
                        href={`/blog/category/${category.slug}`}
                        className="inline-block rounded-full border border-line px-3.5 py-1.5 text-sm text-muted transition hover:border-accent hover:text-ink"
                      >
                        {category.name}
                        <span className="ml-1.5 text-subtle">{category.post_count}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ) : null}

            <form action="/blog" role="search" className="mt-8 flex max-w-md gap-2">
              <label htmlFor="blog-search" className="sr-only">
                Search the guides
              </label>
              <input
                id="blog-search"
                type="search"
                name="q"
                defaultValue={search}
                placeholder="Search the guides"
                className="w-full rounded-lg border border-field-line bg-canvas px-3.5 py-2.5 text-sm text-ink placeholder:text-subtle focus-visible:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              />
              <button
                type="submit"
                className="rounded-lg border border-line px-4 py-2.5 text-sm font-semibold text-ink transition hover:border-accent"
              >
                Search
              </button>
            </form>
          </div>
        </section>

        <div className="mx-auto max-w-6xl px-6 py-12">
          {search ? (
            <p className="mb-8 text-sm text-muted">
              {posts.count === 0
                ? `Nothing matches “${search}” yet.`
                : `${posts.count} ${posts.count === 1 ? "guide" : "guides"} matching “${search}”.`}{" "}
              <Link href="/blog" className="font-medium text-accent hover:underline">
                Show everything
              </Link>
            </p>
          ) : null}

          {posts.results.length === 0 ? (
            <EmptyState search={search} />
          ) : (
            <>
              {leadOut && lead ? (
                <section aria-labelledby="latest" className="mb-14">
                  <h2 id="latest" className="sr-only">
                    Latest guide
                  </h2>
                  <div className="border-t-2 border-accent pt-6">
                    <PostCard post={lead} headingLevel={3} settings={blogSettings} layout="lead" />
                  </div>
                </section>
              ) : null}

              <section aria-labelledby="all-guides">
                <h2
                  id="all-guides"
                  className="font-display mb-6 text-sm font-semibold tracking-wide text-subtle uppercase"
                >
                  {search ? "Results" : leadOut ? "More guides" : "All guides"}
                </h2>
                <ul
                  className={
                    layout === "list"
                      ? "space-y-0"
                      : "grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3"
                  }
                >
                  {gridPosts.map((post) => (
                    <li key={post.slug}>
                      <PostCard
                        post={post}
                        settings={blogSettings}
                        layout={layout === "list" ? "list" : "grid"}
                      />
                    </li>
                  ))}
                </ul>
              </section>

              {totalPages > 1 ? (
                <nav
                  aria-label="Pagination"
                  className="mt-14 flex items-center justify-between border-t border-line pt-6 text-sm"
                >
                  {posts.previous ? (
                    <Link
                      href={`/blog?${new URLSearchParams({ ...(search ? { q: search } : {}), page: String(page - 1) })}`}
                      className="font-medium text-accent hover:underline"
                    >
                      ← Newer guides
                    </Link>
                  ) : (
                    <span />
                  )}
                  <span className="text-subtle">
                    Page {page} of {totalPages}
                  </span>
                  {posts.next ? (
                    <Link
                      href={`/blog?${new URLSearchParams({ ...(search ? { q: search } : {}), page: String(page + 1) })}`}
                      className="font-medium text-accent hover:underline"
                    >
                      Older guides →
                    </Link>
                  ) : (
                    <span />
                  )}
                </nav>
              ) : null}
            </>
          )}
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}

function EmptyState({ search }: { search: string }) {
  return (
    <div className="rounded-xl border border-line px-6 py-14 text-center">
      <h2 className="font-display text-xl font-bold text-ink">
        {search ? "No guide matches that yet" : "The first guides are being written"}
      </h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted">
        {search
          ? "Try fewer words, or ask us directly — we answer the same questions on WhatsApp every day."
          : "We would rather publish nothing than publish filler. In the meantime, ask us anything directly."}
      </p>
      <Link
        href="/contact"
        className="mt-6 inline-block rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-on-accent transition hover:bg-accent-hover"
      >
        Ask us a question
      </Link>
    </div>
  );
}
