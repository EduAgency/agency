"""Where a notification goes, and why.

The routing rule has four inputs that all have to agree — channel enabled and
configured, user opted in, user reachable, not quiet hours — plus one override
that beats all of them. Each test below pins one of those, because the failure
mode is silent: a message that is never delivered looks exactly like a message
that was never sent.

See docs/enterprise-readiness.md, Phase 4.
"""

from __future__ import annotations

from datetime import time

import pytest
from django.utils import timezone

from apps.notifications import preferences
from apps.notifications.models import (
    Channel,
    ChannelConfig,
    Notification,
    NotificationPreference,
    TelegramLink,
)
from apps.notifications.services import create_notification

CATEGORY = Notification.Category


@pytest.fixture
def all_channels_live(db):
    """Agency has switched on and configured every channel."""
    ChannelConfig.objects.create(channel=Channel.EMAIL, is_enabled=True)
    ChannelConfig.objects.create(
        channel=Channel.WHATSAPP,
        is_enabled=True,
        whatsapp_phone_number_id="1234567890",
        access_token="whatsapp-token",
    )
    ChannelConfig.objects.create(
        channel=Channel.TELEGRAM,
        is_enabled=True,
        telegram_bot_username="nasuru_bot",
        access_token="telegram-token",
        webhook_verify_token="verify-me",
    )


@pytest.fixture
def reachable_everywhere(student, all_channels_live):
    """...and the student can actually be reached on all of them."""
    student.whatsapp = "+2348030000001"
    student.whatsapp_opted_in_at = timezone.now()
    student.save()
    TelegramLink.objects.create(user=student.user, chat_id="555", telegram_username="amara")
    return student


def opt_in(user, category, *channels):
    for channel in channels:
        NotificationPreference.objects.update_or_create(
            user=user, category=category, channel=channel, defaults={"is_enabled": True}
        )


@pytest.mark.django_db
class TestSmsIsGone:
    def test_sms_is_not_a_channel(self):
        assert "sms" not in {value for value, _ in Channel.choices}

    def test_the_channels_are_exactly_these(self):
        assert {value for value, _ in Channel.choices} == {
            "in_app",
            "email",
            "whatsapp",
            "telegram",
        }


@pytest.mark.django_db
class TestChannelAvailability:
    def test_a_channel_that_is_not_configured_is_not_offered(self, student, db):
        # Enabled but with no token — the classic way to build a toggle that
        # silently does nothing.
        ChannelConfig.objects.create(channel=Channel.TELEGRAM, is_enabled=True)
        TelegramLink.objects.create(user=student.user, chat_id="1")
        opt_in(student.user, CATEGORY.DOCUMENT, Channel.TELEGRAM)

        assert Channel.TELEGRAM not in preferences.resolve(student.user, CATEGORY.DOCUMENT)

    def test_a_configured_channel_that_is_switched_off_is_not_offered(
        self, student, reachable_everywhere
    ):
        ChannelConfig.objects.filter(channel=Channel.TELEGRAM).update(is_enabled=False)
        opt_in(student.user, CATEGORY.DOCUMENT, Channel.TELEGRAM)

        assert Channel.TELEGRAM not in preferences.resolve(student.user, CATEGORY.DOCUMENT)

    def test_email_is_available_without_any_config_row(self, student, db):
        """The mail backend lives in settings, so email needs no credentials."""
        assert Channel.EMAIL in preferences.live_channels()


@pytest.mark.django_db
class TestReachability:
    def test_telegram_needs_a_linked_chat(self, student, all_channels_live):
        opt_in(student.user, CATEGORY.DOCUMENT, Channel.TELEGRAM)
        assert Channel.TELEGRAM not in preferences.resolve(student.user, CATEGORY.DOCUMENT)

        TelegramLink.objects.create(user=student.user, chat_id="999")
        assert Channel.TELEGRAM in preferences.resolve(student.user, CATEGORY.DOCUMENT)

    def test_whatsapp_needs_an_opt_in_not_just_a_number(self, student, all_channels_live):
        """Holding somebody's number is not permission to message them."""
        student.whatsapp = "+2348030000001"
        student.save()
        opt_in(student.user, CATEGORY.DOCUMENT, Channel.WHATSAPP)

        assert Channel.WHATSAPP not in preferences.resolve(student.user, CATEGORY.DOCUMENT)

        student.whatsapp_opted_in_at = timezone.now()
        student.save()
        assert Channel.WHATSAPP in preferences.resolve(student.user, CATEGORY.DOCUMENT)


@pytest.mark.django_db
class TestDefaults:
    def test_email_is_on_by_default_for_things_that_matter(self, student, all_channels_live):
        for category in [CATEGORY.DOCUMENT, CATEGORY.APPLICATION, CATEGORY.MESSAGE]:
            assert preferences.resolve(student.user, category) == [Channel.EMAIL]

    def test_announcements_are_opt_in_never_opt_out(self, student, reachable_everywhere):
        """Nudges and tips stay off until somebody asks for them."""
        assert preferences.resolve(student.user, CATEGORY.SYSTEM) == []

    def test_rich_channels_stay_off_until_connected(self, student, reachable_everywhere):
        # Reachable on all three, but has not asked for WhatsApp or Telegram.
        assert preferences.resolve(student.user, CATEGORY.DOCUMENT) == [Channel.EMAIL]


