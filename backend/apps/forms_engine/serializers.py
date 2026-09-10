from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import FormDefinition, FormSubmission
from .schema import SchemaError, validate_schema
from .validation import SubmissionError, validate_submission


class FormDefinitionSerializer(serializers.ModelSerializer):
    field_count = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = FormDefinition
        fields = (
            "id", "slug", "version", "title", "description", "status", "audience",
            "purpose", "schema", "allow_multiple_submissions", "allow_drafts",
            "submit_button_label", "success_message", "change_note",
            "published_at", "created_at", "updated_at", "field_count", "submission_count",
        )
        read_only_fields = ("id", "version", "status", "published_at", "created_at", "updated_at")

    def get_field_count(self, obj) -> int:
        from .schema import field_map

        try:
            return len(field_map(obj.schema or {}))
        except Exception:
            return 0

    def get_submission_count(self, obj) -> int:
        return obj.submissions.count()

    def validate_schema(self, value):
        try:
            return validate_schema(value)
        except SchemaError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def update(self, instance, validated):
        # Published forms are immutable — the client must branch a new version.
        if not instance.is_editable:
            raise serializers.ValidationError(
                "This form is published and cannot be edited. Create a new version instead."
            )
        return super().update(instance, validated)


class PublicFormSerializer(serializers.ModelSerializer):
    """What a student sees: the schema and presentation, no internal metadata."""

    class Meta:
        model = FormDefinition
        fields = (
            "id", "slug", "version", "title", "description", "schema",
            "allow_drafts", "submit_button_label", "success_message",
        )
        read_only_fields = fields


class FormSubmissionSerializer(serializers.ModelSerializer):
    form_title = serializers.CharField(source="form_definition.title", read_only=True)
    form_version = serializers.IntegerField(source="form_definition.version", read_only=True)

    class Meta:
        model = FormSubmission
        fields = (
            "id", "form_definition", "form_slug", "form_title", "form_version",
            "student", "school", "application", "status", "data",
            "submitted_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "form_slug", "status", "submitted_at", "created_at", "updated_at")


class SubmitFormSerializer(serializers.Serializer):
    """Validates answers against the schema of the version being answered."""

    data = serializers.DictField()
    is_draft = serializers.BooleanField(default=False)
    application = serializers.UUIDField(required=False, allow_null=True)
    school = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        form: FormDefinition = self.context["form"]
        if attrs["is_draft"] and not form.allow_drafts:
            raise serializers.ValidationError("This form does not allow drafts.")
        try:
            attrs["cleaned"] = validate_submission(
                form.schema, attrs["data"], partial=attrs["is_draft"]
            )
        except SubmissionError as exc:
            # Field-keyed errors so the renderer can put each message on its field.
            raise serializers.ValidationError(exc.errors) from exc
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs
