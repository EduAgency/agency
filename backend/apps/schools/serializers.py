from rest_framework import serializers

from .models import (
    Country,
    Programme,
    RequirementCategory,
    RequirementItem,
    School,
    SchoolRequirementSet,
)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "iso_code", "is_active")


class RequirementCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementCategory
        fields = ("id", "name", "slug", "description", "icon", "display_order", "is_active")


class RequirementItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = RequirementItem
        fields = (
            "id", "requirement_set", "category", "category_name", "label", "description",
            "help_text", "is_required", "priority", "evidence_type", "accepted_file_types",
            "max_file_size_mb", "allow_multiple_files", "linked_form", "data_spec",
            "is_shareable", "shareable_key", "expires_after_months", "display_order",
            "due_offset_days", "is_active",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        requirement_set = attrs.get("requirement_set") or getattr(self.instance, "requirement_set", None)
        if requirement_set and not requirement_set.is_editable:
            raise serializers.ValidationError(
                "This requirement set is published. Create a new version to change its items."
            )
        return attrs


class ProgrammeSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = Programme
        fields = (
            "id", "school", "school_name", "name", "slug", "level", "duration_months",
            "tuition_amount", "tuition_currency", "language_of_instruction", "intakes",
            "application_opens", "application_deadline", "attributes", "is_active",
        )
        read_only_fields = ("id", "slug")


class SchoolSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True, default=None)
    programmes = ProgrammeSerializer(many=True, read_only=True)
    requirement_version = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = (
            "id", "name", "slug", "kind", "country", "country_name", "city", "website",
            "logo", "description", "attributes", "is_active", "programmes", "requirement_version",
        )
        read_only_fields = ("id", "slug")

    def get_requirement_version(self, obj) -> int | None:
        current = obj.current_requirement_set
        return current.version if current else None


class StaffSchoolSerializer(SchoolSerializer):
    """Adds the commercial fields, which students must never see."""

    class Meta(SchoolSerializer.Meta):
        fields = (*SchoolSerializer.Meta.fields, "is_partner", "commission_notes")


class SchoolRequirementSetSerializer(serializers.ModelSerializer):
    items = RequirementItemSerializer(many=True, read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True, default=None)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = SchoolRequirementSet
        fields = (
            "id", "school", "school_name", "programme", "name", "version", "status",
            "is_template", "cloned_from", "notes", "change_note", "published_at",
            "items", "item_count", "created_at",
        )
        read_only_fields = ("id", "version", "status", "published_at", "cloned_from", "created_at")

    def get_item_count(self, obj) -> int:
        return obj.items.filter(is_active=True).count()
