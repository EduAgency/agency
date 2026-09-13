/**
 * The two blocks that hang off an article: its FAQ and its author box.
 *
 * Both are server components — they are indexable content, not interaction.
 */

import Link from "next/link";
import type { AuthorPage, PostFaq } from "@/lib/blog";

/**
 * FAQ entries, as a real definition list.
 *
 * `<dl>` rather than a stack of headings because that is what this is: terms and
 * their definitions. It also means the `FAQPage` JSON-LD on the page describes
 * markup a reader can actually see, which is the condition for emitting it at
 * all — marked-up answers hidden from readers is what earns a manual penalty.
 */
export function FaqBlock({ faqs }: { faqs: PostFaq[] }) {
  if (!faqs.length) return null;

  return (
    <section aria-labelledby="faq" className="mt-12 border-t border-line pt-8">
      <h2 id="faq" className="font-display text-2xl font-bold tracking-tight text-ink">
        Short answers
      </h2>
      <dl className="mt-6 space-y-6">
        {faqs.map((faq) => (
          <div key={faq.id}>
            <dt className="font-display text-base font-bold text-ink">{faq.question}</dt>
            <dd className="mt-1.5 text-sm leading-relaxed text-muted">{faq.answer}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/**
 * The author box.
 *
 * Its job is to answer "who is telling me this" for a reader who arrived from a
 * search result, which on a site about avoiding dishonest agents is not
 * decoration. The `sameAs` links are also what connects the byline to a real
 * identity in `Person` markup.
 */
export function AuthorBox({ author }: { author: AuthorPage }) {
  return (
    <section
      aria-labelledby="about-the-author"
      className="mt-12 rounded-xl border border-line bg-sunken p-6"
    >
      <h2 id="about-the-author" className="sr-only">
        About the author
      </h2>
      <div className="flex flex-wrap items-start gap-4">
        {author.avatar ? (
          // eslint-disable-next-line @next/next/no-img-element -- signed R2 URLs on a host that moves with the bucket.
          <img
            src={author.avatar}
            alt={author.avatar_alt}
            className="h-14 w-14 shrink-0 rounded-full border border-line object-cover"
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <p className="font-display text-lg font-bold text-ink">
            {author.slug ? (
              <Link href={`/blog/author/${author.slug}`} className="hover:underline">
                {author.display_name}
              </Link>
            ) : (
              author.display_name
            )}
          </p>
          {author.headline ? <p className="text-sm text-subtle">{author.headline}</p> : null}
          {author.credentials ? (
            <p className="mt-1 text-sm text-muted">{author.credentials}</p>
          ) : null}
          {author.bio_html ? (
            <div
              className="post-body mt-3 text-sm"
              // Rendered and sanitised server-side by apps.blog.rendering.
              dangerouslySetInnerHTML={{ __html: author.bio_html }}
            />
          ) : null}
          {author.same_as.length ? (
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
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
      </div>
    </section>
  );
}
