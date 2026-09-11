"""Guards the public claims we make about document storage.

The landing page footer and the privacy policy both state that uploaded
documents are encrypted at rest and are never publicly addressable. These tests
exist so that a configuration change breaks the build rather than quietly
turning a published statement into a false one.

Storage is **Cloudflare R2**. It speaks the S3 API, which is how Django talks
to it, but three things that are merely optional on AWS are actively wrong on
R2, and each has its own test below:

* ACLs do not exist. Sending one is rejected.
* ``x-amz-server-side-encryption`` is not accepted. R2 encrypts every object at
  rest with AES-256 itself, which is what makes the claim true — so the test
  asserts the header is *absent*, and that is the guarantee being relied on.
* There are no regions. ``region_name`` must be ``auto``; physical placement is
  a property of the bucket, chosen at creation.

See docs/enterprise-readiness.md, Phase 1.
"""

from __future__ import annotations

import importlib

import pytest


def _r2_options(monkeypatch, **env):
    """Re-import settings with R2 on, and hand back the storage OPTIONS."""
    monkeypatch.setenv("USE_R2", "True")
    monkeypatch.setenv("R2_ACCOUNT_ID", "abc123account")
    monkeypatch.setenv("R2_BUCKET_NAME", "nasuru-test-bucket")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key-id")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from config import settings as settings_module

    reloaded = importlib.reload(settings_module)
    return reloaded.STORAGES["default"]["OPTIONS"]


def test_documents_go_to_r2_not_local_disk(monkeypatch):
    options = _r2_options(monkeypatch)
    assert options["endpoint_url"] == "https://abc123account.r2.cloudflarestorage.com"
    assert options["bucket_name"] == "nasuru-test-bucket"


def test_no_acl_is_sent(monkeypatch):
    """R2 has no ACLs and rejects the header. `private` would be an error here."""
    options = _r2_options(monkeypatch)
    assert options["default_acl"] is None


def test_no_server_side_encryption_header_is_sent(monkeypatch):
    """R2 encrypts at rest itself and will not accept being told to.

    This is the inverse of the equivalent AWS assertion: there, the header had
    to be present for the claim to hold; here its absence is what keeps uploads
    working, and the platform provides the encryption.
    """
    options = _r2_options(monkeypatch)
    assert "ServerSideEncryption" not in (options.get("object_parameters") or {})


def test_region_is_auto(monkeypatch):
    options = _r2_options(monkeypatch)
    assert options["region_name"] == "auto"


def test_documents_are_never_publicly_readable(monkeypatch):
    options = _r2_options(monkeypatch)
    assert options["querystring_auth"] is True


def test_signed_urls_expire_quickly(monkeypatch):
    """A link to somebody's passport should not outlive the session that made it."""
    options = _r2_options(monkeypatch)
    assert options["querystring_expire"] <= 900


def test_uploads_never_overwrite_an_earlier_version(monkeypatch):
    """A rejected document stays retrievable — it is evidence in a dispute."""
    options = _r2_options(monkeypatch)
    assert options["file_overwrite"] is False


def test_signing_is_v4(monkeypatch):
    """R2 only accepts SigV4."""
    options = _r2_options(monkeypatch)
    assert options["signature_version"] == "s3v4"


def test_local_development_never_touches_r2(monkeypatch):
    """With the flag off, uploads stay on disk and no credentials are needed."""
    monkeypatch.setenv("USE_R2", "False")
    from config import settings as settings_module

    reloaded = importlib.reload(settings_module)
    assert (
        reloaded.STORAGES["default"]["BACKEND"]
        == "django.core.files.storage.FileSystemStorage"
    )


@pytest.mark.parametrize("field", ["secret_key", "webhook_secret", "encryption_key"])
def test_gateway_credentials_are_encrypted_at_rest(field):
    from apps.core.encryption import EncryptedTextField
    from apps.payments.models import PaymentGatewayConfig

    model_field = PaymentGatewayConfig._meta.get_field(field)
    assert isinstance(model_field, EncryptedTextField), (
        f"{field} must be an EncryptedTextField — a database dump should not "
        "hand over live gateway credentials."
    )
