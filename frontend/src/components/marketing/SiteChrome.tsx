/**
 * The public site's header and footer.
 *
 * Lifted out of the landing page when the blog arrived, because a blog that
 * doesn't carry the same header is a different website as far as a reader is
 * concerned — and the two would have drifted within a week of being copies.
 *
 * The section links are written as `/#anchor` rather than `#anchor` so they work
 * from an article as well as from the landing page.
 */

import Link from "next/link";
import { COMPANY, formattedAddress } from "@/lib/company";

const SECTIONS = [
  { href: "/#what-we-do", label: "What we do" },
  { href: "/#costs", label: "Real costs" },
  { href: "/#fees", label: "Our fee" },
  { href: "/blog", label: "Guides" },
];

export function SiteHeader({ current }: { current?: string }) {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <Link href="/" className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ color: "var(--on-accent)" }}
            >
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </span>
          <span>
            <span className="font-display block text-xl leading-none font-extrabold tracking-tight text-ink">
              Nasuru
            </span>
            <span className="text-xs text-subtle">International education agent</span>
          </span>
        </Link>
        <nav aria-label="Main" className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
          {SECTIONS.map((section) => (
            <Link
              key={section.href}
              href={section.href}
              aria-current={current === section.href ? "page" : undefined}
              className={
                current === section.href
                  ? "font-medium text-ink"
                  : "text-muted transition hover:text-ink"
              }
            >
              {section.label}
            </Link>
          ))}
          <Link href="/login" className="font-medium text-ink hover:underline">
            Sign in
          </Link>
          <Link
            href="/signup"
            className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-on-accent transition hover:bg-accent-hover"
          >
            Create an account
          </Link>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-canvas py-10">
      <div className="mx-auto max-w-6xl px-6">
        <nav aria-label="Policies" className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <Link href="/blog" className="text-muted hover:text-ink">
            Guides
          </Link>
          <Link href="/privacy" className="text-muted hover:text-ink">
            Privacy policy
          </Link>
          <Link href="/terms" className="text-muted hover:text-ink">
            Terms of service
          </Link>
          <Link href="/refund-policy" className="text-muted hover:text-ink">
            Refund policy
          </Link>
          <Link href="/contact" className="text-muted hover:text-ink">
            Contact
          </Link>
          <a href="/blog/rss.xml" className="text-muted hover:text-ink">
            RSS
          </a>
        </nav>
        <p className="mt-5 max-w-3xl text-sm leading-relaxed text-subtle">
          {COMPANY.legalName} · RC <span className="font-mono">{COMPANY.registrationNumber}</span> ·{" "}
          {formattedAddress()}. Your documents are stored encrypted, are never publicly linkable,
          and are processed in line with the Nigeria Data Protection Regulation.
        </p>
      </div>
    </footer>
  );
}
