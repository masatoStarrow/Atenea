"""
Serializers for auth endpoints.
"""

from rest_framework import serializers


class LoginRequestSerializer(serializers.Serializer):
    """Validates login request payload."""
    email = serializers.EmailField(required=True, help_text="Email del usuario")
    password = serializers.CharField(required=True, min_length=8, help_text="Contraseña del usuario (min 8 caracteres)")


class TokenResponseSerializer(serializers.Serializer):
    """Serializes token response."""
    access_token = serializers.CharField(help_text="JWT access token")
    token_type = serializers.CharField(default="Bearer", help_text="Tipo de token")


class UserProfileSerializer(serializers.Serializer):
    """Serializes user profile for /auth/me."""
    id = serializers.UUIDField(help_text="ID del usuario")
    email = serializers.EmailField(help_text="Email del usuario")
    full_name = serializers.CharField(help_text="Nombre completo")
    role = serializers.CharField(help_text="Rol del usuario")


class SuccessResponseSerializer(serializers.Serializer):
    """Standard success envelope."""
    success = serializers.BooleanField(default=True)
    data = serializers.DictField(required=False)
    message = serializers.CharField(default="OK")


class ErrorDetailSerializer(serializers.Serializer):
    """Error detail within the envelope."""
    code = serializers.CharField()
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error envelope."""
    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()
