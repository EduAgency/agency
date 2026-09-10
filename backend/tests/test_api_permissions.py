"""
Permission boundaries.

Every rule here is one that must hold server-side regardless of what the UI
shows. These are the tests that matter most: the data is passports, transcripts
and payment credentials.
"""

import pytest

from apps.applications.models import ChecklistItemInstance
from apps.applications.services import generate_checklist


@pytest.mark.django_db
class TestAccessFeeGate:
    def test_an_unpaid_student_cannot_reach_applications(self, as_student):
        response = as_student.get("/api/applications/")
        assert response.status_code == 403

    def test_a_paid_student_can(self, as_paid_student):
        assert as_paid_student.get("/api/applications/").status_code == 200

    def test_access_cannot_be_granted_by_patching_the_profile(self, as_student, student):
        """The flag is set by a confirmed payment webhook, and nothing else."""
        response = as_student.patch(
            "/api/profile/", {"has_platform_access": True, "stage": "enrolled"}, format="json"
        )
        assert response.status_code == 200
        student.refresh_from_db()
        assert student.has_platform_access is False
        assert student.stage == student.Stage.REGISTERED


@pytest.mark.django_db
class TestStudentIsolation:
    def test_a_student_cannot_list_another_students_applications(
        self, api, paid_student, other_student, school, programme, requirement_set
    ):
        from apps.applications.models import Application

        theirs = Application.objects.create(
            student=other_student, school=school, programme=programme, intake="October 2027"
        )
        api.force_authenticate(user=paid_student.user)
        listed = api.get("/api/applications/").json()["results"]
        assert all(row["id"] != str(theirs.pk) for row in listed)

    def test_a_student_cannot_fetch_another_students_application(
        self, api, paid_student, other_student, school, programme, requirement_set
    ):
        from apps.applications.models import Application

        theirs = Application.objects.create(
            student=other_student, school=school, programme=programme, intake="October 2027"
        )
        api.force_authenticate(user=paid_student.user)
        assert api.get(f"/api/applications/{theirs.pk}/").status_code == 404

    def test_a_student_cannot_see_another_students_documents(
        self, api, paid_student, other_student
    ):
        from apps.applications.models import StudentDocument

        theirs = StudentDocument.objects.create(student=other_student, title="Their passport")
        api.force_authenticate(user=paid_student.user)
        listed = api.get("/api/documents/").json()["results"]
        assert all(row["id"] != str(theirs.pk) for row in listed)

    def test_a_student_cannot_review_their_own_document(
        self, api, paid_student, school, programme, requirement_set
    ):
        from apps.applications.models import Application

        application = Application.objects.create(
            student=paid_student, school=school, programme=programme, intake="October 2027"
        )
        checklist = generate_checklist(application)
        item = checklist.items.first()
        api.force_authenticate(user=paid_student.user)
        response = api.post(f"/api/checklist-items/{item.pk}/review/", {"status": "verified"}, format="json")
        assert response.status_code == 403
        item.refresh_from_db()
        assert item.status == ChecklistItemInstance.Status.NOT_STARTED


@pytest.mark.django_db
class TestStaffPermissionScoping:
    def test_a_reviewer_cannot_read_gateway_credentials(self, as_reviewer, gateway_config):
        assert as_reviewer.get("/api/admin/gateway-configs/").status_code == 403

    def test_a_reviewer_cannot_write_gateway_credentials(self, as_reviewer, gateway_config):
        response = as_reviewer.patch(
            f"/api/admin/gateway-configs/{gateway_config.pk}/",
            {"secret_key": "sk_live_stolen"},
            format="json",
        )
        assert response.status_code == 403
        gateway_config.refresh_from_db()
        assert gateway_config.secret_key == "sk_test_secret"

    def test_a_reviewer_cannot_build_forms(self, as_reviewer):
        assert as_reviewer.get("/api/admin/forms/").status_code == 403

    def test_a_reviewer_can_work_the_review_queue(self, as_reviewer):
        assert as_reviewer.get("/api/admin/review-queue/").status_code == 200

    def test_a_superadmin_reaches_everything(self, as_admin, gateway_config):
        for path in ("/api/admin/gateway-configs/", "/api/admin/forms/", "/api/admin/review-queue/"):
            assert as_admin.get(path).status_code == 200, path

    def test_gateway_secrets_are_never_returned(self, as_admin, gateway_config):
        row = as_admin.get(f"/api/admin/gateway-configs/{gateway_config.pk}/").json()
        assert "secret_key" not in row
        assert "webhook_secret" not in row
        # A fingerprint is enough to confirm which key is live.
        assert row["secret_key_fingerprint"]