@pytest.mark.django_db
class TestTransactionalOverride:
    def test_security_email_cannot_be_switched_off(self, student, all_channels_live):
        NotificationPreference.objects.create(
            user=student.user, category=CATEGORY.ACCOUNT, channel=Channel.EMAIL, is_enabled=False
        )

        # A password reset a preference swallowed is a lockout, not a
        # preference honoured.
        assert Channel.EMAIL in preferences.resolve(student.user, CATEGORY.ACCOUNT)

    def test_payment_email_cannot_be_switched_off(self, student, all_channels_live):
        NotificationPreference.objects.create(
            user=student.user, category=CATEGORY.PAYMENT, channel=Channel.EMAIL, is_enabled=False
        )
        assert Channel.EMAIL in preferences.resolve(student.user, CATEGORY.PAYMENT)

    def test_the_api_refuses_to_record_that_choice(self, student, all_channels_live):
        with pytest.raises(ValueError, match="cannot be switched off"):
            preferences.set_preference(student.user, CATEGORY.ACCOUNT, Channel.EMAIL, False)

    def test_optional_categories_can_be_switched_off(self, student, all_channels_live):
        preferences.set_preference(student.user, CATEGORY.DOCUMENT, Channel.EMAIL, False)
        assert preferences.resolve(student.user, CATEGORY.DOCUMENT) == []


@pytest.mark.django_db
class TestQuietHours:
    def test_non_urgent_messages_wait(self, student, reachable_everywhere):
        student.quiet_hours_start = time(0, 0)
        student.quiet_hours_end = time(23, 59)
        student.save()

        assert preferences.resolve(student.user, CATEGORY.DOCUMENT) == []

    def test_urgent_messages_do_not(self, student, reachable_everywhere):
        student.quiet_hours_start = time(0, 0)
        student.quiet_hours_end = time(23, 59)
        student.save()

        # A payment receipt at 03:00 is still a payment receipt.
        assert Channel.EMAIL in preferences.resolve(student.user, CATEGORY.PAYMENT)

    def test_quiet_hours_spanning_midnight(self, student):
        student.quiet_hours_start = time(22, 0)
        student.quiet_hours_end = time(7, 0)
        student.save()

        assert preferences.in_quiet_hours(student.user, _at(23, 30)) is True
        assert preferences.in_quiet_hours(student.user, _at(3, 0)) is True
        assert preferences.in_quiet_hours(student.user, _at(12, 0)) is False

    def test_no_quiet_hours_set_means_always_deliverable(self, student, all_channels_live):
        assert preferences.in_quiet_hours(student.user) is False


@pytest.mark.django_db
class TestFanOut:
    def test_every_notification_writes_an_in_app_record(self, student, all_channels_live):
        """The inbox is the answer to 'nobody ever told me'."""
        created = create_notification(
            recipient=student.user,
            category=CATEGORY.DOCUMENT,
            subject="Passport verified",
            body="Looks good.",
            send_now=False,
        )

        channels = {n.channel for n in created}
        assert Channel.IN_APP in channels

    def test_it_reaches_every_channel_the_user_chose(self, student, reachable_everywhere):
        opt_in(student.user, CATEGORY.DOCUMENT, Channel.WHATSAPP, Channel.TELEGRAM)

        created = create_notification(
            recipient=student.user,
            category=CATEGORY.DOCUMENT,
            subject="Passport verified",
            body="Looks good.",
            send_now=False,
        )

        assert {n.channel for n in created} == {
            Channel.IN_APP,
            Channel.EMAIL,
            Channel.WHATSAPP,
            Channel.TELEGRAM,
        }

    def test_the_in_app_record_survives_every_channel_being_off(
        self, student, all_channels_live
    ):
        preferences.set_preference(student.user, CATEGORY.DOCUMENT, Channel.EMAIL, False)

        created = create_notification(
            recipient=student.user,
            category=CATEGORY.DOCUMENT,
            subject="Passport verified",
            body="Looks good.",
            send_now=False,
        )

        assert [n.channel for n in created] == [Channel.IN_APP]

    def test_the_in_app_record_is_not_left_queued_forever(self, student, all_channels_live):
        created = create_notification(
            recipient=student.user,
            category=CATEGORY.DOCUMENT,
            body="Looks good.",
            send_now=False,
        )
        inbox = next(n for n in created if n.channel == Channel.IN_APP)

        # It is a record, not a delivery — nothing will ever "send" it.
        assert inbox.status == Notification.Status.SENT


def _at(hour: int, minute: int):
    return timezone.localtime().replace(hour=hour, minute=minute)
