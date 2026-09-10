/**
 * TypeScript mirror of the backend form schema.
 *
 * Keep this in step with `backend/apps/forms_engine/schema.py` — the two are a
 * single contract. Any field type or condition operator added on one side must
 * be added on the other, or forms will render one way and validate another.
 */

export type FieldType =
  | "text"
  | "textarea"
  | "email"
  | "phone"
  | "url"
  | "number"
  | "date"
  | "datetime"
  | "select"
  | "multiselect"
  | "radio"
  | "checkbox"
  | "checkbox_group"
  | "file"
  | "file_multiple"
  | "country"
  | "consent"
  | "signature"
  | "heading"
  | "paragraph"
  | "divider";

export const DISPLAY_ONLY_TYPES: FieldType[] = ["heading", "paragraph", "divider"];
export const CHOICE_TYPES: FieldType[] = ["select", "multiselect", "radio", "checkbox_group"];
export const FILE_TYPES: FieldType[] = ["file", "file_multiple"];
export const MULTI_VALUE_TYPES: FieldType[] = ["multiselect", "checkbox_group", "file_multiple"];
export const BOOLEAN_TYPES: FieldType[] = ["checkbox", "consent"];

export type ConditionOp =
  "eq" | "neq" | "in" | "not_in" | "gt" | "gte" | "lt" | "lte" | "contains" | "is_set" | "is_empty";

export interface Condition {
  field: string;
  op: ConditionOp;
  value?: unknown;
}

export interface ConditionGroup {
  all?: Condition[];
  any?: Condition[];
}

export interface FieldOption {
  value: string;
  label: string;
}

export interface FieldValidation {
  min?: number;
  max?: number;
  min_length?: number;
  max_length?: number;
  pattern?: string;
  pattern_message?: string;
  min_selected?: number;
  max_selected?: number;
  accepted_file_types?: string[];
  max_file_size_mb?: number;
}

export interface FormField {
  key: string;
  type: FieldType;
  label: string;
  help_text?: string;
  placeholder?: string;
  required?: boolean;
  options?: FieldOption[];
  validation?: FieldValidation;
  visible_when?: ConditionGroup;
  default?: unknown;
}

export interface FormSection {
  key: string;
  title: string;
  description?: string;
  fields: FormField[];
}

export interface FormSchema {
  sections: FormSection[];
}

export type FormStatus = "draft" | "published" | "archived";
export type FormAudience = "public" | "prospect" | "paid_student" | "admin_only";

export interface FormDefinition {
  id: string;
  slug: string;
  version: number;
  title: string;
  description: string;
  status: FormStatus;
  audience: FormAudience;
  purpose: string;
  schema: FormSchema;
  allow_drafts: boolean;
  submit_button_label: string;
  success_message: string;
}

export type FormValues = Record<string, unknown>;
export type FieldErrors = Record<string, string[]>;
