"use client";

/**
 * Renders any admin-built form from its JSON schema.
 *
 * There is no per-form React component anywhere in this app — that is the whole
 * point of the form engine (plan §3.1). A new form built in the admin appears
 * here with no frontend change.
 *
 * Accessibility contract this file upholds, since every form in the product is
 * rendered through it (docs/enterprise-readiness.md §A3, §A4, §B3, §B5):
 *
 *   - Grouped choices (radio / multiselect / checkbox_group) are a `fieldset`
 *     with a `legend`, so the question is announced with each option. A plain
 *     `label` cannot name a group of controls.
 *   - Every message reaches the same place: a per-field `role="alert"`. There
 *     is no path — file validation included — that reports a problem anywhere
 *     an assistive technology cannot follow.
 *   - A failed submit moves focus to a summary listing every failure. Scrolling
 *     alone strands a keyboard or screen reader user on the submit button.
 *   - Motion is conditional on `prefers-reduced-motion`.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import {
  DISPLAY_ONLY_TYPES,
  type FieldErrors,
  type FormField,
  type FormSchema,
  type FormValues,
} from "@/types";
import { isVisible, pruneHidden } from "@/lib/forms/conditions";
import { allFields, checkFile, validateField, validateForm } from "@/lib/forms/validate";

/** Choice fields whose options must be wrapped in a fieldset to be announced. */
const GROUPED_TYPES = ["radio", "multiselect", "checkbox_group"];

