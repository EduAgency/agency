"""Two-factor authentication, end to end.

Every test here corresponds to a way MFA is usually got wrong: enrolment that
switches on before the user can prove they hold the secret, codes that can be
replayed, recovery codes that survive being used, a second factor that the
account holder can simply turn off, and a staff requirement that is advisory
rather than enforced.

See docs/enterprise-readiness.md, Phase 4.
"""

from __future__ import annotations

import time

import pytest
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts import mfa

# Matches the shared fixtures in conftest.py.
PASSWORD = "pass-word-1234"


def code_for(device: TOTPDevice, offset: int = 0) -> str:
    """Generate the code the user's authenticator app would be showing."""
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits)
    totp.time = time.time() + offset
    return f"{totp.token():0{device.digits}d}"


# One TOTP step. A code is single-use, so anything done *after* enrolment needs
# the next window's code — which is what the user's app would be showing by then.
NEXT_WINDOW = 30


def enrol(api, user) -> TOTPDevice:
    """Take an account all the way through enrolment."""
    api.force_authenticate(user=user)
    api.post("/api/auth/mfa/enrol/")
    device = mfa.totp_device(user, confirmed=False)
    response = api.post(
        "/api/auth/mfa/confirm/", {"code": code_for(device)}, format="json"
    )
    assert response.status_code == 200, response.json()
    device.refresh_from_db()
    return device


@pytest.mark.django_db
class TestEnrolment:
    def test_enrolment_returns_a_secret_and_an_otpauth_url(self, api, student, no_throttling):
        api.force_authenticate(user=student.user)
        response = api.post("/api/auth/mfa/enrol/")

        assert response.status_code == 200
        body = response.json()
        assert body["secret"]
        assert body["otpauth_url"].startswith("otpauth://totp/")
        assert student.user.email in body["otpauth_url"], "the label should stay readable"

    def test_mfa_is_not_on_until_the_first_code_is_verified(self, api, student, no_throttling):
        api.force_authenticate(user=student.user)
        api.post("/api/auth/mfa/enrol/")

        # A mistyped secret must be caught here, not at the next sign-in.
        assert mfa.has_mfa(student.user) is False
        assert api.get("/api/auth/mfa/").json()["enabled"] is False

    def test_a_wrong_code_does_not_switch_it_on(self, api, student, no_throttling):
        api.force_authenticate(user=student.user)
        api.post("/api/auth/mfa/enrol/")

        response = api.post("/api/auth/mfa/confirm/", {"code": "000000"}, format="json")

        assert response.status_code == 400
        assert mfa.has_mfa(student.user) is False

    def test_confirming_switches_it_on_and_returns_recovery_codes(self, api, student, no_throttling):
        api.force_authenticate(user=student.user)
        api.post("/api/auth/mfa/enrol/")
        device = mfa.totp_device(student.user, confirmed=False)

        response = api.post(
            "/api/auth/mfa/confirm/", {"code": code_for(device)}, format="json"
        )

        assert response.status_code == 200
        codes = response.json()["recovery_codes"]
        assert len(codes) == mfa.RECOVERY_CODE_COUNT
        assert len(set(codes)) == mfa.RECOVERY_CODE_COUNT, "recovery codes must be unique"
        assert mfa.has_mfa(student.user) is True

    def test_enrolling_twice_is_refused(self, api, student, no_throttling):
        enrol(api, student.user)
        assert api.post("/api/auth/mfa/enrol/").status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_password_alone_stops_at_mfa_required(self, api, student, no_throttling):
        enrol(api, student.user)
        api.force_authenticate(user=None)

        response = api.post(
            "/api/auth/login/",
            {"email": student.user.email, "password": PASSWORD},
            format="json",
        )

        assert response.status_code == 401
        # The frontend branches on this code to show the challenge screen.
        assert response.json()["code"] == "mfa_required"
        assert "tokens" not in response.json()

    def test_a_valid_code_completes_the_sign_in(self, api, student, no_throttling):
        device = enrol(api, student.user)
        api.force_authenticate(user=None)

        response = api.post(
            "/api/auth/login/",
            {
                "email": student.user.email,
                "password": PASSWORD,
                "otp": code_for(device, NEXT_WINDOW),
            },
            format="json",
        )

        assert response.status_code == 200, response.json()
        assert response.json()["tokens"]["access"]

    def test_a_wrong_code_is_refused(self, api, student, no_throttling):
        enrol(api, student.user)
        api.force_authenticate(user=None)

        response = api.post(
            "/api/auth/login/",
            {"email": student.user.email, "password": PASSWORD, "otp": "000000"},
            format="json",
        )

        assert response.status_code == 401
        assert response.json()["code"] == "mfa_invalid"

    def test_the_second_factor_is_only_checked_after_the_password(self, api, student, no_throttling):
        """A wrong password must never reveal whether the account uses MFA."""
        enrol(api, student.user)
        api.force_authenticate(user=None)

        response = api.post(
            "/api/auth/login/",
            {"email": student.user.email, "password": "wrong-password"},
            format="json",
        )

        assert response.status_code == 400
        assert "mfa" not in response.content.decode().lower()

    def test_a_code_cannot_be_replayed(self, api, student, no_throttling):
        device = enrol(api, student.user)
        api.force_authenticate(user=None)
        code = code_for(device, NEXT_WINDOW)
        payload = {"email": student.user.email, "password": PASSWORD, "otp": code}

        assert api.post("/api/auth/login/", payload, format="json").status_code == 200
        # django-otp refuses a token at or below the last used counter.
        assert api.post("/api/auth/login/", payload, format="json").status_code == 401


