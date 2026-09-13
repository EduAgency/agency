/**
 * Fails a production build while any published policy still contains an unmade
 * decision.
 *
 *   node scripts/check-launch-ready.mjs
 *
 * The policy pages deliberately render visible "needs sign-off" blocks rather
 * than inventing terms nobody agreed to (docs/enterprise-readiness.md, Phase 1).
 * That is the right behaviour in development and completely the wrong thing to
 * ship: a privacy policy with a hole in it is worse than one that is late.
 *
 * So the markers are a launch checklist with teeth. This script reports them
 * always, and exits non-zero when it is asked to gate a real deployment.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const srcDir = join(root, "src");

/** Gate on an explicit flag, or on any recognised production environment. */
const GATING =
  process.argv.includes("--strict") ||
  process.env.LAUNCH_CHECK === "strict" ||
  process.env.VERCEL_ENV === "production" ||
  process.env.NODE_ENV === "production";

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(full)) out.push(full);
  }
  return out;
}

const findings = [];

for (const file of walk(srcDir)) {
  const text = readFileSync(file, "utf8");
  const shown = relative(root, file).replace(/\\/g, "/");

  // A page that renders the marker, not the component that defines it.
  if (/<NeedsSignOff>/.test(text) && !shown.endsWith("components/legal.tsx")) {
    const count = (text.match(/<NeedsSignOff>/g) ?? []).length;
    findings.push({ file: shown, kind: "needs sign-off", count });
  }

  // Unmade values in the company config.
  if (shown.endsWith("lib/company.ts")) {
    for (const [, value] of text.matchAll(/\$\{PENDING\}\s*([a-z ]+)/g)) {
      findings.push({ file: shown, kind: "PENDING value", count: 1, detail: value.trim() });
    }
  }
}

const PRICING_NOTE = [
  '  Prices are not checked here. They moved out of company.ts into the',
  '  database (apps.payments.pricing), so this script cannot see them - run',
  '  `make pricing`, or `make pricing ARGS=--strict` in CI, to catch an',
  '  unverified cost figure before it reaches a page.',
].join('\n');

if (findings.length === 0) {
  console.log("\n  Launch check: no unmade decisions remain in published pages.\n");
  console.log(PRICING_NOTE);
  process.exit(0);
}

const total = findings.reduce((sum, f) => sum + f.count, 0);
console.log(`\n  Launch check: ${total} unmade decision${total === 1 ? "" : "s"} still published\n`);
for (const finding of findings) {
  const detail = finding.detail ? ` — ${finding.detail}` : "";
  console.log(`    ${finding.file}  (${finding.count} × ${finding.kind}${detail})`);
}

if (GATING) {
  console.log(
    "\n  Refusing a production build. Resolve these, or drop the marker if the\n" +
      "  clause is genuinely settled. See docs/enterprise-readiness.md.\n",
  );
  process.exit(1);
}

console.log(PRICING_NOTE);
console.log("\n  (Not gating: this is a development build. Run with --strict to gate.)\n");
process.exit(0);
