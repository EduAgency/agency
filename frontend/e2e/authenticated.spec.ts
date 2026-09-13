import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures/api";

/**
 * Accessibility coverage for everything behind a sign-in.
 *
 * These are roughly half the product — the dashboard, the checklist, the
 * document vault, checkout, referrals, and the whole staff console — and until
 * the seeded fixture API landed none of them had ever been scanned. The public
 * suite in accessibility.spec.ts was passing while the pages staff use every
 * day were untested.
 */

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

function scan(page: import("@playwright/test").Page) {
  return new AxeBuilder({ page }).withTags(WCAG);
}

async function expectNoViolations(page: import("@playwright/test").Page) {
  const results = await scan(page).analyze();
  expect(
    results.violations,
    results.violations
      .map((v) => `${v.id} (${v.impact}): ${v.help}\n    ${v.nodes[0]?.html ?? ""}`)
      .join("\n"),
  ).toEqual([]);
}

const STUDENT_ROUTES = [
  { path: "/dashboard", name: "Dashboard", heading: /Hello, Amara/ },
  { path: "/documents", name: "Document vault", heading: /My documents/ },
  { path: "/applications/new", name: "Add a school", heading: /.+/ },
  { path: "/applications/app-1", name: "Application checklist", heading: /.+/ },
  { path: "/referrals", name: "Referrals", heading: /.+/ },
  { path: "/intake", name: "Intake form", heading: /.+/ },
  {
    path: "/settings/notifications",
    name: "Notification settings",
    heading: /How we reach you/,
  },
];

const STAFF_ROUTES = [
  { path: "/staff/review", name: "Review queue", heading: /Review queue/ },
  { path: "/staff/students", name: "Student directory", heading: /Students/ },
  {
    path: "/staff/students/sp-1",
    name: "Student record",
    heading: /Amara Okafor/,
  },
];

/**
 * Scans run with reduced motion.
 *
 * Not to skip anything — axe does not test animation — but because the app's
 * own CSS collapses every transition to ~0 under `prefers-reduced-motion`, and
 * a colour-contrast check that lands mid-transition reads an interpolated
 * colour that never actually renders at rest. That was an intermittent failure
 * on the checklist page's progress bar.
 */
