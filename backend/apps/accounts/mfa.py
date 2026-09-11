"""Two-factor authentication for the API.

``django_otp`` was already installed and already gating the Django admin, but
nothing protected the API — so a staff account holding students' passports and
national identity documents sat behind a password alone
(docs/enterprise-readiness.md §C, "MFA").

Two device types, both from django-otp, so there are no new tables:

* ``TOTPDevice``  — the authenticator app. One confirmed device per user.
* ``StaticDevice`` — single-use recovery codes, for a lost phone. Without these
  a lost phone means a support ticket that can only be resolved by disabling
  somebody's second factor over the phone, which is exactly the social
  engineering path MFA is supposed to close.

Verification accepts either. A recovery code is consumed on use, so a stolen
list is worth less the more it has been used.

One django-otp behaviour worth knowing about: its devices carry a throttling
mixin, so a failed verification puts the device into a brief cooldown and the
next attempt is refused even when the code is right. That is what makes
brute-forcing a six-digit code impractical, but it does mean a mistyped code
costs the user a moment rather than an instant retry.
"""

from __future__ import annotations

import secrets
from base64 import b32encode
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.core import audit

TOTP_DEVICE_NAME = "authenticator"
RECOVERY_DEVICE_NAME = "recovery-codes"
RECOVERY_CODE_COUNT = 10


def totp_device(user, *, confirmed: bool | None = True) -> TOTPDevice | None:
    """The user's authenticator device, or None."""
    query = TOTPDevice.objects.filter(user=user, name=TOTP_DEVICE_NAME)
    if confirmed is not None:
        query = query.filter(confirmed=confirmed)
    return query.first()


def has_mfa(user) -> bool:
    return totp_device(user) is not None


def is_required_for(user) -> bool:
    """Staff must use MFA; students may.

    Staff can reach other people's identity documents, so the trade-off between
    friction and exposure lands differently for them. A student who loses access
    to their own account is inconvenienced; a reviewer who does is a breach.
    """
    return bool(getattr(user, "is_agency_staff", False))


@transaction.atomic
def begin_enrolment(user) -> dict:
    """Create (or reset) an unconfirmed device and hand back its secret.

    The device stays unconfirmed until the user proves they can generate a code
    from it. Enrolling without that check is how people lock themselves out:
    a mistyped secret is only discovered at the next sign-in.
    """
    TOTPDevice.objects.filter(user=user, name=TOTP_DEVICE_NAME, confirmed=False).delete()

    if has_mfa(user):
        raise ValueError("Two-factor authentication is already switched on for this account.")

    device = TOTPDevice.objects.create(user=user, name=TOTP_DEVICE_NAME, confirmed=False)
    issuer = getattr(settings, "MFA_ISSUER_NAME", "Nasuru")

    return {
        # Base32 is what authenticator apps expect for manual entry.
        "secret": b32encode(device.bin_key).decode().rstrip("="),
        "otpauth_url": (
            f"otpauth://totp/{quote(issuer)}:{quote(user.email, safe='@')}"
            f"?secret={b32encode(device.bin_key).decode().rstrip('=')}"
            f"&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
        ),
        "issuer": issuer,
        "account": user.email,
    }


@transaction.atomic
def confirm_enrolment(user, code: str) -> list[str]:
    """Verify the first code, switch MFA on, and mint recovery codes."""
    device = totp_device(user, confirmed=False)
    if device is None:
        raise ValueError("Start setting up two-factor authentication first.")

    if not device.verify_token(_clean(code)):
        raise ValueError("That code is not right. Check your authenticator app and try again.")

    device.confirmed = True
    device.save(update_fields=["confirmed"])
    codes = regenerate_recovery_codes(user, _audit=False)
    audit.record("mfa_enabled", target=user, actor=user)
    return codes


@transaction.atomic
def regenerate_recovery_codes(user, *, _audit: bool = True) -> list[str]:
    """Replace every recovery code. Returned once, in clear, and never again."""
    device, _ = StaticDevice.objects.get_or_create(user=user, name=RECOVERY_DEVICE_NAME)
    device.token_set.all().delete()

    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        # Unambiguous alphabet: no O/0 or I/1, because these get written down
        # and read back by a person under stress.
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        # Stored unformatted, shown as XXXX-XXXX. The hyphen is a reading aid,
        # so it must not be part of what is compared — `_clean` strips it from
        # whatever the user types back, and the stored value never had one.
        StaticToken.objects.create(device=device, token=code)
        codes.append(f"{code[:4]}-{code[4:]}")

    device.confirmed = True
    device.save(update_fields=["confirmed"])
    if _audit:
        audit.record("mfa_recovery_codes_regenerated", target=user, actor=user)
    return codes


def unused_recovery_code_count(user) -> int:
    device = StaticDevice.objects.filter(user=user, name=RECOVERY_DEVICE_NAME).first()
    return device.token_set.count() if device else 0


def verify(user, code: str) -> bool:
    """Accept an authenticator code or a recovery code.

    django-otp's ``verify_token`` handles TOTP replay itself (it refuses a
    token at or below the last used counter), and consumes a static token on
    use, so neither path can be replayed.
    """
    cleaned = _clean(code)
    if not cleaned:
        return False

    device = totp_device(user)
    if device is not None and device.verify_token(cleaned):
        return True

    recovery = StaticDevice.objects.filter(user=user, name=RECOVERY_DEVICE_NAME).first()
    if recovery is not None and recovery.verify_token(cleaned.upper()):
        audit.record("mfa_recovery_code_used", target=user, actor=user)
        return True

    return False


@transaction.atomic
def disable(user) -> None:
    TOTPDevice.objects.filter(user=user, name=TOTP_DEVICE_NAME).delete()
    StaticDevice.objects.filter(user=user, name=RECOVERY_DEVICE_NAME).delete()
    audit.record("mfa_disabled", target=user, actor=user)


def _clean(code: str) -> str:
    """People paste codes with spaces and hyphens; the device wants neither."""
    return (code or "").strip().replace(" ", "").replace("-", "")
