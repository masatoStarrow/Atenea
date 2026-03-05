"""
Custom exception handler for DRF.
Returns all errors in the standard envelope format.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from src.domain.exceptions import (
    DomainException,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    UnauthorizedError,
    ServiceUnavailableError,
)


# Map domain exception codes to HTTP status codes
EXCEPTION_STATUS_MAP = {
    'INVALID_CREDENTIALS': status.HTTP_401_UNAUTHORIZED,
    'TOKEN_EXPIRED': status.HTTP_401_UNAUTHORIZED,
    'TOKEN_INVALID': status.HTTP_401_UNAUTHORIZED,
    'UNAUTHORIZED': status.HTTP_403_FORBIDDEN,
    'NOT_FOUND': status.HTTP_404_NOT_FOUND,
    'VALIDATION_ERROR': status.HTTP_422_UNPROCESSABLE_ENTITY,
    'RATE_LIMIT_EXCEEDED': status.HTTP_429_TOO_MANY_REQUESTS,
    'SERVICE_UNAVAILABLE': status.HTTP_503_SERVICE_UNAVAILABLE,
}


def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler that wraps all errors in the standard envelope.
    """
    # Handle domain exceptions
    if isinstance(exc, DomainException):
        http_status = EXCEPTION_STATUS_MAP.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(
            {
                'success': False,
                'error': {
                    'code': exc.code,
                    'message': exc.message,
                },
            },
            status=http_status,
        )

    # Let DRF handle its own exceptions
    response = exception_handler(exc, context)

    if response is not None:
        # Wrap DRF errors in the standard envelope
        error_data = response.data
        if isinstance(error_data, dict) and 'detail' in error_data:
            message = str(error_data['detail'])
        elif isinstance(error_data, list):
            message = '; '.join(str(e) for e in error_data)
        else:
            message = str(error_data)

        code = 'VALIDATION_ERROR'
        if response.status_code == 401:
            code = 'UNAUTHORIZED'
        elif response.status_code == 403:
            code = 'UNAUTHORIZED'
        elif response.status_code == 404:
            code = 'NOT_FOUND'
        elif response.status_code == 429:
            code = 'RATE_LIMIT_EXCEEDED'

        response.data = {
            'success': False,
            'error': {
                'code': code,
                'message': message,
            },
        }

    return response
