from django_ratelimit.exceptions import Ratelimited
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """Map django-ratelimit's Ratelimited exception to an HTTP 429 response.

    DRF does not know about ``Ratelimited`` and would otherwise return a 500.

    Args:
        exc: The exception raised while processing the request.
        context: The DRF context dict (view, request, args, kwargs).

    Returns:
        An HTTP 429 response for rate-limit hits, otherwise DRF's default
        handling for the exception.
    """
    if isinstance(exc, Ratelimited):
        return Response(
            {"detail": "Trop de tentatives. Reessayez plus tard."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return drf_exception_handler(exc, context)
