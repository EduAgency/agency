"""
The form schema contract.

A FormDefinition stores its structure as JSON, not as Django fields — that is
what makes "the admin can build any form without a developer" literally true
(plan §3.1). This module is the single source of truth for what that JSON may
contain, and it is enforced on save so a malformed schema can never reach a
student's screen.

Shape::

    {
      "sections": [
        {
          "key": "personal",
          "title": "Personal details",
          "description": "",
          "fields": [
            {
              "key": "marital_status",
              "type": "select",
              "label": "Marital status",
              "required": true,
              "options": [{"value": "single", "label": "Single"},
                          {"value": "married", "label": "Married"}]
            },
            {
              "key": "spouse_passport",
              "type": "file",
              "label": "Spouse's passport",
              "required": true,
              "visible_when": {"all": [
                  {"field": "marital_status", "op": "eq", "value": "married"}
              ]}
            }
          ]
        }
      ]
    }
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

# Field types the builder UI offers (plan §3.2).
FIELD_TYPES = {
    "text",
    "textarea",
    "email",
    "phone",
    "url",
    "number",
    "date",
    "datetime",
    "select",
    "multiselect",
    "radio",
    "checkbox",       # single boolean
    "checkbox_group", # multiple boolean choices
    "file",
    "file_multiple",
    "country",
    "consent",        # boolean that must be true, records consent text + timestamp
    "signature",
    "heading",        # display-only
    "paragraph",      # display-only
    "divider",        # display-only
}

# Types that render but never carry an answer.
DISPLAY_ONLY_TYPES = {"heading", "paragraph", "divider"}
CHOICE_TYPES = {"select", "multiselect", "radio", "checkbox_group"}
FILE_TYPES = {"file", "file_multiple"}
MULTI_VALUE_TYPES = {"multiselect", "checkbox_group", "file_multiple"}
BOOLEAN_TYPES = {"checkbox", "consent"}
NUMERIC_TYPES = {"number"}

CONDITION_OPS = {
    "eq",
    "neq",
    "in",
    "not_in",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "is_set",
    "is_empty",
}

DEFAULT_MAX_FILE_MB = 20
ALLOWED_FILE_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".heic", ".webp",
    ".doc", ".docx", ".xls", ".xlsx", ".txt",
}


class SchemaError(ValueError):
    """Raised when a form schema itself is invalid (an admin/builder problem)."""


@dataclass(frozen=True)
class Field:
    """Normalised view of one schema field, used by the validator and renderers."""

    key: str
    type: str
    label: str
    required: bool
    options: list[dict]
    validation: dict
    visible_when: dict | None
    raw: dict

    @property
    def is_display_only(self) -> bool:
        return self.type in DISPLAY_ONLY_TYPES

    @property
    def is_file(self) -> bool:
        return self.type in FILE_TYPES

    @property
    def is_multi(self) -> bool:
        return self.type in MULTI_VALUE_TYPES

    @property
    def option_values(self) -> set:
        return {o["value"] for o in self.options}


def iter_fields(schema: dict):
    """Yield every Field in document order across all sections."""
    for section in schema.get("sections", []):
        for raw in section.get("fields", []):
            yield Field(
                key=raw.get("key", ""),
                type=raw.get("type", ""),
                label=raw.get("label", ""),
                required=bool(raw.get("required", False)),
                options=raw.get("options", []) or [],
                validation=raw.get("validation", {}) or {},
                visible_when=raw.get("visible_when"),
                raw=raw,
            )


def field_map(schema: dict) -> dict[str, Field]:
    return {f.key: f for f in iter_fields(schema) if not f.is_display_only}


def validate_schema(schema: dict) -> dict:
    """Validate a form schema, returning it normalised.

    Raises SchemaError listing every problem found, rather than the first — an
    admin fixing a form wants the whole list, not one error per save.
    """
    errors: list[str] = []

    if not isinstance(schema, dict):
        raise SchemaError("Schema must be a JSON object.")

    sections = schema.get("sections")
    if not isinstance(sections, list) or not sections:
        raise SchemaError("Schema must contain a non-empty 'sections' list.")

    seen_field_keys: set[str] = set()
    seen_section_keys: set[str] = set()
    declared_keys: set[str] = set()

    for s_index, section in enumerate(sections):
        where = f"section[{s_index}]"
        if not isinstance(section, dict):
            errors.append(f"{where}: must be an object.")
            continue

        s_key = section.get("key", "")
        if not KEY_RE.match(str(s_key)):
            errors.append(
                f"{where}: key '{s_key}' must be lowercase letters, digits and underscores."
            )
        elif s_key in seen_section_keys:
            errors.append(f"{where}: duplicate section key '{s_key}'.")
        else:
            seen_section_keys.add(s_key)

        if not str(section.get("title", "")).strip():
            errors.append(f"{where}: a title is required.")

        fields = section.get("fields")
        if not isinstance(fields, list):
            errors.append(f"{where}: 'fields' must be a list.")
            continue

        for f_index, raw in enumerate(fields):
            fwhere = f"{where}.field[{f_index}]"
            if not isinstance(raw, dict):
                errors.append(f"{fwhere}: must be an object.")
                continue
            errors.extend(_validate_field(raw, fwhere, seen_field_keys))
            key = raw.get("key")
            if key:
                declared_keys.add(str(key))

    # Conditional rules may only reference fields that exist, and a field cannot
    # depend on itself — both are silent-breakage bugs if left unchecked.
    for field in iter_fields(schema):
        if not field.visible_when:
            continue
        for cond in _flatten_conditions(field.visible_when):
            ref = cond.get("field")
            if ref not in declared_keys:
                errors.append(
                    f"field '{field.key}': visible_when references unknown field '{ref}'."
                )
            elif ref == field.key:
                errors.append(f"field '{field.key}': visible_when cannot reference itself.")

    if errors:
        raise SchemaError("; ".join(errors))

    return schema


def _validate_field(raw: dict, where: str, seen: set[str]) -> list[str]:
    errors: list[str] = []
    ftype = raw.get("type")

    if ftype not in FIELD_TYPES:
        errors.append(f"{where}: unknown field type '{ftype}'.")
        return errors

    if ftype in DISPLAY_ONLY_TYPES:
        # Display elements need no key, but if given one it must still be sane.
        key = raw.get("key")
        if key and not KEY_RE.match(str(key)):
            errors.append(f"{where}: invalid key '{key}'.")
        return errors

    key = raw.get("key", "")
    if not KEY_RE.match(str(key)):
        errors.append(
            f"{where}: key '{key}' must start with a letter and contain only "
            "lowercase letters, digits and underscores (max 63 chars)."
        )
    elif key in seen:
        errors.append(f"{where}: duplicate field key '{key}'.")
    else:
        seen.add(key)

    if not str(raw.get("label", "")).strip():
        errors.append(f"{where}: a label is required.")

    if ftype in CHOICE_TYPES:
        options = raw.get("options")
        if not isinstance(options, list) or not options:
            errors.append(f"{where}: '{ftype}' requires a non-empty options list.")
        else:
            values = set()
            for o_index, opt in enumerate(options):
                if not isinstance(opt, dict) or "value" not in opt or "label" not in opt:
                    errors.append(f"{where}.option[{o_index}]: needs 'value' and 'label'.")
                    continue
                if opt["value"] in values:
                    errors.append(f"{where}.option[{o_index}]: duplicate value '{opt['value']}'.")
                values.add(opt["value"])

    validation = raw.get("validation", {})
    if validation and not isinstance(validation, dict):
        errors.append(f"{where}: 'validation' must be an object.")
        validation = {}

    if ftype in FILE_TYPES:
        exts = validation.get("accepted_file_types") or []
        if not isinstance(exts, list):
            errors.append(f"{where}: accepted_file_types must be a list of extensions.")
        else:
            for ext in exts:
                if not str(ext).startswith(".") or str(ext).lower() not in ALLOWED_FILE_EXTENSIONS:
                    errors.append(
                        f"{where}: file type '{ext}' is not allowed. Permitted: "
                        + ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
                    )
        max_mb = validation.get("max_file_size_mb", DEFAULT_MAX_FILE_MB)
        if not isinstance(max_mb, (int, float)) or not (0 < max_mb <= DEFAULT_MAX_FILE_MB):
            errors.append(f"{where}: max_file_size_mb must be between 0 and {DEFAULT_MAX_FILE_MB}.")

    if ftype in NUMERIC_TYPES:
        lo, hi = validation.get("min"), validation.get("max")
        if lo is not None and hi is not None and lo > hi:
            errors.append(f"{where}: min ({lo}) is greater than max ({hi}).")

    if pattern := validation.get("pattern"):
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"{where}: invalid regex pattern — {exc}.")

    if (cond := raw.get("visible_when")) is not None:
        errors.extend(_validate_condition_group(cond, where))

    return errors


def _validate_condition_group(group: dict, where: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(group, dict):
        return [f"{where}: visible_when must be an object with 'all' or 'any'."]
    if not ({"all", "any"} & set(group)):
        return [f"{where}: visible_when needs an 'all' or 'any' key."]
    for mode in ("all", "any"):
        conditions = group.get(mode)
        if conditions is None:
            continue
        if not isinstance(conditions, list) or not conditions:
            errors.append(f"{where}: visible_when.{mode} must be a non-empty list.")
            continue
        for c_index, cond in enumerate(conditions):
            cwhere = f"{where}.visible_when.{mode}[{c_index}]"
            if not isinstance(cond, dict):
                errors.append(f"{cwhere}: must be an object.")
                continue
            if not cond.get("field"):
                errors.append(f"{cwhere}: 'field' is required.")
            op = cond.get("op")
            if op not in CONDITION_OPS:
                errors.append(
                    f"{cwhere}: unknown op '{op}'. Allowed: {', '.join(sorted(CONDITION_OPS))}."
                )
            elif op in {"in", "not_in"} and not isinstance(cond.get("value"), list):
                errors.append(f"{cwhere}: op '{op}' requires a list value.")
            elif op not in {"is_set", "is_empty"} and "value" not in cond:
                errors.append(f"{cwhere}: op '{op}' requires a 'value'.")
    return errors


def _flatten_conditions(group: dict):
    for mode in ("all", "any"):
        for cond in group.get(mode, []) or []:
            if isinstance(cond, dict):
                yield cond
