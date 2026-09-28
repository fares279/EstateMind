"""User-facing errors: never send exception text to the client.

Unexpected failures are logged with a short reference code, and the response
carries a plain message plus that code, so a report from a user can be matched
to the log line without exposing database or stack details.
"""
import logging
import uuid

from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger('estatemind.errors')

GENERIC_MESSAGE = 'Something went wrong on our side. Please try again in a moment.'


def log_reference(exc: BaseException, where: str = '') -> str:
    ref = uuid.uuid4().hex[:8]
    logger.error('[ref %s] %s: %s', ref, where or 'unhandled error', exc, exc_info=exc)
    return ref


def error_body(exc: BaseException, message: str = GENERIC_MESSAGE, key: str = 'error', where: str = '') -> dict:
    ref = log_reference(exc, where)
    return {key: f'{message} (reference {ref})', 'reference': ref}


def internal_error(exc: BaseException, message: str = GENERIC_MESSAGE, status: int = 500, key: str = 'error',
                   where: str = '') -> Response:
    """DRF response for an unexpected failure."""
    return Response(error_body(exc, message, key, where), status=status)


def internal_error_json(exc: BaseException, message: str = GENERIC_MESSAGE, status: int = 500,
                        where: str = '') -> JsonResponse:
    """Plain-Django variant (views not built on DRF)."""
    return JsonResponse(error_body(exc, message, 'error', where), status=status)


def api_exception_handler(exc, context):
    """REST_FRAMEWORK['EXCEPTION_HANDLER']: DRF's own errors (validation, auth,
    throttling, 404) pass through; anything else becomes a generic 500 instead of
    a stack trace or database message."""
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    view = context.get('view')
    return internal_error(exc, where=type(view).__name__ if view is not None else '')
