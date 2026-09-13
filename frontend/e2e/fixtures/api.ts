import { test as base, type Page } from "@playwright/test";
import * as seed from "./data";

/**
 * A seeded API, served by Playwright rather than Django.
 *
 * Why not run the real backend? Because what these tests assert is how the
 * *rendered UI* behaves — axe violations, landmark structure, keyboard flow —
 * and for that a real Postgres, Redis, Celery and a migration step buy nothing
 * but flakiness and a two-minute CI step. The API contract is already covered
 * by the backend's own 87 tests.
 *
 * The risk this trades for is drift: a mock that no longer matches the real
 * response makes a broken page look tested. That is handled in two places —
 * `FIELD_CONTRACT` in data.ts, checked by a backend test, and the fact that
 * every route below returns the shape its serializer declares.
 *
 * Usage:
 *
 *   test("...", async ({ studentPage }) => { await studentPage.goto("/dashboard"); });
 *   test("...", async ({ staffPage })   => { await staffPage.goto("/staff/review"); });
 */

type Json = Record<string, unknown> | unknown[];

function paginate(results: unknown[]) {
  return { count: results.length, next: null, previous: null, results };
}

/** Every route the frontend can reach, keyed by a matcher over the pathname. */
function resolve(pathname: string, search: URLSearchParams, session: Json): Json | null {
  // --- auth ---------------------------------------------------------------
  if (pathname === "/api/auth/me/") return session;
  if (pathname === "/api/auth/token/refresh/") return { access: seed.STUDENT_TOKEN };
  if (pathname === "/api/auth/resend-verification/") return { detail: "Confirmation email sent." };

  // --- student ------------------------------------------------------------
  if (pathname === "/api/applications/") return paginate(seed.applications);
  if (/^\/api\/applications\/[^/]+\/checklist\/$/.test(pathname)) return seed.checklist;
  if (/^\/api\/applications\/[^/]+\/$/.test(pathname)) {
    const id = pathname.split("/").filter(Boolean)[2];
    return seed.applications.find((a) => a.id === id) ?? seed.applications[0];
  }
  if (pathname === "/api/documents/") return paginate(seed.documents);
  if (pathname === "/api/schools/") return paginate(seed.schools);
  // Pricing. Read by checkout and signup in the browser; the public pages read
  // it on the server, where page.route() cannot see it.
  if (pathname === "/api/pricing/") return seed.publicPricing;
  if (pathname === "/api/admin/pricing/") return seed.adminPricing;
  if (pathname === "/api/admin/cost-estimates/") return seed.adminCostEstimates;
  if (pathname === "/api/payments/gateways/") return seed.gateways;
  if (pathname === "/api/payments/mine/") return seed.payments;
  if (pathname === "/api/payments/verify/") return seed.payments[0];
  if (pathname === "/api/referrals/mine/") return seed.referrals;
  if (pathname === "/api/notifications/preferences/") return seed.preferenceCentre;
  if (pathname === "/api/notifications/quiet-hours/") return { detail: "Saved." };
  if (pathname === "/api/notifications/whatsapp/") return { detail: "Saved." };
  if (pathname === "/api/notifications/telegram/") {
    return {
      url: "https://t.me/nasuru_bot?start=example",
      bot_username: "nasuru_bot",
      expires_in_seconds: 900,
    };
  }
  if (pathname === "/api/forms/student-intake/") return seed.intakeForm;
  if (pathname === "/api/my/submissions/") return [];

  // --- staff --------------------------------------------------------------
  if (pathname === "/api/admin/review-queue/") {
    const term = (search.get("search") ?? "").toLowerCase();
    const rows = term
      ? seed.reviewQueue.filter(
          (r) =>
            r.label.toLowerCase().includes(term) ||
            (r.student_email ?? "").toLowerCase().includes(term),
        )
      : seed.reviewQueue;
    return paginate(rows);
  }
  if (pathname === "/api/admin/students/") {
    const term = (search.get("search") ?? "").toLowerCase();
    const rows = term
      ? seed.staffStudents.filter(
          (s) =>
            s.user.full_name.toLowerCase().includes(term) ||
            s.user.email.toLowerCase().includes(term),
        )
      : seed.staffStudents;
    return paginate(rows);
  }
  if (/^\/api\/admin\/students\/[^/]+\/$/.test(pathname)) {
    const id = pathname.split("/").filter(Boolean)[3];
    return seed.staffStudents.find((s) => s.id === id) ?? seed.staffStudents[0];
  }
  if (/^\/api\/checklist-items\/[^/]+\/review\/$/.test(pathname)) {
    return {
      ...seed.checklistItems[0],
      status: "verified",
      status_display: "Verified",
    };
  }

  // --- blog ---------------------------------------------------------------
  // Only the staff composer is covered here. The public blog pages fetch from
  // the API on the *server*, which page.route() cannot see — so those are
  // scanned in accessibility.spec.ts in the state they render when the API is
  // unreachable, which is a real state they have to handle.
  if (pathname === "/api/admin/blog/ai/status/") {
    return { enabled: true, model: "claude-opus-5" };
  }
  if (pathname === "/api/admin/blog/settings/") return seed.blogSettings;
  if (pathname === "/api/admin/blog/authors/me/") return seed.authorProfile;
  if (pathname === "/api/admin/blog/authors/") return [seed.authorProfile];
  if (pathname === "/api/admin/blog/comments/summary/") return seed.commentSummaryCounts;
  if (pathname === "/api/admin/blog/comments/") {
    const status = search.get("status") ?? "pending";
    const rows =
      status === "all" ? seed.adminComments : seed.adminComments.filter((c) => c.status === status);
    return paginate(rows);
  }
  if (pathname === "/api/admin/blog/faqs/") return seed.postFaqs;
  if (pathname === "/api/admin/blog/categories/") return seed.blogCategories;
  if (pathname === "/api/admin/blog/tags/") return seed.blogTags;
  if (pathname === "/api/admin/blog/posts/") return paginate([seed.adminBlogPost]);
  if (/^\/api\/admin\/blog\/posts\/[^/]+\/preflight\/$/.test(pathname)) return seed.blogPreflight;
  if (/^\/api\/admin\/blog\/posts\/[^/]+\/revisions\/$/.test(pathname)) return seed.blogRevisions;
  if (/^\/api\/admin\/blog\/posts\/[^/]+\/$/.test(pathname)) return seed.adminBlogPost;

  return null;
}