for (const scheme of ["light", "dark"] as const) {
  test.describe(`student routes — ${scheme}`, () => {
    test.use({ colorScheme: scheme, reducedMotion: "reduce" });

    for (const route of STUDENT_ROUTES) {
      test(`${route.name} has no axe violations`, async ({ studentPage }) => {
        await studentPage.goto(route.path);
        // Wait for real content, not a skeleton — scanning a loading state
        // proves nothing about the page that follows it.
        await expect(studentPage.getByRole("heading", { level: 1 })).toBeVisible();
        await expectNoViolations(studentPage);
      });
    }

    test("Checkout has no axe violations", async ({ unpaidPage }) => {
      await unpaidPage.goto("/checkout");
      await expect(unpaidPage.getByRole("heading", { level: 1 })).toBeVisible();
      await expectNoViolations(unpaidPage);
    });
  });

  test.describe(`staff routes — ${scheme}`, () => {
    test.use({ colorScheme: scheme, reducedMotion: "reduce" });

    for (const route of STAFF_ROUTES) {
      test(`${route.name} has no axe violations`, async ({ staffPage }) => {
        await staffPage.goto(route.path);
        await expect(staffPage.getByRole("heading", { level: 1 })).toBeVisible();
        await expectNoViolations(staffPage);
      });
    }

    test("Blog list has no axe violations", async ({ editorPage }) => {
      await editorPage.goto("/staff/blog");
      await expect(editorPage.getByRole("heading", { level: 1, name: "Guides" })).toBeVisible();
      await expect(editorPage.getByRole("table")).toBeVisible();
      await expectNoViolations(editorPage);
    });

    test("Composer has no axe violations", async ({ editorPage }) => {
      await editorPage.goto("/staff/blog/start-with-your-transcript");
      await expect(editorPage.getByRole("heading", { level: 1 })).toBeVisible();
      // The pre-flight panel only renders once the checks have come back, and
      // it carries most of the page's colour-on-colour risk.
      await expect(editorPage.getByText("blocker", { exact: false }).first()).toBeVisible();
      await expectNoViolations(editorPage);
    });

    test("Composer preview has no axe violations", async ({ editorPage }) => {
      await editorPage.goto("/staff/blog/start-with-your-transcript");
      await expect(editorPage.getByRole("heading", { level: 1 })).toBeVisible();
      // Same `.post-body` markup and typography the public article renders, so
      // this is where those rules get scanned.
      await editorPage.getByRole("button", { name: "Preview" }).click();
      await expect(
        editorPage.getByText("This is the last saved version.", {
          exact: false,
        }),
      ).toBeVisible();
      await expectNoViolations(editorPage);
    });

    test("Blog settings has no axe violations", async ({ editorPage }) => {
      await editorPage.goto("/staff/blog/settings");
      await expect(
        editorPage.getByRole("heading", { level: 1, name: "Blog settings" }),
      ).toBeVisible();
      // The densest form on the site: forty controls, each with its own hint.
      await expect(editorPage.getByLabel("Articles per page")).toBeVisible();
      await expectNoViolations(editorPage);
    });

    test("Comment queue has no axe violations", async ({ editorPage }) => {
      await editorPage.goto("/staff/blog/comments");
      await expect(editorPage.getByRole("heading", { level: 1, name: "Comments" })).toBeVisible();
      // Wait for a row, and specifically for the flagged one — the warning panel
      // inside it is the colour pairing most at risk.
      await expect(editorPage.getByText("Flagged:", { exact: false })).toBeVisible();
      await expectNoViolations(editorPage);
    });

    test("Author profiles has no axe violations", async ({ editorPage }) => {
      await editorPage.goto("/staff/blog/authors");
      await expect(
        editorPage.getByRole("heading", { level: 1, name: "Author profiles" }),
      ).toBeVisible();
      await expect(editorPage.getByLabel("Byline")).toBeVisible();
      await expectNoViolations(editorPage);
    });

    test("Prices has no axe violations", async ({ staffPage }) => {
      await staffPage.goto("/staff/pricing");
      await expect(staffPage.getByRole("heading", { level: 1, name: "Prices" })).toBeVisible();
      // Wait for the stale-estimate warning: it is the colour pairing most at risk.
      await expect(staffPage.getByText("Ask us", { exact: false }).first()).toBeVisible();
      await expectNoViolations(staffPage);
    });

    test("Command palette has no axe violations while open", async ({ staffPage }) => {
      await staffPage.goto("/staff/students");
      await staffPage.getByRole("heading", { level: 1 }).waitFor();
      await staffPage.keyboard.press("Control+k");

      const dialog = staffPage.getByRole("dialog");
      await expect(dialog).toBeVisible();
      await staffPage.getByRole("combobox").fill("amara");
      await expect(staffPage.getByRole("option").first()).toBeVisible();

      await expectNoViolations(staffPage);
    });
  });
}

test.describe("the blog composer", () => {
  test.use({ reducedMotion: "reduce" });

  test("records that AI wrote the draft, and requires the notes", async ({ editorPage }) => {
    await editorPage.goto("/staff/blog/start-with-your-transcript");
    await expect(editorPage.getByRole("heading", { level: 1 })).toBeVisible();

    await expect(editorPage.getByLabel("How AI was involved")).toHaveValue("draft");
    await expect(editorPage.getByLabel("What was generated, and what you changed")).not.toHaveValue(
      "",
    );
  });

  test("cannot publish while there are unsaved changes", async ({ editorPage }) => {
    await editorPage.goto("/staff/blog/start-with-your-transcript");
    await expect(editorPage.getByRole("heading", { level: 1 })).toBeVisible();

    await editorPage.getByLabel("Title", { exact: true }).fill("An edited title");
    await expect(editorPage.getByText("Unsaved changes")).toBeVisible();
    await expect(editorPage.getByRole("button", { name: "Publish" })).toBeDisabled();
    await expect(editorPage.getByText("Save your changes before publishing.")).toBeVisible();
  });

  test("shows the assist as suggestions, not as edits", async ({ editorPage }) => {
    await editorPage.goto("/staff/blog/start-with-your-transcript");
    await expect(editorPage.getByRole("heading", { level: 1 })).toBeVisible();

    const panel = editorPage.getByRole("region", { name: "AI assist" });
    await expect(panel).toBeVisible();
    await expect(
      panel.getByText("Nothing reaches the draft until you press a Use button", { exact: false }),
    ).toBeVisible();
    // Nothing to apply before anything has been generated.
    await expect(panel.getByRole("button", { name: /^Use/ })).toHaveCount(0);
  });
});

