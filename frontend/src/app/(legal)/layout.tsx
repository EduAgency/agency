import Link from "next/link";

/**
 * Shared frame for the four public policy pages.
 *
 * These were linked from the landing page footer and the checkout flow from the
 * beginning but never existed, so every one of them 404'd — including the
 * privacy policy the footer cites as evidence of NDPR compliance
 * (docs/enterprise-readiness.md §A1).
 */

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-2xl px-6 py-12 sm:py-16">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Nasuru
      </Link>

      <main className="mt-8">{children}</main>

      <footer className="mt-16 border-t border-line pt-8 text-sm text-subtle">
        <nav aria-label="Policies" className="flex flex-wrap gap-x-6 gap-y-2">
          <Link href="/privacy" className="hover:underline">
            Privacy policy
          </Link>
          <Link href="/terms" className="hover:underline">
            Terms of service
          </Link>
          <Link href="/refund-policy" className="hover:underline">
            Refund policy
          </Link>
          <Link href="/contact" className="hover:underline">
            Contact
          </Link>
        </nav>
        <p className="mt-4">Nasuru.com Limited</p>
      </footer>
    </div>
  );
}
