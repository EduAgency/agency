import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";
import { PostCard } from "@/components/marketing/PostCard";
import { AuthorBox, FaqBlock } from "@/components/marketing/ArticleExtras";
import { CommentThread } from "@/components/marketing/CommentThread";
import { AI_DISCLOSURE, formatPostDate, getBlogSettings, getPost } from "@/lib/blog";
import { REFUND } from "@/lib/company";
import { getPricing, isPriceKnown } from "@/lib/pricing";
import {
  applyTitleTemplate,
  articleSchema,
  breadcrumbSchema,
  faqSchema,
  jsonLdGraph,
  organisationSchema,
  pageMetadata,
  personSchema,
} from "@/lib/seo";

/**
 * /blog/[slug] — one article.
 *
 * Written for the reader who arrived from a search result and has no idea who
 * we are. So the page does three things in order: answer the question, show who
 * answered it, and then — only at the end — say what we do for a fee. An article
 * that interrupts itself with a sign-up prompt in paragraph two is an
 * advertisement, and a reader who has been burned by an agent before can tell
 * the difference immediately.
 *
 * `body_html`, the FAQ answers and the author bio all arrive already rendered
 * and sanitised (apps/blog/rendering.py). Nothing is assembled here, and raw
 * Markdown never reaches the browser.
 *
 * Almost every display decision on this page — byline, date, reading time, hero
 * image, comments — comes from the editable blog settings rather than from this
 * file, so the person running the site can change them without a deploy.
 */

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [result, blogSettings] = await Promise.all([getPost(slug), getBlogSettings()]);

  if (!result || !("post" in result)) {
    return pageMetadata({
      title: "Not found — Nasuru",
      description: "",
      path: `/blog/${slug}`,
      noindex: true,
    });
  }

  const { post } = result;
  return pageMetadata({
    // The template is editable, so renaming the brand is one edit and not one
    // per post.
    title: applyTitleTemplate(post.seo_title, blogSettings.meta_title_template),
    description: post.seo_description || blogSettings.default_meta_description,
    path: `/blog/${post.slug}`,
    image: post.hero_image ?? blogSettings.default_og_image,
    imageAlt: post.hero_alt,
    type: "article",
    publishedTime: post.published_at,
    modifiedTime: post.updated_at,
    authors: post.author?.name ? [post.author.name] : undefined,
    noindex: post.noindex,
    canonicalOverride: post.canonical_url || undefined,
    blogSettings,
  });
}

