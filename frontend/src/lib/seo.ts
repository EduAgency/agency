/**
 * SEO plumbing.
 *
 * Three jobs, and keeping them together stops them drifting apart:
 *
 * 1. One absolute site origin. Canonical tags, Open Graph URLs, sitemaps and
 *    JSON-LD all need one, and a site reachable on two hostnames splits its own
 *    ranking. `NEXT_PUBLIC_SITE_URL` is the single answer.
 * 2. Metadata builders, so every page gets a title, a description, a canonical
 *    and an Open Graph card without each page author remembering all four.
 * 3. JSON-LD builders. Structured data is how a search engine knows this is an
 *    organisation, an article, a person's question — and it is the one SEO
 *    lever with no downside as long as every claim in it is also on the page.
 *
 * One rule runs through all of it: nothing here asserts anything the site does
 * not also say in plain HTML. Marking up a rating or an award we cannot evidence
 * would be exactly the kind of unverifiable claim the rest of this codebase goes
 * out of its way to refuse.
 */

import type { Metadata } from "next";
import { ACCREDITATION, COMPANY, CONTACT, isPending } from "@/lib/company";
import type { Pricing } from "@/lib/pricing";
import type { AuthorPage, BlogPost, BlogPostCard, PublicBlogSettings } from "@/lib/blog";

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(
  /\/$/,
  "",
);

export const SITE_NAME = COMPANY.tradingName;

/**
 * What the site is, in one sentence, for search results and share cards.
 *
 * A function rather than a constant because it quotes the fee, and the fee is a
 * database row. Callers that have the pricing pass it; the ones that genuinely
 * cannot — the root layout's static metadata — get the sentence without a
 * number, which is accurate rather than approximately right.
 */
const SITE_DESCRIPTION_BASE =
  "We find international schools you can actually afford, tell you exactly what each one requires, " +
  "write your CV and motivation letter with you, and guide the visa once you have an admission letter.";

export function siteDescription(pricing?: Pricing): string {
  const fee = pricing?.access_fee;
  if (!fee || fee.major_units <= 0) {
    return `${SITE_DESCRIPTION_BASE} One fee, from the first shortlist to landing on campus.`;
  }
  return `${SITE_DESCRIPTION_BASE} One fee of ${fee.formatted}, from the first shortlist to landing on campus.`;
}

/** The no-price form, for the root layout's static metadata. */
export const SITE_DESCRIPTION = siteDescription();

export function absoluteUrl(path = "/"): string {
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * Apply the editable title template.
 *
 * The template lives in the blog settings so renaming the brand is one edit
 * rather than one per post. A template that has lost its `{title}` placeholder
 * would silently give every page the same name, so that case falls back.
 */
export function applyTitleTemplate(title: string, template: string): string {
  if (!template.includes("{title}")) return `${title} — ${SITE_NAME}`;
  return template.replace("{title}", title).replace("{site}", SITE_NAME);
}

/**
 * Search Console and Bing verification tags.
 *
 * These live in the blog settings rather than in an env var because the person
 * who needs to add one is the person logged into Search Console, and that should
 * not be a deploy.
 */
export function verificationMeta(blogSettings: PublicBlogSettings): Metadata["verification"] {
  const google = blogSettings.google_site_verification.trim();
  const bing = blogSettings.bing_site_verification.trim();
  if (!google && !bing) return undefined;
  return {
    ...(google ? { google } : {}),
    ...(bing ? { other: { "msvalidate.01": bing } } : {}),
  };
}

interface PageMetaOptions {
  title: string;
  description: string;
  path: string;
  /** Passing the settings adds the @handle to the share card. */
  blogSettings?: PublicBlogSettings;
  /** Absolute or site-relative image URL for the share card. */
  image?: string | null;
  imageAlt?: string;
  type?: "website" | "article";
  publishedTime?: string;
  modifiedTime?: string;
  authors?: string[];
  noindex?: boolean;
  /** Set only when the canonical genuinely points somewhere else. */
  canonicalOverride?: string;
}

export function pageMetadata({
  title,
  description,
  path,
  image,
  imageAlt,
  type = "website",
  publishedTime,
  modifiedTime,
  authors,
  noindex = false,
  canonicalOverride,
  blogSettings,
}: PageMetaOptions): Metadata {
  const url = absoluteUrl(path);
  const ogImage = image
    ? image.startsWith("http")
      ? image
      : absoluteUrl(image)
    : absoluteUrl("/opengraph-image");

  return {
    title,
    description,
    alternates: { canonical: canonicalOverride || url },
    robots: noindex
      ? { index: false, follow: true }
      : { index: true, follow: true, googleBot: { index: true, follow: true } },
    openGraph: {
      title,
      description,
      url,
      siteName: SITE_NAME,
      locale: "en_NG",
      type,
      images: [{ url: ogImage, alt: imageAlt || title }],
      ...(publishedTime ? { publishedTime } : {}),
      ...(modifiedTime ? { modifiedTime } : {}),
      ...(authors ? { authors } : {}),
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage],
      ...(blogSettings?.twitter_site ? { site: blogSettings.twitter_site } : {}),
    },
    ...(blogSettings ? { verification: verificationMeta(blogSettings) } : {}),
  };
}

