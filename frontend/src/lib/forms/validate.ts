/**
 * Client-side mirror of the server's submission validation.
 *
 * Purpose is instant feedback, nothing more. The server re-runs every rule here
 * and its answer wins; a check that exists only in this file is not a check.
 */

import {
  BOOLEAN_TYPES,
  CHOICE_TYPES,
  DISPLAY_ONLY_TYPES,
  FILE_TYPES,
  type FieldErrors,
  type FormField,
  type FormSchema,
  type FormValues,
} from "@/types";
import { isVisible } from "./conditions";

export function allFields(schema: FormSchema): FormField[] {
  return schema.sections.flatMap((section) =>
    section.fields.filter((f) => !DISPLAY_ONLY_TYPES.includes(f.type)),
  );
}

function isBlank(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0)
  );
}

export function validateField(field: FormField, value: unknown): string[] {
  const errors: string[] = [];
  const rules = field.validation ?? {};

  if (isBlank(value) && !BOOLEAN_TYPES.includes(field.type)) {
    if (field.required) errors.push("This field is required.");
    return errors;
  }

  if (field.type === "consent" && value !== true) {
    errors.push("You must agree to continue.");
  }

  if (field.type === "number") {
    const n = Number(value);
    if (!Number.isFinite(n)) {
      errors.push("Enter a valid number.");
    } else {
      if (rules.min !== undefined && n < rules.min) errors.push(`Must be at least ${rules.min}.`);
      if (rules.max !== undefined && n > rules.max) errors.push(`Must be at most ${rules.max}.`);
    }
  }

  if (field.type === "email" && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(value))) {
    errors.push("Enter a valid email address.");
  }

  if (field.type === "phone" && !/^\+?[0-9\s\-()]{7,20}$/.test(String(value))) {
    errors.push("Enter a valid phone number.");
  }

  if (field.type === "url" && !/^https?:\/\/\S+\.\S+$/.test(String(value))) {
    errors.push("Enter a valid URL starting with http:// or https://.");
  }

  if (CHOICE_TYPES.includes(field.type)) {
    const allowed = new Set((field.options ?? []).map((o) => o.value));
    const supplied = Array.isArray(value) ? value : [value];
    for (const item of supplied) {
      if (!allowed.has(String(item))) errors.push("Select one of the available options.");
    }
    if (Array.isArray(value)) {
      if (rules.min_selected && value.length < rules.min_selected) {
        errors.push(`Select at least ${rules.min_selected} option(s).`);
      }
      if (rules.max_selected && value.length > rules.max_selected) {
        errors.push(`Select at most ${rules.max_selected} option(s).`);
      }
    }
  }

  if (typeof value === "string") {
    if (rules.min_length && value.length < rules.min_length) {
      errors.push(`Must be at least ${rules.min_length} characters.`);
    }
    if (rules.max_length && value.length > rules.max_length) {
      errors.push(`Must be at most ${rules.max_length} characters.`);
    }
    if (rules.pattern && !new RegExp(rules.pattern).test(value)) {
      errors.push(rules.pattern_message ?? "Value is not in the expected format.");
    }
  }

  return errors;
}

export function validateForm(schema: FormSchema, values: FormValues): FieldErrors {
  const errors: FieldErrors = {};
  for (const field of allFields(schema)) {
    // Hidden fields impose no requirements — same rule as the server.
    if (!isVisible(field, values)) continue;
    if (FILE_TYPES.includes(field.type)) {
      if (field.required && isBlank(values[field.key])) {
        errors[field.key] = ["This file is required."];
      }
      continue;
    }
    const fieldErrors = validateField(field, values[field.key]);
    if (fieldErrors.length) errors[field.key] = fieldErrors;
  }
  return errors;
}

export function checkFile(field: FormField, file: File): string | null {
  const rules = field.validation ?? {};
  const maxMb = rules.max_file_size_mb ?? 20;
  if (file.size > maxMb * 1024 * 1024) {
    return `This file is ${(file.size / 1024 / 1024).toFixed(1)}MB. The limit is ${maxMb}MB.`;
  }
  const accepted = rules.accepted_file_types ?? [];
  if (accepted.length) {
    const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
    if (!accepted.includes(ext)) {
      return `Accepted file types: ${accepted.join(", ")}.`;
    }
  }
  return null;
}