async function installApi(page: Page, session: Json, token: string) {
  // Seeded before any script runs, so SessionProvider finds a token on its
  // first render rather than flashing the signed-out state.
  await page.addInitScript(
    ([accessKey, refreshKey, value]) => {
      window.localStorage.setItem(accessKey as string, value as string);
      window.localStorage.setItem(refreshKey as string, `${value}-refresh`);
    },
    ["nasuru.access", "nasuru.refresh", token],
  );

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const body = resolve(url.pathname, url.searchParams, session);

    if (body === null) {
      // Loud on purpose. A silent 200 for an unmapped route is how a fixture
      // API starts lying about what the product does.
      return route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          detail: `e2e fixture has no handler for ${url.pathname}. Add one in e2e/fixtures/api.ts.`,
        }),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

export const test = base.extend<{
  studentPage: Page;
  unpaidPage: Page;
  staffPage: Page;
  editorPage: Page;
}>({
  studentPage: async ({ page }, use) => {
    await installApi(page, seed.studentSession, seed.STUDENT_TOKEN);
    await use(page);
  },

  /** A student who has signed up but not paid — checkout and its gates. */
  unpaidPage: async ({ page }, use) => {
    await installApi(page, seed.unpaidStudentSession, seed.STUDENT_TOKEN);
    await use(page);
  },

  staffPage: async ({ page }, use) => {
    await installApi(page, seed.staffSession, seed.STAFF_TOKEN);
    await use(page);
  },

  /** Staff who can write and publish — the blog composer. */
  editorPage: async ({ page }, use) => {
    await installApi(page, seed.editorSession, seed.STAFF_TOKEN);
    await use(page);
  },
});

export { expect } from "@playwright/test";
export { seed };