// ---------------------------------------------------------------------------
// JSON-LD
// ---------------------------------------------------------------------------

type Json = Record<string, unknown>;

/**
 * The organisation, once, referenced by @id everywhere else.
 *
 * `hasCredential` is emitted only when the certification is real. While it is
 * still PENDING the site says "certificate coming" in prose and claims nothing
 * in its structured data — a credential asserted to a search engine and not
 * evidenced on the page is the exact shape of the problem we are avoiding.
 */
export function organisationSchema(): Json {
  const credentialled = !isPending(ACCREDITATION.body);
  return {
    "@type": "Organization",
    "@id": `${SITE_URL}/#organisation`,
    name: COMPANY.legalName,
    alternateName: COMPANY.tradingName,
    url: SITE_URL,
    description: SITE_DESCRIPTION,
    email: CONTACT.email,
    telephone: CONTACT.phone,
    address: {
      "@type": "PostalAddress",
      streetAddress: `${COMPANY.address.street}, ${COMPANY.address.area}`,
      addressLocality: COMPANY.address.lga,
      addressRegion: COMPANY.address.state,
      addressCountry: "NG",
    },
    identifier: {
      "@type": "PropertyValue",
      name: "RC number",
      value: COMPANY.registrationNumber,
    },
    ...(credentialled
      ? {
          hasCredential: {
            "@type": "EducationalOccupationalCredential",
            credentialCategory: ACCREDITATION.credential,
            recognizedBy: { "@type": "Organization", name: ACCREDITATION.body },
          },
        }
      : {}),
  };
}

export function websiteSchema(): Json {
  return {
    "@type": "WebSite",
    "@id": `${SITE_URL}/#website`,
    url: SITE_URL,
    name: SITE_NAME,
    description: SITE_DESCRIPTION,
    inLanguage: "en-NG",
    publisher: { "@id": `${SITE_URL}/#organisation` },
  };
}

export function blogSchema(): Json {
  return {
    "@type": "Blog",
    "@id": `${SITE_URL}/blog#blog`,
    url: absoluteUrl("/blog"),
    name: `${SITE_NAME} — study abroad, explained plainly`,
    description:
      "How Nigerians actually get into international schools: the requirements, the documents, " +
      "the order things happen in, and what it really costs.",
    inLanguage: "en-NG",
    publisher: { "@id": `${SITE_URL}/#organisation` },
  };
}

