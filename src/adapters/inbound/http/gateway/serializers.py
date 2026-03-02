"""
Serializers for Gateway proxy endpoints — define request body schemas
so Swagger UI shows editable fields for POST/PUT operations.
"""

from rest_framework import serializers
from ..validators import (
    validate_strong_password,
    validate_non_empty_name,
)


# ── Users ────────────────────────────────────────────────────────────────

class CreateUserProxySerializer(serializers.Serializer):
    """Request body para crear un usuario (dual-write: gateway + users-service)."""
    email = serializers.EmailField(
        required=True,
        help_text="Email único del usuario",
    )
    full_name = serializers.CharField(
        required=True,
        max_length=255,
        validators=[validate_non_empty_name],
        help_text="Nombre completo del usuario (min 2 caracteres, solo letras)",
    )
    role = serializers.ChoiceField(
        choices=["admin", "soporte", "comercial"],
        required=True,
        help_text="Rol del usuario en el sistema",
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        validators=[validate_strong_password],
        help_text="Contraseña segura: min 8 chars, mayúscula, minúscula, número y símbolo",
    )


class UpdateUserProxySerializer(serializers.Serializer):
    """Request body para actualizar un usuario (dual-write: gateway DB + users-service)."""
    full_name = serializers.CharField(
        required=False,
        max_length=255,
        validators=[validate_non_empty_name],
        help_text="Nombre completo del usuario (min 2 caracteres, solo letras)",
    )
    role = serializers.ChoiceField(
        choices=["admin", "soporte", "comercial"],
        required=False,
        help_text="Rol del usuario en el sistema",
    )
    is_active = serializers.BooleanField(
        required=False,
        help_text="Si el usuario está activo",
    )


# ── Clients ──────────────────────────────────────────────────────────────

class CreateClientProxySerializer(serializers.Serializer):
    """Request body para crear un cliente (proxy → users-service)."""
    company = serializers.CharField(
        required=True,
        min_length=2,
        max_length=255,
        help_text="Nombre de la empresa (requerido, min 2 caracteres)",
    )
    email = serializers.EmailField(
        required=True,
        help_text="Email único del cliente",
    )
    phone = serializers.CharField(
        required=False,
        max_length=50,
        allow_blank=True,
        allow_null=True,
        help_text="Teléfono de contacto",
    )
    status = serializers.ChoiceField(
        choices=["active", "inactive"],
        required=False,
        default="active",
        help_text="Client status (active or inactive)",
    )


class UpdateClientProxySerializer(serializers.Serializer):
    """Request body para actualizar un cliente (proxy → users-service)."""
    company = serializers.CharField(
        required=False,
        min_length=2,
        max_length=255,
        help_text="Nombre de la empresa",
    )
    email = serializers.EmailField(
        required=False,
        help_text="Email del cliente",
    )
    phone = serializers.CharField(
        required=False,
        max_length=50,
        allow_blank=True,
        allow_null=True,
        help_text="Teléfono de contacto",
    )
    status = serializers.ChoiceField(
        choices=["active", "inactive"],
        required=False,
        help_text="Client status (active or inactive)",
    )


# ── Interactions ─────────────────────────────────────────────────────────

class CreateInteractionProxySerializer(serializers.Serializer):
    """Request body para crear una interacción (proxy → interactions-service)."""
    client_id = serializers.UUIDField(
        required=True,
        help_text="UUID del cliente asociado",
    )
    type = serializers.ChoiceField(
        choices=["llamada", "email", "reunion", "nota"],
        required=True,
        help_text="Tipo de interacción",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Notas o descripción de la interacción",
    )


class UpdateInteractionProxySerializer(serializers.Serializer):
    """Request body para actualizar una interacción (proxy → interactions-service)."""
    type = serializers.ChoiceField(
        choices=["llamada", "email", "reunion", "nota"],
        required=False,
        help_text="Tipo de interacción",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Notas o descripción de la interacción",
    )
