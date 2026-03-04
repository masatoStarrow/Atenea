"""
Tests unitarios para los validators personalizados.
"""

import pytest
from rest_framework import serializers
from src.adapters.inbound.http.validators import (
    validate_strong_password,
    validate_non_empty_name,
    validate_phone_format,
    validate_company_name,
)


# ── validate_strong_password ────────────────────────────────────────────

class TestValidateStrongPassword:

    def test_valid_password_passes(self):
        """Una contraseña fuerte debe pasar la validación."""
        valid_passwords = [
            "Strong123!",
            "MySecure@Pass2024",
            "Complex#Password9",
            "Valid123$Test",
        ]
        for password in valid_passwords:
            result = validate_strong_password(password)  # No debe lanzar excepción
            assert result == password

    def test_too_short_password_fails(self):
        """Contraseñas menores a 8 caracteres deben fallar."""
        with pytest.raises(serializers.ValidationError, match="al menos 8 caracteres"):
            validate_strong_password("Short1!")

    def test_no_uppercase_fails(self):
        """Contraseñas sin mayúsculas deben fallar."""
        with pytest.raises(serializers.ValidationError, match="letra mayúscula"):
            validate_strong_password("lowercase123!")

    def test_no_lowercase_fails(self):
        """Contraseñas sin minúsculas deben fallar."""
        with pytest.raises(serializers.ValidationError, match="letra minúscula"):
            validate_strong_password("UPPERCASE123!")

    def test_no_number_fails(self):
        """Contraseñas sin números deben fallar."""
        with pytest.raises(serializers.ValidationError, match="al menos un número"):
            validate_strong_password("NoNumbers!")

    def test_no_special_char_fails(self):
        """Contraseñas sin caracteres especiales deben fallar."""
        with pytest.raises(serializers.ValidationError, match="carácter especial"):
            validate_strong_password("NoSpecial123")


# ── validate_non_empty_name ─────────────────────────────────────────────

class TestValidateNonEmptyName:

    def test_valid_names_pass(self):
        """Nombres válidos deben pasar la validación."""
        valid_names = [
            "Juan Pérez",
            "María José",
            "José Luis García",
            "Ana María",
            "Carlos A. López", 
        ]
        for name in valid_names:
            result = validate_non_empty_name(name)
            assert result == name

    def test_empty_string_fails(self):
        """String vacío debe fallar."""
        with pytest.raises(serializers.ValidationError, match="al menos 2 caracteres"):
            validate_non_empty_name("")

    def test_only_spaces_fails(self):
        """Solo espacios debe fallar."""
        with pytest.raises(serializers.ValidationError, match="al menos 2 caracteres"):
            validate_non_empty_name("   ")

    def test_too_short_fails(self):
        """Nombres muy cortos deben fallar."""
        with pytest.raises(serializers.ValidationError, match="al menos 2 caracteres"):
            validate_non_empty_name("A")

    def test_invalid_characters_fail(self):
        """Nombres con caracteres inválidos deben fallar."""
        invalid_names = [
            "Juan123",
            "María@example.com", 
            "José#López",
            "Ana$$$",
        ]
        for name in invalid_names:
            with pytest.raises(serializers.ValidationError, match="solo puede contener letras"):
                validate_non_empty_name(name)


# ── validate_phone_format ───────────────────────────────────────────────

class TestValidatePhoneFormat:

    def test_empty_phone_allowed(self):
        """Teléfono vacío debe estar permitido (campo opcional)."""
        assert validate_phone_format("") == ""
        assert validate_phone_format(None) == None

    def test_valid_phones_pass(self):
        """Formatos válidos de teléfono deben pasar."""
        valid_phones = [
            "+573001234567",
            "3001234567",
            "+1 234 567 8901", 
            "+57 300-123-4567",
            "+49 (30) 12345678",
        ]
        for phone in valid_phones:
            result = validate_phone_format(phone)
            assert result == phone

    def test_too_short_fails(self):
        """Teléfonos muy cortos deben fallar."""
        with pytest.raises(serializers.ValidationError, match="entre 8 y 15 dígitos"):
            validate_phone_format("1234567")

    def test_too_long_fails(self):
        """Teléfonos muy largos deben fallar.""" 
        with pytest.raises(serializers.ValidationError, match="entre 8 y 15 dígitos"):
            validate_phone_format("+123456789012345678")

    def test_invalid_format_fails(self):
        """Formatos inválidos deben fallar."""
        invalid_phones = [
            "not-a-phone",
            "123abc456",
            "++5712345678",
            "phone123",
        ]
        for phone in invalid_phones:
            with pytest.raises(serializers.ValidationError, match="entre 8 y 15 dígitos"):
                validate_phone_format(phone)


# ── validate_company_name ──────────────────────────────────────────────

class TestValidateCompanyName:

    def test_empty_company_allowed(self):
        """Nombre de empresa vacío debe estar permitido (campo opcional)."""
        assert validate_company_name("") == ""
        assert validate_company_name(None) == None

    def test_valid_companies_pass(self):
        """Nombres válidos de empresas deben pasar."""
        valid_companies = [
            "Google Inc.",
            "Microsoft Corporation",
            "Apple",
            "Meta Platforms",
            "Empresa ABC S.A.S.",
        ]
        for company in valid_companies:
            result = validate_company_name(company)
            assert result == company

    def test_too_short_fails(self):
        """Nombres muy cortos deben fallar."""
        with pytest.raises(serializers.ValidationError, match="al menos 2 caracteres"):
            validate_company_name("A")

    def test_too_long_fails(self):
        """Nombres muy largos deben fallar."""
        long_company = "A" * 256  # 256 caracteres
        with pytest.raises(serializers.ValidationError, match="no puede exceder 255 caracteres"):
            validate_company_name(long_company)

    def test_only_spaces_fails(self):
        """Solo espacios debe fallar."""
        with pytest.raises(serializers.ValidationError, match="al menos 2 caracteres"):
            validate_company_name("   ")