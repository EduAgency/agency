import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommandPalette, type PaletteController } from "./CommandPalette";

/**
 * The staff console needs a backend to reach, so the Playwright axe suite
 * cannot see these routes. The palette is the most intricate widget in the
 * product — a combobox driving a listbox by `aria-activedescendant` — so its
 * contract is pinned here instead.
 */

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/staff", () => ({
  listStudents: vi.fn(async () => ({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: "s1",
        user: { id: "u1", email: "amara@example.com", full_name: "Amara Okafor" },
        stage_display: "Documents",
      },
    ],
  })),
  listReviewQueue: vi.fn(async () => ({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: "i1",
        label: "International passport",
        category_name: "Identity",
        student_email: "amara@example.com",
      },
    ],
  })),
}));

function open(): PaletteController {
  return { isOpen: true, open: vi.fn(), close: vi.fn() };
}

beforeEach(() => {
  push.mockClear();
});

describe("command palette (§D4)", () => {
  it("renders nothing while closed", () => {
    render(<CommandPalette controller={{ isOpen: false, open: vi.fn(), close: vi.fn() }} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens as a labelled modal dialog with focus in the search box", () => {
    render(<CommandPalette controller={open()} />);
    expect(screen.getByRole("dialog", { name: /search students/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveFocus();
  });

  it("does not search on a single character", async () => {
    render(<CommandPalette controller={open()} />);
    await userEvent.type(screen.getByRole("combobox"), "a");
    // Two characters is the floor; one would match most of the database.
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  it("groups results and marks the first one active", async () => {
    render(<CommandPalette controller={open()} />);
    await userEvent.type(screen.getByRole("combobox"), "amara");

    const options = await screen.findAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    expect(options[1]).toHaveAttribute("aria-selected", "false");
  });

  it("keeps DOM focus in the input and moves aria-activedescendant with the arrows", async () => {
    render(<CommandPalette controller={open()} />);
    const input = screen.getByRole("combobox");
    await userEvent.type(input, "amara");
    await screen.findAllByRole("option");

    const first = input.getAttribute("aria-activedescendant");
    await userEvent.keyboard("{ArrowDown}");

    await waitFor(() => {
      expect(input.getAttribute("aria-activedescendant")).not.toBe(first);
    });
    // The whole point of the pattern: focus never leaves the text box.
    expect(input).toHaveFocus();
  });

  it("opens the highlighted result on Enter", async () => {
    render(<CommandPalette controller={open()} />);
    await userEvent.type(screen.getByRole("combobox"), "amara");
    await screen.findAllByRole("option");

    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/staff/students/s1"));
  });

  it("closes on Escape", async () => {
    const controller = open();
    render(<CommandPalette controller={controller} />);
    await userEvent.keyboard("{Escape}");
    expect(controller.close).toHaveBeenCalled();
  });
});
