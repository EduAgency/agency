import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import jsxA11y from "eslint-plugin-jsx-a11y";

/**
 * `jsx-a11y` runs at error level, not warn.
 *
 * A warning is something everybody scrolls past. The findings in
 * docs/enterprise-readiness.md §A4 — a label pointing at an element ID that did
 * not exist — is exactly the class of bug this plugin catches automatically,
 * and it sat in the form engine for the life of the project because nothing was
 * looking.
 */
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["src/**/*.{js,jsx,ts,tsx}"],
    // `eslint-config-next` already registers the jsx-a11y plugin, so this block
    // only raises the rule levels — redefining the plugin is a config error.
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      // Upgraded from the recommended "warn": these are the ones that actually
      // make a screen reader unable to operate the product.
      "jsx-a11y/label-has-associated-control": "error",
      "jsx-a11y/aria-props": "error",
      "jsx-a11y/aria-role": "error",
      "jsx-a11y/role-has-required-aria-props": "error",
      "jsx-a11y/no-redundant-roles": "error",
      /**
       * `tabIndex` on a non-interactive element is usually a mistake — but a
       * scrollable `role="region"` is the exception, and is what WAI recommends
       * for a container with `overflow: auto`. Without it, axe reports
       * `scrollable-region-focusable`: a keyboard user cannot scroll a wide
       * table on a phone at all. Allowing the role here is more precise than
       * scattering inline disables at each call site.
       */
      "jsx-a11y/no-noninteractive-tabindex": [
        "error",
        { tags: [], roles: ["tabpanel", "region"], allowExpressionValues: true },
      ],
    },
  },
  {
    // Playwright fixtures take a callback named `use`, which the React Hooks
    // rules mistake for a hook call. Nothing under e2e/ is React, so the rules
    // are simply not applicable here — the rest of the linting still applies.
    files: ["e2e/**/*.ts", "playwright.config.ts"],
    rules: {
      "react-hooks/rules-of-hooks": "off",
    },
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "coverage/**",
    "playwright-report/**",
    "test-results/**",
  ]),
]);

export default eslintConfig;