@pytest.mark.django_db
class TestRecoveryCodes:
    def test_a_recovery_code_signs_you_in(self, api, student, no_throttling):
        api.force_authenticate(user=student.user)
        api.post("/api/auth/mfa/enrol/")
        device = mfa.totp_device(student.user, confirmed=False)
        codes = api.post(
            "/api/auth/mfa/confirm/", {"code": code_for(device)}, format="json"
        ).json()["recovery_codes"]
        api.force_authenticate(user=None)

        response = api.post(
            "/api/auth/login/",
            {"email": student.user.email, "password": PASSWORD, "otp": codes[0]},
            format="json",
        )

        assert response.status_code == 200, response.json()

    def test_a_recovery_code_works_only_once(self, api, student, no_throttling):
        api.force_authenticate(user=student.user)
        api.post("/api/auth/mfa/enrol/")
        device = mfa.totp_device(student.user, confirmed=False)
        codes = api.post(
            "/api/auth/mfa/confirm/", {"code": code_for(device)}, format="json"
        ).json()["recovery_codes"]
        api.force_authenticate(user=None)
        payload = {"email": student.user.email, "password": PASSWORD, "otp": codes[0]}

        assert api.post("/api/auth/login/", payload, format="json").status_code == 200
        assert api.post("/api/auth/login/", payload, format="json").status_code == 401

    def test_using_one_decrements_the_remaining_count(self, api, student, no_throttling):
        enrol(api, student.user)
        before = mfa.unused_recovery_code_count(student.user)

        codes = mfa.regenerate_recovery_codes(student.user)
        assert mfa.unused_recovery_code_count(student.user) == before

        mfa.verify(student.user, codes[0])
        assert mfa.unused_recovery_code_count(student.user) == before - 1

    def test_regenerating_invalidates_the_old_set(self, api, student, no_throttling):
        enrol(api, student.user)
        first = mfa.regenerate_recovery_codes(student.user)
        second = mfa.regenerate_recovery_codes(student.user)

        assert set(first).isdisjoint(second)
        # Success first: a failed attempt throttles the device, so checking the
        # dead code first would make the live one look dead too.
        assert mfa.verify(student.user, second[0]) is True
        assert mfa.verify(student.user, first[0]) is False

    def test_a_hyphen_is_a_reading_aid_not_part_of_the_code(self, api, student, no_throttling):
        """Codes are shown as XXXX-XXXX but stored unformatted."""
        enrol(api, student.user)
        codes = mfa.regenerate_recovery_codes(student.user)

        assert "-" in codes[0]
        assert mfa.verify(student.user, codes[0].replace("-", "")) is True


@pytest.mark.django_db
class TestDisabling:
    def test_a_student_can_switch_it_off_with_a_current_code(self, api, student, no_throttling):
        device = enrol(api, student.user)

        response = api.post(
            "/api/auth/mfa/disable/", {"code": code_for(device, NEXT_WINDOW)}, format="json"
        )

        assert response.status_code == 200
        assert mfa.has_mfa(student.user) is False

    def test_switching_off_needs_a_code(self, api, student, no_throttling):
        enrol(api, student.user)

        response = api.post(
            "/api/auth/mfa/disable/", {"code": "000000"}, format="json"
        )

        assert response.status_code == 400
        assert mfa.has_mfa(student.user) is True

    def test_staff_may_not_switch_it_off(self, api, reviewer, no_throttling):
        """Otherwise the staff requirement is advisory, not a control."""
        device = enrol(api, reviewer)

        response = api.post(
            "/api/auth/mfa/disable/", {"code": code_for(device, NEXT_WINDOW)}, format="json"
        )

        assert response.status_code == 403
        assert mfa.has_mfa(reviewer) is True


@pytest.mark.django_db
class TestStatus:
    def test_mfa_is_required_for_staff_and_optional_for_students(self, api, student, reviewer, no_throttling):
        api.force_authenticate(user=student.user)
        assert api.get("/api/auth/mfa/").json()["required"] is False

        api.force_authenticate(user=reviewer)
        assert api.get("/api/auth/mfa/").json()["required"] is True

    def test_status_reports_the_remaining_recovery_codes(self, api, student, no_throttling):
        enrol(api, student.user)
        api.force_authenticate(user=student.user)

        body = api.get("/api/auth/mfa/").json()

        assert body["enabled"] is True
        assert body["recovery_codes_remaining"] == mfa.RECOVERY_CODE_COUNT

    def test_status_needs_a_signed_in_user(self, api, no_throttling):
        api.force_authenticate(user=None)
        assert api.get("/api/auth/mfa/").status_code == 401


@pytest.mark.django_db
def test_mfa_never_leaks_the_secret_after_enrolment(api, student, no_throttling):
    """The secret is shown once, at enrolment, and is not readable afterwards."""
    enrol(api, student.user)
    api.force_authenticate(user=student.user)

    body = api.get("/api/auth/mfa/").content.decode()

    device = mfa.totp_device(student.user)
    assert device is not None
    assert device.key not in body
