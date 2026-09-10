/**
 * Conditional field visibility.
 *
 * A deliberate port of `backend/apps/forms_engine/validation.py`. The two must
 * agree: if the browser hides a field the server still thinks is required, the
 * student gets an error about a field they cannot see. The server remains the
 * authority — this exists so the form behaves sensibly while being filled in.
 */

import type { Condition, ConditionGroup, FormField, FormValues } from "@/types";

function isEmpty(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0)
  );
}

function toNumber(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(String(value));
  return Number.isFinite(n) ? n : null;
}

function compare(op: Condition["op"], actual: unknown, expected: unknown): boolean {
  switch (op) {
    case "is_set":
      return !isEmpty(actual);
    case "is_empty":
      return isEmpty(actual);
    case "eq":
      return actual === expected;
    case "neq":
      return actual !== expected;
    case "in":
      return Array.isArray(expected) && expected.includes(actual as never);
    case "not_in":
      return Array.isArray(expected) && !expected.includes(actual as never);
    case "contains":
      if (Array.isArray(actual)) return actual.includes(expected as never);
      return actual != null && String(actual).includes(String(expected));
    case "gt":
    case "gte":
    case "lt":
    case "lte": {
      const a = toNumber(actual);
      const b = toNumber(expected);
      if (a === null || b === null) return false;
      if (op === "gt") return a > b;
      if (op === "gte") return a >= b;
      if (op === "lt") return a < b;
      return a <= b;
    }
    default:
      return false;
  }
}

export function evaluateGroup(group: ConditionGroup | undefined, values: FormValues): boolean {
  if (!group) return true;

  const all = (group.all ?? []).map((c) => compare(c.op, values[c.field], c.value));
  const any = (group.any ?? []).map((c) => compare(c.op, values[c.field], c.value));

  if (all.length > 0 && !all.every(Boolean)) return false;
  if (any.length > 0 && !any.some(Boolean)) return false;
  return true;
}

export function isVisible(field: FormField, values: FormValues): boolean {
  return evaluateGroup(field.visible_when, values);
}

/**
 * Strip answers belonging to fields that are currently hidden.
 *
 * Mirrors the server: switching "Married" back to "Single" must not leave a
 * stale spouse name in the payload.
 */
export function pruneHidden(fields: FormField[], values: FormValues): FormValues {
  const result: FormValues = {};
  for (const field of fields) {
    if (isVisible(field, values) && values[field.key] !== undefined) {
      result[field.key] = values[field.key];
    }
  }
  return result;
}
