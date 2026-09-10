"""
Validate submitted answers against a form schema.

Server-side and authoritative. The Next.js renderer runs the same rules for
instant feedback, but nothing is trusted until it has passed through here —
a hand-crafted POST must not be able to skip a required field or smuggle an
answer into a field that a conditional rule says is not even visible.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .schema import (
    BOOLEAN_TYPES,
    CHOICE_TYPES,
    DEFAULT_MAX_FILE_MB,
    FILE_TYPES,
    MULTI_VALUE_TYPES,
    Field,
    field_map,
    iter_fields,
)

EMPTY = (None, "", [], {})


class SubmissionError(ValueError):
    """Raised with a {field_key: [messages]} payload for the API layer."""

    def __init__(self, errors: dict[str, list[str]]):
        self.errors = errors
        super().__init__(errors)


# --------------------------------------------------------------------------
# Conditional visibility
# --------------------------------------------------------------------------
def _compare(op: str, actual, expected) -> bool:
    if op == "is_set":
        return actual not in EMPTY
    if op == "is_empty":
        return actual in EMPTY
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "in":
        return actual in (expected or [])
    if op == "not_in":
        return actual not in (expected or [])
    if op == "contains":
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        return expected is not None and str(expected) in str(actual or "")
    if op in {"gt", "gte", "lt", "lte"}:
        try:
            a, b = Decimal(str(actual)), Decimal(str(expected))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return {
            "gt": a > b,
            "gte": a >= b,
            "lt": a < b,
            "lte": a <= b,
        }[op]
    return False


def is_visible(field: Field, data: dict, fields: dict[str, Field] | None = None) -> bool:
    """Evaluate a field's visible_when rule against the answers so far.

    Conditions are single-level by design (a rule references other fields, and
    those fields' own rules are not chained). Nested dependency chains are where
    form builders become unpredictable for the admin editing them; if a rule
    needs more depth than this, the form wants splitting into two.
    """
    rule = field.visible_when
    if not rule:
        return True

    results_all = [
        _compare(c.get("op"), data.get(c.get("field")), c.get("value"))
        for c in rule.get("all", []) or []
    ]
    results_any = [
        _compare(c.get("op"), data.get(c.get("field")), c.get("value"))
        for c in rule.get("any", []) or []
    ]

    if results_all and not all(results_all):
        return False
    if results_any and not any(results_any):
        return False
    return True


def visible_fields(schema: dict, data: dict) -> list[Field]:
    return [f for f in iter_fields(schema) if not f.is_display_only and is_visible(f, data)]


# --------------------------------------------------------------------------
# Value coercion + validation
# --------------------------------------------------------------------------
def _coerce(field: Field, value):
    """Normalise a raw JSON value into the type the field promises."""
    ftype = field.type

    if value in EMPTY and ftype not in BOOLEAN_TYPES:
        return None

    if ftype in BOOLEAN_TYPES:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes", "on"}

    if ftype == "number":
        try:
            return float(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Enter a valid number.") from exc

    if ftype in {"date", "datetime"}:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Enter a valid date (YYYY-MM-DD).") from exc
        return parsed.date().isoformat() if ftype == "date" else parsed.isoformat()

    if ftype in MULTI_VALUE_TYPES:
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    return str(value).strip()


def _validate_value(field: Field, value) -> list[str]:
    errors: list[str] = []
    rules = field.validation or {}
    ftype = field.type

    if ftype in CHOICE_TYPES:
        allowed = field.option_values
        supplied = value if isinstance(value, list) else [value]
        for item in supplied:
            if item not in allowed:
                errors.append(f"'{item}' is not one of the available options.")
        if isinstance(value, list):
            if (mn := rules.get("min_selected")) and len(value) < mn:
                errors.append(f"Select at least {mn} option(s).")
            if (mx := rules.get("max_selected")) and len(value) > mx:
                errors.append(f"Select at most {mx} option(s).")

    elif ftype == "number":
        if (mn := rules.get("min")) is not None and value < mn:
            errors.append(f"Must be at least {mn}.")
        if (mx := rules.get("max")) is not None and value > mx:
            errors.append(f"Must be at most {mx}.")

    elif ftype == "email":
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value)):
            errors.append("Enter a valid email address.")

    elif ftype == "phone":
        if not re.match(r"^\+?[0-9\s\-()]{7,20}$", str(value)):
            errors.append("Enter a valid phone number.")

    elif ftype == "url":
        if not re.match(r"^https?://\S+\.\S+$", str(value)):
            errors.append("Enter a valid URL starting with http:// or https://.")

    elif ftype == "consent":
        if value is not True:
            errors.append("You must agree to continue.")

    if isinstance(value, str):
        if (mn := rules.get("min_length")) and len(value) < mn:
            errors.append(f"Must be at least {mn} characters.")
        if (mx := rules.get("max_length")) and len(value) > mx:
            errors.append(f"Must be at most {mx} characters.")
        if (pattern := rules.get("pattern")) and not re.match(pattern, value):
            errors.append(rules.get("pattern_message") or "Value is not in the expected format.")

    return errors


def validate_submission(
    schema: dict,
    data: dict,
    *,
    partial: bool = False,
    uploaded_keys: set[str] | None = None,
) -> dict:
    """Validate ``data`` against ``schema`` and return the cleaned answers.

    ``partial=True`` skips required-field checks — used when a student saves a
    draft part-way through a long intake form.

    ``uploaded_keys`` names the file fields that already have an upload stored,
    so a required file field is not re-flagged on a later edit of the same
    submission.

    Answers to fields that a conditional rule hides are dropped, not merely
    ignored: leaving them in would let a "Married" answer changed to "Single"
    keep a stale spouse passport in the record.
    """
    errors: dict[str, list[str]] = {}
    cleaned: dict = {}
    fields = field_map(schema)
    uploaded_keys = uploaded_keys or set()

    unknown = set(data) - set(fields)
    for key in unknown:
        errors.setdefault(key, []).append("Unknown field for this form version.")

    for key, field in fields.items():
        if not is_visible(field, data, fields):
            continue  # hidden → no value is kept and no requirement applies

        raw = data.get(key)

        if field.type in FILE_TYPES:
            # Files travel through DocumentUpload, not the JSON body; the JSON
            # carries their ids only.
            if raw in EMPTY and key not in uploaded_keys:
                if field.required and not partial:
                    errors.setdefault(key, []).append("This file is required.")
                continue
            cleaned[key] = raw if isinstance(raw, list) else [raw] if raw else []
            max_mb = (field.validation or {}).get("max_file_size_mb", DEFAULT_MAX_FILE_MB)
            cleaned.setdefault("_file_limits", {})[key] = max_mb
            continue

        if raw in EMPTY and field.type not in BOOLEAN_TYPES:
            if field.required and not partial:
                errors.setdefault(key, []).append("This field is required.")
            continue

        try:
            value = _coerce(field, raw)
        except ValueError as exc:
            errors.setdefault(key, []).append(str(exc))
            continue

        if field.required and not partial and value in EMPTY and field.type not in BOOLEAN_TYPES:
            errors.setdefault(key, []).append("This field is required.")
            continue

        if field_errors := _validate_value(field, value):
            errors.setdefault(key, []).extend(field_errors)
            continue

        cleaned[key] = value

    cleaned.pop("_file_limits", None)

    if errors:
        raise SubmissionError(errors)

    return cleaned
