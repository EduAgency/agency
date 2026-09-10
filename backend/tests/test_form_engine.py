"""The form engine's two load-bearing promises: a bad schema can't be saved,
and a published form can't be edited under someone's feet."""

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from apps.forms_engine.models import FormDefinition
from apps.forms_engine.schema import SchemaError, validate_schema
from apps.forms_engine.validation import SubmissionError, validate_submission

BASE_SCHEMA = {
    "sections": [
        {
            "key": "main",
            "title": "Main",
            "fields": [
                {"key": "full_name", "type": "text", "label": "Full name", "required": True},
                {
                    "key": "marital_status", "type": "select", "label": "Marital status", "required": True,
                    "options": [
                        {"value": "single", "label": "Single"},
                        {"value": "married", "label": "Married"},
                    ],
                },
                {
                    "key": "spouse_name", "type": "text", "label": "Spouse's name", "required": True,
                    "visible_when": {"all": [{"field": "marital_status", "op": "eq", "value": "married"}]},
                },
                {"key": "age", "type": "number", "label": "Age", "required": False,
                 "validation": {"min": 16, "max": 80}},
            ],
        }
    ]
}


class TestSchemaValidation:
    def test_valid_schema_passes(self):
        assert validate_schema(BASE_SCHEMA) is BASE_SCHEMA

    def test_duplicate_field_keys_rejected(self):
        schema = {"sections": [{"key": "s", "title": "S", "fields": [
            {"key": "a", "type": "text", "label": "A"},
            {"key": "a", "type": "text", "label": "A again"},
        ]}]}
        with pytest.raises(SchemaError, match="duplicate field key"):
            validate_schema(schema)

    def test_condition_referencing_unknown_field_rejected(self):
        schema = {"sections": [{"key": "s", "title": "S", "fields": [
            {"key": "a", "type": "text", "label": "A",
             "visible_when": {"all": [{"field": "ghost", "op": "eq", "value": 1}]}},
        ]}]}
        with pytest.raises(SchemaError, match="unknown field 'ghost'"):
            validate_schema(schema)

    def test_self_referencing_condition_rejected(self):
        schema = {"sections": [{"key": "s", "title": "S", "fields": [
            {"key": "a", "type": "text", "label": "A",
             "visible_when": {"all": [{"field": "a", "op": "eq", "value": 1}]}},
        ]}]}
        with pytest.raises(SchemaError, match="cannot reference itself"):
            validate_schema(schema)

    def test_select_without_options_rejected(self):
        schema = {"sections": [{"key": "s", "title": "S", "fields": [
            {"key": "a", "type": "select", "label": "A"},
        ]}]}
        with pytest.raises(SchemaError, match="non-empty options"):
            validate_schema(schema)

    def test_all_errors_reported_together(self):
        schema = {"sections": [{"key": "s", "title": "S", "fields": [
            {"key": "BadKey", "type": "text", "label": ""},
            {"key": "b", "type": "nonsense", "label": "B"},
        ]}]}
        with pytest.raises(SchemaError) as exc:
            validate_schema(schema)
        assert "invalid" in str(exc.value).lower() or "key" in str(exc.value)
        assert "unknown field type" in str(exc.value)


class TestSubmissionValidation:
    def test_required_field_enforced(self):
        with pytest.raises(SubmissionError) as exc:
            validate_submission(BASE_SCHEMA, {"marital_status": "single"})
        assert "full_name" in exc.value.errors

    def test_hidden_field_is_not_required(self):
        cleaned = validate_submission(
            BASE_SCHEMA, {"full_name": "Ada", "marital_status": "single"}
        )
        assert "spouse_name" not in cleaned

    def test_hidden_field_value_is_dropped(self):
        """Changing 'married' to 'single' must not leave a stale spouse name behind."""
        cleaned = validate_submission(
            BASE_SCHEMA,
            {"full_name": "Ada", "marital_status": "single", "spouse_name": "Leftover"},
        )
        assert "spouse_name" not in cleaned

    def test_visible_conditional_field_becomes_required(self):
        with pytest.raises(SubmissionError) as exc:
            validate_submission(BASE_SCHEMA, {"full_name": "Ada", "marital_status": "married"})
        assert "spouse_name" in exc.value.errors

    def test_unknown_field_rejected(self):
        with pytest.raises(SubmissionError) as exc:
            validate_submission(
                BASE_SCHEMA, {"full_name": "Ada", "marital_status": "single", "is_admin": True}
            )
        assert "is_admin" in exc.value.errors

    def test_option_value_outside_the_list_rejected(self):
        with pytest.raises(SubmissionError) as exc:
            validate_submission(BASE_SCHEMA, {"full_name": "Ada", "marital_status": "divorced"})
        assert "marital_status" in exc.value.errors

    def test_numeric_bounds_enforced(self):
        with pytest.raises(SubmissionError) as exc:
            validate_submission(
                BASE_SCHEMA, {"full_name": "Ada", "marital_status": "single", "age": 12}
            )
        assert "age" in exc.value.errors

    def test_partial_skips_required_checks(self):
        cleaned = validate_submission(BASE_SCHEMA, {"full_name": "Ada"}, partial=True)
        assert cleaned == {"full_name": "Ada"}


@pytest.mark.django_db
class TestVersioning:
    def _published(self):
        form = FormDefinition.objects.create(
            slug="intake", title="Intake", schema=BASE_SCHEMA,
            purpose=FormDefinition.Purpose.STUDENT_INTAKE,
        )
        return form.publish()

    def test_published_form_is_not_editable(self):
        form = self._published()
        assert form.is_editable is False

    def test_two_published_versions_of_one_slug_are_impossible(self):
        self._published()
        rogue = FormDefinition(
            slug="intake", version=2, title="Intake", schema=BASE_SCHEMA,
            status=FormDefinition.Status.PUBLISHED,
        )
        with pytest.raises(IntegrityError):
            rogue.save()

    def test_publishing_a_new_version_archives_the_old_one(self):
        first = self._published()
        draft = first.create_new_version(change_note="Added a field")
        assert draft.version == 2 and draft.status == FormDefinition.Status.DRAFT
        draft.publish()
        first.refresh_from_db()
        assert first.status == FormDefinition.Status.ARCHIVED
        assert FormDefinition.live("intake").version == 2

    def test_only_one_open_draft_per_form(self):
        form = self._published()
        form.create_new_version()
        with pytest.raises(ValidationError, match="already exists"):
            form.create_new_version()

    def test_invalid_schema_cannot_be_published(self):
        form = FormDefinition.objects.create(
            slug="broken", title="Broken",
            schema={"sections": [{"key": "s", "title": "S", "fields": [
                {"key": "a", "type": "select", "label": "A"}]}]},
        )
        with pytest.raises(SchemaError):
            form.publish()


@pytest.mark.django_db
class TestAudience:
    def test_admin_only_form_is_invisible_to_students(self, student, staff):
        form = FormDefinition.objects.create(
            slug="consult", title="Consultation log", schema=BASE_SCHEMA,
            audience=FormDefinition.Audience.ADMIN_ONLY,
        )
        form.publish()
        assert form.is_visible_to(student.user) is False
        assert form.is_visible_to(staff) is True

    def test_paid_student_form_needs_platform_access(self, student):
        form = FormDefinition.objects.create(
            slug="paid", title="Paid only", schema=BASE_SCHEMA,
            audience=FormDefinition.Audience.PAID_STUDENT,
        )
        form.publish()
        assert form.is_visible_to(student.user) is False
        student.has_platform_access = True
        student.save()
        student.user.refresh_from_db()
        assert form.is_visible_to(student.user) is True
