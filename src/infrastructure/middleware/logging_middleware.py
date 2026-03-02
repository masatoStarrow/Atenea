"""
Logging Middleware.
Structured logging of every request/response using structlog.
"""

import time
import uuid

import structlog

logger = structlog.get_logger()


class LoggingMiddleware:
    """
    Logs every HTTP request and response with structured JSON.
    Adds X-Request-Id header for request tracing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())
        request.META['HTTP_X_REQUEST_ID'] = request_id

        start_time = time.time()

        # Log request
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.path,
            remote_addr=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        response = self.get_response(request)

        # Log response
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Add request ID to response headers
        response['X-Request-Id'] = request_id

        return response
