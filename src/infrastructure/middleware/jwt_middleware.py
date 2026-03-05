"""
JWT Authentication Middleware.
Validates Authorization: Bearer <token> on each request.
Skips public routes (login, health, docs).
"""

from django.http import JsonResponse
from django.conf import settings

from src.application.use_cases.validate_token import ValidateToken
from src.domain.exceptions import TokenExpiredError, TokenInvalidError
from src.adapters.outbound.persistence.models.user_model import User
from src.adapters.outbound.persistence.models.blacklisted_token_model import BlacklistedToken


# Routes that don't require authentication
PUBLIC_PATHS = [
    '/api/v1/auth/login',
    '/api/v1/health/',
    '/api/docs/',
    '/api/redoc/',
    '/api/schema/',
    '/admin/',
]


class JWTMiddleware:
    """
    Middleware that validates JWT tokens on every request.
    Sets request.user and request.auth_token if valid.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.validate_token = ValidateToken(
            jwt_secret=settings.JWT_SECRET_KEY,
            jwt_algorithm=settings.JWT_ALGORITHM,
        )

    def __call__(self, request):
        # Skip auth for public paths
        if self._is_public_path(request.path):
            return self.get_response(request)

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Bearer '):
            return JsonResponse(
                {
                    'success': False,
                    'error': {
                        'code': 'TOKEN_INVALID',
                        'message': 'Token de autenticación requerido',
                    },
                },
                status=401,
            )

        token = auth_header[7:]  # Remove "Bearer "

        # Check blacklist
        if BlacklistedToken.objects.filter(token=token).exists():
            return JsonResponse(
                {
                    'success': False,
                    'error': {
                        'code': 'TOKEN_INVALID',
                        'message': 'Token inválido (sesión cerrada)',
                    },
                },
                status=401,
            )

        try:
            claims = self.validate_token.execute(token)
        except TokenExpiredError as e:
            return JsonResponse(
                {
                    'success': False,
                    'error': {
                        'code': e.code,
                        'message': e.message,
                    },
                },
                status=401,
            )
        except TokenInvalidError as e:
            return JsonResponse(
                {
                    'success': False,
                    'error': {
                        'code': e.code,
                        'message': e.message,
                    },
                },
                status=401,
            )

        # Attach user to request
        try:
            user = User.objects.get(id=claims['sub'])
            request.user = user
        except User.DoesNotExist:
            return JsonResponse(
                {
                    'success': False,
                    'error': {
                        'code': 'TOKEN_INVALID',
                        'message': 'Usuario no encontrado',
                    },
                },
                status=401,
            )

        request.auth_token = token
        request.auth_claims = claims

        return self.get_response(request)

    def _is_public_path(self, path: str) -> bool:
        return any(path.startswith(p) for p in PUBLIC_PATHS)
