"""Single entry point for writing audit rows.

Call ``record()`` from services, never construct AuditLog directly — that keeps
actor/IP capture consistent and gives one place to add redaction rules.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.core.middleware import get_request_context
from apps.core.models import AuditLog

logger = logging.getLogger(__name__)

# Never let these reach the audit trail, whatever a caller passes.
REDACTED_KEYS = {
    "password",
    "secret_key",
    "public_key",
    "secret_hash",
    "encryption_key",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "signature",
}
REDACTED = "***redacted***"


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (REDACTED if k.lower() in REDACTED_KEYS else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


def record(
    action: str,
    *,
    target: Any = None,
    actor=None,
    changes: dict | None = None,
    metadata: dict | None = None,
    target_label: str = "",
) -> AuditLog | None:
    """Write one audit row. Never raises — a failed audit write must not roll
    back the business action, but it is logged loudly."""

    ctx = get_request_context()
    if actor is None:
        candidate = ctx.get("user")
        actor = candidate if getattr(candidate, "is_authenticated", False) else None

    fields = {
        "actor": actor,
        "actor_label": str(actor) if actor else "system",
        "action": action,
        "changes": _scrub(changes or {}),
        "metadata": _scrub(metadata or {}),
        "ip_address": ctx.get("ip_address"),
        "user_agent": ctx.get("user_agent", ""),
    }

    if target is not None:
        fields["target_type"] = f"{target._meta.app_label}.{target._meta.object_name}"
        fields["target_id"] = str(target.pk)
        fields["target_label"] = (target_label or str(target))[:255]
    elif target_label:
        fields["target_label"] = target_label[:255]

    try:
        # on_commit so we never log an action whose transaction later rolls back.
        entry = AuditLog(**fields)
        transaction.on_commit(lambda: AuditLog.objects.bulk_create([entry]))
        return entry
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to write audit log entry for action=%s", action)
        return None


def diff(before: dict, after: dict, fields: list[str] | None = None) -> dict:
    """Build a {'field': {'from': x, 'to': y}} changes dict for changed fields only."""
    keys = fields or sorted(set(before) | set(after))
    return {
        k: {"from": before.get(k), "to": after.get(k)}
        for k in keys
        if before.get(k) != after.get(k)
    }