export function articleSchema(post: BlogPost): Json {
  const url = absoluteUrl(`/blog/${post.slug}`);
  return {
    "@type": "BlogPosting",
    "@id": `${url}#article`,
    headline: post.title,
    description: post.seo_description || post.excerpt,
    url,
    mainEntityOfPage: { "@type": "WebPage", "@id": url },
    datePublished: post.published_at,
    dateModified: post.updated_at || post.published_at,
    inLanguage: "en-NG",
    isPartOf: { "@id": `${SITE_URL}/blog#blog` },
    publisher: { "@id": `${SITE_URL}/#organisation` },
    // Point at the Person node when the author has a page, so the two resolve to
    // one identity inside the graph instead of restating each other.
    author: post.author?.slug
      ? { "@id": `${absoluteUrl(`/blog/author/${post.author.slug}`)}#person` }
      : post.author?.name
        ? {
            "@type": "Person",
            name: post.author.name,
            jobTitle: post.author.job_title || undefined,
          }
        : { "@id": `${SITE_URL}/#organisation` },
    ...(post.hero_image ? { image: [post.hero_image] } : {}),
    ...(post.category ? { articleSection: post.category.name } : {}),
    ...(post.tags.length ? { keywords: post.tags.map((t) => t.name).join(", ") } : {}),
    ...(post.comment_count ? { commentCount: post.comment_count } : {}),
    timeRequired: post.reading_minutes ? `PT${post.reading_minutes}M` : undefined,
  };
}

/**
 * `FAQPage` markup for an article's short answers.
 *
 * Emitted only when there are entries, and the entries are always also rendered
 * on the page by `FaqBlock` — markup describing content a reader cannot see is
 * what earns a manual penalty, and it is dishonest besides.
 */
export function faqSchema(post: BlogPost): Json | null {
  if (!post.faqs.length) return null;
  const url = absoluteUrl(`/blog/${post.slug}`);
  return {
    "@type": "FAQPage",
    "@id": `${url}#faq`,
    mainEntity: post.faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: { "@type": "Answer", text: faq.answer },
    })),
  };
}

/**
 * `Person` markup for an author.
 *
 * `sameAs` is the load-bearing part: it is how a search engine ties this byline
 * to a real identity elsewhere, which is what separates an authored article from
 * an anonymous one. A profile with no external links still gets a node, it just
 * asserts less.
 */
export function personSchema(author: AuthorPage): Json {
  const url = absoluteUrl(`/blog/author/${author.slug}`);
  return {
    "@type": "Person",
    "@id": `${url}#person`,
    name: author.display_name,
    url,
    ...(author.headline ? { jobTitle: author.headline } : {}),
    ...(author.avatar ? { image: author.avatar } : {}),
    ...(author.same_as.length ? { sameAs: author.same_as } : {}),
    worksFor: { "@id": `${SITE_URL}/#organisation` },
  };
}

/** The author archive page itself, as a collection. */
export function authorPageSchema(author: AuthorPage, posts: BlogPostCard[]): Json {
  const url = absoluteUrl(`/blog/author/${author.slug}`);
  return {
    "@type": "ProfilePage",
    "@id": `${url}#page`,
    url,
    mainEntity: { "@id": `${url}#person` },
    isPartOf: { "@id": `${SITE_URL}/blog#blog` },
    hasPart: posts.map((post) => ({
      "@type": "BlogPosting",
      "@id": `${absoluteUrl(`/blog/${post.slug}`)}#article`,
      headline: post.title,
      url: absoluteUrl(`/blog/${post.slug}`),
    })),
  };
}

export function breadcrumbSchema(trail: { name: string; path: string }[]): Json {
  return {
    "@type": "BreadcrumbList",
    itemListElement: trail.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.name,
      item: absoluteUrl(crumb.path),
    })),
  };
}

export function itemListSchema(posts: BlogPostCard[], path: string): Json {
  return {
    "@type": "ItemList",
    "@id": `${absoluteUrl(path)}#list`,
    itemListElement: posts.map((post, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: absoluteUrl(`/blog/${post.slug}`),
      name: post.title,
    })),
  };
}

/**
 * Wrap a set of nodes into one `@graph`.
 *
 * One script tag per page rather than several: cross-references by `@id` only
 * resolve inside a single graph, and that is what lets the article point at the
 * organisation instead of restating it.
 */
export function jsonLdGraph(...nodes: (Json | null | undefined)[]): string {
  const graph = nodes.filter(Boolean) as Json[];
  return JSON.stringify(
    { "@context": "https://schema.org", "@graph": graph },
    // Drop undefined so an optional field never ships as `null`.
    (_key, value) => (value === undefined ? undefined : value),
  );
}
