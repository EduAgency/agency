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
/**
 * A port of its own, and never an adopted server.
 *
 * `reuseExistingServer: true` adopts whatever is already listening on the port.
 * That is not a convenience, it is a trap: on this machine 3000 and 3100 were
 * both taken by unrelated services, and the suite happily ran 32 "passing"
 * accessibility scans against a Grafana login page before anyone noticed. A
 * test run that silently targets the wrong server is worse than no test run.
 *
 * So: an unusual port, and Playwright always starts its own build. If the port
 * is busy it fails loudly instead of guessing. Override with E2E_PORT, or point
 * E2E_BASE_URL at a deployed environment to skip the local server entirely.
 */
const PORT = Number(process.env.E2E_PORT ?? 4317);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? `http://127.0.0.1:${PORT}`,
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
        command: `npm run build && npm run start -- --port ${PORT}`,
        url: `http://127.0.0.1:${PORT}`,
        reuseExistingServer: false,
        timeout: 180_000,
      },
});
