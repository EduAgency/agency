"""Prove the storage configuration works, before a student depends on it.

    python manage.py check_storage

Does a real round trip against whatever `STORAGES["default"]` points at:
writes a small object, reads it back, generates a signed URL, then deletes it.
Every step is reported separately, because the failures have different causes
and a single "it did not work" sends you looking in the wrong place.

Worth running after any credential or bucket change. The alternative is
discovering the problem when a student uploads a passport.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

PROBE_PREFIX = "_healthcheck"


class Command(BaseCommand):
    help = "Write, read, sign and delete a probe object to verify storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Leave the probe object behind (to look at it in the dashboard).",
        )

    def handle(self, *args, **options):
        backend = settings.STORAGES["default"]["BACKEND"]
        options_ = settings.STORAGES["default"].get("OPTIONS", {})

        self.stdout.write(self.style.MIGRATE_HEADING("Storage configuration"))
        self.stdout.write(f"  backend   {backend}")

        if "S3Storage" not in backend:
            self.stdout.write(
                self.style.WARNING(
                    "  USE_R2 is off, so this is local disk. Nothing to verify remotely."
                )
            )
            self.stdout.write(f"  root      {settings.MEDIA_ROOT}")
            return

        self.stdout.write(f"  bucket    {options_.get('bucket_name')}")
        self.stdout.write(f"  endpoint  {options_.get('endpoint_url')}")
        self.stdout.write(f"  region    {options_.get('region_name')}")

        # The single most common misconfiguration: pasting the dashboard URL,
        # which includes the bucket, into the endpoint. Every key then lands
        # under <bucket>/<bucket>/... or the request 404s outright.
        endpoint = (options_.get("endpoint_url") or "").rstrip("/")
        bucket = options_.get("bucket_name") or ""
        if bucket and endpoint.endswith(f"/{bucket}"):
            self.stdout.write(
                self.style.ERROR(
                    f"\n  R2_ENDPOINT_URL ends with /{bucket}. It must be the account "
                    "endpoint only - django-storages appends the bucket itself."
                )
            )
            return

        if not options_.get("access_key") or not options_.get("secret_key"):
            self.stdout.write(
                self.style.ERROR(
                    "\n  R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY are not set."
                )
            )
            return

        key = f"{PROBE_PREFIX}/{uuid.uuid4()}.txt"
        payload = b"nasuru storage check"

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Round trip"))

        try:
            saved = default_storage.save(key, ContentFile(payload))
        except Exception as exc:  # noqa: BLE001 - the message is the whole point
            return self._fail("write", exc)
        self.stdout.write(self.style.SUCCESS(f"  write     ok  -> {saved}"))

        try:
            with default_storage.open(saved, "rb") as handle:
                echoed = handle.read()
        except Exception as exc:  # noqa: BLE001
            return self._fail("read", exc)
        if echoed != payload:
            self.stdout.write(self.style.ERROR("  read      content came back different"))
            return
        self.stdout.write(self.style.SUCCESS("  read      ok"))

        try:
            url = default_storage.url(saved)
        except Exception as exc:  # noqa: BLE001
            return self._fail("sign", exc)
        signed = "X-Amz-Signature" in url or "Signature" in url
        self.stdout.write(
            self.style.SUCCESS("  sign      ok, URL is signed and short-lived")
            if signed
            else self.style.ERROR("  sign      URL is NOT signed - documents would be public")
        )

        if options["keep"]:
            self.stdout.write(f"\n  Probe left at {saved}")
            return

        try:
            default_storage.delete(saved)
        except Exception as exc:  # noqa: BLE001
            return self._fail("delete", exc)
        self.stdout.write(self.style.SUCCESS("  delete    ok"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Storage is working."))

    def _fail(self, step: str, exc: Exception):
        self.stdout.write(self.style.ERROR(f"  {step:<9} FAILED: {type(exc).__name__}: {exc}"))
        hints = {
            "write": (
                "Check the token has Object Read & Write on this bucket, that the "
                "bucket name is exactly right, and that the account id in the "
                "endpoint matches the token's account."
            ),
            "read": "The write succeeded, so this is usually a read permission on the token.",
            "sign": "Signing is local; this usually means malformed credentials.",
            "delete": "Write and read worked, so the token is probably read-only for deletes.",
        }
        self.stdout.write(f"\n  {hints.get(step, '')}")
