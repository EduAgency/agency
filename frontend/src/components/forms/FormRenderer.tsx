"use client";

/**
 * Renders any admin-built form from its JSON schema.
 *
 * There is no per-form React component anywhere in this app — that is the whole
 * point of the form engine (plan §3.1). A new form built in the admin appears
 * here with no frontend change.
 */

import { useCallback, useMemo, useState } from "react";
import {
  DISPLAY_ONLY_TYPES,
  type FieldErrors,
  type FormField,
  type FormSchema,
  type FormValues,
} from "@/types";
import { isVisible, pruneHidden } from "@/lib/forms/conditions";
import { allFields, checkFile, validateField, validateForm } from "@/lib/forms/validate";

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

  const fields = useMemo(() => allFields(schema), [schema]);

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

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const found = validateForm(schema, values);
    setErrors(found);
    setTouched(Object.fromEntries(fields.map((f) => [f.key, true])));
    if (Object.keys(found).length > 0) {
      const first = document.querySelector<HTMLElement>(`[data-field="${Object.keys(found)[0]}"]`);
      first?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    // Hidden answers are dropped before sending, exactly as the server does.
    await onSubmit(pruneHidden(fields, values));
  };

  const errorsFor = (key: string): string[] => {
    const local = touched[key] ? (errors[key] ?? []) : [];
    return [...local, ...(serverErrors[key] ?? [])];
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-10">
      {schema.sections.map((section) => {
        const visibleFields = section.fields.filter(
          (field) => DISPLAY_ONLY_TYPES.includes(field.type) || isVisible(field, values),
        );
        if (visibleFields.length === 0) return null;

        return (
          <section key={section.key} className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                {section.title}
              </h2>
              {section.description && (
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                  {section.description}
                </p>
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
                />
              ))}
            </div>
          </section>
        );
      })}

      <div className="flex flex-wrap gap-3 border-t border-slate-200 pt-6 dark:border-slate-800">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
        >
          {submitting ? "Saving…" : submitLabel}
        </button>
        {onSaveDraft && (
          <button
            type="button"
            onClick={() => onSaveDraft(values)}
            disabled={submitting}
            className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
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
}

const inputClass =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-900 focus:ring-1 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:focus:border-slate-400 dark:focus:ring-slate-400";

function Field({ field, value, errors, onChange, onBlur }: FieldProps) {
  const hasError = errors.length > 0;
  const describedBy = hasError ? `${field.key}-error` : field.help_text ? `${field.key}-help` : undefined;

  if (field.type === "heading") {
    return <h3 className="pt-2 text-base font-semibold text-slate-900 dark:text-slate-100">{field.label}</h3>;
  }
  if (field.type === "paragraph") {
    return <p className="text-sm text-slate-600 dark:text-slate-400">{field.label}</p>;
  }
  if (field.type === "divider") {
    return <hr className="border-slate-200 dark:border-slate-800" />;
  }

  return (
    <div data-field={field.key} className="space-y-1.5">
      {field.type !== "checkbox" && field.type !== "consent" && (
        <label htmlFor={field.key} className="block text-sm font-medium text-slate-800 dark:text-slate-200">
          {field.label}
          {field.required && <span className="ml-0.5 text-rose-600">*</span>}
        </label>
      )}

      <FieldInput
        field={field}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        describedBy={describedBy}
        invalid={hasError}
      />

      {field.help_text && !hasError && (
        <p id={`${field.key}-help`} className="text-xs text-slate-500 dark:text-slate-400">
          {field.help_text}
        </p>
      )}
      {hasError && (
        <p id={`${field.key}-error`} role="alert" className="text-xs text-rose-600 dark:text-rose-400">
          {errors[0]}
        </p>
      )}
    </div>
  );
}

function FieldInput({
  field,
  value,
  onChange,
  onBlur,
  describedBy,
  invalid,
}: Omit<FieldProps, "errors"> & { describedBy?: string; invalid: boolean }) {
  const common = {
    id: field.key,
    name: field.key,
    onBlur,
    "aria-describedby": describedBy,
    "aria-invalid": invalid || undefined,
    className: `${inputClass}${invalid ? " border-rose-500 focus:border-rose-500 focus:ring-rose-500" : ""}`,
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
        <select {...common} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select…</option>
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      );

    case "multiselect":
    case "checkbox_group": {
      const selected = Array.isArray(value) ? (value as string[]) : [];
      return (
        <div className="space-y-2">
          {(field.options ?? []).map((option) => (
            <label key={option.value} className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={selected.includes(option.value)}
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...selected, option.value]
                      : selected.filter((v) => v !== option.value),
                  )
                }
                onBlur={onBlur}
                className="h-4 w-4 rounded border-slate-300 dark:border-slate-600"
              />
              {option.label}
            </label>
          ))}
        </div>
      );
    }

    case "radio":
      return (
        <div className="space-y-2">
          {(field.options ?? []).map((option) => (
            <label key={option.value} className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="radio"
                name={field.key}
                value={option.value}
                checked={value === option.value}
                onChange={() => onChange(option.value)}
                onBlur={onBlur}
                className="h-4 w-4 border-slate-300 dark:border-slate-600"
              />
              {option.label}
            </label>
          ))}
        </div>
      );

    case "checkbox":
    case "consent":
      return (
        <label className="flex items-start gap-2.5 text-sm text-slate-700 dark:text-slate-300">
          <input
            type="checkbox"
            id={field.key}
            checked={value === true}
            onChange={(e) => onChange(e.target.checked)}
            onBlur={onBlur}
            aria-describedby={describedBy}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 dark:border-slate-600"
          />
          <span>
            {field.label}
            {field.required && <span className="ml-0.5 text-rose-600">*</span>}
          </span>
        </label>
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
                window.alert(problem);
                return;
              }
            }
            onChange(field.type === "file_multiple" ? files : (files[0] ?? null));
          }}
          className={`${common.className} file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm dark:file:bg-slate-800 dark:file:text-slate-200`}
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
