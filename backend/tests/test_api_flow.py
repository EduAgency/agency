"""The whole student journey, through the API, in one test class."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import StudentProfile
from apps.applications.models import ChecklistItemInstance, DocumentUpload
from apps.payments.gateways.base import CheckoutSession, TransactionResult
from apps.payments.gateways.paystack import PaystackGateway
from apps.payments.models import Payment


def pdf(name="passport.pdf") -> SimpleUploadedFile:
    # A minimal but genuine PDF header, so content sniffing sees a real type.
    return SimpleUploadedFile(name, b"%PDF-1.4\n%%EOF\n", content_type="application/pdf")


@pytest.mark.django_db
class TestSignupToChecklist:
    def test_the_full_journey(
        self, api, school, programme, requirement_set, reviewer, django_capture_on_commit_callbacks
    ):
        # 1. Sign up ---------------------------------------------------------
        response = api.post(
            "/api/auth/signup/",
            {
                "email": "Ada.Signup@Example.com",
                "password": "a-strong-passphrase-42",
                "first_name": "Ada",
                "last_name": "Okafor",
                "accept_terms": True,
            },
            format="json",
        )
        assert response.status_code == 201, response.json()
        tokens = response.json()["tokens"]
        assert tokens["access"] and tokens["refresh"]

        student = StudentProfile.objects.get(user__email="ada.signup@example.com")
        assert student.user.accepted_terms_at is not None  # consent recorded, not assumed
        assert student.has_platform_access is False

        api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # 2. The paid area is closed until a webhook confirms payment ---------
        assert api.get("/api/applications/").status_code == 403

        # 3. Start a payment -------------------------------------------------
        from apps.payments.models import Gateway, PaymentGatewayConfig

        PaymentGatewayConfig.objects.create(
            gateway=Gateway.PAYSTACK, currency="NGN", is_active=True, is_test_mode=True,
            public_key="pk_test", secret_key="sk_test_secret", webhook_secret="sk_test_secret",
        )
        with patch.object(
            PaystackGateway, "initialize",
            lambda self, payment, cb: CheckoutSession("https://checkout.test/abc", payment.reference, {}),
        ):
            response = api.post("/api/payments/initiate/", {"gateway": "paystack"}, format="json")
        assert response.status_code == 201
        reference = response.json()["payment"]["reference"]
        assert response.json()["checkout_url"] == "https://checkout.test/abc"

        # Still no access — a started payment is not a completed one.
        student.refresh_from_db()
        assert student.has_platform_access is False

        # 4. The webhook confirms it ------------------------------------------
        import hashlib
        import hmac
        import json

        from apps.payments.services import log_webhook, process_webhook_event

        body = json.dumps({
            "event": "charge.success",
            "data": {"reference": reference, "id": 5150, "status": "success",
                     "amount": 500000, "currency": "NGN", "channel": "card"},
        }).encode()
        headers = {
            "HTTP_X_PAYSTACK_SIGNATURE": hmac.new(b"sk_test_secret", body, hashlib.sha512).hexdigest()
        }
        verified = TransactionResult(
            reference=reference, gateway_reference="5150", status="successful",
            amount=Decimal("5000.00"), currency="NGN", channel="card",
        )
        with patch.object(PaystackGateway, "verify", return_value=verified):
            with django_capture_on_commit_callbacks(execute=True):
                process_webhook_event(log_webhook(gateway="paystack", body=body, headers=headers))

        student.refresh_from_db()
        assert student.has_platform_access is True
        assert Payment.objects.get(reference=reference).confirmed_by_webhook is True

        # 5. The dashboard opens ----------------------------------------------
        assert api.get("/api/applications/").status_code == 200

        # 6. Apply to a school — the checklist is snapshotted on creation ------
        response = api.post(
            "/api/applications/",
            {"school": str(school.pk), "programme": str(programme.pk), "intake": "October 2027"},
            format="json",
        )
        assert response.status_code == 201, response.json()
        application_id = response.json()["id"]

        checklist = api.get(f"/api/applications/{application_id}/checklist/").json()
        assert checklist["required_count"] == 2
        assert checklist["percent_complete"] == 0
        assert len(checklist["categories"]) == 1

        # 7. Upload a document -------------------------------------------------
        passport = next(i for i in checklist["items"] if i["label"] == "Passport")
        response = api.post(
            f"/api/checklist-items/{passport['id']}/upload/", {"file": pdf()}, format="multipart"
        )
        assert response.status_code == 201, response.json()
        assert response.json()["status"] == ChecklistItemInstance.Status.PENDING_REVIEW

        # Uploaded moves the "uploaded" figure but not the verified percentage.
        checklist = api.get(f"/api/applications/{application_id}/checklist/").json()
        assert checklist["percent_uploaded"] == 50
        assert checklist["percent_complete"] == 0

        # 8. Staff verify it ----------------------------------------------------
        api.credentials()
        api.force_authenticate(user=reviewer)
        queue = api.get("/api/admin/review-queue/").json()["results"]
        assert any(row["id"] == passport["id"] for row in queue)

        response = api.post(
            f"/api/checklist-items/{passport['id']}/review/", {"status": "verified"}, format="json"
        )
        assert response.status_code == 200

        # 9. Progress moves, and the vault document carries the verdict ---------
        api.force_authenticate(user=student.user)
        checklist = api.get(f"/api/applications/{application_id}/checklist/").json()
        assert checklist["percent_complete"] == 50
        assert DocumentUpload.objects.get().status == DocumentUpload.Status.VERIFIED


@pytest.mark.django_db
class TestUploadRules:
    def _item(self, student, school, programme):
        from apps.applications.models import Application
        from apps.applications.services import generate_checklist

        application = Application.objects.create(
            student=student, school=school, programme=programme, intake="October 2027"
        )
        return generate_checklist(application).items.get(label="Passport")

    def test_an_oversized_file_is_refused(
        self, as_paid_student, paid_student, school, programme, requirement_set
    ):
        item = self._item(paid_student, school, programme)
        item.max_file_size_mb = 1
        item.save()
        big = SimpleUploadedFile("big.pdf", b"x" * (2 * 1024 * 1024), content_type="application/pdf")
        response = as_paid_student.post(
            f"/api/checklist-items/{item.pk}/upload/", {"file": big}, format="multipart"
        )
        assert response.status_code == 400
        assert "file" in response.json()

    def test_a_disallowed_file_type_is_refused(
        self, as_paid_student, paid_student, school, programme, requirement_set
    ):
        item = self._item(paid_student, school, programme)
        item.accepted_file_types = [".pdf"]
        item.save()
        bad = SimpleUploadedFile("script.exe", b"MZ", content_type="application/octet-stream")
        response = as_paid_student.post(
            f"/api/checklist-items/{item.pk}/upload/", {"file": bad}, format="multipart"
        )
        assert response.status_code == 400

    def test_re_uploading_creates_a_new_version_rather_than_overwriting(
        self, as_paid_student, paid_student, school, programme, requirement_set
    ):
        item = self._item(paid_student, school, programme)
        as_paid_student.post(f"/api/checklist-items/{item.pk}/upload/", {"file": pdf("v1.pdf")}, format="multipart")
        as_paid_student.post(f"/api/checklist-items/{item.pk}/upload/", {"file": pdf("v2.pdf")}, format="multipart")

        uploads = DocumentUpload.objects.order_by("version")
        assert [u.version for u in uploads] == [1, 2]
        # The first version survives, marked superseded — a rejection dispute
        # months later can still see what was originally sent.
        assert uploads[0].status == DocumentUpload.Status.SUPERSEDED
        assert uploads[1].status == DocumentUpload.Status.PENDING

    def test_re_uploading_after_rejection_clears_the_rejection_reason(
        self, as_paid_student, paid_student, school, programme, requirement_set, reviewer
    ):
        item = self._item(paid_student, school, programme)
        item.set_status(ChecklistItemInstance.Status.REJECTED, user=reviewer, reason="Blurry scan")
        as_paid_student.post(
            f"/api/checklist-items/{item.pk}/upload/", {"file": pdf()}, format="multipart"
        )
        item.refresh_from_db()
        assert item.status == ChecklistItemInstance.Status.PENDING_REVIEW
        assert item.rejection_reason == ""


@pytest.mark.django_db
class TestFormSubmissionApi:
    def test_conditional_field_required_only_when_visible(self, as_paid_student, db):
        from apps.forms_engine.models import FormDefinition

        form = FormDefinition.objects.create(
            slug="intake", title="Intake", audience=FormDefinition.Audience.PAID_STUDENT,
            purpose=FormDefinition.Purpose.STUDENT_INTAKE,
            schema={"sections": [{"key": "s", "title": "About you", "fields": [
                {"key": "marital_status", "type": "select", "label": "Marital status", "required": True,
                 "options": [{"value": "single", "label": "Single"}, {"value": "married", "label": "Married"}]},
                {"key": "spouse_name", "type": "text", "label": "Spouse's name", "required": True,
                 "visible_when": {"all": [{"field": "marital_status", "op": "eq", "value": "married"}]}},
            ]}]},
        )
        form.publish()

        # Married without a spouse name → rejected, keyed to the field.
        response = as_paid_student.post(
            "/api/forms/intake/submit/", {"data": {"marital_status": "married"}}, format="json"
        )
        assert response.status_code == 400
        assert "spouse_name" in response.json()

        # Single → the hidden field is not required.
        response = as_paid_student.post(
            "/api/forms/intake/submit/", {"data": {"marital_status": "single"}}, format="json"
        )
        assert response.status_code == 201
        assert "spouse_name" not in response.json()["data"]

    def test_a_draft_can_be_saved_incomplete(self, as_paid_student, db):
        from apps.forms_engine.models import FormDefinition

        form = FormDefinition.objects.create(
            slug="intake", title="Intake", audience=FormDefinition.Audience.PAID_STUDENT,
            schema={"sections": [{"key": "s", "title": "S", "fields": [
                {"key": "full_name", "type": "text", "label": "Full name", "required": True},
                {"key": "city", "type": "text", "label": "City", "required": True},
            ]}]},
        )
        form.publish()
        response = as_paid_student.post(
            "/api/forms/intake/submit/", {"data": {"full_name": "Ada"}, "is_draft": True}, format="json"
        )
        assert response.status_code == 201
        assert response.json()["status"] == "draft"
