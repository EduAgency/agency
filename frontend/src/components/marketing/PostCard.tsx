import Link from "next/link";
import { type BlogPostCard, type PublicBlogSettings, formatPostDate } from "@/lib/blog";

/**
 * One article in a list.
 *
 * The whole card is not a link — the title is. A card-wide anchor wrapping a
 * heading, a date and two tag links produces either nested interactive elements
 * or tags that cannot be clicked, and screen reader users hear the entire card
 * read out as one link name.
 *
 * What appears on the card — image, byline, date, reading time — comes from the
 * editable blog settings. `settings` is optional so a caller that does not have
 * them renders something sensible rather than nothing.
 */
export function PostCard({
  post,
  headingLevel = 3,
  settings,
  layout = "grid",
}: {
  post: BlogPostCard;
  headingLevel?: 2 | 3;
  settings?: PublicBlogSettings;
  /** `lead` is the featured article; `list` is the compact row layout. */
  layout?: "grid" | "lead" | "list";
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const showImage = (settings?.show_featured_on_listing ?? true) && Boolean(post.hero_image);
  const showDate = settings?.show_published_date ?? true;
  const showReadingTime = settings?.show_reading_time ?? true;
  const showByline = (settings?.show_author_byline ?? true) && Boolean(post.author?.name);
  const aspectRatio = settings?.featured_aspect_ratio ?? 16 / 9;
  const readMore = settings?.read_more_label ?? "";

  const isLead = layout === "lead";
  const isList = layout === "list";

  return (
    <article
      className={
        isList
          ? "flex flex-wrap items-baseline gap-x-4 gap-y-1 border-t border-line py-4"
          : "flex h-full flex-col gap-3 border-t border-line pt-5"
      }
    >
      {showImage && !isList ? (
        <Link
          href={`/blog/${post.slug}`}
          // The image duplicates the title link, so it is kept out of the
          // keyboard order and the accessibility tree rather than announced
          // twice with no name of its own.
          tabIndex={-1}
          aria-hidden="true"
          className="block overflow-hidden rounded-xl border border-line"
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- signed R2 URLs on a host
              that moves with the bucket; see the article page for the reasoning. */}
          <img
            src={post.hero_image!}
            alt=""
            style={{ aspectRatio }}
            className="w-full object-cover"
          />
        </Link>
      ) : null}

      <p
        className={
          isList
            ? "order-2 flex shrink-0 flex-wrap items-center gap-x-2 text-xs text-subtle"
            : "flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-subtle"
        }
      >
        {post.category ? (
          <>
            <Link
              href={`/blog/category/${post.category.slug}`}
              className="font-medium text-accent hover:underline"
            >
              {post.category.name}
            </Link>
            {showDate || showReadingTime ? <span aria-hidden="true">·</span> : null}
          </>
        ) : null}
        {showDate ? (
          <time dateTime={post.published_at}>{formatPostDate(post.published_at)}</time>
        ) : null}
        {showReadingTime && post.reading_minutes ? (
          <>
            {showDate ? <span aria-hidden="true">·</span> : null}
            <span>{post.reading_minutes} min read</span>
          </>
        ) : null}
        {post.comment_count ? (
          <>
            <span aria-hidden="true">·</span>
            <span>
              {post.comment_count} {post.comment_count === 1 ? "question" : "questions"}
            </span>
          </>
        ) : null}
      </p>

      <Heading
        className={
          isList
            ? "font-display order-1 min-w-0 flex-1 text-base leading-snug font-semibold text-ink"
            : isLead
              ? "font-display text-2xl leading-tight font-bold tracking-tight text-balance text-ink sm:text-3xl"
              : "font-display text-xl leading-snug font-bold tracking-tight text-balance text-ink"
        }
      >
        <Link href={`/blog/${post.slug}`} className="hover:underline">
          {post.title}
        </Link>
      </Heading>

      {!isList ? (
        <p
          className={
            isLead ? "text-base leading-relaxed text-muted" : "text-sm leading-relaxed text-muted"
          }
        >
          {post.excerpt}
        </p>
      ) : null}

      {!isList && showByline ? (
        <p className="text-xs text-subtle">
          {post.author!.has_page && post.author!.slug ? (
            <Link href={`/blog/author/${post.author!.slug}`} className="hover:text-ink">
              {post.author!.name}
            </Link>
          ) : (
            post.author!.name
          )}
          {post.author!.job_title ? <span>, {post.author!.job_title}</span> : null}
        </p>
      ) : null}

      {post.tags.length && !isList ? (
        <ul className="mt-auto flex flex-wrap gap-2 pt-1">
          {post.tags.slice(0, 3).map((tag) => (
            <li key={tag.slug}>
              <Link
                href={`/blog/tag/${tag.slug}`}
                className="inline-block rounded-full border border-line px-2.5 py-1 text-xs text-subtle transition hover:border-accent hover:text-ink"
              >
                {tag.name}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      {readMore && isLead ? (
        <p>
          <Link
            href={`/blog/${post.slug}`}
            className="text-sm font-semibold text-accent hover:underline"
          >
            {readMore} →
          </Link>
        </p>
      ) : null}
    </article>
  );
}
