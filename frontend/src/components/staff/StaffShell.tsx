"use client";

/**
 * The staff workspace frame.
 *
 * Separate from `AppShell` on purpose: staff and students share nothing in
 * their navigation, and merging them would mean one component branching on role
 * in a dozen places. The accessibility structure is the same — skip link,
 * banner, one `<main id="content">`, labelled navs.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/lib/auth/SessionProvider";
import { CommandPalette, useCommandPalette } from "@/components/staff/CommandPalette";

const NAV = [
  { href: "/staff/review", label: "Review queue" },
  { href: "/staff/students", label: "Students" },
  { href: "/staff/blog", label: "Guides" },
  { href: "/staff/pricing", label: "Prices" },
];

const STAFF_ROLES = ["counsellor", "reviewer", "finance", "admin", "superadmin"];

export function StaffShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, loading, signOut } = useSession();
  const palette = useCommandPalette();

  const isStaff = Boolean(session && STAFF_ROLES.includes(session.user.role));

  useEffect(() => {
    if (loading) return;
    if (!session) {
      router.replace("/login");
      return;
    }
    // The server refuses every /api/admin/ route regardless; this only spares a
    // student the confusion of an empty console they cannot use.
    if (!isStaff) router.replace("/dashboard");
  }, [loading, session, isStaff, router]);

  if (loading || !session || !isStaff) {
    return (
      <div className="p-12 text-sm text-subtle" role="status">
        Checking your access…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-on-accent"
      >
        Skip to main content
      </a>

      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-6 py-3">
          <div className="flex items-center gap-6">
            <Link href="/staff/review" className="text-sm font-semibold text-ink">
              Nasuru <span className="font-normal text-subtle">staff</span>
            </Link>

            <nav aria-label="Staff sections">
              {/* `gap-y-1` and the links' own vertical padding keep every target
                  at least 24px with clear space around it (WCAG 2.5.8). Adding a
                  fourth section made the row wrap on a phone, and without this
                  the wrapped links sat close enough to overlap each other's
                  touch targets — axe caught it as target-offset. */}
              <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
                {NAV.map((item) => {
                  const active = pathname.startsWith(item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={
                          active
                            ? "block py-1.5 font-medium text-ink underline underline-offset-8"
                            : "block py-1.5 text-muted hover:text-ink"
                        }
                      >
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
          </div>

          <nav aria-label="Account" className="flex items-center gap-4 text-sm">
            <button
              type="button"
              onClick={palette.open}
              className="rounded-lg border border-field-line px-2.5 py-1 text-xs text-muted hover:border-line-strong hover:text-ink"
            >
              Search
              <kbd className="ml-2 font-mono text-[0.65rem] text-subtle">Ctrl K</kbd>
            </button>
            <span className="hidden text-muted sm:inline">{session.user.first_name}</span>
            <button type="button" onClick={signOut} className="text-muted hover:text-ink">
              Sign out
            </button>
          </nav>
        </div>
      </header>

      <main id="content" tabIndex={-1}>
        {children}
      </main>

      <CommandPalette controller={palette} />
    </div>
  );
}
