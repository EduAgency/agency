import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end accessibility gate.
 *
 * Phase 2's exit criterion is "axe reports zero violations on all routes;
 * keyboard-only walkthrough passes" — this is what makes that an observable
 * test rather than an opinion (docs/enterprise-readiness.md §B9).
 *
 * Public routes are scanned as-is. Signed-in routes — the student dashboard,
 * the checklist, the document vault, checkout, and the whole staff console —
 * run against the seeded fixture API in `e2e/fixtures/`, which serves the real
 * serializer shapes over `page.route()` so the suite needs no Postgres, Redis
 * or migration step. Drift between those fixtures and the API is caught by
 * `backend/tests/test_frontend_contract.py`.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // Most of this audience is on a phone, and the layout stacks there.
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run build && npm run start",
        url: "http://127.0.0.1:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
      },
});
