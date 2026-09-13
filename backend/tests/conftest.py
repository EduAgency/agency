from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import StudentProfile
from apps.applications.models import Application
from apps.schools.models import (
    Country,
    Programme,
    RequirementCategory,
    RequirementItem,
    School,
    SchoolRequirementSet,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def isolated_cache(settings):
    """Give each test its own throttle counters.

    DRF throttling counts against the default cache. Sharing the dev Redis means
    one test's signups exhaust the 5/hour limit for every later test — and
    leaves that state behind for the next run.
    """
    from django.core.cache import cache

    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-cache",
        }
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def isolated_singletons():
    """Clear the cached singleton rows between tests.

    `Pricing.load()` and `BlogSettings.load()` cache, and a cache entry outlives
    a transaction rollback — so a test that raises the access fee would raise it
    for every test that ran afterwards, in a different file, with no visible
    connection.
    """
    from django.core.cache import cache

    keys = ("payments:pricing", "blog:settings")
    for key in keys:
        cache.delete(key)
    yield
    for key in keys:
        cache.delete(key)


@pytest.fixture
def access_fee():
    """The live access fee, for tests that need to quote it.

    A test must never hardcode the price: that is the bug this whole layer
    exists to remove, and a test that hardcodes it would start failing the moment
    somebody legitimately changed the fee.
    """
    from apps.payments.pricing import Pricing

    return Pricing.load()


@pytest.fixture
def no_throttling(settings):
    """For tests about something other than rate limiting."""
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {k: None for k in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]},
    }
    return settings


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    """Keep uploaded test files out of the repo's media directory.

    Autouse: any test that uploads should get a throwaway location without
    having to remember to ask for one.
    """
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        # Skip the manifest storage in tests — there is no collectstatic run.
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    return settings.MEDIA_ROOT


@pytest.fixture
def student(db):
    user = User.objects.create_user(email="ada@example.com", password="pass-word-1234", first_name="Ada")
    return StudentProfile.objects.get(user=user)


@pytest.fixture
def other_student(db):
    user = User.objects.create_user(email="bola@example.com", password="pass-word-1234", first_name="Bola")
    return StudentProfile.objects.get(user=user)


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        email="reviewer@nasuru.com", password="pass-word-1234", role=User.Role.REVIEWER, is_staff=True
    )


@pytest.fixture
def category(db):
    return RequirementCategory.objects.create(name="Documents & Transcripts", display_order=10)


@pytest.fixture
def school(db):
    country = Country.objects.create(name="Germany", iso_code="DE")
    return School.objects.create(name="HWR Berlin", country=country, city="Berlin")


@pytest.fixture
def programme(school):
    return Programme.objects.create(school=school, name="International Business Management")


@pytest.fixture
def requirement_set(school, programme, category):
    rset = SchoolRequirementSet.objects.create(school=school, programme=programme, name="Intake set")
    RequirementItem.objects.create(
        requirement_set=rset, category=category, label="Passport", is_required=True,
        is_shareable=True, shareable_key="passport", display_order=1,
    )
    RequirementItem.objects.create(
        requirement_set=rset, category=category, label="Transcript", is_required=True, display_order=2,
    )
    RequirementItem.objects.create(
        requirement_set=rset, category=category, label="Reference letter", is_required=False, display_order=3,
    )
    rset.publish()
    return rset


@pytest.fixture
def application(student, school, programme, requirement_set):
    return Application.objects.create(
        student=student, school=school, programme=programme, intake="October 2027"
    )


@pytest.fixture
def gateway_config(db, settings):
    from apps.payments.models import Gateway, PaymentGatewayConfig

    return PaymentGatewayConfig.objects.create(
        gateway=Gateway.PAYSTACK,
        currency="NGN",
        is_active=True,
        is_test_mode=True,
        public_key="pk_test_123",
        secret_key="sk_test_secret",
        webhook_secret="sk_test_secret",
    )


@pytest.fixture
def access_fee_payment(student, gateway_config):
    from apps.payments.models import Payment

    return Payment.objects.create(
        reference=Payment.generate_reference(),
        gateway=gateway_config.gateway,
        gateway_config=gateway_config,
        student=student,
        email=student.user.email,
        purpose=Payment.Purpose.ACCESS_FEE,
        amount=Decimal("5000.00"),
        currency="NGN",
    )


@pytest.fixture
def api():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def as_student(api, student):
    api.force_authenticate(user=student.user)
    return api


@pytest.fixture
def paid_student(student):
    """A student who has actually paid — most of the platform is behind this."""
    student.has_platform_access = True
    student.stage = student.Stage.PAID
    student.save()
    return student


@pytest.fixture
def as_paid_student(api, paid_student):
    api.force_authenticate(user=paid_student.user)
    return api


@pytest.fixture
def reviewer(db):
    """Staff who may review documents and nothing else."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email="doc.reviewer@nasuru.com", password="pass-word-1234",
        role=User.Role.REVIEWER, is_staff=True,
    )


@pytest.fixture
def as_reviewer(api, reviewer):
    api.force_authenticate(user=reviewer)
    return api


@pytest.fixture
def superadmin(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_superuser(email="boss@nasuru.com", password="pass-word-1234")


@pytest.fixture
def as_admin(api, superadmin):
    api.force_authenticate(user=superadmin)
    return api
