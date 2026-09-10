"""The checklist engine's central promise: a student's checklist is a snapshot,
and nothing a school does later rewrites it silently."""

import pytest
from django.core.exceptions import ValidationError

from apps.applications.models import ChecklistItemInstance
from apps.applications.services import generate_checklist, resync_checklist
from apps.schools.models import RequirementItem


@pytest.mark.django_db
class TestGeneration:
    def test_checklist_snapshots_every_item(self, application, requirement_set):
        checklist = generate_checklist(application)
        assert checklist.items.count() == 3
        assert checklist.source_version == requirement_set.version
        assert checklist.items.first().label  # text copied, not joined

    def test_only_required_items_count_toward_progress(self, application):
        checklist = generate_checklist(application)
        assert checklist.required_count == 2  # the reference letter is optional
        assert checklist.percent_complete == 0

    def test_generating_twice_is_refused(self, application):
        generate_checklist(application)
        with pytest.raises(ValidationError, match="already has a checklist"):
            generate_checklist(application)

    def test_school_without_published_requirements_is_refused(self, student, school):
        from apps.applications.models import Application
        from apps.schools.models import SchoolRequirementSet

        SchoolRequirementSet.objects.all().update(status=SchoolRequirementSet.Status.DRAFT)
        blank = Application.objects.create(student=student, school=school, intake="2028")
        with pytest.raises(ValidationError, match="no published requirement set"):
            generate_checklist(blank)


@pytest.mark.django_db
class TestSnapshotIsolation:
    def test_editing_the_school_set_does_not_touch_a_live_checklist(self, application, requirement_set, category):
        checklist = generate_checklist(application)
        before = set(checklist.items.values_list("label", flat=True))

        # The school changes its mind a month later.
        RequirementItem.objects.create(
            requirement_set=requirement_set, category=category, label="Police clearance", is_required=True,
        )
        RequirementItem.objects.filter(label="Passport").update(label="Passport (certified copy)")

        checklist.refresh_from_db()
        assert set(checklist.items.values_list("label", flat=True)) == before
        assert checklist.required_count == 2

    def test_resync_is_explicit_and_reports_what_changed(self, application, requirement_set, category):
        checklist = generate_checklist(application)
        RequirementItem.objects.create(
            requirement_set=requirement_set, category=category, label="Police clearance", is_required=True,
        )
        report = resync_checklist(checklist, remove_obsolete=True)
        assert report.added == ["Police clearance"]
        checklist.refresh_from_db()
        assert checklist.required_count == 3

    def test_resync_preserves_work_already_done(self, application, requirement_set, staff):
        checklist = generate_checklist(application)
        item = checklist.items.get(label="Transcript")
        item.set_status(ChecklistItemInstance.Status.VERIFIED, user=staff)

        # The school drops the transcript requirement entirely.
        RequirementItem.objects.filter(label="Transcript").delete()

        report = resync_checklist(checklist, remove_obsolete=True)
        assert "Transcript" in report.preserved
        item.refresh_from_db()
        assert item.status == ChecklistItemInstance.Status.VERIFIED
        assert item.is_active is True


@pytest.mark.django_db
class TestProgress:
    def test_verified_basis_ignores_merely_uploaded_documents(self, application, staff):
        checklist = generate_checklist(application)
        passport = checklist.items.get(label="Passport")
        passport.set_status(ChecklistItemInstance.Status.PENDING_REVIEW)

        checklist.refresh_from_db()
        assert checklist.percent_complete == 0     # nothing verified yet
        assert checklist.percent_uploaded == 50    # but the student can see it landed

        passport.set_status(ChecklistItemInstance.Status.VERIFIED, user=staff)
        checklist.refresh_from_db()
        assert checklist.percent_complete == 50

    def test_uploaded_basis_moves_on_upload(self, application):
        checklist = generate_checklist(application)
        checklist.progress_basis = checklist.ProgressBasis.UPLOADED
        checklist.save()
        checklist.items.get(label="Passport").set_status(ChecklistItemInstance.Status.UPLOADED)
        checklist.refresh_from_db()
        assert checklist.percent_complete == 50

    def test_optional_items_never_block_completion(self, application, staff):
        checklist = generate_checklist(application)
        for label in ("Passport", "Transcript"):
            checklist.items.get(label=label).set_status(
                ChecklistItemInstance.Status.VERIFIED, user=staff
            )
        checklist.refresh_from_db()
        assert checklist.percent_complete == 100  # reference letter still not started

    def test_progress_by_category_matches_the_tracker_layout(self, application, staff):
        checklist = generate_checklist(application)
        checklist.items.get(label="Passport").set_status(
            ChecklistItemInstance.Status.VERIFIED, user=staff
        )
        rows = checklist.progress_by_category()
        assert len(rows) == 1
        assert rows[0]["category"] == "Documents & Transcripts"
        assert rows[0]["verified"] == 1 and rows[0]["total"] == 3


@pytest.mark.django_db
class TestRejection:
    def test_rejection_without_a_reason_is_refused(self, application, staff):
        checklist = generate_checklist(application)
        item = checklist.items.get(label="Passport")
        with pytest.raises(ValidationError):
            item.set_status(ChecklistItemInstance.Status.REJECTED, user=staff, reason="  ")

    def test_rejection_records_reason_and_reviewer(self, application, staff):
        checklist = generate_checklist(application)
        item = checklist.items.get(label="Passport")
        item.set_status(
            ChecklistItemInstance.Status.REJECTED, user=staff, reason="Page is cut off — re-scan the full page."
        )
        item.refresh_from_db()
        assert item.reviewed_by == staff
        assert "re-scan" in item.rejection_reason.lower()

    def test_re_verifying_clears_a_previous_rejection_reason(self, application, staff):
        checklist = generate_checklist(application)
        item = checklist.items.get(label="Passport")
        item.set_status(ChecklistItemInstance.Status.REJECTED, user=staff, reason="Blurry")
        item.set_status(ChecklistItemInstance.Status.VERIFIED, user=staff)
        item.refresh_from_db()
        assert item.rejection_reason == ""


@pytest.mark.django_db
class TestSharedDocuments:
    def test_a_verified_shared_document_satisfies_a_second_application(
        self, student, school, programme, requirement_set, application
    ):
        from apps.applications.models import Application, DocumentUpload, StudentDocument

        first = generate_checklist(application)
        document = StudentDocument.objects.create(
            student=student, title="Passport", shareable_key="passport"
        )
        upload = DocumentUpload.objects.create(
            document=document, version=1, original_filename="passport.pdf",
            status=DocumentUpload.Status.VERIFIED,
        )
        document.current_upload = upload
        document.save()

        second_app = Application.objects.create(
            student=student, school=school, programme=programme, intake="April 2028"
        )
        second = generate_checklist(second_app)
        reused = second.items.get(label="Passport")
        assert reused.document == document
        assert reused.status == ChecklistItemInstance.Status.VERIFIED
        assert first.items.get(label="Passport").status == ChecklistItemInstance.Status.NOT_STARTED

    def test_an_unverified_document_is_not_auto_attached(self, student, school, requirement_set, application):
        from apps.applications.models import DocumentUpload, StudentDocument

        document = StudentDocument.objects.create(
            student=student, title="Passport", shareable_key="passport"
        )
        document.current_upload = DocumentUpload.objects.create(
            document=document, version=1, original_filename="p.pdf", status=DocumentUpload.Status.PENDING
        )
        document.save()
        checklist = generate_checklist(application)
        assert checklist.items.get(label="Passport").document is None
