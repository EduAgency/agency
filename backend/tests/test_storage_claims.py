"""Guards the public claims we make about document storage.

The landing page footer and the privacy policy both state that uploaded
documents are encrypted at rest. That was, for a while, only true by accident:
``EncryptedTextField`` covers payment gateway credentials, and nothing in the
S3 configuration asked for server-side encryption at all — it relied on AWS's
post-2023 default, which S3-compatible providers do not necessarily share.

These tests exist so that removing the setting breaks the build rather than
quietly turning a published statement into a false one.

See docs/enterprise-readiness.md, Phase 1.
"""

from __future__ import annotations

import importlib

import pytest


def _s3_options(monkeypatch, **env):
    """Re-import settings with USE_S3 on, and hand back the storage OPTIONS."""
    monkeypatch.setenv("USE_S3", "True")
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "nasuru-test-bucket")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from config import settings as settings_module

    reloaded = importlib.reload(settings_module)
    return reloaded.STORAGES["default"]["OPTIONS"]


def test_uploads_request_server_side_encryption(monkeypatch):
    options = _s3_options(monkeypatch)
    assert options["object_parameters"]["ServerSideEncryption"] == "AES256", (
        "Documents must be uploaded with SSE requested. The landing page and "
        "the privacy policy both claim encryption at rest."
    )


def test_documents_are_never_publicly_readable(monkeypatch):
    options = _s3_options(monkeypatch)
    assert options["default_acl"] == "private"
    assert options["querystring_auth"] is True


def test_signed_urls_expire_quickly(monkeypatch):
    options = _s3_options(monkeypatch)
    # A link to somebody's passport should not outlive the session that made it.
    assert options["querystring_expire"] <= 900


def test_uploads_never_overwrite_an_earlier_version(monkeypatch):
    """A rejected document stays retrievable — it is evidence in a dispute."""
    options = _s3_options(monkeypatch)
    assert options["file_overwrite"] is False


@pytest.mark.parametrize("field", ["secret_key", "webhook_secret", "encryption_key"])
def test_gateway_credentials_are_encrypted_at_rest(field):
    from apps.core.encryption import EncryptedTextField
    from apps.payments.models import PaymentGatewayConfig

    model_field = PaymentGatewayConfig._meta.get_field(field)
    assert isinstance(model_field, EncryptedTextField), (
        f"{field} must be an EncryptedTextField — a database dump should not "
        "hand over live gateway credentials."
    )
