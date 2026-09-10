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
