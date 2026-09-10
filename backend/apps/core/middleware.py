"""Request-scoped context so audit rows can capture who/where without threading
the request object through every service function."""

import contextvars

# A ContextVar default must not be mutable — it would be shared across every
# context. The sentinel is None and callers always get a fresh dict.
_request_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "audit_request_context", default=None
)


def get_request_context() -> dict:
    return _request_context.get() or {}


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _request_context.set(
            {
                "user": getattr(request, "user", None),
                "ip_address": _client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:400],
                "path": request.path,
            }
        )
        try:
            return self.get_response(request)
        finally:
            _request_context.reset(token)
