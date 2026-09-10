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
];

const STAFF_ROUTES = [
  { path: "/staff/review", name: "Review queue", heading: /Review queue/ },
  { path: "/staff/students", name: "Student directory", heading: /Students/ },
  { path: "/staff/students/sp-1", name: "Student record", heading: /Amara Okafor/ },
];

for (const scheme of ["light", "dark"] as const) {
  test.describe(`student routes — ${scheme}`, () => {
    test.use({ colorScheme: scheme });

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
    test.use({ colorScheme: scheme });

    for (const route of STAFF_ROUTES) {
      test(`${route.name} has no axe violations`, async ({ staffPage }) => {
        await staffPage.goto(route.path);
        await expect(staffPage.getByRole("heading", { level: 1 })).toBeVisible();
        await expectNoViolations(staffPage);
      });
    }

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
    const skip = studentPage.getByRole("link", { name: /skip to main content/i });
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
    const response = await studentPage.request.get("http://127.0.0.1:3000/api/not-a-real-route/");
    // Guards against the fixture silently answering 200 for everything, which
    // would make every test above meaningless.
    expect(response.status()).toBe(404);
  });
});
