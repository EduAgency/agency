"""Fernet-encrypted model field for gateway credentials (plan §5.1).

Values are encrypted on the way into the database and decrypted on the way out,
so a database dump or read-replica leak does not hand over live Paystack /
Flutterwave secret keys. The key itself comes from FIELD_ENCRYPTION_KEY in the
environment and must never be committed.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _fernet():
    from cryptography.fernet import Fernet

    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY is not set. Generate one with:\n"
            '  python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """TextField whose database value is a Fernet token.

    Not searchable or indexable by design — encrypted credentials should never
    be filtered on. Store a non-sensitive fingerprint alongside if you need to
    identify which key is in use.
    """

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        if isinstance(value, str):
            value = value.encode()
        return _fernet().encrypt(value).decode()

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        from cryptography.fernet import InvalidToken

        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Wrong/rotated key — surface as empty rather than crashing the admin.
            return ""


def fingerprint(secret: str) -> str:
    """Short non-reversible identifier so admins can confirm *which* key is live
    without ever displaying it."""
    import hashlib

    if not secret:
        return ""
    return hashlib.sha256(secret.encode()).hexdigest()[:12]
