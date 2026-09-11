"""The notification preference centre, and channel connection.

Three things a user can do here:

* see and change what reaches them, per category, per channel
* connect or disconnect Telegram
* opt in to or out of WhatsApp

Plus one unauthenticated endpoint: the Telegram bot webhook, which is how a
``/start`` in a chat becomes a link between a chat id and an account.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import audit

from . import preferences
from .models import (
    CATEGORY_DESCRIPTIONS,
    CHOOSABLE_CHANNELS,
    Channel,
    ChannelConfig,
    Notification,
    TelegramLink,
    TelegramLinkToken,
)

LINK_TOKEN_TTL = timedelta(minutes=15)


class PreferenceUpdateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=Notification.Category.choices)
    channel = serializers.ChoiceField(choices=[(c, c) for c in CHOOSABLE_CHANNELS])
    enabled = serializers.BooleanField()


class QuietHoursSerializer(serializers.Serializer):
    start = serializers.TimeField(allow_null=True, required=False)
    end = serializers.TimeField(allow_null=True, required=False)


class NotificationPreferencesView(APIView):
    """Everything the preference screen needs, in one response."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Preference matrix.")})
    def get(self, request):
        payload = preferences.describe(request.user)
        # The copy lives with the policy, not in the frontend, so a change to
        # what a category means travels with the code that sends it.
        for row in payload["categories"]:
            row["description"] = CATEGORY_DESCRIPTIONS.get(row["category"], "")
        payload["telegram"] = _telegram_state(request.user)
        payload["whatsapp"] = _whatsapp_state(request.user)
        return Response(payload)

    @extend_schema(request=PreferenceUpdateSerializer, responses={200: OpenApiResponse(description="Saved.")})
    def patch(self, request):
        serializer = PreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            preferences.set_preference(
                request.user, data["category"], data["channel"], data["enabled"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Saved."})


class QuietHoursView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=QuietHoursSerializer, responses={200: OpenApiResponse(description="Saved.")})
    def put(self, request):
        serializer = QuietHoursSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preferences.set_quiet_hours(
            request.user,
            serializer.validated_data.get("start"),
            serializer.validated_data.get("end"),
        )
        return Response({"detail": "Saved."})


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------


def _whatsapp_state(user) -> dict:
    profile = getattr(user, "student_profile", None)
    config = ChannelConfig.objects.filter(channel=Channel.WHATSAPP).first()
    return {
        "available": bool(config and config.is_live),
        "number": (profile.whatsapp if profile else "") or getattr(user, "phone", ""),
        "opted_in": bool(getattr(profile, "whatsapp_opted_in_at", None)),
    }


class WhatsAppOptInView(APIView):
    """Record or withdraw consent to be messaged on WhatsApp.

    WhatsApp Business policy requires an opt-in that the business can evidence
    before the first message. Holding somebody's number is not consent, so this
    is a deliberate action with a timestamp rather than a checkbox default.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Opted in.")})
    def post(self, request):
        profile = getattr(request.user, "student_profile", None)
        if profile is None:
            return Response({"detail": "No student profile."}, status=status.HTTP_400_BAD_REQUEST)
        if not (profile.whatsapp or request.user.phone):
            return Response(
                {"detail": "Add a WhatsApp number to your profile first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile.whatsapp_opted_in_at = timezone.now()
        profile.save(update_fields=["whatsapp_opted_in_at", "updated_at"])
        audit.record("whatsapp_opt_in", target=request.user, actor=request.user)
        return Response({"detail": "You'll get updates on WhatsApp."})

    @extend_schema(responses={200: OpenApiResponse(description="Opted out.")})
    def delete(self, request):
        profile = getattr(request.user, "student_profile", None)
        if profile is None:
            return Response({"detail": "No student profile."}, status=status.HTTP_400_BAD_REQUEST)
        profile.whatsapp_opted_in_at = None
        profile.save(update_fields=["whatsapp_opted_in_at", "updated_at"])
        audit.record("whatsapp_opt_out", target=request.user, actor=request.user)
        return Response({"detail": "WhatsApp messages are off."})


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def _telegram_state(user) -> dict:
    config = ChannelConfig.objects.filter(channel=Channel.TELEGRAM).first()
    link = TelegramLink.objects.filter(user=user).first()
    return {
        "available": bool(config and config.is_live),
        "bot_username": config.telegram_bot_username if config else "",
        "connected": link is not None,
        "username": link.telegram_username if link else "",
    }


class TelegramLinkView(APIView):
    """Mint a deep link that connects this account to a Telegram chat.

    A bot cannot start a conversation — it can only reply in a chat the user
    opened. So the flow is: mint a short-lived token, send the user to
    ``t.me/<bot>?start=<token>``, and let the webhook below match the chat that
    arrives back to the account that asked.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "mfa"

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Deep link.")})
    def post(self, request):
        config = ChannelConfig.objects.filter(channel=Channel.TELEGRAM).first()
        if config is None or not config.is_live:
            return Response(
                {"detail": "Telegram is not available right now."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # One live token at a time, so an abandoned attempt cannot be used later.
        TelegramLinkToken.objects.filter(user=request.user, used_at__isnull=True).delete()
        token = secrets.token_urlsafe(24)
        TelegramLinkToken.objects.create(
            user=request.user, token=token, expires_at=timezone.now() + LINK_TOKEN_TTL
        )
        return Response(
            {
                "url": f"https://t.me/{config.telegram_bot_username}?start={token}",
                "bot_username": config.telegram_bot_username,
                "expires_in_seconds": int(LINK_TOKEN_TTL.total_seconds()),
            }
        )

    @extend_schema(responses={200: OpenApiResponse(description="Disconnected.")})
    def delete(self, request):
        TelegramLink.objects.filter(user=request.user).delete()
        audit.record("telegram_unlinked", target=request.user, actor=request.user)
        return Response({"detail": "Telegram is disconnected."})


class TelegramWebhookView(APIView):
    """Where Telegram posts updates for the bot.

    Unauthenticated by necessity — Telegram has no credentials of ours — so the
    URL carries a secret path segment and the request is checked against the
    configured verify token. Only ``/start <token>`` is acted on; everything
    else is acknowledged and ignored, because a bot that replies to arbitrary
    text invites people to use it as a support channel it is not.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Acknowledged.")})
    def post(self, request, secret: str):
        config = ChannelConfig.objects.filter(channel=Channel.TELEGRAM).first()
        if config is None or not config.webhook_verify_token:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not secrets.compare_digest(secret, config.webhook_verify_token):
            return Response(status=status.HTTP_404_NOT_FOUND)

        message = (request.data or {}).get("message") or {}
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")

        if not chat_id or not text.startswith("/start"):
            return Response({"ok": True})

        parts = text.split(maxsplit=1)
        if len(parts) != 2:
            _reply(config, chat_id, "Open the link from your Nasuru notification settings to connect.")
            return Response({"ok": True})

        linked = _consume_link_token(parts[1].strip(), chat_id, chat.get("username", ""))
        _reply(
            config,
            chat_id,
            "Connected. You'll get your Nasuru updates here."
            if linked
            else "That link has expired. Generate a new one in your notification settings.",
        )
        return Response({"ok": True})


@transaction.atomic
def _consume_link_token(token: str, chat_id: str, username: str) -> bool:
    record = TelegramLinkToken.objects.select_for_update().filter(token=token).first()
    if record is None or not record.is_usable:
        return False

    record.used_at = timezone.now()
    record.save(update_fields=["used_at", "updated_at"])

    # A chat can only belong to one account, and an account to one chat.
    TelegramLink.objects.filter(chat_id=chat_id).delete()
    TelegramLink.objects.update_or_create(
        user=record.user,
        defaults={"chat_id": chat_id, "telegram_username": username or "", "linked_at": timezone.now()},
    )
    audit.record("telegram_linked", target=record.user, actor=record.user)
    return True


def _reply(config: ChannelConfig, chat_id: str, text: str) -> None:
    """Best-effort acknowledgement. A failure here must not fail the webhook."""
    import requests

    try:
        requests.post(
            f"https://api.telegram.org/bot{config.access_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception:  # noqa: BLE001 — Telegram retries the update anyway.
        pass


# ---------------------------------------------------------------------------
# In-app inbox
# ---------------------------------------------------------------------------


class InboxSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id", "category", "category_display", "subject", "body",
            "action_url", "read_at", "created_at",
        )
        read_only_fields = fields


class InboxView(APIView):
    """The in-app record of everything this user has been told.

    Every notification writes an ``in_app`` row whatever else it does, so this
    is complete even for a user who has switched every delivery channel off —
    and it is the answer when somebody says they were never told.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InboxSerializer(many=True)})
    def get(self, request):
        rows = Notification.objects.filter(
            recipient=request.user, channel=Channel.IN_APP
        ).order_by("-created_at")[:100]
        return Response(
            {
                "unread": Notification.objects.filter(
                    recipient=request.user, channel=Channel.IN_APP, read_at__isnull=True
                ).count(),
                "results": InboxSerializer(rows, many=True).data,
            }
        )

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Marked read.")})
    def post(self, request):
        """Mark everything read. Per-item read state is not worth the round trip."""
        Notification.objects.filter(
            recipient=request.user, channel=Channel.IN_APP, read_at__isnull=True
        ).update(read_at=timezone.now())
        return Response({"detail": "Marked as read."})
