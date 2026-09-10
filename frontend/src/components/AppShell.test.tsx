import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SkipLink } from "./AppShell";

/**
 * The skip link cannot be reached by the Playwright suite, because it only
 * renders inside the signed-in shell and those routes need a backend. It is
 * the app's WCAG 2.4.1 mechanism, so it gets a test here instead.
 */
describe("skip link (§B1)", () => {
  it("points at the app's single main landmark", () => {
    render(<SkipLink />);
    expect(screen.getByRole("link", { name: /skip to main content/i })).toHaveAttribute(
      "href",
      "#content",
    );
  });

  it("is reachable by keyboard as the first stop", async () => {
    render(<SkipLink />);
    await userEvent.tab();
    expect(screen.getByRole("link", { name: /skip to main content/i })).toHaveFocus();
  });

  it("stops being visually hidden once focused", async () => {
    render(<SkipLink />);
    const link = screen.getByRole("link", { name: /skip to main content/i });

    // `sr-only` alone would keep it invisible even when focused, which defeats
    // the point for a sighted keyboard user.
    expect(link.className).toContain("sr-only");
    expect(link.className).toContain("focus:not-sr-only");
  });
});
