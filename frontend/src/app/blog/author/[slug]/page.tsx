import Link from "next/link";
import { notFound } from "next/navigation";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";
import { PostCard } from "@/components/marketing/PostCard";
import { getAuthor, getBlogSettings, listAuthorPosts } from "@/lib/blog";
import {
  authorPageSchema,
  breadcrumbSchema,
  jsonLdGraph,
  organisationSchema,
  pageMetadata,
  personSchema,
} from "@/lib/seo";

/**
 * /blog/author/[slug] — an author archive.
 *
 * The SEO argument for this page is specific and worth stating: the `Person`
 * node it carries, with `sameAs` links to profiles elsewhere, is how a search
 * engine connects a byline to a real identity. On a site whose whole pitch is
 * "we tell you what other agents won't", an author who demonstrably exists is
 * doing more work than any badge.
 *
 * The page only exists for authors who opted in *and* have live posts — the API
 * enforces both, and a 404 here is correct rather than unfortunate. A thin
 * author page costs the whole site.
 */

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [author, blogSettings] = await Promise.all([getAuthor(slug), getBlogSettings()]);

  if (!author) {
    return pageMetadata({
      title: "Not found — Nasuru",
      description: "",
      path: `/blog/author/${slug}`,
      noindex: true,
    });
  }

  return pageMetadata({
    title: `${author.display_name} — Nasuru`,
    description: author.headline
      ? `${author.display_name}, ${author.headline}. Guides on studying abroad from Nigeria.`
      : `Guides written by ${author.display_name}.`,
    path: `/blog/author/${author.slug}`,
    image: author.avatar,
    imageAlt: author.avatar_alt,
    blogSettings,
  });
}

export default async function AuthorPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [author, posts] = await Promise.all([getAuthor(slug), listAuthorPosts(slug)]);

  if (!author) notFound();

  return (
    <div className="bg-canvas">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLdGraph(
            organisationSchema(),
            personSchema(author),
            authorPageSchema(author, posts),
            breadcrumbSchema([
              { name: "Home", path: "/" },
              { name: "Guides", path: "/blog" },
              { name: author.display_name, path: `/blog/author/${author.slug}` },
            ]),
          ),
        }}
      />

      <SiteHeader />

      <main id="content">
        <section className="border-b border-line">
          <div className="mx-auto max-w-3xl px-6 py-12">
            <nav aria-label="Breadcrumb" className="text-sm">
              <ol className="flex items-center gap-2 text-subtle">
                <li>
                  <Link href="/blog" className="hover:text-ink">
                    Guides
                  </Link>
                </li>
                <li aria-hidden="true">/</li>
                <li className="text-ink">{author.display_name}</li>
              </ol>
            </nav>

            <div className="mt-6 flex flex-wrap items-start gap-5">
              {author.avatar ? (
                // eslint-disable-next-line @next/next/no-img-element -- signed R2 URLs; see the article page.
                <img
                  src={author.avatar}
                  alt={author.avatar_alt}
                  className="h-20 w-20 shrink-0 rounded-full border border-line object-cover"
                />
              ) : null}
              <div className="min-w-0">
                <h1 className="font-display text-3xl leading-tight font-extrabold tracking-tight text-ink">
                  {author.display_name}
                </h1>
                {author.headline ? (
                  <p className="mt-1 text-lg text-muted">{author.headline}</p>
                ) : null}
                {author.credentials ? (
                  <p className="mt-2 text-sm text-subtle">{author.credentials}</p>
                ) : null}
              </div>
            </div>

            {author.bio_html ? (
              <div
                className="post-body mt-7"
                // Rendered and sanitised server-side, like a post body.
                dangerouslySetInnerHTML={{ __html: author.bio_html }}
              />
            ) : null}

            {author.same_as.length ? (
              <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm">
                {author.same_as.map((url) => (
                  <li key={url}>
                    <a href={url} rel="me noopener" className="text-accent hover:underline">
                      {new URL(url).hostname.replace(/^www\./, "")}
                    </a>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </section>

        <div className="mx-auto max-w-6xl px-6 py-12">
          <h2 className="font-display text-sm font-semibold tracking-wide text-subtle uppercase">
            {posts.length} {posts.length === 1 ? "guide" : "guides"}
          </h2>
          <ul className="mt-6 grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {posts.map((post) => (
              <li key={post.slug}>
                <PostCard post={post} headingLevel={3} />
              </li>
            ))}
          </ul>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
