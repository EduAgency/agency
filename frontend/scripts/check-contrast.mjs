/**
 * Verifies every colour pair the design system actually uses, in both themes,
 * against its WCAG 2.2 threshold.
 *
 *   node scripts/check-contrast.mjs
 *
 * Values are read out of `src/app/globals.css` rather than duplicated here, so
 * this cannot drift from the tokens it checks: change a token, and the next run
 * checks the new value.
 *
 * Thresholds (WCAG 2.2):
 *   4.5  normal text                      (1.4.3 AA)
 *   3.0  large text ≥18.66px bold/24px    (1.4.3 AA)
 *   3.0  UI component and state boundaries (1.4.11 AA)
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, "..", "src", "app", "globals.css"), "utf8");

/** Pull one `:root`-style block's custom properties into a map. */
function readBlock(source, startPattern) {
  const start = source.indexOf(startPattern);
  if (start === -1) throw new Error(`Could not find block: ${startPattern}`);
  const open = source.indexOf("{", start);
  let depth = 0;
  let end = open;
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === "{") depth += 1;
    if (source[i] === "}") {
      depth -= 1;
      if (depth === 0) {
        end = i;
        break;
      }
    }
  }
  const body = source.slice(open + 1, end);
  const tokens = {};
  for (const [, name, value] of body.matchAll(/--([a-z-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;/g)) {
    tokens[name] = value;
  }
  return tokens;
}

// The bare `:root` block carries the complete light palette; the explicit dark
// stamp carries the complete dark palette. The `prefers-color-scheme` block is
// identical to the latter by construction, and is checked for exactly that.
const light = readBlock(css, "\n:root {");
const dark = readBlock(css, ':root[data-theme="dark"] {');
const media = readBlock(css, ':root:not([data-theme="light"]) {');

function toRgb(hex) {
  let value = hex.replace("#", "");
  if (value.length === 3)
    value = value
      .split("")
      .map((c) => c + c)
      .join("");
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16));
}

function luminance(hex) {
  const [r, g, b] = toRgb(hex).map((channel) => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
}

/**
 * [foreground, background, minimum, description, level]
 *
 * `level` matters, because applying 3:1 indiscriminately to every border is
 * both wrong and counterproductive — it forces a heavy, garish UI in the name
 * of a rule that does not apply.
 *
 *   text  WCAG 1.4.3 AA. Required. Anything a person reads.
 *   ui    WCAG 1.4.11 AA. Required. Boundaries that are the ONLY way to
 *         identify a control or its state — input borders, the focus ring.
 *   decor Not a WCAG requirement, reported for eyeballing only. An alert
 *         panel's border is decorative: the panel is already identified by
 *         its background tint, its icon-free text and, for assistive tech, its
 *         `role`. Removing the border loses no information.
 */
const PAIRS = [
  ["ink", "canvas", 4.5, "Body text on the page", "text"],
  ["ink", "surface", 4.5, "Body text on a card", "text"],
  ["ink", "sunken", 4.5, "Body text on a sunken panel", "text"],
  ["muted", "canvas", 4.5, "Secondary text on the page", "text"],
  ["muted", "surface", 4.5, "Secondary text on a card", "text"],
  ["muted", "sunken", 4.5, "Secondary text on a sunken panel", "text"],
  ["subtle", "canvas", 4.5, "Tertiary text (hints, timestamps)", "text"],
  ["subtle", "surface", 4.5, "Tertiary text on a card", "text"],

  ["on-accent", "accent", 4.5, "Primary button label", "text"],
  ["on-accent", "accent-hover", 4.5, "Primary button label, hovered", "text"],
  ["on-danger", "danger", 4.5, "Destructive button label", "text"],

  ["focus", "canvas", 3, "Focus ring against the page", "ui"],
  ["focus", "surface", 3, "Focus ring against a card", "ui"],
  ["focus", "sunken", 3, "Focus ring against a sunken panel", "ui"],

  ["field-line", "canvas", 3, "Input border on the page", "ui"],
  ["field-line", "surface", 3, "Input border on a card", "ui"],
  ["field-line", "sunken", 3, "Input border on a sunken panel", "ui"],
  ["line-strong", "canvas", 3, "Emphasised / hovered control border", "ui"],

  ["danger", "danger-bg", 4.5, "Error text in an error panel", "text"],
  ["danger", "canvas", 4.5, "Inline error text", "text"],
  ["danger", "surface", 4.5, "Error text on a card", "text"],
  ["warning", "warning-bg", 4.5, "Warning text in a warning panel", "text"],
  ["warning", "canvas", 4.5, "Inline warning text", "text"],
  ["success", "success-bg", 4.5, "Success text in a success panel", "text"],
  ["success", "canvas", 4.5, "Inline success text", "text"],
  ["info", "info-bg", 4.5, "Info text in an info panel", "text"],
  ["info", "canvas", 4.5, "Inline info text", "text"],

  ["danger-line", "danger-bg", 1.2, "Error panel border", "decor"],
  ["warning-line", "warning-bg", 1.2, "Warning panel border", "decor"],
  ["success-line", "success-bg", 1.2, "Success panel border", "decor"],
  ["info-line", "info-bg", 1.2, "Info panel border", "decor"],
  ["line", "canvas", 1.1, "Card border / divider", "decor"],
];

let failures = 0;
let checks = 0;

for (const [themeName, tokens] of [
  ["light", light],
  ["dark", dark],
]) {
  console.log(`\n  ${themeName.toUpperCase()}`);
  for (const [fg, bg, min, label, level] of PAIRS) {
    const fgValue = tokens[fg];
    const bgValue = tokens[bg];
    if (!fgValue || !bgValue) {
      console.log(`  ??  ${label} — missing token (--${fg} or --${bg})`);
      failures += 1;
      continue;
    }
    const value = ratio(fgValue, bgValue);
    const ok = value >= min;
    let mark;
    if (level === "decor") {
      mark = ok ? "  · " : " !· ";
    } else {
      checks += 1;
      if (!ok) failures += 1;
      mark = ok ? "ok  " : "FAIL";
    }
    console.log(
      `  ${mark} ${value.toFixed(2).padStart(5)}:1  (min ${min})  ${label}` +
        `  [--${fg} ${fgValue} on --${bg} ${bgValue}]`,
    );
  }
}

// The two dark blocks must stay in step; if they drift, viewers on the default
// "system" setting get a different palette from those who chose dark.
const drift = Object.keys(dark).filter((key) => dark[key] !== media[key]);
if (drift.length > 0) {
  console.log(
    `\n  FAIL  prefers-color-scheme block differs from [data-theme="dark"] for: ${drift.join(", ")}`,
  );
  failures += drift.length;
}

console.log(
  `\n  ${checks} required pairs checked across 2 themes — ` +
    `${failures === 0 ? "all pass" : `${failures} FAILED`}\n` +
    `  (rows marked · are decorative — reported, not enforced; see PAIRS)\n`,
);

process.exit(failures === 0 ? 0 : 1);
