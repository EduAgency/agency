"""Deciding where a notification actually goes.

One question, asked on every send: *given this user and this category, which
channels should this message reach?*

The answer is the intersection of four things, and all four have to agree:

1. The agency has the channel **enabled and configured** (``ChannelConfig``).
2. The user has **opted in** for that category on that channel.
3. The user is **reachable** there — a Telegram chat linked, a WhatsApp number
   opted in. An enabled channel with no address is not a channel.
4. It is not **quiet hours**, unless the message is urgent.

Plus one override that beats all of it: transactional categories always go by
email. A password reset that a preference silently swallowed is not a
preference honoured, it is a lockout.
"""

from __future__ import annotations

from datetime import time

from django.utils import timezone

from .models import (
    ALWAYS_EMAIL_CATEGORIES,
    CHOOSABLE_CHANNELS,
    DEFAULT_PREFERENCES,
    Channel,
    ChannelConfig,
    Notification,
    NotificationPreference,
    TelegramLink,
)

#: Categories that should never wait for quiet hours to end.
URGENT_CATEGORIES = {
    Notification.Category.ACCOUNT,
    Notification.Category.PAYMENT,
}


def live_channels() -> set[str]:
    """Channels the agency has switched on AND finished configuring."""
    live = set()
    for config in ChannelConfig.objects.all():
        if config.is_live:
            live.add(config.channel)
    # Email needs no credentials of its own — the mail backend is in settings —
    # so it is available unless somebody has explicitly switched it off.
    if not ChannelConfig.objects.filter(channel=Channel.EMAIL, is_enabled=False).exists():
        live.add(Channel.EMAIL)
    return live


def is_reachable(user, channel: str) -> bool:
    """Whether we actually hold an address for this user on this channel."""
    if channel == Channel.EMAIL:
        return bool(user.email)
    if channel == Channel.TELEGRAM:
        return TelegramLink.objects.filter(user=user).exists()
    if channel == Channel.WHATSAPP:
        # WhatsApp Business policy requires a recorded opt-in before the first
        # message, so a number alone is not permission.
        profile = getattr(user, "student_profile", None)
        number = (profile.whatsapp if profile else "") or user.phone
        return bool(number) and bool(getattr(profile, "whatsapp_opted_in_at", None))
    return False


def stored_preferences(user) -> dict[tuple[str, str], bool]:
    return {
        (row.category, row.channel): row.is_enabled
        for row in NotificationPreference.objects.filter(user=user)
    }


def wants(user, category: str, channel: str, *, stored=None) -> bool:
    """Has this user opted in for this category on this channel?"""
    stored = stored if stored is not None else stored_preferences(user)
    if (category, channel) in stored:
        return stored[(category, channel)]
    return channel in DEFAULT_PREFERENCES.get(category, set())


def in_quiet_hours(user, at=None) -> bool:
    """Quiet hours are stored on the student profile, in the agency timezone."""
    profile = getattr(user, "student_profile", None)
    if profile is None:
        return False
    start = getattr(profile, "quiet_hours_start", None)
    end = getattr(profile, "quiet_hours_end", None)
    if not start or not end:
        return False

    now = (at or timezone.localtime()).time()
    if start == end:
        return False
    if start < end:
        return start <= now < end
    # Spans midnight — 22:00 to 07:00 is the normal case.
    return now >= start or now < end


def resolve(user, category: str, *, urgent: bool | None = None) -> list[str]:
    """Every channel this notification should be delivered on.

    ``Channel.IN_APP`` is not returned: it is the record of the notification,
    created unconditionally, not a delivery target.
    """
    if urgent is None:
        urgent = category in URGENT_CATEGORIES

    available = live_channels()
    stored = stored_preferences(user)
    quiet = (not urgent) and in_quiet_hours(user)

    chosen = []
    for channel in CHOOSABLE_CHANNELS:
        if channel not in available:
            continue
        if not is_reachable(user, channel):
            continue
        if not wants(user, category, channel, stored=stored):
            continue
        chosen.append(channel)

    # Transactional mail is not negotiable. It is added even when the user has
    # switched email off for this category, and even during quiet hours.
    if category in ALWAYS_EMAIL_CATEGORIES and Channel.EMAIL in available and user.email:
        if Channel.EMAIL not in chosen:
            chosen.append(Channel.EMAIL)
    elif quiet:
        # Everything else waits. The notification is still recorded in-app, so
        # nothing is lost — it just does not buzz someone's phone at 03:00.
        return []

    return chosen


def describe(user) -> dict:
    """The whole preference picture, shaped for the preference centre UI."""
    available = live_channels()
    stored = stored_preferences(user)
    profile = getattr(user, "student_profile", None)

    return {
        "channels": [
            {
                "channel": channel,
                "label": Channel(channel).label,
                "available": channel in available,
                "connected": is_reachable(user, channel),
                "locked": channel == Channel.EMAIL,
            }
            for channel in CHOOSABLE_CHANNELS
        ],
        "categories": [
            {
                "category": category,
                "label": Notification.Category(category).label,
                "always_email": category in ALWAYS_EMAIL_CATEGORIES,
                "channels": {
                    channel: wants(user, category, channel, stored=stored)
                    for channel in CHOOSABLE_CHANNELS
                },
            }
            for category, _ in Notification.Category.choices
        ],
        "quiet_hours": {
            "start": getattr(profile, "quiet_hours_start", None),
            "end": getattr(profile, "quiet_hours_end", None),
        },
    }


def set_preference(user, category: str, channel: str, enabled: bool) -> None:
    """Record one choice, refusing the ones that are not really choices."""
    if channel not in CHOOSABLE_CHANNELS:
        raise ValueError(f"{channel} is not a channel a user can choose.")
    if category in ALWAYS_EMAIL_CATEGORIES and channel == Channel.EMAIL and not enabled:
        raise ValueError(
            "Security and payment emails cannot be switched off — they are how "
            "you keep control of your account."
        )
    NotificationPreference.objects.update_or_create(
        user=user, category=category, channel=channel, defaults={"is_enabled": enabled}
    )


def set_quiet_hours(user, start: time | None, end: time | None) -> None:
    profile = getattr(user, "student_profile", None)
    if profile is None:
        return
    profile.quiet_hours_start = start
    profile.quiet_hours_end = end
    profile.save(update_fields=["quiet_hours_start", "quiet_hours_end", "updated_at"])
