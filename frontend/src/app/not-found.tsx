import Link from "next/link";

/**
 * Branded 404. Six routes linked from the landing page and dashboard used to
 * land on the stock Next.js error page (docs/enterprise-readiness.md §A1).
 */

export const metadata = {
  title: "Page not found — Nasuru",
};

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <p className="font-mono text-sm text-subtle">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-ink">We can&apos;t find that page</h1>
      <p className="mt-3 text-sm text-muted">
        The link may be out of date, or the page may have moved.
      </p>

      <nav aria-label="Suggested pages" className="mt-8 flex flex-col gap-2 text-sm">
        <Link href="/dashboard" className="text-ink underline underline-offset-4">
          My dashboard
        </Link>
        <Link href="/" className="text-muted underline underline-offset-4">
          Home
        </Link>
        <Link href="/contact" className="text-muted underline underline-offset-4">
          Contact us
        </Link>
      </nav>
    </main>
  );
}
