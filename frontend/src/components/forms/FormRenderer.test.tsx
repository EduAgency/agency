import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormRenderer } from "./FormRenderer";
import type { FormSchema } from "@/types";

/**
 * These tests exist because every one of them corresponds to a bug that shipped
 * (docs/enterprise-readiness.md §A3, §A4, §B3). They assert the accessible
 * contract rather than the markup, so a refactor that keeps the contract keeps
 * them passing.
 */

const schema: FormSchema = {
  key: "intake",
  title: "Intake",
  sections: [
    {
      key: "about",
      title: "About you",
      fields: [
        {
          key: "full_name",
          type: "text",
          label: "Full name",
          required: true,
          help_text: "As it appears on your passport.",
        },
        {
          key: "funding",
          type: "radio",
          label: "How will you fund your studies?",
          required: true,
          options: [
            { value: "self", label: "Self-funded" },
            { value: "sponsor", label: "Sponsor" },
          ],
        },
      ],
    },
  ],
} as unknown as FormSchema;

function renderForm(onSubmit = vi.fn()) {
  render(<FormRenderer schema={schema} onSubmit={onSubmit} submitLabel="Continue" />);
  return onSubmit;
}

describe("grouped choice fields (§A4)", () => {
  it("names the radio group with its question", () => {
    renderForm();
    // The whole bug: this used to be a `label htmlFor` pointing at an ID that
    // no element had, so the question was announced to nobody.
    expect(
      screen.getByRole("group", { name: /How will you fund your studies\?/ }),
    ).toBeInTheDocument();
  });

  it("gives every option its own label", () => {
    renderForm();
    expect(screen.getByRole("radio", { name: "Self-funded" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Sponsor" })).toBeInTheDocument();
  });

  it("marks the group required and invalid once it fails", async () => {
    renderForm();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => {
      expect(screen.getByRole("group", { name: /fund your studies/ })).toHaveAttribute(
        "aria-invalid",
        "true",
      );
    });
  });
});

describe("failed submit (§B3)", () => {
  it("does not submit, and moves focus to a summary of every failure", async () => {
    const onSubmit = renderForm();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(onSubmit).not.toHaveBeenCalled();

    const summary = await screen.findByRole("alert", { name: /2 answers to fix/ });
    // Scrolling alone left the keyboard user on the submit button.
    await waitFor(() => expect(summary).toHaveFocus());
  });

  it("summary entries send focus to the field they name", async () => {
    renderForm();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await userEvent.click(await screen.findByRole("button", { name: /Full name/ }));
    expect(screen.getByRole("textbox", { name: /Full name/ })).toHaveFocus();
  });

  it("submits once the answers are valid", async () => {
    const onSubmit = renderForm();
    await userEvent.type(screen.getByRole("textbox", { name: /Full name/ }), "Amara Okafor");
    await userEvent.click(screen.getByRole("radio", { name: "Self-funded" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      full_name: "Amara Okafor",
      funding: "self",
    });
  });
});

describe("field description wiring", () => {
  it("associates help text with its input", () => {
    renderForm();
    expect(screen.getByRole("textbox", { name: /Full name/ })).toHaveAccessibleDescription(
      "As it appears on your passport.",
    );
  });
});
