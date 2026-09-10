"""
DRF exception handling.

DRF puts a machine-readable code on every ErrorDetail but does not put it in
the response body, so a client can only match on prose. That is brittle — and
in one case it matters: a student who simply hasn't paid yet must be told to
pay, not shown a generic "forbidden". This handler surfaces the code.
"""

from rest_framework.exceptions import ErrorDetail
from rest_framework.views import exception_handler as drf_exception_handler


def _first_code(detail) -> str:
    if isinstance(detail, ErrorDetail):
        return str(detail.code)
    if isinstance(detail, dict):
        for value in detail.values():
            if code := _first_code(value):
                return code
    if isinstance(detail, list):
        for value in detail:
            if code := _first_code(value):
                return code
    return ""


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    # Only decorate the simple {"detail": ...} shape. Field-error payloads are
    # already keyed by field name and the renderer relies on that shape.
    if isinstance(response.data, dict) and set(response.data) <= {"detail"}:
        code = getattr(exc, "code", "") or _first_code(response.data.get("detail"))
        if code:
            response.data["code"] = str(code)

    return response