export default async function ArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [result, blogSettings, pricing] = await Promise.all([
    getPost(slug),
    getBlogSettings(),
    getPricing(),
  ]);

  if (!result) notFound();
  // A slug that used to belong to a live post answers 301 rather than 404, so a
  // link printed on somebody else's site two years ago still lands on the
  // article. The backend keeps the old slug; this turns it into a real redirect.
  if ("movedTo" in result) permanentRedirect(`/blog/${result.movedTo}`);

  const { post } = result;
  const disclosure = AI_DISCLOSURE[post.ai_involvement];
  const showHero = blogSettings.show_featured_on_detail && Boolean(post.hero_image);
  const showByline = blogSettings.show_author_byline && Boolean(post.author?.name);

  return (
    <div className="bg-canvas">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLdGraph(
            organisationSchema(),
            articleSchema(post),
            // Only ever emitted when the same answers are rendered on the page
            // below — see FaqBlock.
            faqSchema(post),
            post.author_bio ? personSchema(post.author_bio) : null,
            breadcrumbSchema([
              { name: "Home", path: "/" },
              { name: "Guides", path: "/blog" },
              ...(post.category
                ? [
                    {
                      name: post.category.name,
                      path: `/blog/category/${post.category.slug}`,
                    },
                  ]
                : []),
              { name: post.title, path: `/blog/${post.slug}` },
            ]),
          ),
        }}
      />

      <SiteHeader />

      <main id="content">
        <article>
          <header className="border-b border-line">
            <div className="mx-auto max-w-3xl px-6 pt-10 pb-12">
              <nav aria-label="Breadcrumb" className="text-sm">
                <ol className="flex flex-wrap items-center gap-2 text-subtle">
                  <li>
                    <Link href="/blog" className="hover:text-ink">
                      Guides
                    </Link>
                  </li>
                  {post.category ? (
                    <>
                      <li aria-hidden="true">/</li>
                      <li>
                        <Link
                          href={`/blog/category/${post.category.slug}`}
                          className="hover:text-ink"
                        >
                          {post.category.name}
                        </Link>
                      </li>
                    </>
                  ) : null}
                </ol>
              </nav>

              <h1 className="font-display mt-5 text-4xl leading-[1.12] font-extrabold tracking-tight text-balance text-ink sm:text-[2.75rem]">
                {post.title}
              </h1>

              {post.excerpt ? (
                <p className="mt-5 text-lg leading-relaxed text-muted">{post.excerpt}</p>
              ) : null}

              <div className="mt-7 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-subtle">
                {showByline ? (
                  <span className="text-ink">
                    {post.author!.has_page && post.author!.slug ? (
                      <Link
                        href={`/blog/author/${post.author!.slug}`}
                        className="font-medium hover:underline"
                      >
                        {post.author!.name}
                      </Link>
                    ) : (
                      post.author!.name
                    )}
                    {post.author!.job_title ? (
                      <span className="text-subtle">, {post.author!.job_title}</span>
                    ) : null}
                  </span>
                ) : null}

                {blogSettings.show_published_date ? (
                  <>
                    {showByline ? <span aria-hidden="true">·</span> : null}
                    <time dateTime={post.published_at}>{formatPostDate(post.published_at)}</time>
                  </>
                ) : null}

                {blogSettings.show_reading_time && post.reading_minutes ? (
                  <>
                    <span aria-hidden="true">·</span>
                    <span>{post.reading_minutes} min read</span>
                  </>
                ) : null}

                {post.comment_count ? (
                  <>
                    <span aria-hidden="true">·</span>
                    <a href="#comments" className="hover:text-ink">
                      {post.comment_count} {post.comment_count === 1 ? "question" : "questions"}
                    </a>
                  </>
                ) : null}
              </div>

              {disclosure ? (
                <p className="mt-6 border-l-2 border-line pl-4 text-sm leading-relaxed text-subtle">
                  {disclosure} Every figure and requirement in it was checked by a person before it
                  was published.
                </p>
              ) : null}
            </div>
          </header>

          {showHero ? (
            <figure className="mx-auto max-w-4xl px-6 pt-10">
              {/* eslint-disable-next-line @next/next/no-img-element -- the API returns
                  signed R2 URLs on a host that changes with the bucket; a
                  configured remotePatterns list would be one more thing to keep
                  in step with the storage config. */}
              <img
                src={post.hero_image!}
                alt={post.hero_alt}
                style={{ aspectRatio: blogSettings.featured_aspect_ratio }}
                className="w-full rounded-xl border border-line object-cover"
              />
              {post.hero_caption || post.hero_credit ? (
                <figcaption className="mt-2.5 text-sm text-subtle">
                  {post.hero_caption}
                  {post.hero_caption && post.hero_credit ? " " : null}
                  {post.hero_credit ? <span className="italic">{post.hero_credit}</span> : null}
                </figcaption>
              ) : null}
            </figure>
          ) : null}

          <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[minmax(0,1fr)_15rem]">
            <div className="min-w-0 max-w-2xl">
              {/* Sanitised server-side by apps.blog.rendering — no script tags,
                  no event handlers, no schemes but http/https/mailto. */}
              <div className="post-body" dangerouslySetInnerHTML={{ __html: post.body_html }} />

              <FaqBlock faqs={post.faqs} />

              {post.tags.length ? (
                <footer className="mt-12 border-t border-line pt-6">
                  <h2 className="text-sm font-semibold text-subtle">Filed under</h2>
                  <ul className="mt-3 flex flex-wrap gap-2">
                    {post.tags.map((tag) => (
                      <li key={tag.slug}>
                        <Link
                          href={`/blog/tag/${tag.slug}`}
                          className="inline-block rounded-full border border-line px-3 py-1.5 text-sm text-muted transition hover:border-accent hover:text-ink"
                        >
                          {tag.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </footer>
              ) : null}

              <aside
                aria-labelledby="what-we-do-cta"
                className="mt-12 rounded-xl border border-line bg-sunken p-6"
              >
                <h2 id="what-we-do-cta" className="font-display text-lg font-bold text-ink">
                  This is the part we do with you
                </h2>
                <p className="mt-2.5 text-sm leading-relaxed text-muted">
                  We find the schools you can actually get into, tell you exactly what each one
                  requires, write your CV and motivation letter with you, and guide the visa once
                  you hold an admission letter.{" "}
                  {isPriceKnown(pricing)
                    ? `One fee of ${pricing.access_fee.formatted} covers all of it, and it is refundable for ${REFUND.coolingOffDays} days if you change your mind before we start.`
                    : `One fee covers all of it, and it is refundable for ${REFUND.coolingOffDays} days if you change your mind before we start.`}
                </p>
                <div className="mt-5 flex flex-wrap gap-3">
                  <Link
                    href="/signup"
                    className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-on-accent transition hover:bg-accent-hover"
                  >
                    Create an account
                  </Link>
                  <Link
                    href="/#fees"
                    className="rounded-lg border border-line px-5 py-2.5 text-sm font-semibold text-ink transition hover:border-accent"
                  >
                    What the fee covers
                  </Link>
                </div>
              </aside>

              {post.author_bio ? <AuthorBox author={post.author_bio} /> : null}

              <CommentThread
                slug={post.slug}
                comments={post.comments}
                open={post.comments_open}
                requireEmail={blogSettings.comments_require_email}
                allowReplies={blogSettings.comments_allow_replies}
                commentsEnabled={blogSettings.comments_enabled}
              />
            </div>

            {post.toc.length > 1 ? (
              <nav aria-labelledby="on-this-page" className="hidden lg:block">
                <div className="sticky top-8">
                  <h2
                    id="on-this-page"
                    className="text-xs font-semibold tracking-wide text-subtle uppercase"
                  >
                    On this page
                  </h2>
                  <ol className="mt-3 space-y-2 border-l border-line text-sm">
                    {post.toc
                      .filter((entry) => entry.level === 2)
                      .map((entry) => (
                        <li key={entry.anchor}>
                          <a
                            href={`#${entry.anchor}`}
                            className="-ml-px block border-l-2 border-transparent pl-3 leading-snug text-muted transition hover:border-accent hover:text-ink"
                          >
                            {entry.text}
                          </a>
                        </li>
                      ))}
                    {post.faqs.length ? (
                      <li>
                        <a
                          href="#faq"
                          className="-ml-px block border-l-2 border-transparent pl-3 leading-snug text-muted transition hover:border-accent hover:text-ink"
                        >
                          Short answers
                        </a>
                      </li>
                    ) : null}
                  </ol>
                </div>
              </nav>
            ) : null}
          </div>
        </article>

        {post.related.length ? (
          <section aria-labelledby="read-next" className="border-t border-line bg-sunken">
            <div className="mx-auto max-w-6xl px-6 py-12">
              <h2
                id="read-next"
                className="font-display text-2xl font-bold tracking-tight text-ink"
              >
                Read next
              </h2>
              <ul className="mt-8 grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
                {post.related.map((related) => (
                  <li key={related.slug}>
                    <PostCard post={related} />
                  </li>
                ))}
              </ul>
            </div>
          </section>
        ) : null}
      </main>

      <SiteFooter />
    </div>
  );
}