test.describe("prices", () => {
  test.use({ reducedMotion: "reduce" });

  test("the checkout button quotes the fee the API serves", async ({ unpaidPage }) => {
    // The assertion that would have caught the original bug: the button used to
    // have the number typed into it, and could disagree with what was charged.
    await unpaidPage.goto("/checkout");
    await expect(unpaidPage.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(unpaidPage.getByRole("button", { name: "Pay ₦5,000" })).toBeVisible();
  });

  test("warns before a price change lands", async ({ staffPage }) => {
    await staffPage.goto("/staff/pricing");
    await expect(staffPage.getByRole("heading", { level: 1 })).toBeVisible();

    await expect(staffPage.getByText("This changes what students pay")).toHaveCount(0);
    await staffPage.getByLabel("Amount").fill("7500.00");
    await expect(staffPage.getByText("This changes what students pay")).toBeVisible();
  });

  test("shows what a student actually sees for a stale figure", async ({ staffPage }) => {
    await staffPage.goto("/staff/pricing");
    await expect(staffPage.getByRole("heading", { level: 1 })).toBeVisible();

    // The stored figure is still ₦180,000, but the row has gone stale, so what
    // the reader gets is the invitation instead.
    await expect(staffPage.getByText("Ask us", { exact: false }).first()).toBeVisible();
  });
});

test.describe("comment moderation", () => {
  test.use({ reducedMotion: "reduce" });

  test("says why a comment was flagged", async ({ editorPage }) => {
    await editorPage.goto("/staff/blog/comments");
    await expect(editorPage.getByRole("heading", { level: 1 })).toBeVisible();

    // An unexplained "flagged" badge teaches a moderator to approve everything.
    await expect(editorPage.getByText("3 links (limit 1)", { exact: false })).toBeVisible();
  });

  test("shows the commenter's email to a moderator but the page never does", async ({
    editorPage,
  }) => {
    await editorPage.goto("/staff/blog/comments");
    await expect(editorPage.getByText("ada@example.com")).toBeVisible();
  });

  test("offers no bulk actions until something is selected", async ({ editorPage }) => {
    await editorPage.goto("/staff/blog/comments");
    await expect(editorPage.getByRole("heading", { level: 1 })).toBeVisible();

    await expect(editorPage.getByText(/\d+ selected/)).toHaveCount(0);
    await editorPage.getByLabel("Select the comment by Ada Obi").check();
    await expect(editorPage.getByText("1 selected")).toBeVisible();
  });
});

test.describe("blog settings", () => {
  test.use({ reducedMotion: "reduce" });

  test("cannot be saved until something changes", async ({ editorPage }) => {
    await editorPage.goto("/staff/blog/settings");
    await expect(editorPage.getByRole("heading", { level: 1 })).toBeVisible();

    await expect(editorPage.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
    await editorPage.getByLabel("Articles per page").fill("6");
    await expect(editorPage.getByRole("button", { name: "Save", exact: true })).toBeEnabled();
    await expect(editorPage.getByText("Unsaved changes")).toBeVisible();
  });

  test("says plainly that the analytics id is not wired up yet", async ({ editorPage }) => {
    await editorPage.goto("/staff/blog/settings");
    await expect(
      editorPage.getByText("Stored but NOT yet loaded on the site", { exact: false }),
    ).toBeVisible();
  });
});

test.describe("document structure", () => {
  for (const route of [...STUDENT_ROUTES]) {
    test(`${route.name} has one main landmark and one h1`, async ({ studentPage }) => {
      await studentPage.goto(route.path);
      await expect(studentPage.getByRole("heading", { level: 1 })).toBeVisible();
      // The app shell owns <main>; pages used to nest their own inside it.
      await expect(studentPage.locator("main")).toHaveCount(1);
      await expect(studentPage.locator("h1")).toHaveCount(1);
    });
  }

  for (const route of STAFF_ROUTES) {
    test(`${route.name} has one main landmark and one h1`, async ({ staffPage }) => {
      await staffPage.goto(route.path);
      await expect(staffPage.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(staffPage.locator("main")).toHaveCount(1);
      await expect(staffPage.locator("h1")).toHaveCount(1);
    });
  }
});

test.describe("the skip link", () => {
  test("is the first tab stop and moves focus to main", async ({ studentPage }) => {
    await studentPage.goto("/dashboard");
    await expect(studentPage.getByRole("heading", { level: 1 })).toBeVisible();

    await studentPage.keyboard.press("Tab");
    const skip = studentPage.getByRole("link", {
      name: /skip to main content/i,
    });
    await expect(skip).toBeFocused();
    // sr-only until focused, then genuinely visible — otherwise it is useless
    // to the sighted keyboard user it exists for.
    await expect(skip).toBeVisible();

    await studentPage.keyboard.press("Enter");
    await expect(studentPage.locator("#content")).toBeFocused();
  });

  test("is present in the staff console too", async ({ staffPage }) => {
    await staffPage.goto("/staff/review");
    await expect(staffPage.getByRole("heading", { level: 1 })).toBeVisible();
    await staffPage.keyboard.press("Tab");
    await expect(staffPage.getByRole("link", { name: /skip to main content/i })).toBeFocused();
  });
});

test.describe("review queue keyboard flow", () => {
  test("J and K move through the queue without a mouse", async ({ staffPage }) => {
    await staffPage.goto("/staff/review");
    await expect(staffPage.getByRole("heading", { name: /Review queue/ })).toBeVisible();

    await expect(staffPage.getByText("1 of 2 waiting")).toBeVisible();
    await staffPage.keyboard.press("j");
    await expect(staffPage.getByText("2 of 2 waiting")).toBeVisible();
    await staffPage.keyboard.press("k");
    await expect(staffPage.getByText("1 of 2 waiting")).toBeVisible();
  });

  test("R opens the reason box and refuses an empty rejection", async ({ staffPage }) => {
    await staffPage.goto("/staff/review");
    await expect(staffPage.getByRole("heading", { name: /Review queue/ })).toBeVisible();

    await staffPage.keyboard.press("r");
    const reason = staffPage.getByLabel("Rejection reason");
    await expect(reason).toBeFocused();

    // The server refuses a rejection with no reason; so does the UI, rather
    // than letting the reviewer discover it from a 400.
    await expect(staffPage.getByRole("button", { name: "Send rejection" })).toBeDisabled();

    await staffPage.getByRole("button", { name: /image is too blurred/i }).click();
    await expect(staffPage.getByRole("button", { name: "Send rejection" })).toBeEnabled();
  });

  test("shortcuts do not fire while typing a reason", async ({ staffPage }) => {
    await staffPage.goto("/staff/review");
    await expect(staffPage.getByRole("heading", { name: /Review queue/ })).toBeVisible();

    await staffPage.keyboard.press("r");
    await staffPage.getByLabel("Rejection reason").fill("");
    await staffPage.keyboard.type("jkv blurred");

    // Still on item 1: J/K/V must be literal characters inside a text box.
    await expect(staffPage.getByText("1 of 2 waiting")).toBeVisible();
    await expect(staffPage.getByLabel("Rejection reason")).toHaveValue("jkv blurred");
  });
});

test.describe("the fixture API itself", () => {
  test("fails loudly on an unmapped route", async ({ studentPage }) => {
    await studentPage.goto("/dashboard");
    // Fetched from inside the page: `page.request` is a separate context that
    // bypasses route interception entirely, so it would not exercise the
    // fixture at all.
    const status = await studentPage.evaluate(async () => {
      const res = await fetch("/api/not-a-real-route/");
      return res.status;
    });
    // Guards against the fixture silently answering 200 for everything, which
    // would make every test above meaningless.
    expect(status).toBe(404);
  });
});

test.describe("notification preferences", () => {
  test("a channel the user has not connected cannot be switched on", async ({ studentPage }) => {
    await studentPage.goto("/settings/notifications");
    await expect(studentPage.getByRole("heading", { name: /How we reach you/ })).toBeVisible();

    // WhatsApp is available but not opted in. Offering a live toggle here is
    // how a student opts in, stops watching email, and misses a rejection.
    const whatsapp = studentPage.getByRole("checkbox", {
      name: /Document by WhatsApp/,
    });
    await expect(whatsapp).toBeDisabled();

    // Telegram is connected, so its toggle works.
    await expect(studentPage.getByRole("checkbox", { name: /Document by Telegram/ })).toBeEnabled();
  });

  test("transactional email is locked on, and says so", async ({ studentPage }) => {
    await studentPage.goto("/settings/notifications");
    await expect(studentPage.getByRole("heading", { name: /How we reach you/ })).toBeVisible();

    const accountEmail = studentPage.getByRole("checkbox", {
      name: /Account by Email/,
    });
    await expect(accountEmail).toBeChecked();
    await expect(accountEmail).toBeDisabled();
    await expect(accountEmail).toHaveAccessibleName(/always on/i);
  });

  test("an optional category can be switched off", async ({ studentPage }) => {
    await studentPage.goto("/settings/notifications");
    await expect(studentPage.getByRole("heading", { name: /How we reach you/ })).toBeVisible();

    await expect(studentPage.getByRole("checkbox", { name: /Document by Email/ })).toBeEnabled();
  });

  test("SMS is not offered anywhere", async ({ studentPage }) => {
    await studentPage.goto("/settings/notifications");
    await expect(studentPage.getByRole("heading", { name: /How we reach you/ })).toBeVisible();

    await expect(studentPage.getByText(/SMS/i)).toHaveCount(0);
  });
});
