"use client";

/**
 * The signed-in app frame.
 *
 * Every page used to hand-roll its own `<main>` and its own `<nav>`, with no
 * banner landmark, no skip target, and two unlabelled navs on the dashboard
 * (§B1). Now there is one banner, one `<main id="content">`, and every nav has
 * a name a screen reader can distinguish.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "@/lib/auth/SessionProvider";

const NAV = [
  { href: "/dashboard", label: "Applications" },
  { href: "/documents", label: "Documents" },
  { href: "/referrals", label: "Referrals" },
  { href: "/settings/notifications", label: "Notifications" },
];

export function SkipLink() {
  /**
   * Off-screen until focused, then pinned to the top-left. `sr-only` alone
   * would keep it invisible even when focused, which defeats the point — a
   * sighted keyboard user has to be able to see what they have landed on.
   */
  return (
    <a
      href="#content"
      className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-on-accent"
    >
      Skip to main content
    </a>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { session, signOut, hasAccess } = useSession();

  /**
   * Before the access fee is confirmed, every destination in the main nav
   * bounces straight back to checkout — so showing it would be a loop with no
   * exit. Checkout and the payment callback get the banner, the skip link and
   * the landmark structure, but no navigation to pages the student cannot
   * reach yet.
   */
  const showNav = Boolean(session) && hasAccess;

  return (
    <div className="min-h-screen bg-canvas">
      <SkipLink />

      <header className="border-b border-line">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-6 py-4">
          <Link href="/dashboard" className="text-sm font-semibold text-ink">
            Nasuru
          </Link>

          {showNav && (
            <nav aria-label="Main" className="order-3 w-full sm:order-none sm:w-auto">
              <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
                {NAV.map((item) => {
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        // `aria-current` is what tells a screen reader which page
                        // this is; the underline is the sighted equivalent.
                        aria-current={active ? "page" : undefined}
                        className={
                          active
                            ? "font-medium text-ink underline underline-offset-8"
                            : "text-muted hover:text-ink"
                        }
                      >
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
          )}

          <nav aria-label="Account" className="flex items-center gap-4 text-sm">
            {session?.user.first_name && (
              <span className="hidden text-muted sm:inline">{session.user.first_name}</span>
            )}
            <button type="button" onClick={signOut} className="text-muted hover:text-ink">
              Sign out
            </button>
          </nav>
        </div>
      </header>

      <main id="content" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
