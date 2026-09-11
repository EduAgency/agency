"""How files are laid out in the bucket.

There is nothing to create at signup — an object store has no folders, only
keys that share a prefix. What makes the bucket tidy is that every key is
server-generated and every student-owned object sits under one prefix, so
erasure and export are a prefix walk rather than a join.

These tests pin the three properties that makes possible.

See apps/core/storage.py.
"""

from __future__ import annotations

import uuid

import pytest

from apps.core import storage


class TestKeysCarryNoPersonalData:
    """Keys appear in access logs, presigned URLs, errors and the dashboard."""

    def test_the_students_filename_is_not_used(self):
        key = storage.document_upload_path(
            _upload(document_id="doc-1", student_id="stu-1", version=2),
            "Ebuka_Emmanuel_Passport_Scan.pdf",
        )

        assert "Ebuka" not in key
        assert "Passport" not in key
        assert key.endswith(".pdf"), "the extension is kept; the name is not"

    def test_the_stored_name_is_the_upload_id(self):
        upload = _upload(document_id="doc-1", student_id="stu-1", version=1)
        key = storage.document_upload_path(upload, "anything.png")

        assert key.endswith(f"{upload.pk}.png")


class TestNothingInAKeyComesFromUserInput:
    @pytest.mark.parametrize(
        "filename",
        [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config.sam",
            "passport.pdf/../../escape.pdf",
            "nul.pdf",
        ],
    )
    def test_traversal_attempts_cannot_escape_the_prefix(self, filename):
        upload = _upload(document_id="doc-1", student_id="stu-1", version=1)
        key = storage.document_upload_path(upload, filename)

        assert key.startswith("students/stu-1/documents/doc-1/v1/")
        assert ".." not in key

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("scan.PDF", "pdf"),
            ("scan.pdf", "pdf"),
            ("scan.jpeg", "jpeg"),
            ("archive.tar.gz", "bin"),
            ("payload.php", "bin"),
            ("payload.exe", "bin"),
            ("no-extension", "bin"),
            ("", "bin"),
            ("long." + "x" * 40, "bin"),
            # Stray whitespace and punctuation are stripped before the
            # whitelist is consulted, so real-world filenames like "scan.pdf "
            # still land on `pdf` rather than being demoted to `bin`.
            ("scan.pdf ", "pdf"),
            ("weird.p df", "pdf"),
            # Stripping cannot smuggle anything through: the whitelist is the
            # gate, and it sees the stripped value.
            ("payload.p h p", "bin"),
            ("payload.e x e", "bin"),
        ],
    )
    def test_extensions_are_whitelisted(self, filename, expected):
        assert storage.safe_extension(filename) == expected

    def test_an_unknown_type_is_still_stored(self):
        """Rejecting the upload is the validator's job, not the key builder's."""
        key = storage.document_upload_path(
            _upload(document_id="doc-1", student_id="stu-1", version=1), "thing.xyz"
        )
        assert key.endswith(".bin")


class TestOnePrefixPerStudent:
    def test_documents_sit_under_the_student_prefix(self):
        key = storage.document_upload_path(
            _upload(document_id="doc-9", student_id="stu-7", version=3), "a.pdf"
        )
        assert key.startswith(storage.student_prefix("stu-7") + "/")

    def test_message_attachments_sit_under_the_same_prefix(self):
        """They used to live under messages/<year>/<month>/.

        Which meant an erasure that deleted a student's documents left their
        chat attachments behind — often the same passport, re-sent in a thread.
        """
        key = storage.message_attachment_path(
            _attachment(thread_id="thr-1", student_id="stu-7"), "a.pdf"
        )
        assert key.startswith(storage.student_prefix("stu-7") + "/")

    def test_erasing_one_student_cannot_touch_another(self):
        mine = storage.student_prefix("stu-7")
        theirs = storage.student_prefix("stu-70")

        # A prefix delete of `students/stu-7` must not match `students/stu-70`,
        # which is why callers delete `students/<id>/` with the separator.
        assert not theirs.startswith(mine + "/")

    def test_school_logos_are_not_student_data(self):
        key = storage.school_logo_path(None, "logo.png")
        assert not key.startswith(storage.STUDENT_ROOT + "/")

    def test_versions_do_not_overwrite_each_other(self):
        document_id, student_id = "doc-1", "stu-1"
        first = storage.document_upload_path(
            _upload(document_id=document_id, student_id=student_id, version=1), "a.pdf"
        )
        second = storage.document_upload_path(
            _upload(document_id=document_id, student_id=student_id, version=2), "a.pdf"
        )

        assert first != second
        assert "/v1/" in first and "/v2/" in second


def test_the_historical_migration_reference_still_resolves():
    """`0001_initial` refers to apps.applications.models.document_upload_path.

    The function moved to apps.core.storage and is re-exported by the model
    module, which is the only reason a fresh `migrate` still works. Removing
    that import would break database creation without breaking anything a
    normal test touches — so it is asserted here instead.
    """
    from apps.applications import models

    assert models.document_upload_path is storage.document_upload_path


@pytest.mark.django_db
def test_a_real_upload_lands_where_the_layout_says(student, tmp_path, settings):
    """End to end through Django's storage, not just string building."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.applications.models import DocumentUpload, StudentDocument

    document = StudentDocument.objects.create(
        student=student, title="International passport", shareable_key="passport"
    )
    upload = DocumentUpload.objects.create(
        document=document,
        version=1,
        original_filename="Ebuka Passport Scan.pdf",
        content_type="application/pdf",
        size_bytes=11,
        file=SimpleUploadedFile("Ebuka Passport Scan.pdf", b"hello world"),
    )

    assert upload.file.name.startswith(f"students/{student.pk}/documents/{document.pk}/v1/")
    assert "Ebuka" not in upload.file.name
    # The human name is kept where the UI reads it from.
    assert upload.original_filename == "Ebuka Passport Scan.pdf"


class _Doc:
    def __init__(self, student_id):
        self.student_id = student_id


class _Thread:
    def __init__(self, student_id):
        self.student_id = student_id


def _upload(*, document_id, student_id, version):
    class Upload:
        pass

    upload = Upload()
    upload.pk = uuid.uuid4()
    upload.document_id = document_id
    upload.document = _Doc(student_id)
    upload.version = version
    return upload


def _attachment(*, thread_id, student_id):
    class Attachment:
        pass

    attachment = Attachment()
    attachment.pk = uuid.uuid4()
    attachment.thread_id = thread_id
    attachment.thread = _Thread(student_id)
    return attachment
