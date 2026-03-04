"""
Rate Limiting Middleware.
Applies rate limits per IP and per authenticated user.
"""

import time
from collections import defaultdict

from django.http import JsonResponse
from django.conf import settings


class RateLimitMiddleware:
    """
    Simple in-memory rate limiter.
    In production, use Redis-backed solution.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._request_counts = defaultdict(list)
        self._parse_limits()

    def _parse_limits(self):
        """Parse rate limit config strings like '5/minute' or '100/minute'."""
        self.login_limit = self._parse_limit_string(
            getattr(settings, 'RATE_LIMIT_LOGIN', '5/minute')
        )
        self.api_limit = self._parse_limit_string(
            getattr(settings, 'RATE_LIMIT_API', '100/minute')
        )

    @staticmethod
    def _parse_limit_string(limit_str: str) -> tuple[int, int]:
        """Parse '5/minute' → (5, 60)"""
        parts = limit_str.split('/')
        count = int(parts[0])
        period_map = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400,
        }
        period = period_map.get(parts[1], 60)
        return count, period

    def __call__(self, request):
        client_ip = self._get_client_ip(request)
        now = time.time()

        # Determine which limit to apply
        is_login = request.path.rstrip('/').endswith('/auth/login')
        max_requests, window = self.login_limit if is_login else self.api_limit

        # Build a rate-limit key
        key = f"{client_ip}:{request.path}" if is_login else f"{client_ip}:api"

        # Clean old entries and check
        self._request_counts[key] = [
            t for t in self._request_counts[key] if t > now - window
        ]

        if len(self._request_counts[key]) >= max_requests:
            return JsonResponse(
                {
                    'success': False,
                    'error': {
                        'code': 'RATE_LIMIT_EXCEEDED',
                        'message': 'Demasiadas solicitudes. Intente más tarde.',
                    },
                },
                status=429,
            )

        self._request_counts[key].append(now)

        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