function motionOk(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Focus the first control of a field and bring it into view. */
function focusField(key: string) {
  const container = document.querySelector<HTMLElement>(`[data-field="${key}"]`);
  if (!container) return;
  const control = container.querySelector<HTMLElement>("input, select, textarea");
  (control ?? container).focus({ preventScroll: true });
  container.scrollIntoView({ behavior: motionOk() ? "smooth" : "auto", block: "center" });
}

interface Props {
  schema: FormSchema;
  initialValues?: FormValues;
  serverErrors?: FieldErrors;
  submitLabel?: string;
  submitting?: boolean;
  onSubmit: (values: FormValues) => void | Promise<void>;
  onSaveDraft?: (values: FormValues) => void | Promise<void>;
}

export function FormRenderer({
  schema,
  initialValues = {},
  serverErrors = {},
  submitLabel = "Submit",
  submitting = false,
  onSubmit,
  onSaveDraft,
}: Props) {
  const [values, setValues] = useState<FormValues>(initialValues);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [summaryKeys, setSummaryKeys] = useState<string[]>([]);
  const summaryRef = useRef<HTMLDivElement>(null);

  const fields = useMemo(() => allFields(schema), [schema]);
  const labelFor = useMemo(
    () => new Map(fields.map((field) => [field.key, field.label])),
    [fields],
  );

  const setValue = useCallback((key: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const blur = useCallback(
    (field: FormField) => {
      setTouched((prev) => ({ ...prev, [field.key]: true }));
      const fieldErrors = validateField(field, values[field.key]);
      setErrors((prev) => ({ ...prev, [field.key]: fieldErrors }));
    },
    [values],
  );

  /**
   * A rejected file is a validation error like any other, not an interruption.
   * It used to be a `window.alert`, which is unstyleable, untranslatable, and
   * gone before a screen reader can tie it to the control that caused it.
   */
  const reportFileProblem = useCallback((key: string, problem: string | null) => {
    setTouched((prev) => ({ ...prev, [key]: true }));
    setErrors((prev) => ({ ...prev, [key]: problem ? [problem] : [] }));
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const found = validateForm(schema, values);
    setErrors(found);
    setTouched(Object.fromEntries(fields.map((f) => [f.key, true])));

    const failed = Object.keys(found);
    setSummaryKeys(failed);

    if (failed.length > 0) {
      // Focus, not just scroll — otherwise the keyboard user is still on the
      // submit button and hears nothing about why it did not work.
      requestAnimationFrame(() => summaryRef.current?.focus());
      return;
    }
    // Hidden answers are dropped before sending, exactly as the server does.
    await onSubmit(pruneHidden(fields, values));
  };

  const errorsFor = useCallback(
    (key: string): string[] => {
      const local = touched[key] ? (errors[key] ?? []) : [];
      return [...local, ...(serverErrors[key] ?? [])];
    },
    [touched, errors, serverErrors],
  );

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-10">
      {summaryKeys.length > 0 && (
        <div
          ref={summaryRef}
          tabIndex={-1}
          role="alert"
          /* Named by its own heading. Per-field errors are alerts too, so
             without a name this region is indistinguishable from them — to a
             screen reader user moving by landmark, and to a test. */
          aria-labelledby="form-error-summary-heading"
          className="rounded-lg border border-danger-line bg-danger-bg p-4"
        >
          <h2 id="form-error-summary-heading" className="text-sm font-semibold text-danger">
            {summaryKeys.length === 1
              ? "There is one answer to fix before you can continue"
              : `There are ${summaryKeys.length} answers to fix before you can continue`}
          </h2>
          <ul className="mt-2 space-y-1">
            {summaryKeys.map((key) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => focusField(key)}
                  className="text-left text-sm text-danger underline underline-offset-2 hover:opacity-80"
                >
                  {labelFor.get(key) ?? key}: {(errors[key] ?? [])[0]}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {schema.sections.map((section) => {
        const visibleFields = section.fields.filter(
          (field) => DISPLAY_ONLY_TYPES.includes(field.type) || isVisible(field, values),
        );
        if (visibleFields.length === 0) return null;

        return (
          <section key={section.key} className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-ink">{section.title}</h2>
              {section.description && (
                <p className="mt-1 text-sm text-muted">{section.description}</p>
              )}
            </div>

            <div className="space-y-5">
              {visibleFields.map((field) => (
                <Field
                  key={field.key || `${section.key}-${field.type}-${field.label}`}
                  field={field}
                  value={values[field.key]}
                  errors={errorsFor(field.key)}
                  onChange={(value) => setValue(field.key, value)}
                  onBlur={() => blur(field)}
                  onFileProblem={(problem) => reportFileProblem(field.key, problem)}
                />
              ))}
            </div>
          </section>
        );
      })}

      <div className="flex flex-wrap gap-3 border-t border-line pt-6">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-on-accent transition hover:bg-accent-hover disabled:opacity-50"
        >
          {submitting ? "Saving…" : submitLabel}
        </button>
        {onSaveDraft && (
          <button
            type="button"
            onClick={() => onSaveDraft(values)}
            disabled={submitting}
            className="rounded-lg border border-field-line px-5 py-2.5 text-sm font-medium text-muted transition hover:bg-sunken disabled:opacity-50"
          >
            Save and finish later
          </button>
        )}
      </div>
    </form>
  );
}

interface FieldProps {
  field: FormField;
  value: unknown;
  errors: string[];
  onChange: (value: unknown) => void;
  onBlur: () => void;
  onFileProblem: (problem: string | null) => void;
}

/**
 * `bg-surface`, never `bg-white`.
 *
 * This was `bg-white` until the seeded e2e suite scanned the intake form in
 * dark mode: near-white `text-ink` on a hardcoded white ground is 1.09:1, so
 * every input on every admin-built form was unreadable. The token migration
 * missed it because `bg-white` is not one of the slate classes it rewrote.
 */
const inputClass =
  "w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink transition placeholder:text-subtle hover:border-line-strong";

function Field({ field, value, errors, onChange, onBlur, onFileProblem }: FieldProps) {
  const hasError = errors.length > 0;
  const errorId = `${field.key}-error`;
  const helpId = `${field.key}-help`;
  const describedBy =
    [field.help_text ? helpId : null, hasError ? errorId : null].filter(Boolean).join("") ||
    undefined;

  if (field.type === "heading") {
    return <h3 className="pt-2 text-base font-semibold text-ink">{field.label}</h3>;
  }
  if (field.type === "paragraph") {
    return <p className="text-sm text-muted">{field.label}</p>;
  }
  if (field.type === "divider") {
    return <hr className="border-line" />;
  }

  /* Help text and errors are rendered identically for every field type — only
     the element that names the control changes. */
  const messages = (
    <>
      {field.help_text && (
        <p id={helpId} className="text-xs text-subtle">
          {field.help_text}
        </p>
      )}
      {hasError && (
        <div id={errorId} role="alert" className="space-y-0.5">
          {errors.map((message) => (
            <p key={message} className="text-xs text-danger">
              {message}
            </p>
          ))}
        </div>
      )}
    </>
  );

  const requiredMark = field.required && (
    <>
      <span aria-hidden="true" className="ml-0.5 text-danger">
        *
      </span>
      <span className="sr-only"> (required)</span>
    </>
  );

  // A group of controls is named by a legend. A `label` can only name one
  // control, so using it here left the question unannounced entirely.
  if (GROUPED_TYPES.includes(field.type)) {
    return (
      <fieldset
        data-field={field.key}
        aria-describedby={describedBy}
        aria-invalid={hasError || undefined}
        className="space-y-1.5 border-0 p-0"
      >
        <legend className="mb-1.5 block text-sm font-medium text-ink">
          {field.label}
          {requiredMark}
        </legend>
        <GroupedInput field={field} value={value} onChange={onChange} onBlur={onBlur} />
        {messages}
      </fieldset>
    );
  }

  return (
    <div data-field={field.key} className="space-y-1.5">
      {field.type !== "checkbox" && field.type !== "consent" && (
        <label htmlFor={field.key} className="block text-sm font-medium text-ink">
          {field.label}
          {requiredMark}
        </label>
      )}

      <FieldInput
        field={field}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        onFileProblem={onFileProblem}
        describedBy={describedBy}
        invalid={hasError}
      />

      {messages}
    </div>
  );
}

/** Radio / multiselect / checkbox groups. Always inside a fieldset. */
function GroupedInput({
  field,
  value,
  onChange,
  onBlur,
}: Pick<FieldProps, "field" | "value" | "onChange" | "onBlur">) {
  const options = field.options ?? [];

  if (field.type === "radio") {
    return (
      <div className="space-y-2">
        {options.map((option, index) => {
          const id = `${field.key}-opt-${index}`;
          return (
            <div key={option.value} className="flex items-center gap-2">
              <input
                id={id}
                type="radio"
                name={field.key}
                value={option.value}
                checked={value === option.value}
                onChange={() => onChange(option.value)}
                onBlur={onBlur}
                className="h-4 w-4 border-field-line"
              />
              <label htmlFor={id} className="text-sm text-muted">
                {option.label}
              </label>
            </div>
          );
        })}
      </div>
    );
  }

  const selected = Array.isArray(value) ? (value as string[]) : [];
  return (
    <div className="space-y-2">
      {options.map((option, index) => {
        const id = `${field.key}-opt-${index}`;
        return (
          <div key={option.value} className="flex items-center gap-2">
            <input
              id={id}
              type="checkbox"
              name={field.key}
              value={option.value}
              checked={selected.includes(option.value)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, option.value]
                    : selected.filter((v) => v !== option.value),
                )
              }
              onBlur={onBlur}
              className="h-4 w-4 rounded border-field-line"
            />
            <label htmlFor={id} className="text-sm text-muted">
              {option.label}
            </label>
          </div>
        );
      })}
    </div>
  );
}

function FieldInput({
  field,
  value,
  onChange,
  onBlur,
  onFileProblem,
  describedBy,
  invalid,
}: Omit<FieldProps, "errors"> & { describedBy?: string; invalid: boolean }) {
  const common = {
    id: field.key,
    name: field.key,
    onBlur,
    "aria-describedby": describedBy,
    "aria-invalid": invalid || undefined,
    "aria-required": field.required || undefined,
    className: `${inputClass}${invalid ? " border-danger" : ""}`,
  };

  switch (field.type) {
    case "textarea":
      return (
        <textarea
          {...common}
          rows={4}
          placeholder={field.placeholder}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    case "select":
      return (
        <select
          {...common}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Select…</option>
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      );

    case "checkbox":
    case "consent":
      return (
        <div className="flex items-start gap-2.5">
          <input
            type="checkbox"
            id={field.key}
            name={field.key}
            checked={value === true}
            onChange={(e) => onChange(e.target.checked)}
            onBlur={onBlur}
            aria-describedby={describedBy}
            aria-invalid={invalid || undefined}
            aria-required={field.required || undefined}
            className="mt-0.5 h-4 w-4 rounded border-field-line"
          />
          <label htmlFor={field.key} className="text-sm text-muted">
            {field.label}
            {field.required && (
              <>
                <span aria-hidden="true" className="ml-0.5 text-danger">
                  *
                </span>
                <span className="sr-only"> (required)</span>
              </>
            )}
          </label>
        </div>
      );

    case "file":
    case "file_multiple":
      return (
        <input
          {...common}
          type="file"
          multiple={field.type === "file_multiple"}
          accept={(field.validation?.accepted_file_types ?? []).join(",") || undefined}
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            for (const file of files) {
              const problem = checkFile(field, file);
              if (problem) {
                e.target.value = "";
                onChange(null);
                onFileProblem(problem);
                return;
              }
            }
            onFileProblem(null);
            onChange(field.type === "file_multiple" ? files : (files[0] ?? null));
          }}
          className={`${common.className} file:mr-3 file:rounded file:border-0 file:bg-sunken file:px-3 file:py-1.5 file:text-sm`}
        />
      );

    case "number":
      return (
        <input
          {...common}
          type="number"
          min={field.validation?.min}
          max={field.validation?.max}
          placeholder={field.placeholder}
          value={(value as number | string) ?? ""}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      );

    case "date":
    case "datetime":
      return (
        <input
          {...common}
          type={field.type === "date" ? "date" : "datetime-local"}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    default:
      return (
        <input
          {...common}
          type={field.type === "email" ? "email" : field.type === "phone" ? "tel" : "text"}
          placeholder={field.placeholder}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}
