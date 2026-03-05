"""
Auth views: login, logout, me.
"""

from datetime import datetime, timezone

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes

from src.adapters.inbound.http.auth.serializers import (
    LoginRequestSerializer,
    TokenResponseSerializer,
    UserProfileSerializer,
    SuccessResponseSerializer,
    ErrorResponseSerializer,
)
from src.domain.exceptions import InvalidCredentialsError
from src.infrastructure.di.container import get_login_use_case, get_validate_token_use_case
from src.adapters.outbound.persistence.models.blacklisted_token_model import BlacklistedToken
from src.adapters.outbound.persistence.models.user_model import User


class LoginView(APIView):
    """POST /api/v1/auth/login — Authenticate user and return JWT."""
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Login de usuario",
        description="Autentica un usuario con email y contraseña. Retorna un JWT access token.",
        request=LoginRequestSerializer,
        responses={
            200: SuccessResponseSerializer,
            401: ErrorResponseSerializer,
            422: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Login exitoso",
                value={
                    "success": True,
                    "data": {
                        "access_token": "eyJhbGciOiJIUzI1NiIs...",
                        "token_type": "Bearer",
                    },
                    "message": "OK",
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
        tags=["Auth"],
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = LoginRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'VALIDATION_ERROR',
                        'message': serializer.errors,
                    },
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        login_use_case = get_login_use_case()

        try:
            token_entity = login_use_case.execute(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
            )
        except InvalidCredentialsError as e:
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': e.code,
                        'message': e.message,
                    },
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            {
                'success': True,
                'data': TokenResponseSerializer(token_entity).data,
                'message': 'OK',
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """POST /api/v1/auth/logout — Invalidate the current token."""

    @extend_schema(
        summary="Logout de usuario",
        description="Invalida el JWT actual añadiéndolo a la blacklist.",
        responses={
            200: SuccessResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=["Auth"],
    )
    def post(self, request: Request) -> Response:
        token = request.auth or getattr(request._request, 'auth_token', None)
        if not token:
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'TOKEN_INVALID',
                        'message': 'No se proporcionó un token válido',
                    },
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Decode to get expiry
        validate_use_case = get_validate_token_use_case()
        claims = validate_use_case.execute(token)
        expires_at = datetime.fromtimestamp(claims['exp'], tz=timezone.utc)

        BlacklistedToken.objects.get_or_create(
            token=token,
            defaults={'expires_at': expires_at},
        )

        return Response(
            {
                'success': True,
                'data': None,
                'message': 'Sesión cerrada exitosamente',
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """GET /api/v1/auth/me — Return current user profile."""

    @extend_schema(
        summary="Perfil del usuario autenticado",
        description="Retorna la información del usuario asociado al JWT actual.",
        responses={
            200: SuccessResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=["Auth"],
    )
    def get(self, request: Request) -> Response:
        user = request.user
        if not user or not hasattr(user, 'email'):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'UNAUTHORIZED',
                        'message': 'No autenticado',
                    },
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        profile_data = UserProfileSerializer({
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
        }).data

        return Response(
            {
                'success': True,
                'data': profile_data,
                'message': 'OK',
            },
            status=status.HTTP_200_OK,
        )
