"""Delivery to each channel.

Every provider has the same shape: take a Notification, send it, and either
return normally or raise. The task layer above handles persistence, retries
and recording the failure, so nothing here touches the database.

Two failure modes are distinguished deliberately:

* ``ChannelNotConfigured`` — we cannot send and retrying will not help. The
  notification is marked failed immediately rather than retried three times.
* anything else — transient. The task retries with backoff.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import Channel, ChannelConfig, TelegramLink

logger = logging.getLogger(__name__)

TIMEOUT = 15


class ChannelNotConfigured(Exception):
    """Permanent: no credentials, no address, or the channel is switched off."""


def _config(channel: str) -> ChannelConfig:
    config = ChannelConfig.objects.filter(channel=channel).first()
    if config is None or not config.is_live:
        raise ChannelNotConfigured(f"{channel} is not enabled and configured.")
    return config


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def send_email(notification) -> None:
    recipient = notification.recipient
    if not recipient.email:
        raise ChannelNotConfigured("This account has no email address.")

    body = notification.body
    if notification.action_url:
        body = f"{body}\n\n{notification.action_url}"

    message = EmailMultiAlternatives(
        subject=notification.subject or "Nasuru",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient.email],
    )
    message.send(fail_silently=False)


# ---------------------------------------------------------------------------
# WhatsApp — Meta Cloud API
# ---------------------------------------------------------------------------


def whatsapp_number_for(user) -> str:
    profile = getattr(user, "student_profile", None)
    number = (profile.whatsapp if profile else "") or getattr(user, "phone", "")
    return "".join(ch for ch in (number or "") if ch.isdigit())


def send_whatsapp(notification) -> None:
    config = _config(Channel.WHATSAPP)
    number = whatsapp_number_for(notification.recipient)
    if not number:
        raise ChannelNotConfigured("This account has no WhatsApp number.")

    profile = getattr(notification.recipient, "student_profile", None)
    if not getattr(profile, "whatsapp_opted_in_at", None):
        # Sending without a recorded opt-in risks the business account itself,
        # not just this one message.
        raise ChannelNotConfigured("This account has not opted in to WhatsApp.")

    text = notification.body
    if notification.action_url:
        text = f"{text}\n\n{notification.action_url}"

    response = requests.post(
        f"https://graph.facebook.com/v21.0/{config.whatsapp_phone_number_id}/messages",
        headers={
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "text",
            # Link previews are noise on a transactional message.
            "text": {"preview_url": False, "body": text[:4096]},
        },
        timeout=TIMEOUT,
    )

    if response.status_code == 400:
        # Meta uses 400 for "this number is not on WhatsApp" and for an expired
        # 24-hour session — neither is worth retrying.
        raise ChannelNotConfigured(f"WhatsApp refused the message: {response.text[:300]}")
    response.raise_for_status()


# ---------------------------------------------------------------------------
# Telegram — Bot API
# ---------------------------------------------------------------------------


def send_telegram(notification) -> None:
    config = _config(Channel.TELEGRAM)
    link = TelegramLink.objects.filter(user=notification.recipient).first()
    if link is None:
        raise ChannelNotConfigured("This account has not connected Telegram.")

    text = notification.body
    if notification.subject:
        # Telegram renders a bold first line as a usable heading.
        text = f"*{_escape(notification.subject)}*\n\n{_escape(text)}"
    else:
        text = _escape(text)
    if notification.action_url:
        text = f"{text}\n\n{_escape(notification.action_url)}"

    response = requests.post(
        f"https://api.telegram.org/bot{config.access_token}/sendMessage",
        json={
            "chat_id": link.chat_id,
            "text": text[:4096],
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        },
        timeout=TIMEOUT,
    )

    if response.status_code == 403:
        # The user blocked the bot. Drop the link so we stop trying and the
        # preference centre shows Telegram as disconnected rather than lying.
        TelegramLink.objects.filter(pk=link.pk).delete()
        raise ChannelNotConfigured("The user has blocked the Telegram bot.")
    if response.status_code == 400:
        raise ChannelNotConfigured(f"Telegram refused the message: {response.text[:300]}")
    response.raise_for_status()


def _escape(text: str) -> str:
    """MarkdownV2 requires every one of these to be escaped, everywhere."""
    for char in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(char, f"\\{char}")
    return text


# ---------------------------------------------------------------------------


SENDERS = {
    Channel.EMAIL: send_email,
    Channel.WHATSAPP: send_whatsapp,
    Channel.TELEGRAM: send_telegram,
}


def send(notification) -> None:
    sender = SENDERS.get(notification.channel)
    if sender is None:
        raise ChannelNotConfigured(f"No sender for channel {notification.channel!r}.")
    sender(notification)