@pytest.mark.django_db
class TestFormAudience:
    def test_an_admin_only_form_is_invisible_to_students(self, as_paid_student, db):
        from apps.forms_engine.models import FormDefinition

        form = FormDefinition.objects.create(
            slug="consult-log", title="Consultation log",
            audience=FormDefinition.Audience.ADMIN_ONLY,
            schema={"sections": [{"key": "s", "title": "S", "fields": [
                {"key": "note", "type": "textarea", "label": "Note"}]}]},
        )
        form.publish()
        # 404 rather than 403 — an internal form should not confirm it exists.
        assert as_paid_student.get("/api/forms/consult-log/").status_code == 404
        assert as_paid_student.post("/api/forms/consult-log/submit/", {"data": {}}, format="json").status_code == 404

    def test_a_paid_form_is_closed_to_an_unpaid_student(self, as_student, db):
        from apps.forms_engine.models import FormDefinition

        form = FormDefinition.objects.create(
            slug="intake", title="Intake", audience=FormDefinition.Audience.PAID_STUDENT,
            schema={"sections": [{"key": "s", "title": "S", "fields": [
                {"key": "name", "type": "text", "label": "Name", "required": True}]}]},
        )
        form.publish()
        assert as_student.get("/api/forms/intake/").status_code == 404


@pytest.mark.django_db
class TestPaymentEndpoints:
    def test_the_client_cannot_choose_the_amount(self, as_student, gateway_config, student, monkeypatch):
        """A posted amount is ignored — the server prices the access fee."""
        from apps.payments.gateways.base import CheckoutSession
        from apps.payments.gateways.paystack import PaystackGateway

        monkeypatch.setattr(
            PaystackGateway, "initialize",
            lambda self, payment, cb: CheckoutSession("https://checkout.test/x", payment.reference, {}),
        )
        response = as_student.post(
            "/api/payments/initiate/", {"gateway": "paystack", "amount": "1.00"}, format="json"
        )
        assert response.status_code == 201
        assert response.json()["payment"]["amount"] == "5000.00"

    def test_gateway_options_expose_no_credentials(self, as_student, gateway_config):
        rows = as_student.get("/api/payments/gateways/").json()
        assert rows and rows[0]["gateway"] == "paystack"
        assert set(rows[0]) == {"gateway", "label", "currency", "is_test_mode"}

    def test_a_student_cannot_verify_someone_elses_payment(
        self, api, paid_student, access_fee_payment
    ):
        api.force_authenticate(user=paid_student.user)
        from django.contrib.auth import get_user_model

        from apps.accounts.models import StudentProfile

        User = get_user_model()
        stranger = StudentProfile.objects.get(
            user=User.objects.create_user(email="stranger@example.com", password="pass-word-1234")
        )
        stranger.has_platform_access = True
        stranger.save()
        api.force_authenticate(user=stranger.user)
        response = api.post(
            "/api/payments/verify/", {"reference": access_fee_payment.reference}, format="json"
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestReviewFlow:
    def _item(self, student, school, programme):
        from apps.applications.models import Application

        application = Application.objects.create(
            student=student, school=school, programme=programme, intake="October 2027"
        )
        return generate_checklist(application).items.get(label="Passport")

    def test_rejection_without_a_reason_is_refused(
        self, as_reviewer, paid_student, school, programme, requirement_set
    ):
        item = self._item(paid_student, school, programme)
        response = as_reviewer.post(
            f"/api/checklist-items/{item.pk}/review/", {"status": "rejected"}, format="json"
        )
        assert response.status_code == 400
        assert "reason" in response.json()

    def test_rejection_with_a_reason_notifies_the_student(
        self, as_reviewer, paid_student, school, programme, requirement_set
    ):
        from apps.notifications.models import Notification

        item = self._item(paid_student, school, programme)
        response = as_reviewer.post(
            f"/api/checklist-items/{item.pk}/review/",
            {"status": "rejected", "reason": "The photo page is cut off — re-scan the whole page."},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["rejection_reason"].startswith("The photo page")

        notification = Notification.objects.filter(
            recipient=paid_student.user, category=Notification.Category.DOCUMENT
        ).first()
        assert notification is not None
        assert "re-scan" in notification.body.lower()

    def test_verifying_moves_the_progress_bar(
        self, as_reviewer, paid_student, school, programme, requirement_set
    ):
        item = self._item(paid_student, school, programme)
        as_reviewer.post(f"/api/checklist-items/{item.pk}/review/", {"status": "verified"}, format="json")
        item.checklist.refresh_from_db()
        assert item.checklist.percent_complete == 50  # one of two required items
