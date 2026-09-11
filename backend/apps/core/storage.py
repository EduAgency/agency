"""Where files live in the bucket.

**There are no folders to create.** R2, like every object store, is a flat
keyspace — `/` is an ordinary character in a key, and the "folder" you see in
the Cloudflare dashboard is the console grouping keys by common prefix. It
appears the moment the first object with that prefix is written and disappears
when the last one is deleted.

So nothing needs provisioning at signup or at payment. Writing a zero-byte
placeholder to make a folder "exist" is a common instinct and an active
nuisance: it costs a write, shows up in every listing and object count, has to
be skipped by anything that iterates, and is easy to delete by accident, at
which point the folder vanishes anyway.

What actually delivers a tidy bucket is a **deterministic key scheme**, which
is what this module is. Every student-owned object sits under one prefix:

    students/<student-id>/documents/<document-id>/v<n>/<upload-id>.<ext>
    students/<student-id>/messages/<thread-id>/<attachment-id>.<ext>

Three properties that scheme is chosen for:

1. **One prefix per student.** An NDPR erasure or export is "everything under
   students/<id>/", not a join across three tables. Deletion cannot miss a file
   nobody remembered was student-owned.
2. **Keys carry no personal data.** Object keys turn up in access logs, in
   presigned URLs, in error messages and on the dashboard. A key like
   `Ebuka_Emmanuel_Passport_Scan.pdf` leaks a name and a document type to every
   one of those. The stored name is a UUID; the human filename lives in the
   database, on `DocumentUpload.original_filename`, which is what the UI shows.
3. **Nothing in a key comes from user input.** The extension is whitelisted and
   everything else is server-generated, so path traversal, absurd lengths,
   control characters and collisions are all structurally impossible rather
   than merely handled.
"""

from __future__ import annotations

import posixpath
import uuid

#: Extensions a key may end in. Anything else becomes `.bin` — the file is
#: still stored and still served, it just does not get to choose its own
#: extension. Upload validation (accepted_file_types per checklist item) is a
#: separate, stricter gate; this is only about what may appear in a key.
ALLOWED_EXTENSIONS = {
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "webp",
    "heic",
    "gif",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "txt",
    "csv",
    "zip",
}

FALLBACK_EXTENSION = "bin"

STUDENT_ROOT = "students"


def safe_extension(filename: str) -> str:
    """The extension to use in a key, never trusting the one supplied."""
    _, _, raw = (filename or "").rpartition(".")
    candidate = "".join(character for character in raw.lower() if character.isalnum())
    if not candidate or len(candidate) > 8 or candidate not in ALLOWED_EXTENSIONS:
        return FALLBACK_EXTENSION
    return candidate


def student_prefix(student_id) -> str:
    """Everything one student owns lives under here.

    This is the unit of erasure and of export, so it is deliberately the only
    place a student id appears in a path.
    """
    return f"{STUDENT_ROOT}/{student_id}"


def document_upload_path(instance, filename: str) -> str:
    """Key for one version of one document.

    Versioned rather than overwritten: a rejected upload stays retrievable
    because it is evidence if the rejection is disputed.
    """
    document = instance.document
    return posixpath.join(
        student_prefix(document.student_id),
        "documents",
        str(instance.document_id),
        f"v{instance.version}",
        f"{instance.pk or uuid.uuid4()}.{safe_extension(filename)}",
    )


def message_attachment_path(instance, filename: str) -> str:
    """Key for a file attached to a counsellor conversation.

    Under the student prefix like everything else. It used to be
    `messages/<year>/<month>/`, which meant an erasure request that deleted a
    student's documents quietly left their attachments behind — and those are
    frequently the same passport, re-sent in a chat.
    """
    thread = instance.thread
    return posixpath.join(
        student_prefix(thread.student_id),
        "messages",
        str(instance.thread_id),
        f"{instance.pk or uuid.uuid4()}.{safe_extension(filename)}",
    )


def school_logo_path(instance, filename: str) -> str:
    """Not student data, so not under the student root."""
    return posixpath.join("schools", "logos", f"{uuid.uuid4()}.{safe_extension(filename)}")
